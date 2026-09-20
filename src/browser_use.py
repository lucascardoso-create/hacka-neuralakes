from __future__ import annotations

import hashlib
import json
import os
import re
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .schemas import DownloadedDocument, ResearchPlan


class BrowserUseError(RuntimeError):
    pass


class BrowserUseClient:
    """Cliente REST da Browser Use Cloud API V4, isolado do resto do grafo."""

    base_url = "https://api.browser-use.com/api/v4"
    terminal_statuses = {"completed", "failed", "cancelled"}

    def __init__(self) -> None:
        self.api_key = os.getenv("BROWSER_USE_API_KEY")
        if not self.api_key:
            raise BrowserUseError("BROWSER_USE_API_KEY não configurada")
        try:
            self.max_cost_usd = float(os.getenv("BROWSER_USE_MAX_COST_USD", "0.10"))
        except ValueError as exc:
            raise BrowserUseError("BROWSER_USE_MAX_COST_USD precisa ser numérico") from exc
        if self.max_cost_usd <= 0:
            raise BrowserUseError("BROWSER_USE_MAX_COST_USD precisa ser maior que zero")
        self.last_session_id: str | None = None
        self.last_run_id: str | None = None
        self.last_result: dict | None = None

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "X-Browser-Use-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=90) as response:  # nosec B310: host fixo da Browser Use
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BrowserUseError(f"Browser Use HTTP {exc.code}: {detail[:500]}") from exc
        except (URLError, RemoteDisconnected, OSError) as exc:
            reason = getattr(exc, "reason", str(exc))
            raise BrowserUseError(f"Não foi possível acessar Browser Use: {reason}") from exc

    def _task(self, plan: ResearchPlan) -> str:
        judge = plan.judge or "não informado"
        topic = plan.query.strip() or "empréstimo"
        return f"""
Você é o subagente de pesquisa documental. Sua única tarefa é coletar PDFs públicos.

Use exclusivamente a consulta de julgados de primeiro grau do TJSP nesta URL:
https://esaj.tjsp.jus.br/cjpg/

Não faça análise jurídica, classificação, pontuação de similaridade, estimativa de êxito ou seleção por relevância.

Siga exatamente estes passos:
1. Abra a URL acima.
2. No campo "Pesquisa Livre" (id HTML `iddadosConsulta.pesquisaLivre`), digite exatamente: "{topic}".
3. No campo "Magistrado" (id HTML `nmAgente`), digite exatamente: "{judge}". Se a tela apresentar uma sugestão/autocomplete, selecione a sugestão com esse nome antes de consultar; não altere o campo oculto manualmente.
4. Clique em "Consultar".
5. Pegue TODOS os resultados retornados pela consulta, na ordem exibida, até o teto técnico de {plan.document_limit} documentos. Não descarte resultados por assunto, vara, comarca, tipo de ação ou qualquer outro critério.
6. Para cada resultado, abra o inteiro teor e acione o download do PDF público no navegador. Se a consulta retornar 3 resultados, devem existir 3 tentativas de download e você só poderá finalizar depois de processar os 3.
7. Se um clique falhar, tente o caminho alternativo visível do próprio portal uma vez e siga para o próximo resultado. Não abandone os resultados restantes porque um deles falhou.
8. Antes de responder, confira os downloads do navegador. Uma URL `pastadigital` sozinha não conta como documento baixado.

Não altere outros campos. Não use fontes privadas, não tente contornar login, CAPTCHA ou bloqueios e não invente documentos. Se houver menos de {plan.document_limit} resultados, processe todos os resultados que existirem.

No fim, responda SOMENTE este JSON:
{{
  "covers": [
    {{
      "case_id": "número do processo",
      "title": "tipo de decisão",
      "class_name": "classe processual exibida na grade",
      "subject": "assunto exibido na grade",
      "judge": "nome do magistrado",
      "court": "vara/comarca exibida na grade",
      "source_url": "URL pública da consulta"
    }}
  ],
  "documents": [
    {{
      "case_id": "número do processo",
      "title": "tipo de decisão e identificação",
      "pdf_url": "URL pública direta do PDF",
      "source_url": "URL da página pública de origem",
      "judge": "nome do magistrado",
      "court": "vara/comarca/tribunal",
      "similarity_reason": "coletado pela consulta de tema e magistrado",
      "similarity_score": 1.0
    }}
  ],
  "limitations": ["..."],
  "searched_sources": ["..."]
}}
""".strip()

    def stop_last_browser(self) -> None:
        """Encerra o navegador da sessão, inclusive após erro local ou timeout."""
        if not self.last_session_id:
            return
        try:
            browsers = self._request("GET", "/browsers")
            for browser in browsers.get("items", []):
                if browser.get("agentSessionId") == self.last_session_id and browser.get("status") == "active":
                    self._request("PATCH", f"/browsers/{browser['id']}", {"action": "stop"})
        except BrowserUseError:
            # O erro original da pesquisa continua sendo a informação principal.
            pass

    def cancel_last_run(self) -> None:
        """Cancela a execução remota para ela não continuar cobrando após uma falha local."""
        if not self.last_run_id:
            return
        try:
            self._request("POST", f"/runs/{self.last_run_id}/cancel", {})
        except BrowserUseError:
            # A execução pode já ter chegado a um estado terminal.
            pass

    @staticmethod
    def _result_json(result: str) -> dict:
        start, end = result.find("{"), result.rfind("}")
        if start < 0 or end < start:
            raise BrowserUseError("A execução não retornou o JSON de documentos solicitado")
        try:
            value = json.loads(result[start : end + 1])
        except json.JSONDecodeError as exc:
            raise BrowserUseError("A execução retornou JSON inválido") from exc
        if not isinstance(value.get("covers", []), list):
            raise BrowserUseError("O resultado contém capas em formato inválido")
        if not isinstance(value.get("documents"), list):
            raise BrowserUseError("O resultado não contém uma lista de documentos")
        return value

    @staticmethod
    def _download_pdf(url: str, destination: Path) -> str:
        host = urlparse(url).hostname or ""
        parsed = urlparse(url)
        if not host.endswith("tjsp.jus.br") or "/cjsg/" in parsed.path:
            raise BrowserUseError(f"URL de PDF fora do domínio oficial permitido: {host}")
        request = Request(url, headers={"User-Agent": "LegalResearchMVP/0.1"})
        with urlopen(request, timeout=90) as response:  # nosec B310: domínio validado acima
            content_type = response.headers.get("Content-Type", "")
            content = response.read()
        if not content.startswith(b"%PDF"):
            raise BrowserUseError(f"A URL não entregou um PDF válido (Content-Type: {content_type})")
        destination.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _download_browser_pdf(url: str, destination: Path) -> str:
        """Baixa uma URL pré-assinada, emitida pela API Browser Use, e valida o arquivo."""
        with urlopen(Request(url), timeout=90) as response:  # nosec B310: URL pré-assinada da API autenticada
            content = response.read()
        if not content.startswith(b"%PDF"):
            raise BrowserUseError("O download do navegador não contém um PDF válido")
        destination.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def _browser_downloads(self) -> list[dict]:
        if not self.last_session_id:
            return []
        browsers = self._request("GET", "/browsers")
        browser = next(
            (item for item in browsers.get("items", []) if item.get("agentSessionId") == self.last_session_id),
            None,
        )
        if not browser:
            return []
        response = self._request("GET", f"/browsers/{browser['id']}/downloads?includeUrls=true")
        return [item for item in response.get("files", []) if item.get("url")]

    def _save_browser_downloads(self, output_dir: str, records: list[dict]) -> list[DownloadedDocument]:
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        documents: list[DownloadedDocument] = []
        for index, item in enumerate(self._browser_downloads(), start=1):
            record = records[index - 1] if index <= len(records) and isinstance(records[index - 1], dict) else {}
            filename = re.sub(r"[^0-9A-Za-z._-]+", "_", Path(str(item["path"])).name)
            path = folder / f"{index:02d}_{filename}"
            digest = self._download_browser_pdf(str(item["url"]), path)
            try:
                score = float(record.get("similarity_score", 0))
            except (TypeError, ValueError):
                score = 0.0
            documents.append(
                DownloadedDocument(
                    case_id=str(record.get("case_id", "não informado")),
                    title=str(record.get("title", path.name)),
                    source_url=str(record.get("source_url", "https://esaj.tjsp.jus.br/cjpg/")),
                    local_path=str(path.resolve()),
                    sha256=digest,
                    text_excerpt="",
                    judge=str(record.get("judge", "não informado")),
                    court=str(record.get("court", "não informado")),
                    similarity_reason=str(record.get("similarity_reason", "download obtido no navegador")),
                    similarity_score=max(0.0, min(score, 1.0)),
                )
            )
        return documents

    def search_and_download(self, plan: ResearchPlan, output_dir: str) -> list[DownloadedDocument]:
        run = self._request(
            "POST",
            "/runs",
            {
                "task": self._task(plan),
                "model": "gpt-5.6-luna",
                # O padrão do provedor é xhigh; para coleta determinística de PDFs,
                # low reduz passos de raciocínio sem ampliar o escopo da navegação.
                "modelParams": {"reasoning": {"effort": "low"}},
                "browserSettings": {"record": True},
                "maxCostUsd": self.max_cost_usd,
            },
        )
        run_id = run["id"]
        self.last_run_id = run_id
        self.last_session_id = run.get("sessionId")
        try:
            deadline = time.monotonic() + 600
            status = run.get("status", "queued")
            while status not in self.terminal_statuses:
                if time.monotonic() >= deadline:
                    raise BrowserUseError(f"Tempo limite local atingido; execução Browser Use ainda ativa: {run_id}")
                time.sleep(3)
                status = self._request("GET", f"/runs/{run_id}/status").get("status", "queued")
            summary = self._request("GET", f"/runs/{run_id}")
            if summary.get("status") != "completed":
                raise BrowserUseError(f"Execução Browser Use {run_id} terminou como {summary.get('status')}: {summary.get('error')}")
        except Exception:
            self.cancel_last_run()
            raise

        records = self._result_json(summary.get("result") or "")
        self.last_result = records
        browser_documents = self._save_browser_downloads(output_dir, records["documents"])
        if browser_documents:
            return browser_documents
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        documents: list[DownloadedDocument] = []
        for index, record in enumerate(records["documents"][: plan.document_limit], start=1):
            if not isinstance(record, dict) or not record.get("pdf_url"):
                continue
            safe_case = re.sub(r"[^0-9A-Za-z._-]+", "_", str(record.get("case_id", index))).strip("_")
            path = folder / f"{index:02d}_{safe_case or 'sem_numero'}.pdf"
            try:
                digest = self._download_pdf(str(record["pdf_url"]), path)
            except BrowserUseError:
                continue
            try:
                score = float(record.get("similarity_score", 0))
            except (TypeError, ValueError):
                score = 0.0
            documents.append(
                DownloadedDocument(
                    case_id=str(record.get("case_id", "não informado")),
                    title=str(record.get("title", "decisão judicial")),
                    source_url=str(record.get("source_url") or record["pdf_url"]),
                    local_path=str(path.resolve()),
                    sha256=digest,
                    text_excerpt="",
                    judge=str(record.get("judge") or "não informado"),
                    court=str(record.get("court") or "não informado"),
                    similarity_reason=str(record.get("similarity_reason", "não informado")),
                    similarity_score=max(0.0, min(score, 1.0)),
                )
            )
        return documents
