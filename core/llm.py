from langchain_openai import ChatOpenAI

# from config.settings import (
#     DEFAULT_OPEN_MODEL,
#     MAX_RETRIES,
#     OPENROUTER_API_KEY,
#     OPENROUTER_BASE_URL,
#     REQUEST_TIMEOUT,
# )


# def build_llm_with_tools(tools):
#     llm = ChatOpenAI(
#         model=DEFAULT_OPEN_MODEL,
#         openai_api_key=OPENROUTER_API_KEY,
#         openai_api_base=OPENROUTER_BASE_URL,
#         max_retries=MAX_RETRIES,
#         timeout=REQUEST_TIMEOUT,
#     )
#     return llm.bind_tools(tools)


# def build_llm(MODEL=DEFAULT_OPEN_MODEL):
#     llm = ChatOpenAI(
#         model=MODEL,
#         openai_api_key=OPENROUTER_API_KEY,
#         openai_api_base=OPENROUTER_BASE_URL,
#         max_retries=MAX_RETRIES,
#         timeout=REQUEST_TIMEOUT,
#     )
#     return llm


# Using groq api key

from config.settings import (
    DEFAULT_GROQ_MODEL,
    GROQ_API_KEY,
    MAX_RETRIES,
    GROQ_BASE_URL,
)

REQUEST_TIMEOUT = 3


def build_llm_with_tools(tools):
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set")
    llm = ChatOpenAI(
        model=DEFAULT_GROQ_MODEL,
        openai_api_key=GROQ_API_KEY,
        openai_api_base=GROQ_BASE_URL,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )
    return llm.bind_tools(tools)


def build_llm(MODEL=DEFAULT_GROQ_MODEL):
    llm = ChatOpenAI(
        model=MODEL,
        openai_api_key=GROQ_API_KEY,
        openai_api_base=GROQ_BASE_URL,
        max_retries=MAX_RETRIES,
        timeout=REQUEST_TIMEOUT,
    )
    return llm


# import os
# from typing import List

# from langchain_core.tools import BaseTool

# from config.settings import GROQ_API_KEY

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

#     return llm.bind_tools(tools)


# def build_llm():
#     llm = ChatOpenAI(
#         model=MODEL_NAME,
#         openai_api_key=HF_API_KEY,
#         openai_api_base=HF_BASE_URL,
#         max_retries=3,
#         timeout=60,
#     )
#     return llm
