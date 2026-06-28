from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)


def _run_prompt(system_prompt: str, human_prompt: str, **kwargs) -> str:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(human_prompt),
    ])
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)
    chain = prompt | llm
    try:
        return chain.invoke(kwargs)
    except Exception:
        return chain.run(**kwargs)


def analyze_security(diff: str) -> List[str]:
    system = "You are a security review expert. Analyze pull request diffs for vulnerabilities."
    human = "Analyze the following PR diff and list any security findings in bullet form:\n\n{diff}"
    resp = _run_prompt(system, human, diff=diff)
    if isinstance(resp, (list, tuple)):
        resp_text = "\n".join(map(str, resp))
    else:
        resp_text = str(resp)
    return [line.strip("- ") for line in resp_text.splitlines() if line.strip()]


def analyze_performance(diff: str) -> List[str]:
    system = "You are a performance optimization specialist. Identify performance issues in the code changes."
    human = "Analyze the following PR diff and list performance findings in bullet form:\n\n{diff}"
    resp = _run_prompt(system, human, diff=diff)
    if isinstance(resp, (list, tuple)):
        resp_text = "\n".join(map(str, resp))
    else:
        resp_text = str(resp)
    return [line.strip("- ") for line in resp_text.splitlines() if line.strip()]


def analyze_style(diff: str) -> List[str]:
    system = "You are a code style and maintainability expert. Review the PR diff for style problems."
    human = "Analyze the following PR diff and list style or readability findings in bullet form:\n\n{diff}"
    resp = _run_prompt(system, human, diff=diff)
    if isinstance(resp, (list, tuple)):
        resp_text = "\n".join(map(str, resp))
    else:
        resp_text = str(resp)
    return [line.strip("- ") for line in resp_text.splitlines() if line.strip()]


def summarize_findings(security_findings: List[str], performance_findings: List[str], style_findings: List[str], title: str, repo_name: str, pr_number: int) -> str:
    system = "You are a summarizer for GitHub pull request reviews. Combine findings into a concise PR comment."
    human = (
        "Create one GitHub PR comment summary from these findings:\n\n"
        "Security Findings:\n{security}\n\n"
        "Performance Findings:\n{performance}\n\n"
        "Style Findings:\n{style}\n\n"
        "PR title: {title}\n"
        "Repository: {repo_name}\n"
        "PR number: {pr_number}\n"
    )
    resp = _run_prompt(
        system,
        human,
        security="\n".join(security_findings) or "No security issues found.",
        performance="\n".join(performance_findings) or "No performance issues found.",
        style="\n".join(style_findings) or "No style issues found.",
        title=title,
        repo_name=repo_name,
        pr_number=str(pr_number),
    )
    if isinstance(resp, (list, tuple)):
        return "\n".join(map(str, resp))
    return str(resp)
