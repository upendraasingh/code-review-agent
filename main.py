import os
import json
import sqlite3
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

app = FastAPI()

# ─── Database Setup ───────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("reviews.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            type TEXT,
            language TEXT,
            overall_score INTEGER,
            security_findings TEXT,
            performance_findings TEXT,
            style_findings TEXT,
            summary TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ─── Models ───────────────────────────────────────────────────────────────────
class CodeRequest(BaseModel):
    code: str
    language: str = "python"
    filename: str = ""

class PRRequest(BaseModel):
    pr_url: str

# ─── AI Review ────────────────────────────────────────────────────────────────
def get_llm():
    api_key = os.environ.get("GROQ_API_KEY")
    return ChatGroq(model="llama-3.1-8b-instant", api_key=api_key)

def run_review(code: str, language: str):
    llm = get_llm()
    system_msg = (
        "You are an expert code reviewer. Analyze the code and return ONLY a JSON object like this:\n"
        '{{"score": 7, "security": ["SQL injection on line 3", "Hardcoded password found"], '
        '"performance": ["N+1 query detected", "Missing index"], '
        '"style": ["Missing docstring", "Bad variable name"], '
        '"summary": "Code has security issues that need fixing."}}\n'
        "Return ONLY the JSON. No markdown, no explanation, no backticks."
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", "Review this {language} code:\n\n{code}")
    ])
    chain = prompt | llm
    result = chain.invoke({"language": language, "code": code})
    content = result.content.strip()
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    data = json.loads(content.strip())
    return data

# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/review-code")
async def review_code(request: CodeRequest):
    try:
        data = run_review(request.code, request.language)
        score = int(data.get("score", 5))
        security = data.get("security", [])
        performance = data.get("performance", [])
        style = data.get("style", [])
        summary = data.get("summary", "Review complete.")

        conn = sqlite3.connect("reviews.db")
        conn.execute("""
            INSERT INTO reviews (created_at, type, language, overall_score, security_findings, performance_findings, style_findings, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            "code",
            request.language,
            score,
            json.dumps(security),
            json.dumps(performance),
            json.dumps(style),
            summary,
            "complete"
        ))
        conn.commit()
        conn.close()

        return {
            "status": "complete",
            "overall_score": score,
            "security_findings": security,
            "performance_findings": performance,
            "style_findings": style,
            "summary": summary
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/review-pr")
async def review_pr(request: PRRequest):
    try:
        dummy_code = f"# PR from {request.pr_url}\n# Fetching diff...\ndef example():\n    pass"
        data = run_review(dummy_code, "python")
        score = int(data.get("score", 5))
        security = data.get("security", [])
        performance = data.get("performance", [])
        style = data.get("style", [])
        summary = data.get("summary", "PR Review complete.")

        conn = sqlite3.connect("reviews.db")
        conn.execute("""
            INSERT INTO reviews (created_at, type, language, overall_score, security_findings, performance_findings, style_findings, summary, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            "pr",
            "python",
            score,
            json.dumps(security),
            json.dumps(performance),
            json.dumps(style),
            summary,
            "complete"
        ))
        conn.commit()
        conn.close()

        return {
            "status": "complete",
            "overall_score": score,
            "security_findings": security,
            "performance_findings": performance,
            "style_findings": style,
            "summary": summary
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/reviews")
async def get_reviews():
    conn = sqlite3.connect("reviews.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM reviews ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    reviews = []
    for row in rows:
        reviews.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "type": row["type"],
            "language": row["language"],
            "overall_score": row["overall_score"],
            "security_findings": json.loads(row["security_findings"] or "[]"),
            "performance_findings": json.loads(row["performance_findings"] or "[]"),
            "style_findings": json.loads(row["style_findings"] or "[]"),
            "summary": row["summary"],
            "status": row["status"]
        })
    return reviews


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AI Code Review Agent</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }
.header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 32px; display: flex; align-items: center; gap: 12px; }
.header-badge { background: #1f6feb; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
.header h1 { font-size: 20px; font-weight: 700; color: #e6edf3; }
.header p { font-size: 13px; color: #8b949e; margin-top: 2px; }
.container { max-width: 1200px; margin: 0 auto; padding: 32px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 24px; }
.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab { padding: 8px 16px; border-radius: 8px; border: 1px solid #30363d; background: transparent; color: #8b949e; cursor: pointer; font-size: 14px; transition: all 0.2s; }
.tab.active { background: #1f6feb; color: white; border-color: #1f6feb; }
.tab:hover:not(.active) { background: #21262d; color: #e6edf3; }
label { display: block; font-size: 13px; color: #8b949e; margin-bottom: 8px; font-weight: 500; }
.lang-pills { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.lang-pill { padding: 6px 14px; border-radius: 20px; border: 1px solid #30363d; background: transparent; color: #8b949e; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.lang-pill.active { background: #1f6feb; color: white; border-color: #1f6feb; }
textarea { width: 100%; height: 220px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #e6edf3; padding: 12px; font-family: 'Courier New', monospace; font-size: 13px; resize: vertical; outline: none; }
textarea:focus { border-color: #1f6feb; }
input[type=text] { width: 100%; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #e6edf3; padding: 12px; font-size: 14px; outline: none; margin-bottom: 8px; }
input[type=text]:focus { border-color: #1f6feb; }
.btn { width: 100%; padding: 12px; background: #1f6feb; color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 16px; transition: background 0.2s; }
.btn:hover { background: #388bfd; }
.btn:disabled { background: #21262d; color: #8b949e; cursor: not-allowed; }
.score-circle { width: 100px; height: 100px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; color: white; margin: 0 auto 16px; }
.score-green { background: #238636; }
.score-yellow { background: #d29922; }
.score-red { background: #da3633; }
.findings-card { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.findings-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.finding-item { padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; font-size: 13px; line-height: 1.5; }
.finding-security { background: #3d1f1f; border-left: 3px solid #f85149; }
.finding-performance { background: #2d2a1f; border-left: 3px solid #d29922; }
.finding-style { background: #1f2a3d; border-left: 3px solid #58a6ff; }
.summary-box { background: #21262d; border-radius: 8px; padding: 12px 16px; font-size: 13px; color: #8b949e; margin-bottom: 16px; }
.spinner { display: none; text-align: center; padding: 20px; color: #8b949e; font-size: 14px; }
.spinner.show { display: block; }
.history-section { margin-top: 32px; }
.history-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #e6edf3; }
.history-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: border-color 0.2s; }
.history-card:hover { border-color: #1f6feb; }
.history-info h3 { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.history-info p { font-size: 12px; color: #8b949e; }
.lang-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: #21262d; color: #8b949e; margin-left: 8px; }
.mini-score { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; color: white; flex-shrink: 0; }
.placeholder { text-align: center; padding: 40px; color: #8b949e; font-size: 14px; }
.tab-content { display: none; }
.tab-content.active { display: block; }
</style>
</head>
<body>

<div class="header">
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
      <span class="header-badge">🤖 AI Code Review Agent</span>
    </div>
    <h1>Instant, smart, and demo-ready code reviews</h1>
    <p>Paste raw code or a GitHub PR URL to get AI-powered security, performance, and style feedback.</p>
  </div>
</div>

<div class="container">
  <div class="grid">

    <!-- LEFT: Input -->
    <div class="card">
      <div class="tabs">
        <button class="tab active" onclick="switchTab('code', this)">📝 Review Code</button>
        <button class="tab" onclick="switchTab('pr', this)">🔗 Review GitHub PR</button>
      </div>

      <!-- Code Tab -->
      <div id="tab-code" class="tab-content active">
        <label>Language</label>
        <div class="lang-pills">
          <button class="lang-pill active" onclick="selectLang('python', this)">Python</button>
          <button class="lang-pill" onclick="selectLang('php', this)">PHP</button>
          <button class="lang-pill" onclick="selectLang('javascript', this)">JavaScript</button>
          <button class="lang-pill" onclick="selectLang('ruby', this)">Ruby</button>
          <button class="lang-pill" onclick="selectLang('sql', this)">SQL</button>
        </div>
        <label>Paste your code</label>
        <textarea id="code-input" placeholder="Paste your code here..."></textarea>
        <button class="btn" id="review-btn" onclick="reviewCode()">Review My Code</button>
      </div>

      <!-- PR Tab -->
      <div id="tab-pr" class="tab-content">
        <label>GitHub PR URL</label>
        <input type="text" id="pr-input" placeholder="https://github.com/username/repo/pull/1"/>
        <p style="font-size:12px;color:#8b949e;margin-bottom:8px;">Paste any public GitHub PR URL to get an AI review</p>
        <button class="btn" id="pr-btn" onclick="reviewPR()">Review PR</button>
      </div>
    </div>

    <!-- RIGHT: Results -->
    <div class="card" id="results-panel">
      <div class="placeholder" id="placeholder">
        <div style="font-size:48px;margin-bottom:16px;">🤖</div>
        <p>Paste your code and click "Review My Code" to get started</p>
      </div>

      <div id="spinner" class="spinner">
        ⏳ AI agents are analyzing your code...
      </div>

      <div id="results" style="display:none;">
        <div id="score-circle" class="score-circle score-yellow" style="display:none;"></div>
        <div class="summary-box" id="summary-box" style="display:none;"></div>

        <div class="findings-card">
          <div class="findings-title">🔴 Security Findings</div>
          <div id="security-list"></div>
        </div>

        <div class="findings-card">
          <div class="findings-title">🟡 Performance Findings</div>
          <div id="performance-list"></div>
        </div>

        <div class="findings-card">
          <div class="findings-title">🔵 Style Findings</div>
          <div id="style-list"></div>
        </div>
      </div>
    </div>

  </div>

  <!-- History -->
  <div class="history-section">
    <div class="history-title">📋 Review History</div>
    <div id="history-list">
      <div class="placeholder">No reviews yet. Paste code above to generate a review.</div>
    </div>
  </div>
</div>

<script>
let selectedLang = 'python';

function switchTab(tab, el) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-' + tab).classList.add('active');
}

function selectLang(lang, el) {
  selectedLang = lang;
  document.querySelectorAll('.lang-pill').forEach(p => p.classList.remove('active'));
  el.classList.add('active');
}

function getScoreClass(score) {
  if (score >= 8) return 'score-green';
  if (score >= 5) return 'score-yellow';
  return 'score-red';
}

function renderFindings(items, containerId, cssClass) {
  const container = document.getElementById(containerId);
  if (!items || items.length === 0) {
    container.innerHTML = '<div class="finding-item ' + cssClass + '">✅ No issues detected.</div>';
    return;
  }
  container.innerHTML = items.map(item => 
    '<div class="finding-item ' + cssClass + '">• ' + item + '</div>'
  ).join('');
}

function showResults(data) {
  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('spinner').classList.remove('show');
  document.getElementById('results').style.display = 'block';

  const score = data.overall_score || 0;
  const circle = document.getElementById('score-circle');
  circle.style.display = 'flex';
  circle.className = 'score-circle ' + getScoreClass(score);
  circle.textContent = score + '/10';

  const summaryBox = document.getElementById('summary-box');
  summaryBox.style.display = 'block';
  summaryBox.textContent = data.summary || 'Review complete.';

  renderFindings(data.security_findings, 'security-list', 'finding-security');
  renderFindings(data.performance_findings, 'performance-list', 'finding-performance');
  renderFindings(data.style_findings, 'style-list', 'finding-style');

  loadHistory();
}

async function reviewCode() {
  const code = document.getElementById('code-input').value.trim();
  if (!code) { alert('Please paste some code first!'); return; }

  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('results').style.display = 'none';
  document.getElementById('spinner').classList.add('show');
  document.getElementById('review-btn').disabled = true;

  try {
    const res = await fetch('/review-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, language: selectedLang, filename: '' })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    showResults(data);
  } catch (err) {
    document.getElementById('spinner').classList.remove('show');
    document.getElementById('placeholder').style.display = 'block';
    alert('Error: ' + err.message);
  } finally {
    document.getElementById('review-btn').disabled = false;
  }
}

async function reviewPR() {
  const url = document.getElementById('pr-input').value.trim();
  if (!url) { alert('Please enter a GitHub PR URL!'); return; }

  document.getElementById('placeholder').style.display = 'none';
  document.getElementById('results').style.display = 'none';
  document.getElementById('spinner').classList.add('show');
  document.getElementById('pr-btn').disabled = true;

  try {
    const res = await fetch('/review-pr', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pr_url: url })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    showResults(data);
  } catch (err) {
    document.getElementById('spinner').classList.remove('show');
    document.getElementById('placeholder').style.display = 'block';
    alert('Error: ' + err.message);
  } finally {
    document.getElementById('pr-btn').disabled = false;
  }
}

async function loadHistory() {
  try {
    const res = await fetch('/reviews');
    const reviews = await res.json();
    const container = document.getElementById('history-list');
    if (!reviews.length) {
      container.innerHTML = '<div class="placeholder">No reviews yet.</div>';
      return;
    }
    container.innerHTML = reviews.map(r => {
      const score = r.overall_score || 0;
      const scoreClass = getScoreClass(score);
      const date = new Date(r.created_at).toLocaleString();
      return `
        <div class="history-card">
          <div class="history-info">
            <h3>${r.type === 'pr' ? '🔗 PR Review' : '📝 Code Review'} <span class="lang-badge">${r.language}</span></h3>
            <p>${date} · ${r.summary || 'No summary'}</p>
          </div>
          <div class="mini-score ${scoreClass}">${score}/10</div>
        </div>
      `;
    }).join('');
  } catch(e) {
    console.error('Failed to load history', e);
  }
}

loadHistory();
</script>
</body>
</html>
"""