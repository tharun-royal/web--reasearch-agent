import os

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai

load_dotenv()

app = Flask(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

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
font-family:Arial;
background:#f5f5f5;
padding:40px;
}

.container{
background:white;
padding:20px;
border-radius:10px;
max-width:900px;
margin:auto;
}

input{
width:80%;
padding:10px;
font-size:16px;
}

button{
padding:10px 20px;
font-size:16px;
cursor:pointer;
}

pre{
background:#eee;
padding:20px;
margin-top:20px;
white-space:pre-wrap;
}

</style>

</head>

<body>

<div class="container">

<h2>🔍 Gemini Web Research Agent</h2>

<input
id="query"
placeholder="Enter Research Topic">

<button onclick="research()">

Search

</button>

<pre id="result"></pre>

</div>

<script>

async function research(){

const query=document.getElementById("query").value;

document.getElementById("result").innerHTML="Searching...";

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

document.getElementById("result").innerHTML=data.report;

}

</script>

</body>

</html>

"""


@app.route("/research", methods=["POST"])
def research():

    data=request.get_json()

    query=data.get("query")

    if not query:
        return jsonify({
            "report":"Please enter a topic."
        })

    search=tavily.search(
        query=query,
        search_depth="advanced",
        max_results=5
    )

    results=search.get("results",[])

    text=""

    for r in results:

        text+=f"""

Title: {r.get('title')}

URL: {r.get('url')}

Content:
{r.get('content')}

"""

    prompt=f"""

Research Topic:

{query}

Search Results:

{text}

Generate:

1. Summary

2. Key Findings

3. Sources

"""

    response=gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return jsonify({
        "report":response.text
    })


if __name__=="__main__":
    app.run(host="0.0.0.0",port=10000)
