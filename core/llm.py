from langchain_openai import ChatOpenAI

from config.settings import (
    DEFAULT_MODEL,
    MAX_RETRIES,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    REQUEST_TIMEOUT,
)


def build_llm_with_tools(tools):
    llm = ChatOpenAI(
        model=DEFAULT_MODEL,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base=OPENROUTER_BASE_URL,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )
    return llm.bind_tools(tools)


# import os
# from typing import List

# from langchain_core.tools import BaseTool

# HF_API_KEY = os.environ.get("HF_TOKEN")
# HF_BASE_URL = "https://router.huggingface.co/v1"

# MODEL_NAME = "openai/gpt-oss-20b:groq"


# def build_llm_with_tools(tools: List[BaseTool]):
#     llm = ChatOpenAI(
#         model=MODEL_NAME,
#         openai_api_key=HF_API_KEY,
#         openai_api_base=HF_BASE_URL,
#         max_retries=3,
#         timeout=60,
#     )

#     if not tools:
#         return llm

#     return llm.bind_tools(tools)
