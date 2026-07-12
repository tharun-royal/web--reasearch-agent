import argparse
import os

from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai

# Load environment variables
load_dotenv()


def search_web(query):
    """Search the web using Tavily."""
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    response = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5,
    )

    return response.get("results", [])


def generate_report(query, results):
    """Generate a research report using Gemini."""
    client = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY")
    )

    search_text = ""

    for r in results:
        search_text += (
            f"Title: {r.get('title', '')}\n"
            f"URL: {r.get('url', '')}\n"
            f"Content: {r.get('content', '')}\n\n"
        )

    prompt = f"""
You are a professional research analyst.

Research Topic:
{query}

Search Results:
{search_text}

Create a structured report with:

1. Summary
2. Key Findings (bullet points)
3. Sources
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text


def main():
    parser = argparse.ArgumentParser(
        description="Web Research Agent"
    )

    parser.add_argument(
        "--query",
        default="Latest AI Agents",
        help="Research topic",
    )

    args = parser.parse_args()

    print(f"\n🔍 Researching: {args.query}\n")

    results = search_web(args.query)

    report = generate_report(args.query, results)

    print("=" * 60)
    print("📄 RESEARCH REPORT")
    print("=" * 60)
    print(report)


if __name__ == "__main__":
    main()
