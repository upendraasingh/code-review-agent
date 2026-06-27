# Code Review Agent

AI-powered GitHub pull request review service built with FastAPI.

## Start

1. Create a virtual environment
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run Redis locally:

```bash
redis-server
```

4. Start Celery:

```bash
celery -A celery_app.celery worker --loglevel=info
```

5. Run the app:

```bash
uvicorn main:app --reload
```

## Webhook Receiver

Configure GitHub to send pull request webhooks to `POST /webhook`.

- The app uses `diff_url` from the `pull_request` payload.
- Optionally set `GITHUB_TOKEN` in the environment for private repos and GitHub API access.

Example payload fields used:
- `action`
- `repository.full_name`
- `pull_request.number`
- `pull_request.title`
- `pull_request.body`
- `pull_request.diff_url`

The webhook endpoint enqueues a Celery task to analyze the diff with Security, Performance, and Style agents, and then generates a summarized PR comment.

## Manual Review Endpoint

Use `POST /review-pr` to manually trigger AI review for a GitHub pull request URL.

Request body:

```json
{
  "pr_url": "https://github.com/owner/repo/pull/123"
}
```

This will fetch PR metadata and diff from GitHub, store a pending review in SQLite, and queue the async analysis.

## Dashboard

Open `GET /` in your browser to see:

- List of all PRs reviewed
- Review status (`pending` / `complete`)
- Full AI review report for each PR

## Environment

Set the OpenAI key with:

```bash
export OPENAI_API_KEY="your_api_key"
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY = "your_api_key"
```

Optionally set `GITHUB_TOKEN` for private repository access:

```bash
export GITHUB_TOKEN="your_github_token"
```

## Start

1. Create a virtual environment
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run Redis locally:

```bash
redis-server
```

4. Start Celery:

```bash
celery -A celery_app.celery worker --loglevel=info
```

5. Run the app:

```bash
uvicorn main:app --reload
```

## Endpoint

POST `/review-pr`

Request body:

```json
{
  "repo_name": "owner/repo",
  "pull_request_number": 123,
  "title": "Add new authentication flow",
  "body": "This PR adds support for OAuth2 login.",
  "diff": "..."
}
```

The service returns a structured review summary, issues, and recommendations.
