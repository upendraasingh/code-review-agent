from typing import List
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.chains import LLMChain


def _build_llm_chain(system_prompt: str, human_prompt: str) -> LLMChain:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(human_prompt),
    ])
    return LLMChain(llm=ChatOpenAI(temperature=0.2), prompt=prompt)


def analyze_security(diff: str) -> List[str]:
    chain = _build_llm_chain(
        system_prompt="You are a security review expert. Analyze pull request diffs for vulnerabilities.",
        human_prompt="Analyze the following PR diff and list any security findings in bullet form:\n\n{diff}",
    )
    response = chain.predict(diff=diff)
    return [line.strip("- ") for line in response.splitlines() if line.strip()]


def analyze_performance(diff: str) -> List[str]:
    chain = _build_llm_chain(
        system_prompt="You are a performance optimization specialist. Identify performance issues in the code changes.",
        human_prompt="Analyze the following PR diff and list performance findings in bullet form:\n\n{diff}",
    )
    response = chain.predict(diff=diff)
    return [line.strip("- ") for line in response.splitlines() if line.strip()]


def analyze_style(diff: str) -> List[str]:
    chain = _build_llm_chain(
        system_prompt="You are a code style and maintainability expert. Review the PR diff for style problems.",
        human_prompt="Analyze the following PR diff and list style or readability findings in bullet form:\n\n{diff}",
    )
    response = chain.predict(diff=diff)
    return [line.strip("- ") for line in response.splitlines() if line.strip()]


def summarize_findings(security_findings: List[str], performance_findings: List[str], style_findings: List[str], title: str, repo_name: str, pr_number: int) -> str:
    chain = _build_llm_chain(
        system_prompt="You are a summarizer for GitHub pull request reviews. Combine findings into a concise PR comment.",
        human_prompt=(
            "Create one GitHub PR comment summary from these findings:\n\n"
            "Security Findings:\n{security}\n\n"
            "Performance Findings:\n{performance}\n\n"
            "Style Findings:\n{style}\n\n"
            "PR title: {title}\n"
            "Repository: {repo_name}\n"
            "PR number: {pr_number}\n"
        ),
    )
    response = chain.predict(
        security="\n".join(security_findings) or "No security issues found.",
        performance="\n".join(performance_findings) or "No performance issues found.",
        style="\n".join(style_findings) or "No style issues found.",
        title=title,
        repo_name=repo_name,
        pr_number=str(pr_number),
    )
    return response.strip()
