# Miku toolset & skills (quick map)

Companion for RAG — how the expert agent should reach for tools.

## Always-on tools
| Tool | Expert use |
|------|------------|
| `rag_query` / `rag_remember` | Memory first; save decisions |
| `web_search` → `web_fetch` | Advisories, docs, writeups |
| `github` | Prior art: `search_repos`, `code_search`, `contents`, `file_get`, releases/commits; also PRs/issues |
| `cve_lookup` | Open/related/KEV CVE detail + develop hints |
| `malware_intel` | MalwareBazaar metadata |
| `android` | apktool/jadx/adb/frida actions |
| `read_file` / `write_file` / `edit_file` / `grep` / `list_dir` | Local code |
| Compile / link | `shell_exec` + skill `lab-build` |
| Tests red→green | skill `test-harness` |
| Crash / hang / step-through | skill `debugger` + `debug-triage` |
| Local files | `read_file` / `write_file` / `grep` / `git` |
| `use_skill` | Load full playbook |
| `spawn_subagent` | Parallel research / implement / review |

## Skill playbooks (load with use_skill)
See `skills/SKILLS.md`. Highlights: `github-explore`, `research-pipeline`, `cve-research`,
`attack-ttps`, `malware-authoring`, `cve-malware-test`, `windows-rat-dev`, `android-malware-*`, `knowledge-rag`, `browsing`.

Malware+TTP capability bar: `workspace/references/malware-capability-contract.md`
Catalog: `workspace/references/attack-ttp-catalog.md`

## Default investigate loop
1. `rag_query`
2. `web_search` / `cve_lookup` / `github search_repos`
3. `web_fetch` or `github file_get`
4. Implement / harness
5. Notes + `rag_remember` + index
