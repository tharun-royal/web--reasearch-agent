"""
Web Research Agent using LangGraph + Tavily Search + Gemini
"""

import argparse
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_tavily import TavilySearch
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()


class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    search_results: list[dict]
    report: str


def search_web(state: ResearchState) -> ResearchState:
    tool = TavilySearch(max_results=5)

    raw_results = tool.invoke(state["query"])

    if isinstance(raw_results, dict):
        results = raw_results.get("results", [])
    elif isinstance(raw_results, list):
        results = raw_results
    else:
        results = []

    return {"search_results": results}


def synthesize_report(state: ResearchState) -> ResearchState:

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
    )

    results_text = "\n\n".join(
        f"Source: {r.get('url','N/A')}\n"
        f"Title: {r.get('title','N/A')}\n"
        f"Content: {r.get('content','')[:500]}"
        for r in state["search_results"]
    )

    messages = [
        SystemMessage(
            content=(
                "You are a research analyst. "
                "Create a structured report with:\n"
                "1. Summary\n"
                "2. Key Findings (bullet points)\n"
                "3. Sources"
            )
        ),
        HumanMessage(
            content=f"Research Query:\n{state['query']}\n\nSearch Results:\n{results_text}"
        ),
    ]

    response = llm.invoke(messages)

    return {
        "report": response.content,
        "messages": [response],
    }


def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("search", search_web)
    graph.add_node("synthesize", synthesize_report)

    graph.set_entry_point("search")

    graph.add_edge("search", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def main():
    parser = argparse.ArgumentParser(description="Web Research Agent")

    parser.add_argument(
        "--query",
        default="Latest advances in AI agents",
        help="Research Query",
    )

    args = parser.parse_args()

    print(f"\nResearching: {args.query}\n")

    agent = build_graph()

    result = agent.invoke(
        {
            "query": args.query,
            "messages": [],
            "search_results": [],
            "report": "",
        }
    )

    print("=" * 60)
    print("RESEARCH REPORT")
    print("=" * 60)
    print(result["report"])


if __name__ == "__main__":
    main()
