# knowledge/

Drop your own reference material here for Miku to RAG-ingest: malware-dev notes, CVE
writeups, PDFs converted to text/markdown, course material, cheat sheets — anything you want
retrievable during a session. She chunks, embeds, and indexes whatever she finds under this
directory (see `knowledge_dir` in `config.example.yaml` if you'd rather point at a different
location).

This is your own private research material, so `.gitignore` at the repo root excludes
everything in this folder except this `README.md` — that keeps Hermes portable and shareable
as a repo without ever bundling (or accidentally pushing) your actual notes, samples, or
writeups. Feel free to organize it however you like; subdirectories are fine.
