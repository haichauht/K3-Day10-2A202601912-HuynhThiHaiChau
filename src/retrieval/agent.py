from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool

from core.config import Settings
from retrieval.index import LocalEmbeddingIndex
from retrieval.llm import build_llm


def build_agent(settings: Settings, index: LocalEmbeddingIndex):
    @tool
    def semantic_search_papers(query: str, top_k: int = 4) -> str:
        """Search the local paper corpus with embeddings and return the most relevant papers."""
        results = index.search(query, top_k=top_k)
        lines = []
        for result in results:
            lines.append(
                f"paper_id: {result.paper_id}\n"
                f"title: {result.title}\n"
                f"score: {result.score:.4f}\n"
                f"{result.content}"
            )
        return "\n\n".join(lines)

    @tool
    def lookup_paper(paper_id_or_title: str) -> str:
        """Look up a paper by exact paper_id or exact title from the local corpus."""
        record = index.lookup(paper_id_or_title)
        if not record:
            return "No exact paper match found."
        return (
            f"paper_id: {record['paper_id']}\n"
            f"title: {record['title']}\n"
            f"{record['content']}"
        )

    # Chat Completions function tools on GPT-5.6 Luna require reasoning_effort=none.
    llm = build_llm(settings=settings, temperature=0.0, reasoning_effort="none")
    return create_agent(
        model=llm,
        tools=[semantic_search_papers, lookup_paper],
        system_prompt=(
            "You answer questions about the indexed scholarly paper corpus sourced from Crossref. "
            "Use tools before answering factual questions. "
            "If the indexed corpus does not support the answer, say so clearly."
        ),
        name="paper_corpus_agent",
    )


def run_agent_question(agent: Any, question: str) -> str:
    return run_agent_question_with_trace(agent, question)["answer"]


def run_agent_question_with_trace(agent: Any, question: str) -> dict[str, Any]:
    """Run the LangChain agent and expose its tool decisions for the demo UI."""
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    messages = result.get("messages", [])
    if not messages:
        return {"answer": "", "tool_calls": []}

    tool_calls: list[dict[str, Any]] = []
    for message in messages:
        for call in getattr(message, "tool_calls", []) or []:
            tool_calls.append(
                {
                    "name": call.get("name", "unknown_tool"),
                    "args": call.get("args", {}),
                }
            )

    final_message = messages[-1]
    return {
        "answer": getattr(final_message, "content", str(final_message)),
        "tool_calls": tool_calls,
    }
