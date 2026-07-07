"""Answer generation behind the core Generator port (shell).

Provider-agnostic: `make_generator` picks an implementation from settings so
swapping Ollama for an API is a config change. Ollama is the local default,
matching the no-paid-API constraint. Generators stream text deltas so the API
can forward them over SSE as they arrive.
"""

from __future__ import annotations

from collections.abc import Iterator

from mdhpp_core import Generator, Settings


class OllamaGenerator:
    """Streams from a local Ollama server. Satisfies mdhpp_core.ports.Generator."""

    def __init__(self, model: str, temperature: float, host: str) -> None:
        self._model = model
        self._temperature = temperature
        self._host = host.rstrip("/")

    def generate(self, prompt: str) -> Iterator[str]:
        import json
        import urllib.request

        payload = json.dumps(
            {
                "model": self._model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": self._temperature},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self._host}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            for line in resp:
                if not line.strip():
                    continue
                obj = json.loads(line)
                token = obj.get("response", "")
                if token:
                    yield token
                if obj.get("done"):
                    break


def make_generator(settings: Settings, host: str | None = None) -> Generator:
    """Build the configured generator. Currently supports the Ollama provider."""
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaGenerator(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            host=host or settings.llm_host,
        )
    raise ValueError(
        f"Unsupported llm_provider: {settings.llm_provider!r}. "
        "Only 'ollama' is wired up in this phase."
    )
