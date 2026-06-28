from agents.security_agent import analyze_security
from agents.performance_agent import analyze_performance
from agents.style_agent import analyze_style
from agents.summarizer_agent import summarize_findings


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
