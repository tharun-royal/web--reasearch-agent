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
    return """
<!DOCTYPE html>
<html>
<head>
<title>Gemini Web Research Agent</title>

<style>

body{
margin:0;
font-family:Arial,sans-serif;
background:linear-gradient(135deg,#4f46e5,#06b6d4);
display:flex;
justify-content:center;
align-items:center;
height:100vh;
}

.container{
background:white;
padding:30px;
border-radius:15px;
width:90%;
max-width:900px;
box-shadow:0 10px 30px rgba(0,0,0,.2);
text-align:center;
}

h1{
color:#4f46e5;
}

input{
width:80%;
padding:12px;
font-size:16px;
border-radius:8px;
border:1px solid #ccc;
}

button{
padding:12px 20px;
margin-top:15px;
background:#4f46e5;
color:white;
border:none;
border-radius:8px;
cursor:pointer;
font-size:16px;
}

button:hover{
background:#3730a3;
}

pre{
margin-top:20px;
background:#f4f4f4;
padding:20px;
border-radius:10px;
text-align:left;
white-space:pre-wrap;
max-height:400px;
overflow:auto;
}

</style>

</head>

<body>

<div class="container">

<h1>🔍 Gemini Web Research Agent</h1>

<p>Search any topic using Gemini AI + Tavily</p>

<input id="query" placeholder="Enter research topic">

<br>

<button onclick="research()">Search</button>

<pre id="result">Your report will appear here...</pre>

</div>

<script>

async function research(){

const query=document.getElementById("query").value.trim();

const resultEl=document.getElementById("result");

if(!query){
resultEl.textContent="Please enter a topic.";
return;
}

resultEl.textContent="⏳ Researching...";

try{

const response=await fetch("/research",{

method:"POST",

headers:{
"Content-Type":"application/json"
},

body:JSON.stringify({
query:query
})

});

const data=await response.json();

// Use textContent (not innerHTML) to avoid rendering
// untrusted text as HTML.
resultEl.textContent=data.report || data.error || "No response received.";

}catch(err){

resultEl.textContent="Error: "+err;

}

}

</script>

</body>

</html>
"""


@app.route("/research", methods=["POST"])
def research():

    data = request.get_json(silent=True) or {}

    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Please enter a topic."}), 400

    try:
        search = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )
    except Exception as e:
        return jsonify({"error": f"Search failed: {e}"}), 502

    results = search.get("results", [])

    if not results:
        return jsonify({"error": "No search results found for that topic."}), 404

    search_text = ""

    for r in results:
        search_text += f"""
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
{search_text}

Generate:

1. Summary

2. Key Findings

3. Sources
"""

    try:
        response = gemini.models.generate_content(
            # "gemini-flash-latest" always points to Google's current
            # recommended Flash model, so this won't 404 on the next
            # deprecation. Pin to "gemini-3.5-flash" instead if you want
            # a fixed, reproducible model version.
            model="gemini-flash-latest",
            contents=prompt
        )

        report_text = getattr(response, "text", None)

        if not report_text:
            return jsonify({
                "error": "Gemini returned no usable content (possibly blocked by safety filters)."
            }), 502

        return jsonify({
            "report": report_text
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

<br>

<button onclick="research()">Search</button>

<pre id="result">Your report will appear here...</pre>

</div>

<script>

async function research(){

const query=document.getElementById("query").value.trim();

const resultEl=document.getElementById("result");

if(!query){
resultEl.textContent="Please enter a topic.";
return;
}

resultEl.textContent="⏳ Researching...";

try{

const response=await fetch("/research",{

method:"POST",

headers:{
"Content-Type":"application/json"
},

body:JSON.stringify({
query:query
})

});

const data=await response.json();

// Use textContent (not innerHTML) to avoid rendering
// untrusted text as HTML.
resultEl.textContent=data.report || data.error || "No response received.";

}catch(err){

resultEl.textContent="Error: "+err;

}

}

</script>

</body>

</html>
"""


@app.route("/research", methods=["POST"])
def research():

    data = request.get_json(silent=True) or {}

    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Please enter a topic."}), 400

    try:
        search = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )
    except Exception as e:
        return jsonify({"error": f"Search failed: {e}"}), 502

    results = search.get("results", [])

    if not results:
        return jsonify({"error": "No search results found for that topic."}), 404

    search_text = ""

    for r in results:
        search_text += f"""
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
{search_text}

Generate:

1. Summary

2. Key Findings

3. Sources
"""

    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        report_text = getattr(response, "text", None)

        if not report_text:
            return jsonify({
                "error": "Gemini returned no usable content (possibly blocked by safety filters)."
            }), 502

        return jsonify({
            "report": report_text
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
