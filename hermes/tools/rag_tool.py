"""RAG tools exposed to the model mid-conversation: querying the knowledge base, and a
generic "remember this" note-taking tool. DIFFERENT signature than every other tool module —
build_tools here takes live wired-up RAGRetriever/IngestPipeline objects (they carry an
embedder + vector store that must already be constructed against a running Ollama client),
not just a HermesConfig. That wiring happens in integration code outside this file's scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hermes.tools.base import Tool, ToolResult, ToolSchema

if TYPE_CHECKING:
    from hermes.rag.ingest import IngestPipeline
    from hermes.rag.retriever import RAGRetriever


def build_tools(retriever: "RAGRetriever", ingest: "IngestPipeline") -> list[Tool]:
    async def rag_query(query: str, k: int = 5, source_type: str | None = None) -> ToolResult:
        if not query or not query.strip():
            return ToolResult.failure("missing_argument", "rag_query requires a non-empty query.")
        try:
            chunks = await retriever.query(query, k=k, source_type=source_type)
        except Exception as e:  # noqa: BLE001 - never crash the agent loop on a retrieval hiccup
            return ToolResult.failure(f"rag_query_error: {type(e).__name__}: {e}")

        if not chunks:
            return ToolResult.success(
                "No matching knowledge found." + (f" (source_type={source_type!r})" if source_type else "")
            )
        formatted = retriever.format_for_prompt(chunks)
        return ToolResult.success(
            formatted,
            display=f"Found {len(chunks)} matching chunk(s) for {query!r}.",
        )

    async def rag_remember(text: str, label: str) -> ToolResult:
        if not text or not text.strip():
            return ToolResult.failure("missing_argument", "rag_remember requires non-empty text.")
        if not label or not label.strip():
            return ToolResult.failure("missing_argument", "rag_remember requires a short label.")

        label = label.strip()
        try:
            added = await ingest.ingest_note(text, label)
        except Exception as e:  # noqa: BLE001
            return ToolResult.failure(f"rag_remember_error: {type(e).__name__}: {e}")

        if added == 0:
            return ToolResult.success(f"Already remembered under '{label}' — nothing new to add.")
        return ToolResult.success(f"Remembered {added} chunk(s) under source='note:{label}'.")

    query_schema = ToolSchema(
        name="rag_query",
        description=(
            "Search Miku's local knowledge base (ingested CVEs, malware intel, project code/docs, "
            "remembered notes, and reference corpora like Win32 API docs, Linux kernel docs, and "
            "MITRE ATT&CK technique data) for text relevant to `query`. Optionally filter by "
            "source_type ('knowledge', 'cve', 'malware_intel', 'project', 'reference', 'web_cache')."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language search query."},
                "k": {"type": "integer", "description": "Max number of chunks to return. Default 5."},
                "source_type": {
                    "type": "string",
                    "enum": ["knowledge", "cve", "malware_intel", "project", "reference", "web_cache"],
                    "description": "Optional: restrict results to one source type.",
                },
            },
            "required": ["query"],
        },
    )

    remember_schema = ToolSchema(
        name="rag_remember",
        description=(
            "Remember a piece of text for later — embeds and stores it in the knowledge base "
            "under a short label so a future rag_query can retrieve it. Use for durable facts, "
            "decisions, or context worth recalling in a later conversation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to remember."},
                "label": {"type": "string", "description": "A short label identifying this note, e.g. 'fyp-mdm-decision'."},
            },
            "required": ["text", "label"],
        },
    )

    return [
        Tool(schema=query_schema, handler=rag_query),
        Tool(schema=remember_schema, handler=rag_remember),
    ]
