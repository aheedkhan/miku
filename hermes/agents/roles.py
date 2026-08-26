"""Sub-agent role presets — pins each spawned sub-agent to a model tier and a small tool
set matched to its job, and appends a short scope statement to its system prompt.

Consumed by hermes/agents/subagent.py (spawn_subagent) and hermes/tools/subagent_tool.py
(the spawn_subagent tool exposed to the main agent). `tool_names` entries are ToolSchema
names as registered in the process's live ToolRegistry — ToolRegistry.subset() silently
skips any name that isn't currently registered (e.g. a tool whose external binary isn't
installed on this machine), so listing a tool here that happens to be unavailable degrades
gracefully instead of crashing the sub-agent spawn.
"""

from __future__ import annotations

ROLE_PRESETS: dict[str, dict] = {
    "researcher": {
        "model_role": "fast",
        "tool_names": ["web_search", "cve_lookup", "malware_intel", "rag_query", "rag_remember"],
        "system_prompt_suffix": (
            "You are operating as a RESEARCH sub-agent. Your job is read-only information "
            "gathering: web search, CVE/vulnerability lookups, malware intelligence lookups, "
            "and querying/recording notes in the RAG knowledge store. You have no filesystem, "
            "shell, or git access and cannot edit anything or run commands — if the task asks "
            "for that, explain what you found instead and note that execution is outside your "
            "scope. Be concise, and cite sources (URLs, CVE IDs, hashes) whenever you have them."
        ),
    },
    "reviewer": {
        "model_role": "code",
        "tool_names": ["read_file", "list_dir", "grep", "git"],
        "system_prompt_suffix": (
            "You are operating as a CODE REVIEW sub-agent. Read and inspect the codebase using "
            "read_file, list_dir, grep, and git (e.g. `git diff`, `git log`, `git show`) to "
            "understand what changed and why. You cannot edit files or run arbitrary shell "
            "commands — report findings (bugs, risks, style issues, suggestions) as text; you "
            "do not apply fixes yourself. Be specific: cite file paths and line numbers."
        ),
    },
    "pentest_runner": {
        "model_role": "default",
        "tool_names": ["shell_exec", "read_file", "grep", "cve_lookup", "malware_intel", "android"],
        "system_prompt_suffix": (
            "You are operating as a PENTEST/EXECUTION sub-agent — the one role trusted to "
            "actually run commands (shell_exec) and Android tooling (android) against systems "
            "the user has confirmed they are authorized to test. Use read_file/grep to inspect "
            "results, and cve_lookup/malware_intel to cross-reference findings. Work "
            "methodically, run one meaningful step at a time, and report exactly what you ran "
            "and what came back — don't summarize away command output the user will need."
        ),
    },
    "general": {
        "model_role": "default",
        "tool_names": None,  # sentinel: None means "use the full, unrestricted tool registry"
        "system_prompt_suffix": (
            "You are operating as a general-purpose sub-agent with the full tool set available. "
            "Complete the delegated task directly and return a clear, self-contained final "
            "answer — the parent agent will only see your final message, not your intermediate "
            "steps."
        ),
    },
}

# Fallback preset used when an unrecognized role name is requested (a typo, or a model
# hallucinating a role that doesn't exist), so spawning degrades to a working
# general-purpose agent instead of raising. See hermes/agents/subagent.py.
GENERAL_PRESET: dict = ROLE_PRESETS["general"]
