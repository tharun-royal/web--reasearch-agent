import os

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai

load_dotenv()

app = Flask(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing")

if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY is missing")

gemini = genai.Client(api_key=GOOGLE_API_KEY)
tavily = TavilyClient(api_key=TAVILY_API_KEY)


@app.route("/")
def home():
    return jsonify({
        "message": "Gemini Web Research Agent is Running!"
    })


@app.route("/research", methods=["POST"])
def research():

    data = request.get_json()

    query = data.get("query")

    if not query:
        return jsonify({
            "error": "Query is required"
        }), 400

    search = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5
    )

    results = search.get("results", [])

    text = ""

    for r in results:
        text += f"""
Title: {r.get('title')}

URL: {r.get('url')}

Content:
{r.get('content')}

"""

    prompt = f"""
You are an expert research analyst.

Research Topic:
{query}

Search Results:
{text}

Generate:

1. Summary

2. Key Findings

3. Sources
"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return jsonify({
        "query": query,
        "report": response.text
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000) 
