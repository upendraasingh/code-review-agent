import os
import re
from typing import Any, List
from langchain_groq import ChatGroq
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)


def _normalize_response_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, dict):
        if "content" in response:
            response = response["content"]
        elif "text" in response:
            response = response["text"]
    if hasattr(response, "content"):
        response = response.content
    if hasattr(response, "text"):
        response = response.text

    text = str(response).strip()

    # Handle representations like content='...', metadata=... or raw escaped newlines
    if text.startswith("content="):
        quote = text[8]
        if quote in "'\"":
            end_index = text.rfind(quote)
            if end_index > 8:
                text = text[9:end_index]
    text = re.sub(r"\\\\n", "\n", text)
    text = re.sub(r"\\\\r\\\\n", "\n", text)
    text = re.sub(r"\\\\t", "\t", text)
    return text.strip()



def summarize_findings(
    security_findings: List[str],
    performance_findings: List[str],
    style_findings: List[str],
    title: str,
    repo_name: str,
    pr_number: int,
) -> str:
    system_prompt = "You are a GitHub PR review summarizer. Create a structured markdown report."
    human_prompt = (
        "Combine these findings into a markdown report with sections for security, performance, and style. "
        "If no findings are present for a section, note that the code appears clean.\n\n"
        "PR Title: {title}\n"
        "Repository: {repo_name}\n"
        "PR Number: {pr_number}\n\n"
        "Security Findings:\n{security}\n\n"
        "Performance Findings:\n{performance}\n\n"
        "Style Findings:\n{style}\n"
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(human_prompt),
    ])

    llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.environ.get("GROQ_API_KEY"))
    chain = prompt | llm

    response = chain.invoke(
        {
            "title": title,
            "repo_name": repo_name,
            "pr_number": str(pr_number),
            "security": "\n".join(security_findings)
            if security_findings
            else "No security issues detected.",
            "performance": "\n".join(performance_findings)
            if performance_findings
            else "No performance issues detected.",
            "style": "\n".join(style_findings) if style_findings else "No style issues detected.",
        }
    )

    response_text = _normalize_response_text(response)
    return response_text
