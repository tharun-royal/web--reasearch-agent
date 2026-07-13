import io
import re
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from tavily import TavilyClient
from google import genai
import os

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

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


# ---------------------------------------------------------------------------
# PDF generation helpers
# ---------------------------------------------------------------------------

def _sanitize_pdf_text(text: str) -> str:
    """The built-in PDF core fonts only support latin-1. Replace common
    unicode punctuation with ascii equivalents, then drop anything else
    that still can't be encoded instead of crashing the request."""
    replacements = {
        "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...", "\u2022": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(query: str, report_text: str, sources: list) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(79, 70, 229)  # #4f46e5
    pdf.multi_cell(0, 10, _sanitize_pdf_text("Research Report"))
    pdf.ln(1)

    # Query subtitle
    pdf.set_font("Helvetica", "I", 12)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 7, _sanitize_pdf_text(f"Topic: {query}"))

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(140, 140, 140)
    pdf.multi_cell(0, 6, _sanitize_pdf_text(
        f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
    ))
    pdf.ln(4)

    # Body — render simple markdown-ish structure (#, numbered headings, bullets, bold)
    pdf.set_text_color(20, 20, 20)

    for raw_line in report_text.splitlines():
        line = _sanitize_pdf_text(raw_line.strip())

        if not line:
            pdf.ln(2)
            continue

        heading_match = re.match(r"^#{1,3}\s+(.*)", line) or re.match(r"^\d+\.\s+(.*)", line)
        bullet_match = re.match(r"^[-*]\s+(.*)", line)

        if heading_match and len(line) < 80:
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(79, 70, 229)
            pdf.ln(2)
            pdf.multi_cell(0, 8, re.sub(r"\*\*(.*?)\*\*", r"\1", heading_match.group(1)))
            pdf.set_text_color(20, 20, 20)
            pdf.ln(1)
        elif bullet_match:
            pdf.set_font("Helvetica", "", 11)
            text = re.sub(r"\*\*(.*?)\*\*", r"\1", bullet_match.group(1))
            pdf.multi_cell(0, 7, f"  -  {text}")
        else:
            pdf.set_font("Helvetica", "", 11)
            text = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            pdf.multi_cell(0, 7, text)

    # Sources — rendered from real search results, not model output
    if sources:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(79, 70, 229)
        pdf.multi_cell(0, 8, "Sources")
        pdf.set_text_color(20, 20, 20)
        pdf.ln(1)

        for i, s in enumerate(sources, 1):
            title = _sanitize_pdf_text(s.get("title") or s.get("url", ""))
            url = _sanitize_pdf_text(s.get("url", ""))

            pdf.set_font("Helvetica", "B", 10.5)
            pdf.multi_cell(0, 6.5, f"{i}. {title}")

            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(37, 99, 235)
            start_y = pdf.get_y()
            pdf.multi_cell(0, 6, url, link=url)
            pdf.set_text_color(20, 20, 20)
            pdf.ln(0.5)

    output = pdf.output()
    return bytes(output)


def _domain(url: str) -> str:
    m = re.match(r"^https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else (url or "")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Research Agent</title>

<style>

*{box-sizing:border-box;}

:root{
  --accent:#6366f1;
  --accent-2:#22d3ee;
  --bg-1:#0f0c29;
  --bg-2:#302b63;
  --bg-3:#24243e;
  --card:#ffffff;
  --text-dim:#6b7280;
  --success:#16a34a;
}

body{
  margin:0;
  min-height:100vh;
  font-family:'Segoe UI',Arial,sans-serif;
  background:linear-gradient(135deg,var(--bg-1),var(--bg-2) 50%,var(--bg-3));
  background-size:200% 200%;
  animation:gradientShift 15s ease infinite;
  display:flex;
  justify-content:center;
  align-items:flex-start;
  padding:48px 16px 90px;
}

@keyframes gradientShift{
  0%{background-position:0% 50%;}
  50%{background-position:100% 50%;}
  100%{background-position:0% 50%;}
}

.wrap{
  width:100%;
  max-width:820px;
}

.header{
  text-align:center;
  margin-bottom:28px;
  color:white;
}

.header h1{
  font-size:32px;
  margin:0 0 6px 0;
  font-weight:700;
  letter-spacing:-0.5px;
}

.header p{
  margin:0;
  color:rgba(255,255,255,0.7);
  font-size:15px;
}

.card{
  background:var(--card);
  border-radius:20px;
  padding:28px;
  box-shadow:0 20px 60px rgba(0,0,0,0.35);
}

.search-row{
  display:flex;
  gap:10px;
}

.search-box{
  flex:1;
  position:relative;
}

.search-box svg{
  position:absolute;
  left:14px;
  top:50%;
  transform:translateY(-50%);
  opacity:0.4;
}

input{
  width:100%;
  padding:14px 14px 14px 42px;
  font-size:15px;
  border-radius:12px;
  border:1.5px solid #e5e7eb;
  outline:none;
  transition:border-color .15s ease;
}

input:focus{
  border-color:var(--accent);
}

button{
  padding:14px 22px;
  background:linear-gradient(135deg,var(--accent),#8b5cf6);
  color:white;
  border:none;
  border-radius:12px;
  cursor:pointer;
  font-size:15px;
  font-weight:600;
  white-space:nowrap;
  transition:transform .12s ease, box-shadow .12s ease;
}

button:hover{
  transform:translateY(-1px);
  box-shadow:0 8px 20px rgba(99,102,241,0.35);
}

button:disabled{
  opacity:0.6;
  cursor:not-allowed;
  transform:none;
  box-shadow:none;
}

button.secondary{
  background:#f3f4f6;
  color:#374151;
}

button.secondary:hover{
  box-shadow:0 8px 20px rgba(0,0,0,0.08);
}

button.success{
  background:linear-gradient(135deg,#16a34a,#22c55e);
}

.chips{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin-top:14px;
}

.chip{
  padding:7px 13px;
  background:#f3f4f6;
  border-radius:999px;
  font-size:12.5px;
  color:#4b5563;
  cursor:pointer;
  transition:background .12s ease, color .12s ease;
  border:1px solid transparent;
}

.chip:hover{
  background:#eef2ff;
  color:var(--accent);
  border-color:#e0e7ff;
}

.status{
  margin-top:18px;
  text-align:center;
  color:var(--text-dim);
  font-size:14px;
  min-height:20px;
}

.spinner{
  width:18px;
  height:18px;
  border:2.5px solid #e5e7eb;
  border-top-color:var(--accent);
  border-radius:50%;
  display:inline-block;
  vertical-align:middle;
  margin-right:8px;
  animation:spin .7s linear infinite;
}

@keyframes spin{to{transform:rotate(360deg);}}

.result{
  display:none;
  margin-top:24px;
  border-top:1px solid #eee;
  padding-top:22px;
  animation:fadeUp .35s ease;
}

@keyframes fadeUp{
  from{opacity:0; transform:translateY(8px);}
  to{opacity:1; transform:translateY(0);}
}

.result-toolbar{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  margin-bottom:6px;
  flex-wrap:wrap;
  gap:10px;
}

.result-title-block strong{
  display:block;
  color:#111827;
  font-size:15.5px;
  margin-bottom:3px;
}

.result-meta{
  color:#9ca3af;
  font-size:12.5px;
}

.result-toolbar .actions{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}

.result-toolbar button{
  padding:9px 16px;
  font-size:13px;
}

.result-content{
  margin-top:16px;
}

.result-content h3{
  color:var(--accent);
  font-size:16px;
  margin:18px 0 8px 0;
}

.result-content h3:first-child{
  margin-top:0;
}

.result-content p{
  color:#374151;
  line-height:1.65;
  font-size:14.5px;
  margin:0 0 10px 0;
}

.result-content ul{
  margin:0 0 12px 0;
  padding-left:20px;
}

.result-content li{
  color:#374151;
  line-height:1.6;
  font-size:14.5px;
  margin-bottom:4px;
}

.sources{
  margin-top:8px;
  padding-top:18px;
  border-top:1px dashed #e5e7eb;
}

.sources h3{
  color:var(--accent);
  font-size:16px;
  margin:0 0 10px 0;
}

.source-card{
  display:flex;
  align-items:flex-start;
  gap:10px;
  padding:11px 12px;
  border-radius:12px;
  text-decoration:none;
  margin-bottom:8px;
  transition:background .12s ease;
}

.source-card:hover{
  background:#f9fafb;
}

.source-num{
  flex-shrink:0;
  width:22px;
  height:22px;
  border-radius:50%;
  background:#eef2ff;
  color:var(--accent);
  font-size:11.5px;
  font-weight:700;
  display:flex;
  align-items:center;
  justify-content:center;
  margin-top:1px;
}

.source-text strong{
  display:block;
  color:#1f2937;
  font-size:13.5px;
  font-weight:600;
  margin-bottom:2px;
}

.source-text span{
  color:#9ca3af;
  font-size:12px;
}

.empty-hint{
  text-align:center;
  color:#9ca3af;
  font-size:13.5px;
  margin-top:6px;
}

.toast-stack{
  position:fixed;
  bottom:22px;
  right:22px;
  display:flex;
  flex-direction:column;
  gap:10px;
  z-index:999;
}

.toast{
  background:#111827;
  color:white;
  padding:12px 18px;
  border-radius:10px;
  font-size:13.5px;
  box-shadow:0 10px 30px rgba(0,0,0,0.3);
  animation:toastIn .2s ease;
  max-width:320px;
}

.toast.error{ background:#dc2626; }
.toast.success{ background:#16a34a; }

@keyframes toastIn{
  from{opacity:0; transform:translateY(10px);}
  to{opacity:1; transform:translateY(0);}
}

@media(max-width:520px){
  .search-row{flex-direction:column;}
  .result-toolbar{flex-direction:column;}
}

</style>
</head>

<body>

<div class="wrap">

  <div class="header">
    <h1>🔍 Research Agent</h1>
    <p>AI-powered web research — search any topic and get a structured report</p>
  </div>

  <div class="card">

    <div class="search-row">
      <div class="search-box">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input id="query" placeholder="Enter a research topic..." onkeydown="if(event.key==='Enter')research()">
      </div>
      <button id="searchBtn" onclick="research()">Search</button>
    </div>

    <div id="chips" class="chips">
      <div class="chip" onclick="useChip(this)">impact of remote work on productivity</div>
      <div class="chip" onclick="useChip(this)">latest advances in solid-state batteries</div>
      <div class="chip" onclick="useChip(this)">global coffee supply chain trends</div>
    </div>

    <div id="status" class="status"></div>

    <div id="result" class="result">
      <div class="result-toolbar">
        <div class="result-title-block">
          <strong id="resultTitle"></strong>
          <span id="resultMeta" class="result-meta"></span>
        </div>
        <div class="actions">
          <button class="secondary" onclick="newSearch()">↺ New search</button>
          <button class="secondary" onclick="copyReport()">📋 Copy</button>
          <button onclick="downloadPdf()" id="pdfBtn">⬇ Download PDF</button>
        </div>
      </div>
      <div id="resultContent" class="result-content"></div>

      <div id="sourcesBlock" class="sources" style="display:none;">
        <h3>Sources</h3>
        <div id="sourcesList"></div>
      </div>
    </div>

  </div>
</div>

<div id="toastStack" class="toast-stack"></div>

<script>

let currentQuery = "";
let currentReport = "";
let currentSources = [];
let loadingInterval = null;

function showToast(message, type){
  const stack = document.getElementById("toastStack");
  const el = document.createElement("div");
  el.className = "toast" + (type ? " " + type : "");
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function useChip(el){
  document.getElementById("query").value = el.textContent;
  research();
}

function escapeHtml(str){
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatReport(text){
  const lines = text.split("\\n");
  let html = "";
  let inList = false;

  for (let rawLine of lines){
    const line = rawLine.trim();

    if(!line){
      if(inList){ html += "</ul>"; inList = false; }
      continue;
    }

    const headingMatch = line.match(/^#{1,3}\\s+(.*)/) || line.match(/^\\d+\\.\\s+(.*)/);
    const bulletMatch = line.match(/^[-*]\\s+(.*)/);

    if(headingMatch && line.length < 80){
      if(inList){ html += "</ul>"; inList = false; }
      const content = escapeHtml(headingMatch[1]).replace(/\\*\\*(.*?)\\*\\*/g, "<strong>$1</strong>");
      html += `<h3>${content}</h3>`;
    } else if(bulletMatch){
      if(!inList){ html += "<ul>"; inList = true; }
      const content = escapeHtml(bulletMatch[1]).replace(/\\*\\*(.*?)\\*\\*/g, "<strong>$1</strong>");
      html += `<li>${content}</li>`;
    } else {
      if(inList){ html += "</ul>"; inList = false; }
      const content = escapeHtml(line).replace(/\\*\\*(.*?)\\*\\*/g, "<strong>$1</strong>");
      html += `<p>${content}</p>`;
    }
  }

  if(inList) html += "</ul>";
  return html;
}

function renderSources(sources){
  const block = document.getElementById("sourcesBlock");
  const list = document.getElementById("sourcesList");

  if(!sources || !sources.length){
    block.style.display = "none";
    list.innerHTML = "";
    return;
  }

  list.innerHTML = sources.map((s, i) => `
    <a class="source-card" href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">
      <div class="source-num">${i + 1}</div>
      <div class="source-text">
        <strong>${escapeHtml(s.title || s.url)}</strong>
        <span>${escapeHtml(s.domain || "")}</span>
      </div>
    </a>
  `).join("");

  block.style.display = "block";
}

function cycleStatus(){
  const messages = [
    "Searching the web...",
    "Reading sources...",
    "Synthesizing findings...",
    "Writing report..."
  ];
  let i = 0;
  const statusEl = document.getElementById("status");
  statusEl.innerHTML = `<span class="spinner"></span> ${messages[0]}`;
  loadingInterval = setInterval(() => {
    i = (i + 1) % messages.length;
    statusEl.innerHTML = `<span class="spinner"></span> ${messages[i]}`;
  }, 1600);
}

function stopCycleStatus(){
  if(loadingInterval){
    clearInterval(loadingInterval);
    loadingInterval = null;
  }
}

async function research(){

  const queryInput = document.getElementById("query");
  const query = queryInput.value.trim();
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const searchBtn = document.getElementById("searchBtn");
  const chips = document.getElementById("chips");

  if(!query){
    showToast("Please enter a topic.", "error");
    return;
  }

  searchBtn.disabled = true;
  resultEl.style.display = "none";
  chips.style.display = "none";
  cycleStatus();

  try{
    const response = await fetch("/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query })
    });

    const data = await response.json();

    if(data.error){
      showToast(data.error, "error");
      chips.style.display = "flex";
      return;
    }

    currentQuery = query;
    currentReport = data.report;
    currentSources = data.sources || [];

    const wordCount = data.report.trim().split(/\\s+/).length;
    const readMins = Math.max(1, Math.round(wordCount / 200));

    document.getElementById("resultTitle").textContent = "Report: " + query;
    document.getElementById("resultMeta").textContent =
      `${wordCount} words · ~${readMins} min read · ${currentSources.length} sources`;
    document.getElementById("resultContent").innerHTML = formatReport(data.report);
    renderSources(currentSources);

    const pdfBtn = document.getElementById("pdfBtn");
    pdfBtn.className = "";
    pdfBtn.textContent = "⬇ Download PDF";

    resultEl.style.display = "block";
    resultEl.scrollIntoView({ behavior: "smooth", block: "start" });

  }catch(err){
    showToast("Something went wrong: " + err, "error");
    chips.style.display = "flex";
  }finally{
    stopCycleStatus();
    document.getElementById("status").innerHTML = "";
    searchBtn.disabled = false;
  }
}

function newSearch(){
  document.getElementById("result").style.display = "none";
  document.getElementById("chips").style.display = "flex";
  document.getElementById("query").value = "";
  document.getElementById("query").focus();
}

function copyReport(){
  if(!currentReport) return;
  navigator.clipboard.writeText(currentReport).then(() => {
    showToast("Report copied to clipboard.", "success");
  }).catch(() => {
    showToast("Couldn't copy — try selecting the text manually.", "error");
  });
}

async function downloadPdf(){
  if(!currentReport) return;

  const pdfBtn = document.getElementById("pdfBtn");
  pdfBtn.disabled = true;
  pdfBtn.textContent = "Generating...";

  try{
    const response = await fetch("/download-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: currentQuery, report: currentReport, sources: currentSources })
    });

    if(response.status === 501){
      const errData = await response.json();
      showToast(errData.error || "PDF export is not available on this server.", "error");
      return;
    }

    if(!response.ok){
      throw new Error("PDF generation failed");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `research-report-${currentQuery.slice(0,30).replace(/[^a-z0-9]+/gi,"-")}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    pdfBtn.className = "success";
    pdfBtn.textContent = "✓ PDF ready";
    showToast("PDF downloaded.", "success");
    setTimeout(() => {
      pdfBtn.className = "";
      pdfBtn.textContent = "⬇ Download PDF";
    }, 2500);

  }catch(err){
    showToast("Could not generate PDF: " + err, "error");
  }finally{
    pdfBtn.disabled = false;
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

    # Real sources taken directly from the search results, not from the
    # model's own output — this way links are always accurate and clickable.
    sources = [
        {
            "title": r.get("title") or r.get("url"),
            "url": r.get("url"),
            "domain": _domain(r.get("url")),
        }
        for r in results
        if r.get("url")
    ]

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

Generate a report with these sections only:

1. Summary

2. Key Findings

Do not include a Sources section — sources will be listed separately.
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
            "report": report_text,
            "sources": sources,
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 502


@app.route("/download-pdf", methods=["POST"])
def download_pdf():

    data = request.get_json(silent=True) or {}

    query = (data.get("query") or "Research Report").strip()
    report_text = (data.get("report") or "").strip()
    sources = data.get("sources") or []

    if not report_text:
        return jsonify({"error": "No report content to export."}), 400

    if not FPDF_AVAILABLE:
        return jsonify({
            "error": "PDF export isn't available: the 'fpdf2' package is not "
                     "installed on the server. Run: pip install fpdf2"
        }), 501

    try:
        pdf_bytes = build_pdf(query, report_text, sources)
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}"}), 500

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="research-report.pdf"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
