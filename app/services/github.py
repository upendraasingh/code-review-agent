import os
from typing import Tuple
from urllib.parse import urlparse

import httpx

GITHUB_API_BASE = "https://api.github.com"


def parse_github_pr_url(pr_url: str) -> tuple[str, int]:
    parsed = urlparse(pr_url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError("URL must point to github.com")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 4 or segments[2] != "pull":
        raise ValueError("URL must use the format /owner/repo/pull/<number>")

    repo_name = f"{segments[0]}/{segments[1]}"
    try:
        pr_number = int(segments[3])
    except ValueError as exc:
        raise ValueError("Pull request number must be an integer") from exc

    return repo_name, pr_number


def _build_github_headers(accept: str) -> dict[str, str]:
    headers = {"Accept": accept}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


async def fetch_github_pr_details(repo_name: str, pr_number: int) -> dict:
    headers = _build_github_headers("application/vnd.github.v3+json")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{GITHUB_API_BASE}/repos/{repo_name}/pulls/{pr_number}", headers=headers
        )
        response.raise_for_status()
        pr_data = response.json()

        diff_headers = _build_github_headers("application/vnd.github.v3.diff")
        diff_url = pr_data.get("diff_url")
        if not diff_url:
            raise ValueError("Pull request payload did not include a diff URL.")

        diff_response = await client.get(diff_url, headers=diff_headers)
        diff_response.raise_for_status()
        return {
            "title": pr_data.get("title", ""),
            "body": pr_data.get("body", ""),
            "diff": diff_response.text,
            "html_url": pr_data.get("html_url", ""),
        }
