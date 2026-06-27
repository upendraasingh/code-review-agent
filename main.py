import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.db import create_review, get_all_reviews
from app.models import GitHubPRURLRequest, GitHubWebhookPayload
from app.services.github import fetch_github_pr_details, parse_github_pr_url
from app.tasks import process_pull_request_review

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

    payload_data = {
        "review_id": review_id,
        "repo_name": repo_name,
        "pull_request_number": pr_number,
        "title": pr_details["title"],
        "body": pr_details["body"],
        "diff": pr_details["diff"],
    }
    process_pull_request_review.delay(payload_data)
    return {"review_id": review_id, "status": "queued"}


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

    payload_data = {
        "review_id": review_id,
        "repo_name": repo_name,
        "pull_request_number": pr.get("number"),
        "title": pr.get("title", ""),
        "body": pr.get("body", ""),
        "diff": diff,
    }
    process_pull_request_review.delay(payload_data)
    return {"review_id": review_id, "status": "queued"}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    reviews = get_all_reviews()
    rows = []
    for review in reviews:
        rows.append(
            f"""
            <div style='border:1px solid #ddd;padding:16px;margin-bottom:16px;'>
                <h2><a href='{review['pr_url']}' target='_blank'>{review['repo_name']} PR #{review['pr_number']}</a></h2>
                <p><strong>Source:</strong> {review['source']} | <strong>Status:</strong> {review['status']} | <strong>Updated:</strong> {review['updated_at']}</p>
                <p><strong>Title:</strong> {review['title']}</p>
                <details>
                    <summary>Full Review Report</summary>
                    <pre style='white-space:pre-wrap;'>{review['summary_comment']}</pre>
                </details>
            </div>
            """
        )

    return f"""
    <html>
        <head>
            <title>Code Review Agent Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ margin-bottom: 16px; }}
                a {{ color: #0366d6; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <h1>Code Review Agent Dashboard</h1>
            <p>Manual review endpoint: <code>POST /review-pr</code></p>
            {''.join(rows) if rows else '<p>No reviews yet.</p>'}
        </body>
    </html>
    """
