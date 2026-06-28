import os
from typing import List
from langchain_groq import ChatGroq
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)


def analyze_style(diff: str) -> List[str]:
    system_prompt = "You are a code style and maintainability expert."
    human_prompt = (
        "Review the following PR diff for code style issues. Detect bad naming conventions, missing docstrings, "
        "and code duplication. Return each finding as a bullet point.\n\n{diff}"
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(human_prompt),
    ])

    llm = ChatGroq(model="llama-3.1-8b-instant", api_key=os.environ.get("GROQ_API_KEY"))
    chain = prompt | llm

    response = chain.invoke({"diff": diff})

    if isinstance(response, (list, tuple)):
        response_text = "\n".join(map(str, response))
    else:
        response_text = str(response)

    return [line.strip("- ") for line in response_text.splitlines() if line.strip()]
