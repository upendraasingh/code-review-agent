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


def summarize_findings(
    security_findings: List[str],
    performance_findings: List[str],
    style_findings: List[str],
    title: str,
    repo_name: str,
    pr_number: int,
) -> str:
    chain = _build_llm_chain(
        system_prompt="You are a GitHub PR review summarizer. Create a structured markdown report.",
        human_prompt=(
            "Combine these findings into a markdown report with sections for security, performance, and style. "
            "If no findings are present for a section, note that the code appears clean.\n\n"
            "PR Title: {title}\n"
            "Repository: {repo_name}\n"
            "PR Number: {pr_number}\n\n"
            "Security Findings:\n{security}\n\n"
            "Performance Findings:\n{performance}\n\n"
            "Style Findings:\n{style}\n"
        ),
    )
    response = chain.predict(
        title=title,
        repo_name=repo_name,
        pr_number=str(pr_number),
        security="\n".join(security_findings) if security_findings else "No security issues detected.",
        performance="\n".join(performance_findings) if performance_findings else "No performance issues detected.",
        style="\n".join(style_findings) if style_findings else "No style issues detected.",
    )
    return response.strip()
