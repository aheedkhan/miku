"""Opt-in fetcher for external reference corpora Miku draws on for Windows API/kernel and
Linux kernel expertise, plus MITRE ATT&CK technique data (covering Windows/Linux/macOS/cloud
platforms) for both understanding and building new malware techniques.

Deliberately NOT run automatically by install.sh or daily_refresh.py — these are real,
sometimes sizeable downloads (a full API-reference doc tree, a kernel-docs sparse-checkout),
and on a Qubes-style split setup you'd want this fetched once on whichever VM does research,
not duplicated on every client VM. Run it by hand:

    python -m hermes.rag.fetch_references                  # fetch + ingest everything
    python -m hermes.rag.fetch_references win32-api         # just one source

daily_refresh.py calls ingest_references() every day regardless (cheap — content-hash dedup
makes re-ingesting an unchanged tree a near no-op) but never calls fetch_all() itself; a
corpus that hasn't been fetched yet is just cleanly skipped (0 chunks), not an error.
"""

from __future__ import annotations

import asyncio
import json
import sys
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from hermes.config import HermesConfig, load_config
from hermes.rag.ingest import scan_dir

if TYPE_CHECKING:
    from hermes.rag.ingest import IngestPipeline

FetchFn = Callable[[Path], Awaitable[None]]


@dataclass
class ReferenceSource:
    name: str
    description: str
    fetch: FetchFn


async def _run(*cmd: str, cwd: Path | None = None, timeout: float = 900.0) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"command timed out after {timeout}s: {' '.join(cmd)}")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(cmd)}): {out.decode(errors='replace')[-2000:]}")


async def _retry(fn: Callable[[], Awaitable[None]], attempts: int = 3, base_delay: float = 5.0) -> None:
    """git's smart-HTTP protocol proved unreliable over a slow/constrained connection during
    development (a real mid-transfer "RPC failed; ... stream was not closed cleanly" was
    reproduced) — a transient failure like that often succeeds on a plain retry, so every
    git-based fetch gets a few attempts with backoff before giving up for real."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await fn()
            return
        except Exception as e:  # noqa: BLE001 - retried at this layer, re-raised after the last attempt
            last_error = e
            if attempt < attempts:
                await asyncio.sleep(base_delay * attempt)
    assert last_error is not None
    raise last_error


async def _git_sparse_clone_or_pull(url: str, dest: Path, sparse_paths: list[str]) -> None:
    async def _attempt() -> None:
        if not (dest / ".git").is_dir():
            dest.parent.mkdir(parents=True, exist_ok=True)
            await _run("git", "clone", "--filter=blob:none", "--sparse", "--depth", "1", url, str(dest))
        else:
            await _run("git", "-C", str(dest), "pull")
        # ALWAYS (re-)apply the sparse-checkout, even on the resume path: `sparse-checkout
        # set` is the step that actually fetches the target paths' blob data from the
        # promisor remote (the bulk of the transfer, and the step observed to fail with a
        # network timeout in practice) — it's idempotent, so re-running it costs nothing
        # when it already succeeded, but skipping it on retry (as an earlier version of this
        # function did) silently leaves the working tree empty forever if `git pull` alone
        # reports success while the real sparse-checkout was never actually completed.
        await _run("git", "-C", str(dest), "sparse-checkout", "set", *sparse_paths)

    await _retry(_attempt)


async def _download_github_zip_docs(owner_repo: str, ref: str, dest: Path, suffix_filter: str = ".md") -> None:
    """Downloads a GitHub repo's zipball at a ref via one plain HTTPS GET (the same streamed
    download path already proven reliable for the ATT&CK JSON fetch) and extracts just files
    matching suffix_filter into dest, stripping the zip's single top-level '<repo>-<ref>/'
    directory. Used instead of `git clone` for doc trees with no single "whole corpus" file
    to download directly — git's smart-HTTP protocol is more fragile over a slow connection
    than one big streamed GET."""
    zip_url = f"https://codeload.github.com/{owner_repo}/zip/refs/heads/{ref}"
    tmp_zip = dest.parent / f".{dest.name}.download.zip"
    await _retry(lambda: _download_file(zip_url, tmp_zip, timeout=1800.0, stall_timeout=60.0))
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_zip) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            if not names:
                return
            root_prefix = names[0].split("/", 1)[0] + "/"
            for name in names:
                if not name.endswith(suffix_filter):
                    continue
                rel = name[len(root_prefix):] if name.startswith(root_prefix) else name
                if not rel:
                    continue
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, target.open("wb") as out:
                    out.write(src.read())
    finally:
        tmp_zip.unlink(missing_ok=True)


def _convert_attack_stix_to_markdown(stix_path: Path, out_dir: Path) -> int:
    """MITRE ATT&CK ships technique data as a STIX 2.1 bundle — deeply nested JSON that's a
    poor RAG-chunking target as-is. Converts each non-revoked, non-deprecated attack-pattern
    object into one clean per-technique Markdown file (id, name, platforms, description,
    detection guidance)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()  # full rewrite each time — cheap, and avoids stale files from a renamed/removed technique

    data = json.loads(stix_path.read_text(encoding="utf-8"))
    count = 0
    for obj in data.get("objects", []):
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        ext_refs = obj.get("external_references") or []
        mitre_ref = next((r for r in ext_refs if r.get("source_name") == "mitre-attack"), None)
        technique_id = (mitre_ref or {}).get("external_id") or obj.get("id", "unknown")
        name = obj.get("name", "Unnamed technique")
        platforms = ", ".join(obj.get("x_mitre_platforms") or [])
        description = obj.get("description", "")
        detection = obj.get("x_mitre_detection", "")

        lines = [f"# {technique_id}: {name}", "", f"Platforms: {platforms}"]
        if description:
            lines += ["", description]
        if detection:
            lines += ["", "## Detection", detection]

        safe_id = technique_id.replace("/", "_").replace(" ", "_")
        (out_dir / f"{safe_id}.md").write_text("\n".join(lines), encoding="utf-8")
        count += 1
    return count


ENTERPRISE_ATTACK_JSON_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
    "enterprise-attack/enterprise-attack.json"
)


async def _download_file(url: str, dest: Path, timeout: float = 600.0, stall_timeout: float = 60.0) -> None:
    """Streams url to dest. `stall_timeout` bounds how long any single chunk read may take —
    a silently-dead connection (observed live: bytes stop arriving but the socket never
    errors) would otherwise hang for the full `timeout` doing nothing, since httpx's own
    per-request timeout wasn't tripping fast enough on that failure mode. `timeout` is the
    overall cap across the whole transfer."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    async def _do_download() -> None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, read=stall_timeout), follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
                tmp.replace(dest)

    await asyncio.wait_for(_do_download(), timeout=timeout)


async def fetch_win32_api_docs(dest: Path) -> None:
    # Microsoft's own Win32/WDK API reference, already in Markdown, one page per API. Fetched
    # as a zip (default branch is "docs", not "main" — verified live) rather than git-cloned;
    # see _download_github_zip_docs's docstring for why.
    await _download_github_zip_docs("MicrosoftDocs/sdk-api", "docs", dest, suffix_filter=".md")


async def fetch_linux_kernel_docs(dest: Path) -> None:
    # Partial clone + sparse-checkout: just Documentation/, not the multi-GB kernel source tree.
    await _git_sparse_clone_or_pull("https://github.com/torvalds/linux.git", dest, ["Documentation"])


async def fetch_mitre_attack(dest: Path) -> None:
    # A direct single-file download of just the latest Enterprise ATT&CK STIX bundle, rather
    # than git-cloning the whole attack-stix-data repo (which carries every historical version
    # across enterprise/mobile/ics matrices — much bigger than needed, and a long-lived git
    # clone of it proved unreliable over a slow/constrained connection: a real mid-transfer
    # "RPC failed ... stream was not closed cleanly" was hit and reproduced during development).
    stix_path = dest / "enterprise-attack.json"
    await _download_file(ENTERPRISE_ATTACK_JSON_URL, stix_path)
    _convert_attack_stix_to_markdown(stix_path, dest / "techniques_md")


REFERENCE_SOURCES: dict[str, ReferenceSource] = {
    "win32-api": ReferenceSource(
        name="win32-api",
        description="Microsoft's Win32/WDK API reference (Markdown) — the Windows API surface for malware-dev/analysis work.",
        fetch=fetch_win32_api_docs,
    ),
    "linux-kernel-docs": ReferenceSource(
        name="linux-kernel-docs",
        description="The Linux kernel's own Documentation/ tree (sparse-checkout) — kernel internals, syscalls, subsystems.",
        fetch=fetch_linux_kernel_docs,
    ),
    "mitre-attack": ReferenceSource(
        name="mitre-attack",
        description="MITRE ATT&CK Enterprise technique data, converted to per-technique Markdown — Windows/Linux/macOS/cloud technique + detection knowledge.",
        fetch=fetch_mitre_attack,
    ),
}


def reference_dir(config: HermesConfig, name: str) -> Path:
    return config.data_dir / "reference" / name


async def fetch_all(config: HermesConfig, only: list[str] | None = None) -> dict[str, str]:
    names = only or list(REFERENCE_SOURCES)
    results: dict[str, str] = {}
    for name in names:
        source = REFERENCE_SOURCES.get(name)
        if source is None:
            results[name] = f"unknown source: {name}"
            continue
        try:
            await source.fetch(reference_dir(config, name))
            results[name] = "ok"
        except Exception as e:  # noqa: BLE001 - one source failing shouldn't abort the others
            results[name] = f"failed: {type(e).__name__}: {e}"
    return results


_SCAN_SPEC: dict[str, tuple[str, list[str]]] = {
    # name -> (subdir relative to the fetched dest, include globs)
    "win32-api": (".", ["*.md"]),
    "linux-kernel-docs": ("Documentation", ["*.rst", "*.txt"]),
    "mitre-attack": ("techniques_md", ["*.md"]),
}


async def ingest_references(
    config: HermesConfig, ingest: "IngestPipeline", only: list[str] | None = None
) -> dict[str, int]:
    """Ingests whatever reference corpora have ALREADY been fetched (never fetches on its
    own). A corpus that hasn't been fetched yet is cleanly skipped with a count of 0, not an
    error — called unconditionally every daily_refresh pass since content-hash dedup makes
    re-ingesting an unchanged tree cheap."""
    names = only or list(REFERENCE_SOURCES)
    summary: dict[str, int] = {}
    for name in names:
        subdir, include_globs = _SCAN_SPEC.get(name, (".", ["*.md"]))
        scan_root = reference_dir(config, name) / subdir
        if not scan_root.is_dir():
            summary[name] = 0
            continue
        total = 0
        for path in scan_dir(scan_root, include_globs=include_globs, exclude_globs=["*/.git/*"]):
            rel = path.relative_to(scan_root).as_posix()
            total += await ingest.ingest_file(path, source_type="reference", source=f"reference:{name}:{rel}")
        summary[name] = total
    return summary


def _cli() -> None:
    """`python -m hermes.rag.fetch_references` — fetch then ingest (matches module docs)."""
    from hermes.core.llm_client import OllamaClient
    from hermes.rag.embeddings import EmbeddingClient
    from hermes.rag.ingest import IngestPipeline
    from hermes.rag.store import VectorStore

    async def _main() -> None:
        config = load_config()
        only = sys.argv[1:] or None
        results = await fetch_all(config, only=only)
        for name, status in results.items():
            print(f"fetch {name}: {status}")
        failed = any(status != "ok" for status in results.values())

        llm = OllamaClient(config.ollama_host)
        try:
            embedder = EmbeddingClient(llm, model=config.model("embed").name)
            store = VectorStore(config.rag_dir, dim=768)
            try:
                ingest = IngestPipeline(embedder, store)
                # Ingest whatever landed on disk — even if one source failed to fetch.
                counts = await ingest_references(config, ingest, only=only)
                for name, n in counts.items():
                    print(f"ingest {name}: {n} chunk(s)")
            finally:
                store.close()
        finally:
            await llm.aclose()

        if failed:
            sys.exit(1)

    asyncio.run(_main())


if __name__ == "__main__":
    _cli()
