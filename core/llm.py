from langchain_openai import ChatOpenAI

from config.settings import (
    LLM_PROVIDER,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    DEFAULT_OPEN_MODEL,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    DEFAULT_GROQ_MODEL,
    HF_API_KEY,
    HF_BASE_URL,
    DEFAULT_HF_MODEL,
)


def _get_provider_config(model: str = None):
    """Return (api_key, base_url, model) for the configured LLM_PROVIDER."""
    if LLM_PROVIDER == "groq":
        return GROQ_API_KEY, GROQ_BASE_URL, model or DEFAULT_GROQ_MODEL
    if LLM_PROVIDER == "huggingface":
        return HF_API_KEY, HF_BASE_URL, model or DEFAULT_HF_MODEL
    # default: openrouter
    return OPENROUTER_API_KEY, OPENROUTER_BASE_URL, model or DEFAULT_OPEN_MODEL


def build_llm_with_tools(tools, model: str = None):
    api_key, base_url, resolved_model = _get_provider_config(model)
    llm = ChatOpenAI(
        model=resolved_model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )
    return llm.bind_tools(tools)


def build_llm(model: str = None):
    api_key, base_url, resolved_model = _get_provider_config(model)
    return ChatOpenAI(
        model=resolved_model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )
