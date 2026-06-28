import os
from dotenv import load_dotenv
load_dotenv()

import html
import httpx

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.db import create_review, get_all_reviews, update_review_results
from app.models import CodeReviewRequest, GitHubPRURLRequest, GitHubWebhookPayload
from app.services.github import fetch_github_pr_details, parse_github_pr_url
from app.tasks import run_code_review

app = FastAPI(
    title="Code Review Agent",
    description="AI-powered GitHub pull request review service built with FastAPI.",
    version="0.1.0",
)


@app.post("/review-pr")
async def review_pr(request: GitHubPRURLRequest):
    try:
        repo_name, pr_number = parse_github_pr_url(request.pr_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        pr_details = await fetch_github_pr_details(repo_name, pr_number)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to fetch PR details: {exc}")

    review_id = create_review(
        source="manual",
        repo_name=repo_name,
        pr_number=pr_number,
        title=pr_details["title"],
        body=pr_details["body"],
        diff=pr_details["diff"],
        pr_url=request.pr_url,
    )

    security_findings, performance_findings, style_findings, summary_comment, overall_score = run_code_review(
        pr_details["diff"], pr_details["title"], repo_name, pr_number
    )
    update_review_results(
        review_id=review_id,
        security_findings=security_findings,
        performance_findings=performance_findings,
        style_findings=style_findings,
        summary_comment=summary_comment,
        overall_score=overall_score,
    )

    return {
        "review_id": review_id,
        "status": "complete",
        "security_findings": security_findings,
        "performance_findings": performance_findings,
        "style_findings": style_findings,
        "summary_comment": summary_comment,
        "overall_score": overall_score,
    }


@app.post("/review-code")
async def review_code(request: CodeReviewRequest):
    try:
        import os
        groq_key = os.environ.get("GROQ_API_KEY")
        if not groq_key:
            return {"error": "GROQ_API_KEY not set", "status": 500}

        if not request.code.strip():
            return {"error": "Code cannot be empty.", "status": 400}

        title = request.filename or f"Code Review ({request.language})"
        repo_name = "local-code"
        pr_number = 0
        diff_text = request.code

        review_id = create_review(
            source="code",
            repo_name=repo_name,
            pr_number=pr_number,
            title=title,
            body=f"Language: {request.language}",
            diff=diff_text,
            pr_url="",
            status="complete",
            language=request.language,
            filename=request.filename,
            code_text=request.code,
        )

        security_findings, performance_findings, style_findings, summary_comment, overall_score = run_code_review(
            diff_text, title, repo_name, pr_number
        )
        update_review_results(
            review_id=review_id,
            security_findings=security_findings,
            performance_findings=performance_findings,
            style_findings=style_findings,
            summary_comment=summary_comment,
            overall_score=overall_score,
        )

        def normalize_findings(findings):
            if findings is None:
                return ""
            if isinstance(findings, (list, tuple)):
                return "\n".join(str(item) for item in findings if item is not None)
            return str(findings)

        return {
            "overall_score": overall_score,
            "summary": summary_comment or "Code review completed",
            "security_findings": normalize_findings(security_findings),
            "performance_findings": normalize_findings(performance_findings),
            "style_findings": normalize_findings(style_findings),
            "status": "complete",
        }
    except Exception as e:
        return {"error": str(e), "detail": type(e).__name__, "status": 500}


@app.post("/webhook")
async def github_webhook(request: Request):
    try:
        payload = await request.json()
        webhook = GitHubWebhookPayload(**payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}")

    if webhook.action not in {"opened", "edited", "reopened", "synchronize"}:
        return JSONResponse(status_code=202, content={"detail": "Event ignored."})

    pr = webhook.pull_request
    repo_name = webhook.repository.get("full_name") or ""
    diff_url = pr.get("diff_url")
    if not diff_url:
        raise HTTPException(status_code=400, detail="Missing diff_url in webhook payload.")

    headers = {"Accept": "application/vnd.github.v3.diff"}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(diff_url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Unable to fetch PR diff from GitHub: {response.status_code}",
            )
        diff = response.text

    pr_url = pr.get("html_url") or f"https://github.com/{repo_name}/pull/{pr.get('number')}"
    review_id = create_review(
        source="webhook",
        repo_name=repo_name,
        pr_number=pr.get("number"),
        title=pr.get("title", ""),
        body=pr.get("body", ""),
        diff=diff,
        pr_url=pr_url,
    )

    security_findings, performance_findings, style_findings, summary_comment, overall_score = run_code_review(
        diff, pr.get("title", ""), repo_name, pr.get("number")
    )
    update_review_results(
        review_id=review_id,
        security_findings=security_findings,
        performance_findings=performance_findings,
        style_findings=style_findings,
        summary_comment=summary_comment,
        overall_score=overall_score,
    )

    return {
        "review_id": review_id,
        "status": "complete",
        "security_findings": security_findings,
        "performance_findings": performance_findings,
        "style_findings": style_findings,
        "summary_comment": summary_comment,
        "overall_score": overall_score,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    reviews = get_all_reviews()
    rows = []
    for review in reviews:
        score = review.get('overall_score') or 0
        score_class = 'history-score score-green' if score >= 8 else 'history-score score-yellow' if score >= 5 else 'history-score score-red'
        rows.append(
            f"""
            <div class="history-card">
                <div class="history-card-top">
                    <div>
                        <div class="history-meta">{html.escape(review['source'])} · {html.escape(review['status'])} · {html.escape(review['updated_at'])}</div>
                        <h3>{html.escape(review['repo_name'])} PR #{html.escape(str(review['pr_number']))}</h3>
                        <div class="history-badge">{html.escape(review.get('language') or 'Code')}</div>
                    </div>
                    <div class="{score_class}">{html.escape(str(score))}/10</div>
                </div>
                <details class="history-details">
                    <summary>View full results</summary>
                    <div class="history-markdown">{html.escape(review.get('summary_comment') or '')}</div>
                </details>
            </div>
            """
        )

    history_html = ''.join(rows) if rows else '<div class="history-empty-card"><p>No reviews yet. Paste code above to generate a review.</p></div>'

    return """
    <html>
        <head>
            <title>AI Code Review Agent</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
            <style>
                :root {
                    color-scheme: dark;
                    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    background: #0d1117;
                    color: #c9d1d9;
                }
                * { box-sizing: border-box; }
                body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top left, rgba(56, 139, 253, 0.12), transparent 20%), #0d1117; }
                .page-wrap { max-width: 1260px; margin: 0 auto; padding: 32px 28px 40px; }
                .brand-row { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 28px; }
                .brand-row h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.2rem); letter-spacing: -0.05em; color: #ffffff; }
                .brand-subtitle { max-width: 760px; line-height: 1.7; color: #8b949e; margin-top: 12px; }
                .hero-tag { display: inline-flex; gap: 8px; align-items: center; padding: 12px 18px; border-radius: 999px; border: 1px solid rgba(88, 166, 255, 0.22); background: rgba(56, 139, 253, 0.12); color: #58a6ff; font-weight: 700; }
                .layout-grid { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 24px; align-items: start; }
                .panel { background: rgba(14, 21, 33, 0.98); border: 1px solid rgba(110, 118, 129, 0.22); border-radius: 28px; box-shadow: 0 24px 70px rgba(0,0,0,0.35); padding: 28px; }
                .panel h2 { margin-top: 0; margin-bottom: 18px; font-size: 1.55rem; color: #f0f6fc; }
                .label { display: block; margin-bottom: 10px; font-size: 0.95rem; font-weight: 600; color: #8b949e; }
                .code-input { width: 100%; min-height: 520px; border-radius: 24px; border: 1px solid rgba(110, 118, 129, 0.24); background: #010409; color: #c9d1d9; padding: 20px; font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 0.98rem; line-height: 1.6; resize: vertical; }
                .code-input::placeholder { color: rgba(203, 213, 225, 0.5); }
                .pill-row { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
                .pill { padding: 12px 18px; border-radius: 999px; background: rgba(110, 118, 129, 0.16); border: 1px solid rgba(110, 118, 129, 0.22); color: #c9d1d9; cursor: pointer; transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease; }
                .pill.active, .pill:hover { background: rgba(56, 139, 253, 0.18); border-color: rgba(88, 166, 255, 0.30); color: #ffffff; transform: translateY(-1px); }
                .pill input { display: none; }
                .details-row { display: grid; gap: 18px; margin-top: 22px; }
                .button-primary { width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: 12px; padding: 18px 24px; border-radius: 18px; border: none; background: linear-gradient(135deg, #58a6ff, #1f6feb); color: #fff; font-size: 1rem; font-weight: 700; cursor: pointer; transition: transform 0.18s ease, box-shadow 0.18s ease; }
                .button-primary:hover { transform: translateY(-1px); box-shadow: 0 18px 30px rgba(56, 139, 253, 0.30); }
                .button-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
                .button-spinner { width: 18px; height: 18px; border: 3px solid rgba(255,255,255,0.35); border-top-color: #ffffff; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block; }
                .text-input { width: 100%; border-radius: 20px; border: 1px solid rgba(110, 118, 129, 0.24); background: #010409; color: #c9d1d9; padding: 16px 18px; font-size: 0.98rem; }
                .text-input::placeholder { color: rgba(203, 213, 225, 0.5); }
                .tabs { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
                .tab-button { padding: 14px 22px; border-radius: 16px; border: 1px solid rgba(110, 118, 129, 0.25); background: rgba(15, 23, 42, 0.95); color: #c9d1d9; font-weight: 700; cursor: pointer; transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease; }
                .tab-button.active { background: linear-gradient(135deg, rgba(56, 139, 253, 0.16), rgba(56, 139, 253, 0.08)); border-color: rgba(88, 166, 255, 0.35); color: #ffffff; transform: translateY(-1px); }
                .tab-button:hover { background: rgba(56, 139, 253, 0.12); }
                .tab-panel { margin-top: 12px; }
                .button-spinner { width: 18px; height: 18px; border: 3px solid rgba(255,255,255,0.35); border-top-color: #ffffff; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block; }
                .score-circle { display: inline-flex; align-items: center; justify-content: center; width: 120px; height: 120px; border-radius: 50%; font-size: 2rem; font-weight: 800; color: #ffffff; margin-bottom: 18px; }
                .score-green { background: linear-gradient(180deg, #1f6feb 0%, #0c5dc0 100%); }
                .score-yellow { background: linear-gradient(180deg, #f5b301 0%, #d28700 100%); }
                .score-red { background: linear-gradient(180deg, #ef4444 0%, #b91c1c 100%); }
                .summary-card { border-radius: 24px; padding: 24px; background: rgba(10, 16, 28, 0.96); border: 1px solid rgba(110, 118, 129, 0.22); }
                .summary-card p { margin: 0; color: #c9d1d9; line-height: 1.75; }
                .result-grid { display: grid; gap: 18px; margin-top: 24px; }
                .result-panel { padding: 22px; border-radius: 24px; border: 1px solid rgba(110, 118, 129, 0.22); background: rgba(18, 26, 42, 0.95); }
                .result-panel h3 { margin-top: 0; margin-bottom: 14px; font-size: 1.05rem; }
                .result-panel.red { border-color: rgba(248, 113, 113, 0.24); }
                .result-panel.yellow { border-color: rgba(245, 158, 11, 0.24); }
                .result-panel.blue { border-color: rgba(56, 139, 253, 0.24); }
                .result-list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
                .result-item { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 18px; background: rgba(10, 16, 28, 0.9); color: #c9d1d9; border: 1px solid rgba(110, 118, 129, 0.12); }
                .result-item span { font-size: 1.05rem; margin-top: 2px; }
                .result-item p { margin: 0; line-height: 1.65; }
                .history-list { display: grid; gap: 18px; margin-top: 28px; }
                .history-card { border-radius: 24px; padding: 22px; background: rgba(8, 12, 20, 0.96); border: 1px solid rgba(110, 118, 129, 0.22); }
                .history-card-top { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 18px; align-items: center; }
                .history-meta { color: #8b949e; font-size: 0.95rem; margin-bottom: 10px; }
                .history-card h3 { margin: 0; color: #ffffff; }
                .history-badge { display: inline-flex; align-items: center; padding: 8px 14px; border-radius: 999px; background: rgba(56, 139, 253, 0.14); color: #58a6ff; font-size: 0.9rem; font-weight: 700; }
                .history-score { display: inline-flex; align-items: center; justify-content: center; width: 88px; height: 88px; border-radius: 50%; font-weight: 800; color: #ffffff; }
                .history-score.score-green { background: #1f6feb; }
                .history-score.score-yellow { background: #d28700; }
                .history-score.score-red { background: #ef4444; }
                .history-details { margin-top: 18px; }
                .history-details summary { cursor: pointer; color: #58a6ff; font-weight: 600; }
                .history-markdown { margin-top: 18px; color: #c9d1d9; line-height: 1.75; }
                .history-markdown p { margin: 0.9rem 0; }
                .history-empty-card { border-radius: 24px; padding: 26px; background: rgba(14, 21, 33, 0.95); color: #8b949e; border: 1px dashed rgba(110, 118, 129, 0.18); }
                .note { color: #8b949e; font-size: 0.95rem; line-height: 1.7; margin-top: 8px; }
                .hidden { display: none !important; }
                @keyframes spin { to { transform: rotate(360deg); } }
                @media (max-width: 980px) { .layout-grid { grid-template-columns: 1fr; } }
            </style>
        </head>
        <body>
            <div class="page-wrap">
                <div class="brand-row">
                    <div>
                        <div class="hero-tag">🤖 AI Code Review Agent</div>
                        <h1>Instant, smart, and demo-ready code reviews</h1>
                        <p class="brand-subtitle">Paste raw code, get security, performance, and style feedback instantly with a polished UI built for hiring demos.</p>
                    </div>
                </div>
                <div class="layout-grid">
                    <section class="panel">
                        <div class="tabs" role="tablist">
                            <button type="button" class="tab-button active" data-tab="code" id="tabCode">📝 Review Code</button>
                            <button type="button" class="tab-button" data-tab="pr" id="tabPr">🔗 Review GitHub PR</button>
                        </div>
                        <div class="tab-panel" id="codeReviewTab">
                            <h2>Review your code</h2>
                            <div class="label">Language</div>
                            <div class="pill-row" id="languagePills">
                                <button type="button" class="pill active" data-lang="python">Python</button>
                                <button type="button" class="pill" data-lang="php">PHP</button>
                                <button type="button" class="pill" data-lang="javascript">JavaScript</button>
                                <button type="button" class="pill" data-lang="ruby">Ruby</button>
                                <button type="button" class="pill" data-lang="sql">SQL</button>
                            </div>
                            <input type="hidden" id="languageInput" name="language" value="python" />
                            <label class="label" for="codeInput">Paste your code</label>
                            <textarea id="codeInput" class="code-input" placeholder="Paste code here..."></textarea>
                            <label class="label" for="filenameInput">Filename (optional)</label>
                            <input id="filenameInput" type="text" class="text-input" placeholder="example.py" />
                            <div class="details-row">
                                <button type="button" class="button-primary" id="reviewBtn">Review My Code</button>
                            </div>
                        </div>
                        <div class="tab-panel hidden" id="prReviewTab">
                            <h2>Review a GitHub PR</h2>
                            <div class="label">GitHub PR URL</div>
                            <input id="prUrlInput" class="text-input" type="url" placeholder="https://github.com/username/repo/pull/1" />
                            <p class="note">Paste any public GitHub PR URL to get an AI review.</p>
                            <div class="details-row">
                                <button type="button" class="button-primary" id="reviewPrBtn">Review PR</button>
                            </div>
                        </div>
                    </section>
                    <section class="panel hidden" id="reviewResultPanel">
                        <div class="summary-card">
                            <div class="score-circle score-green" id="overallScore">0/10</div>
                            <div id="reviewSummary">Your review summary will appear here once you submit code.</div>
                        </div>
                        <div class="result-grid">
                            <div class="result-panel red">
                                <h3>🔴 Security Findings</h3>
                                <ul class="result-list" id="securityIssues"></ul>
                            </div>
                            <div class="result-panel yellow">
                                <h3>🟡 Performance Findings</h3>
                                <ul class="result-list" id="performanceIssues"></ul>
                            </div>
                            <div class="result-panel blue">
                                <h3>🔵 Style Findings</h3>
                                <ul class="result-list" id="styleIssues"></ul>
                            </div>
                        </div>
                    </section>
                </div>
                <section class="history-list">
                    """ + history_html + """
                </section>
            </div>
            <script>
                const languagePills = document.querySelectorAll('.pill');
                const languageInput = document.getElementById('languageInput');
                const reviewBtn = document.getElementById('reviewBtn');
                const reviewPrBtn = document.getElementById('reviewPrBtn');
                const resultPanel = document.getElementById('reviewResultPanel');
                const overallScore = document.getElementById('overallScore');
                const reviewSummary = document.getElementById('reviewSummary');
                const securityIssues = document.getElementById('securityIssues');
                const performanceIssues = document.getElementById('performanceIssues');
                const styleIssues = document.getElementById('styleIssues');
                const codeInput = document.getElementById('codeInput');
                const filenameInput = document.getElementById('filenameInput');
                const prUrlInput = document.getElementById('prUrlInput');
                const tabButtons = document.querySelectorAll('.tab-button');
                const codeReviewTab = document.getElementById('codeReviewTab');
                const prReviewTab = document.getElementById('prReviewTab');

                const getScoreClass = (score) => {
                    if (score >= 8) return 'score-circle score-green';
                    if (score >= 5) return 'score-circle score-yellow';
                    return 'score-circle score-red';
                };

                const renderMarkdown = (content) => {
                    if (!content) return '<p class="note">No summary available.</p>';
                    return marked.parse(content || '');
                };

                const parseSection = (text, section) => {
                    const pattern = new RegExp(section + ' Findings:\\s*([\\s\\S]*?)(?=\\n[A-Z][a-z]+ Findings:|$)', 'i');
                    const match = text.match(pattern);
                    if (!match) return [];
                    const sectionText = match[1].trim();
                    const lines = sectionText.split(/\\r?\\n/).map((line) => line.trim()).filter(Boolean);
                    const bullets = lines.filter((line) => /^[-*+]\\s+/.test(line)).map((line) => line.replace(/^[-*+]\\s+/, ''));
                    return bullets.length ? bullets : lines;
                };

                const renderList = (container, items, icon) => {
                    if (!items || !items.length) {
                        container.innerHTML = '<li class="result-item"><span>' + icon + '</span><p>No issues detected.</p></li>';
                        return;
                    }
                    container.innerHTML = items.map(item => `\n                        <li class="result-item"><span>${icon}</span><p>${item}</p></li>\n                    `).join('');
                };

                const selectLanguage = (lang) => {
                    languagePills.forEach((pill) => {
                        pill.classList.toggle('active', pill.dataset.lang === lang);
                    });
                    languageInput.value = lang;
                };

                languagePills.forEach((pill) => {
                    pill.addEventListener('click', () => selectLanguage(pill.dataset.lang));
                });

                tabButtons.forEach((button) => {
                    button.addEventListener('click', () => {
                        tabButtons.forEach((btn) => btn.classList.toggle('active', btn === button));
                        const activeTab = button.dataset.tab;
                        codeReviewTab.classList.toggle('hidden', activeTab !== 'code');
                        prReviewTab.classList.toggle('hidden', activeTab !== 'pr');
                    });
                });

                const hydrateHistory = () => {
                    document.querySelectorAll('.history-markdown').forEach((container) => {
                        container.innerHTML = marked.parse(container.textContent || '');
                    });
                };

                document.addEventListener('DOMContentLoaded', hydrateHistory);

                const setLoading = (isLoading, button) => {
                    button.disabled = isLoading;
                    button.innerHTML = isLoading ? '<span class="button-spinner"></span> Reviewing...' : button.dataset.defaultLabel;
                };

                reviewBtn.dataset.defaultLabel = 'Review My Code';
                reviewPrBtn.dataset.defaultLabel = 'Review PR';

                const handleReviewResponse = async (response) => {
                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.detail || 'Unable to review request.');
                    }
                    return data;
                };

                const parseFindings = (findings) => {
                    if (!findings) return [];
                    if (Array.isArray(findings)) return findings.filter(Boolean);
                    return findings
                        .split(/\r?\n/)
                        .map((line) => line.trim())
                        .filter(Boolean);
                };

                const showReviewResults = (data) => {
                    console.log(data);
                    const score = data.overall_score ?? data.score ?? 0;
                    const cleanText = data.summary || data.summary_comment || '';
                    const securityItems = parseFindings(data.security_findings);
                    const performanceItems = parseFindings(data.performance_findings);
                    const styleItems = parseFindings(data.style_findings);

                    resultPanel.classList.remove('hidden');
                    overallScore.textContent = `${score}/10`;
                    overallScore.className = getScoreClass(score);
                    reviewSummary.innerHTML = renderMarkdown(cleanText);
                    renderList(securityIssues, securityItems, '❌');
                    renderList(performanceIssues, performanceItems, '⚡');
                    renderList(styleIssues, styleItems, '💡');
                    resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                };

                reviewBtn.addEventListener('click', async () => {
                    const code = codeInput.value.trim();
                    const language = languageInput.value;
                    const filename = filenameInput.value.trim();
                    if (!code) {
                        codeInput.focus();
                        return;
                    }
                    setLoading(true, reviewBtn);
                    try {
                        const response = await fetch('/review-code', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ code, language, filename }),
                        });
                        const data = await handleReviewResponse(response);
                        showReviewResults(data);
                    } catch (error) {
                        alert(error.message || 'Unable to review code. Please try again.');
                    } finally {
                        setLoading(false, reviewBtn);
                    }
                });

                reviewPrBtn.addEventListener('click', async () => {
                    const prUrl = prUrlInput.value.trim();
                    if (!prUrl) {
                        prUrlInput.focus();
                        return;
                    }
                    setLoading(true, reviewPrBtn);
                    try {
                        const response = await fetch('/review-pr', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ pr_url: prUrl }),
                        });
                        const data = await handleReviewResponse(response);
                        showReviewResults(data);
                    } catch (error) {
                        alert(error.message || 'Unable to review PR. Please try again.');
                    } finally {
                        setLoading(false, reviewPrBtn);
                    }
                });
            </script>
        </body>
    </html>
    """
