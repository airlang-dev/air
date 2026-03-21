"""Shared LLM utilities for AIR runtime executors."""

import litellm


def call_llm(model, messages, config=None):
    """Execute an LLM completion and return the response content string."""
    response = litellm.completion(model=model, messages=messages)
    return response.choices[0].message.content
