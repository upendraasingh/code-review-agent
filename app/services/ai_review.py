from pydantic import BaseModel


class PullRequestReviewRequest(BaseModel):
    repo_name: str
    pull_request_number: int
    title: str
    body: str
    diff: str


async def review_pull_request(request: PullRequestReviewRequest) -> dict:
    """Mock AI review logic.

    Replace this with your AI provider integration.
    """
    review_summary = (
        f"Review for PR #{request.pull_request_number} in {request.repo_name}: "
        "The change introduces scoped improvements and requires follow-up." 
    )

    strengths = [
        "Clear PR title and description.",
        "Diff appears focused on a single feature area.",
    ]
    issues = [
        "There are missing tests for edge cases.",
        "Some variables in the diff could be more descriptive.",
    ]
    recommendations = [
        "Add unit tests for the new login flow.",
        "Use consistent naming for authentication helpers.",
    ]

    return {
        "summary": review_summary,
        "strengths": strengths,
        "issues": issues,
        "recommendations": recommendations,
    }
