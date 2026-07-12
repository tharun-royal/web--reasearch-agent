import argparse
import os

from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai

load_dotenv()


def search_web(query):
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5
    )

    return response.get("results", [])


def generate_report(query, results):
    client = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    search_text = ""

    for r in results:
        search_text += f"""
Title: {r.get("title")}
URL: {r.get("url")}
Content: {r.get("content")}

"""

    prompt = f"""
You are a professional research analyst.

Research Topic:
{query}

Search Results:
{search_text}

Create a report with:

1. Summary
2. Key Findings
3. Sources
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--query",
        default="Latest AI Agents",
        help="Research topic",
    )

    args = parser.parse_args()

    print(f"\nResearching: {args.query}\n")

    results = search_web(args.query)

    report = generate_report(args.query, results)

    print("=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()    result = agent.invoke(
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
