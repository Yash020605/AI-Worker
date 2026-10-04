"""
LLM factory — returns the right LangChain chat model based on config.
"""
from __future__ import annotations

from agent.config import config
from agent.logger import logger


def get_llm(temperature: float | None = None, model: str | None = None):
    """Return a configured LangChain LLM instance."""
    temp = temperature if temperature is not None else config.AGENT_TEMPERATURE
    mdl = model or config.LLM_MODEL

    logger.info(f"[LLM] Loading model={mdl} temperature={temp}")

    if mdl.startswith("gpt-") or mdl.startswith("o1") or mdl.startswith("o3"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=mdl,
            temperature=temp,
            api_key=config.OPENAI_API_KEY,
            streaming=False,
        )
    elif mdl.startswith("claude-"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=mdl,
            temperature=temp,
            api_key=config.ANTHROPIC_API_KEY,
        )
    else:
        # Default to OpenAI
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=mdl,
            temperature=temp,
            api_key=config.OPENAI_API_KEY,
        )
