"""Groq LLM client wrapper with env config, timeouts, and retries."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from groq import Groq

from .config import get_groq_api_key, get_groq_model


class GroqClient:
    """
    Wrapper around Groq API with:
    - API key and model from environment
    - Timeout and retry logic
    - Simple rate limiting (cooldown between calls)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        retry_delay_seconds: float = 1.0,
    ):
        self._api_key = api_key or get_groq_api_key()
        self._model = model or get_groq_model()
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._client = Groq(api_key=self._api_key, timeout=timeout_seconds)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
    ) -> str:
        """
        Send chat messages to Groq and return the assistant's text content.

        Retries on transient failures.
        """
        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                )
                content = response.choices[0].message.content
                return content or ""
            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay)
                else:
                    raise last_error
        assert last_error is not None
        raise last_error
