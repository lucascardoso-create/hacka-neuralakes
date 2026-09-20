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
        """Uma única primitiva: pesquisar e retornar metadados.

        O agente NÃO abre o inteiro teor nem faz download de nenhum arquivo.
        Apenas executa a consulta no CJPG e devolve os metadados de TODOS os
        resultados encontrados. O download dos PDFs é feito pelo nosso código Python.
        """
        judge = plan.judge or "não informado"
        topic = plan.query.strip() or "empréstimo"
        return f"""
Você é o subagente de pesquisa documental.

Sua ÚNICA tarefa é executar a consulta abaixo e devolver os metadados de TODOS os resultados. Não abra o inteiro teor. Não faça download de nenhum arquivo. Não analise os documentos.

Passos obrigatórios:
1. Abra https://esaj.tjsp.jus.br/cjpg/
2. Campo "Pesquisa Livre" (id `iddadosConsulta.pesquisaLivre`): digite exatamente "{topic}".
3. Campo "Magistrado" (id `nmAgente`): digite exatamente "{judge}". Se aparecer autocomplete, selecione a sugestão antes de consultar.
4. Clique em "Consultar".
5. Na página de resultados, colete os metadados exibidos na grade para TODOS os resultados (até {plan.document_limit}). NÃO abra nenhum deles. NÃO clique em nenhum link de documento.
6. Para cada resultado, localize a URL direta do PDF do inteiro teor (geralmente href do link "Inteiro Teor" ou "Visualizar" na grade). Registre-a como `pdf_url`. Se não estiver visível na grade, registre `null`.

Regras absolutas:
- Não abra páginas individuais de processo.
- Não faça nenhum download.
- Não invente dados. Se um campo não estiver visível na grade, use null.
- Devolva todos os resultados encontrados. Se a consulta retornar 3, o JSON terá 3 itens. Se retornar 0, a lista será vazia.

Responda SOMENTE com este JSON (sem texto antes ou depois):
{{
  "results": [
    {{
      "case_id": "número do processo conforme exibido",
      "title": "classe/tipo de decisão conforme exibido",
      "judge": "nome do magistrado conforme exibido",
      "court": "vara e comarca conforme exibido",
      "subject": "assunto conforme exibido",
      "source_url": "URL da página de resultados onde este item foi encontrado",
      "pdf_url": "URL direta do PDF ou null"
    }}
  ],
  "total_found": "número total de resultados exibidos pelo portal",
  "searched_sources": ["https://esaj.tjsp.jus.br/cjpg/"]
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
            raise BrowserUseError("A execução não retornou o JSON solicitado")
        try:
            value = json.loads(result[start : end + 1])
        except json.JSONDecodeError as exc:
            raise BrowserUseError("A execução retornou JSON inválido") from exc
        if not isinstance(value.get("results"), list):
            raise BrowserUseError("O resultado não contém a lista 'results' esperada")
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

    def _download_all(self, records: list[dict], output_dir: str) -> list[DownloadedDocument]:
        """Baixa TODOS os PDFs da lista retornada pelo agente. Erros por documento
        são registrados mas não descartam os documentos restantes."""
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        documents: list[DownloadedDocument] = []
        errors: list[str] = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                continue
            pdf_url = str(record.get("pdf_url") or "")
            if not pdf_url or pdf_url == "null":
                # Agente não encontrou URL direta; registra cobertura sem arquivo local.
                documents.append(
                    DownloadedDocument(
                        case_id=str(record.get("case_id", "não informado")),
                        title=str(record.get("title", "decisão judicial")),
                        source_url=str(record.get("source_url", "https://esaj.tjsp.jus.br/cjpg/")),
                        local_path="",
                        sha256="",
                        text_excerpt="",
                        judge=str(record.get("judge") or "não informado"),
                        court=str(record.get("court") or "não informado"),
                        similarity_reason="pdf_url ausente na grade; somente metadados coletados",
                        similarity_score=0.0,
                    )
                )
                continue
            safe_case = re.sub(r"[^0-9A-Za-z._-]+", "_", str(record.get("case_id", index))).strip("_")
            path = folder / f"{index:02d}_{safe_case or 'sem_numero'}.pdf"
            try:
                digest = self._download_pdf(pdf_url, path)
            except BrowserUseError as exc:
                errors.append(f"[{index}] {record.get('case_id', '?')}: {exc}")
                # Adiciona o registro sem arquivo, não descarta.
                documents.append(
                    DownloadedDocument(
                        case_id=str(record.get("case_id", "não informado")),
                        title=str(record.get("title", "decisão judicial")),
                        source_url=str(record.get("source_url") or pdf_url),
                        local_path="",
                        sha256="",
                        text_excerpt="",
                        judge=str(record.get("judge") or "não informado"),
                        court=str(record.get("court") or "não informado"),
                        similarity_reason=f"download falhou: {exc}",
                        similarity_score=0.0,
                    )
                )
                continue
            documents.append(
                DownloadedDocument(
                    case_id=str(record.get("case_id", "não informado")),
                    title=str(record.get("title", "decisão judicial")),
                    source_url=str(record.get("source_url") or pdf_url),
                    local_path=str(path.resolve()),
                    sha256=digest,
                    text_excerpt="",
                    judge=str(record.get("judge") or "não informado"),
                    court=str(record.get("court") or "não informado"),
                    similarity_reason="coletado pela consulta de tema e magistrado",
                    similarity_score=1.0,
                )
            )
        if errors:
            # Propaga erros de download como aviso (não como falha fatal).
            raise BrowserUseError(
                f"{len(errors)} de {len(records)} downloads falharam:\n" + "\n".join(errors)
            )
        return documents

    def search_and_download(self, plan: ResearchPlan, output_dir: str) -> list[DownloadedDocument]:
        """Fluxo em duas fases:
        1. Uma única chamada ao Browser Use: pesquisar e retornar metadados.
        2. Download de TODOS os PDFs encontrados feito pelo nosso código Python.
        O agente não navega para páginas individuais nem faz download de nada.
        """
        run = self._request(
            "POST",
            "/runs",
            {
                "task": self._task(plan),
                # Modelo leve: a tarefa é só preencher um formulário e ler uma grade.
                "model": "gpt-4o",
                "browserSettings": {"record": False},
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
                raise BrowserUseError(
                    f"Execução Browser Use {run_id} terminou como {summary.get('status')}: {summary.get('error')}"
                )
        except Exception:
            self.cancel_last_run()
            raise

        payload = self._result_json(summary.get("result") or "")
        self.last_result = payload
        records: list[dict] = payload.get("results", [])
        if not records:
            raise BrowserUseError("O agente de pesquisa não encontrou nenhum resultado para a consulta")
        # Baixa TODOS os registros retornados, sem descartar por falha individual.
        try:
            return self._download_all(records, output_dir)
        except BrowserUseError as exc:
            # Erros parciais de download: propaga, mas o nó de pesquisa decide o que fazer.
            raise
