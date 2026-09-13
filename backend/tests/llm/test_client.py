"""The real LLM call path.

Never imports `litellm` here — in this dev environment, `litellm` 1.100.1's
bundled Rust extension hard-crashes the Python process on import on Windows
(see the docstring in `app/llm/client.py`). `call_llm` accepts an injectable
`completion_fn` for exactly this reason: every test below passes a fake and
never touches the real `litellm` package, so this file is safe to collect
and run regardless of that environment bug.
"""

from types import SimpleNamespace

import pytest

from app.llm import client
from app.llm.schema import LLMCallError, LLMValidationError


def _fake_completion_returning(content: str):
    def _fake(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return _fake


class TestCallLlm:
    def test_uses_configured_model_and_provider(self):
        captured = {}

        def _fake(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"message": "ok"}'))]
            )

        client.call_llm([{"role": "user", "content": "hi"}], completion_fn=_fake)

        assert captured["model"] == "openrouter/openai/gpt-oss-120b"
        assert captured["extra_body"] == {"provider": {"order": ["cerebras"]}}
        assert captured["reasoning_effort"] == "low"
        assert captured["response_format"] is not None

    def test_valid_response_parsed(self):
        resp = client.call_llm(
            [{"role": "user", "content": "hi"}],
            completion_fn=_fake_completion_returning('{"message": "Hi!"}'),
        )
        assert resp.message == "Hi!"

    def test_malformed_response_raises_validation_error(self):
        with pytest.raises(LLMValidationError):
            client.call_llm(
                [{"role": "user", "content": "hi"}],
                completion_fn=_fake_completion_returning("not json"),
            )

    def test_provider_exception_raises_call_error(self):
        def _raise(**kwargs):
            raise RuntimeError("connection reset")

        with pytest.raises(LLMCallError):
            client.call_llm([{"role": "user", "content": "hi"}], completion_fn=_raise)

    def test_completion_fn_called_exactly_once(self):
        calls = []

        def _fake(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"message": "ok"}'))]
            )

        client.call_llm([{"role": "user", "content": "hi"}], completion_fn=_fake)
        assert len(calls) == 1
