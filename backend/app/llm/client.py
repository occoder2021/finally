"""Real LLM invocation via LiteLLM -> OpenRouter -> Cerebras.

Follows the project `cerebras-inference` skill exactly: model, extra_body and
reasoning_effort are fixed per that contract, not configurable per call.

`litellm` is imported lazily, inside `call_llm`, rather than at module scope.
This is not merely style: in this dev environment, `litellm` 1.100.1 bundles
a Rust extension (`litellm.rust_bridge._native`) that hard-crashes the
Python process on import on Windows (`OPENSSL_Uplink ... no
OPENSSL_Applink` — a native fault, not a catchable Python exception). A
module-level `from litellm import completion` would take down every test
(and the whole app) the instant this module is imported. Keeping the import
inside the function means `litellm` is only ever touched at an actual chat
request, in production, and never during import or in tests — every test
here (and in test_router.py) injects `completion_fn` instead.
"""

from __future__ import annotations

import logging

from .schema import ChatStructuredResponse, LLMCallError, parse_structured_response

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def call_llm(messages: list[dict], *, completion_fn=None) -> ChatStructuredResponse:
    """Call the model with structured-output enforcement and return the
    validated response.

    `completion_fn` defaults to `litellm.completion`, imported lazily on
    first use; tests inject a fake here instead of monkeypatching a
    module-level import (see the docstring above for why).

    Raises `LLMCallError` if the provider call itself fails (network,
    provider error). Raises `LLMValidationError` (via
    `parse_structured_response`) if the content doesn't satisfy the schema.
    """
    if completion_fn is None:
        from litellm import completion as completion_fn  # noqa: PLC0415

    try:
        response = completion_fn(
            model=MODEL,
            messages=messages,
            response_format=ChatStructuredResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
    except Exception as exc:  # noqa: BLE001 - any provider/network failure maps to one error
        logger.exception("LLM call failed")
        raise LLMCallError(f"The AI service call failed: {exc}") from exc

    raw_content = response.choices[0].message.content
    return parse_structured_response(raw_content)
