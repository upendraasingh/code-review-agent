from pydantic import BaseModel


class PullRequestReviewRequest(BaseModel):
    repo_name: str
    pull_request_number: int
    title: str
    body: str
    diff: str


class GitHubPRURLRequest(BaseModel):
    pr_url: str


class GitHubWebhookPayload(BaseModel):
    action: str
    repository: dict
    pull_request: dict
