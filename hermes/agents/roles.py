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
        "tool_names": [
            "web_search", "web_fetch", "github", "cve_lookup",
            "malware_intel", "rag_query", "rag_remember", "use_skill",
        ],
        "system_prompt_suffix": (
            "You are a RESEARCH sub-agent. Gather with rag_query, web_search, web_fetch, "
            "github explore (search_repos/code_search/contents/file_get), and cve_lookup. "
            "No shell/fs writes. Cite URLs and owner/repo@path. Return a tight brief."
        ),
    },
    "reviewer": {
        "model_role": "code",
        "tool_names": ["read_file", "list_dir", "grep", "git", "github", "rag_query"],
        "system_prompt_suffix": (
            "You are a CODE REVIEW sub-agent. Inspect with read_file/list_dir/grep/git; "
            "optionally github file_get for upstream prior art. Do not edit or shell. "
            "Cite file paths and line numbers; report risks specifically."
        ),
    },
    "pentest_runner": {
        "model_role": "default",
        "tool_names": [
            "shell_exec", "read_file", "grep", "cve_lookup", "malware_intel",
            "android", "web_fetch", "github", "rag_query",
        ],
        "system_prompt_suffix": (
            "You are a PENTEST/EXECUTION sub-agent on authorized targets only. "
            "Run shell_exec/android carefully; cross-check with cve_lookup/github/web_fetch. "
            "Report exact commands and output — don't over-summarize."
        ),
    },
    "general": {
        "model_role": "default",
        "tool_names": None,  # sentinel: None means "use the full, unrestricted tool registry"
        "system_prompt_suffix": (
            "You are a general-purpose sub-agent with the full tool set. "
            "Complete the task and return a clear final answer — parent sees only that."
        ),
    },
}

# Fallback preset used when an unrecognized role name is requested (a typo, or a model
# hallucinating a role that doesn't exist), so spawning degrades to a working
# general-purpose agent instead of raising. See hermes/agents/subagent.py.
GENERAL_PRESET: dict = ROLE_PRESETS["general"]
