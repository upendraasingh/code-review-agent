from celery import chord, shared_task
from pydantic import BaseModel
from agents.security_agent import analyze_security
from agents.performance_agent import analyze_performance
from agents.style_agent import analyze_style
from agents.summarizer_agent import summarize_findings
from app.db import update_review_results


class PullRequestTaskPayload(BaseModel):
    review_id: int
    repo_name: str
    pull_request_number: int
    title: str
    body: str
    diff: str


@shared_task(name="app.tasks.security_review")
def security_review(diff: str) -> list[str]:
    return analyze_security(diff)


def score_findings(
    security_findings: list[str],
    performance_findings: list[str],
    style_findings: list[str],
) -> int:
    total_issues = (
        len(security_findings)
        + len(performance_findings)
        + len(style_findings)
    )
    return max(0, min(10, 10 - total_issues))


def run_code_review(code: str, title: str, repo_name: str, pr_number: int) -> tuple[list[str], list[str], list[str], str, int]:
    security_findings = analyze_security(code)
    performance_findings = analyze_performance(code)
    style_findings = analyze_style(code)
    summary_comment = summarize_findings(
        security_findings=security_findings,
        performance_findings=performance_findings,
        style_findings=style_findings,
        title=title,
        repo_name=repo_name,
        pr_number=pr_number,
    )
    overall_score = score_findings(security_findings, performance_findings, style_findings)
    return security_findings, performance_findings, style_findings, summary_comment, overall_score


@shared_task(name="app.tasks.performance_review")
def performance_review(diff: str) -> list[str]:
    return analyze_performance(diff)


@shared_task(name="app.tasks.style_review")
def style_review(diff: str) -> list[str]:
    return analyze_style(diff)


@shared_task(name="app.tasks.summarize_and_update_review")
def summarize_and_update_review(results: list, review_id: int, title: str, repo_name: str, pr_number: int) -> dict:
    security_findings, performance_findings, style_findings = results
    summary_comment = summarize_findings(
        security_findings=security_findings,
        performance_findings=performance_findings,
        style_findings=style_findings,
        title=title,
        repo_name=repo_name,
        pr_number=pr_number,
    )
    overall_score = score_findings(security_findings, performance_findings, style_findings)
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
        "summary_comment": summary_comment,
        "overall_score": overall_score,
    }


@shared_task(name="app.tasks.process_pull_request_review")
def process_pull_request_review(payload: dict) -> dict:
    request = PullRequestTaskPayload(**payload)
    chord(
        [
            security_review.s(request.diff),
            performance_review.s(request.diff),
            style_review.s(request.diff),
        ],
        summarize_and_update_review.s(
            request.review_id,
            request.title,
            request.repo_name,
            request.pull_request_number,
        ),
    )()

    return {
        "review_id": request.review_id,
        "status": "queued",
    }
