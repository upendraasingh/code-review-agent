from typing import List
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.chains import LLMChain


def _build_llm_chain(system_prompt: str, human_prompt: str) -> LLMChain:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template(human_prompt),
    ])
    return LLMChain(llm=ChatOpenAI(temperature=0.0), prompt=prompt)


def analyze_security(diff: str) -> List[str]:
    chain = _build_llm_chain(
        system_prompt="You are a security analyst focused on code vulnerabilities.",
        human_prompt=(
            "Review the following PR diff for security issues. Detect SQL injection, hardcoded secrets, open ports, "
            "and XSS vulnerabilities. Return each finding as a bullet point.\n\n{diff}"
        ),
    )
    response = chain.predict(diff=diff)
    return [line.strip("- ") for line in response.splitlines() if line.strip()]
