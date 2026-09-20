from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypeVar
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        """Leitor mínimo de .env para o ambiente sem python-dotenv."""
        path = Path(".env")
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[misc,assignment]

T = TypeVar("T", bound=BaseModel)


class LLMProvider:
    """Cliente Neuralake (API compatível com ``openai.OpenAI``)."""

    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("NEURALAKE_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL") or os.getenv("NEURALAKE_BASE_URL")
        self.model = os.getenv("LLM_MODEL") or os.getenv("NEURALAKE_MODEL", "text")
        self.offline = os.getenv("OFFLINE_MODE", "false").lower() == "true"

    def structured(self, system: str, user: str, schema: type[T]) -> T:
        if self.offline:
            raise RuntimeError("LLM está em modo offline")
        if not self.api_key:
            raise RuntimeError("LLM_API_KEY não configurada")
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system}\n"
                    "Retorne somente um objeto JSON válido, sem markdown. "
                    "Use exatamente as chaves do schema abaixo; não crie chaves novas.\n"
                    f"SCHEMA: {json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
                ),
            },
            {"role": "user", "content": user},
        ]
        if OpenAI is not None:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            stream = client.chat.completions.create(
                model=self.model, temperature=0, max_tokens=4096, messages=messages, stream=True
            )
            content = "".join(
                chunk.choices[0].delta.content or ""
                for chunk in stream
                if chunk.choices
            )
        else:
            # Mesma rota OpenAI-compatible e stream=true do exemplo do provedor.
            base = (self.base_url or "").rstrip("/")
            request = Request(
                f"{base}/chat/completions",
                data=json.dumps({"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 4096, "stream": True}).encode(),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "text/event-stream"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=90) as raw:  # nosec B310: URL vem da configuração local
                    pieces: list[str] = []
                    for raw_line in raw:
                        line = raw_line.decode("utf-8").strip()
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        event = json.loads(data)
                        choices = event.get("choices", [])
                        if choices:
                            pieces.append(choices[0].get("delta", {}).get("content") or "")
            except HTTPError as exc:
                raise RuntimeError(f"Provedor LLM respondeu HTTP {exc.code}") from exc
            except URLError as exc:
                raise RuntimeError(f"Não foi possível acessar o provedor LLM: {exc.reason}") from exc
            content = "".join(pieces)
        if not content:
            raise RuntimeError("O provedor retornou stream sem conteúdo")
        # Provedores compatíveis podem incluir texto antes/depois do objeto.
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end < start:
            raise RuntimeError("O provedor não retornou um objeto JSON")
        return schema.model_validate(json.loads(content[start : end + 1]))
