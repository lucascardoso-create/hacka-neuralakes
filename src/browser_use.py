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
        """Instrui o subagente a pesquisar no CJPG, acionar o download do PDF
        de cada um dos processos encontrados no navegador e devolver o JSON."""
        topic = plan.query.strip() or "empréstimo"
        if plan.judge and plan.judge.strip():
            judge_step = f'3. Campo "Magistrado" (id `nmAgente`): digite exatamente "{plan.judge.strip()}". Se aparecer autocomplete, selecione a sugestão antes de consultar.'
        else:
            judge_step = '3. Deixe o campo "Magistrado" (id `nmAgente`) em branco.'

        return f"""
Você é o subagente de pesquisa documental jurídica no TJSP.

Sua missão é baixar os arquivos PDF de TODOS os {plan.document_limit} primeiros resultados encontrados no TJSP.

Passos obrigatórios e sequenciais:
1. Abra https://esaj.tjsp.jus.br/cjpg/
2. Campo "Pesquisa Livre" (id `iddadosConsulta.pesquisaLivre`): digite exatamente "{topic}".
{judge_step}
4. Clique no botão "Consultar".
5. Para CADA um dos {plan.document_limit} resultados encontrados na listagem (Processo 1, Processo 2, Processo 3):
   a) Clique no link de inteiro teor / visualizar do processo.
   b) Na tela/popup da Pasta Digital que se abrir, clique no botão "Salvar o documento" ou no ícone de download para disparar o download do arquivo PDF no navegador.
   c) Aguarde a conclusão do download do arquivo PDF pelo navegador.
   d) Feche o popup/aba ou retorne para a lista de resultados.
   e) Repita OBRIGATORIAMENTE os passos para o próximo processo até ter acionado o download dos {plan.document_limit} PDFs.
6. Apenas após ter baixado os PDFs de todos os {plan.document_limit} processos, responda com o JSON de metadados.

Responda SOMENTE com este JSON (sem texto antes ou depois):
{{
  "documents": [
    {{
      "case_id": "número do processo conforme exibido",
      "title": "classe/tipo de decisão conforme exibido",
      "judge": "nome do magistrado conforme exibido",
      "court": "vara e comarca conforme exibido",
      "subject": "assunto conforme exibido",
      "source_url": "URL da página de consulta",
      "similarity_reason": "decisão baixada no navegador",
      "similarity_score": 1.0
    }}
  ],
  "total_found": "total de resultados exibidos na consulta",
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
            pass

    def cancel_last_run(self) -> None:
        """Cancela a execução remota para ela não continuar cobrando após uma falha local."""
        if not self.last_run_id:
            return
        try:
            self._request("POST", f"/runs/{self.last_run_id}/cancel", {})
        except BrowserUseError:
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
        # Aceita tanto chave 'documents' quanto 'results'
        docs = value.get("documents") or value.get("results")
        if not isinstance(docs, list):
            raise BrowserUseError("O resultado não contém a lista de documentos esperada")
        value["documents"] = docs
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
        """Consulta arquivos baixados dentro da sessão do navegador da Browser Use Cloud."""
        if not self.last_session_id:
            return []
        try:
            browsers = self._request("GET", "/browsers")
            browser = next(
                (item for item in browsers.get("items", []) if item.get("agentSessionId") == self.last_session_id),
                None,
            )
            if not browser:
                return []
            response = self._request("GET", f"/browsers/{browser['id']}/downloads?includeUrls=true")
            return [item for item in response.get("files", []) if item.get("url")]
        except Exception:
            return []

    def _save_browser_downloads(self, output_dir: str, records: list[dict]) -> list[DownloadedDocument]:
        """Salva localmente os arquivos baixados pelo navegador na nuvem."""
        files = self._browser_downloads()
        if not files:
            return []
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        documents: list[DownloadedDocument] = []
        for index, item in enumerate(files, start=1):
            record = records[index - 1] if index <= len(records) and isinstance(records[index - 1], dict) else {}
            filename = re.sub(r"[^0-9A-Za-z._-]+", "_", Path(str(item.get("path", f"doc_{index}.pdf"))).name)
            path = folder / f"{index:02d}_{filename}"
            try:
                digest = self._download_browser_pdf(str(item["url"]), path)
            except BrowserUseError:
                continue
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
                    similarity_reason=str(record.get("similarity_reason", "download concluído no navegador")),
                    similarity_score=float(record.get("similarity_score", 1.0) or 1.0),
                )
            )
        return documents

    def _execute_run(self, model: str, plan: ResearchPlan) -> dict:
        payload: dict = {
            "task": self._task(plan),
            "model": model,
            "browserSettings": {"record": False},
            "maxCostUsd": self.max_cost_usd,
        }
        run = self._request("POST", "/runs", payload)
        run_id = run["id"]
        self.last_run_id = run_id
        self.last_session_id = run.get("sessionId")
        try:
            deadline = time.monotonic() + 360
            status = run.get("status", "queued")
            while status not in self.terminal_statuses:
                if time.monotonic() >= deadline:
                    raise BrowserUseError(f"Tempo limite local atingido para {model} ({run_id})")
                time.sleep(3)
                status = self._request("GET", f"/runs/{run_id}/status").get("status", "queued")
            summary = self._request("GET", f"/runs/{run_id}")
            if summary.get("status") != "completed":
                raise BrowserUseError(
                    f"Execução Browser Use {run_id} ({model}) terminou como {summary.get('status')}: {summary.get('error')}"
                )
            return summary
        except Exception:
            self.cancel_last_run()
            raise

    def search_and_download(self, plan: ResearchPlan, output_dir: str) -> list[DownloadedDocument]:
        """Fluxo de busca e download de PDFs:
        1. Executa o subagente no Browser Use com o modelo principal (GPT-5.6).
        2. Em caso de falha ou indisponibilidade, aciona automaticamente o fallback (DeepSeek).
        3. Baixa todos os PDFs capturados no navegador remoto.
        4. Fallback local: Se não baixou via navegador, tenta download direto por URL.
        5. Garante que todos os metadados coletados sejam preservados.
        """
        primary_model = os.getenv("BROWSER_USE_MODEL", "gpt-5.6-luna")
        fallback_model = "deepseek-v4.1-flash"

        try:
            summary = self._execute_run(primary_model, plan)
            payload = self._result_json(summary.get("result") or "")
        except BrowserUseError:
            if primary_model != fallback_model:
                summary = self._execute_run(fallback_model, plan)
                payload = self._result_json(summary.get("result") or "")
            else:
                raise

        self.last_result = payload
        records: list[dict] = payload.get("documents", [])
        if not records:
            raise BrowserUseError("O agente de pesquisa não encontrou nenhum resultado para a consulta")

        # 1. Tenta recuperar os arquivos baixados pelo navegador na nuvem
        browser_docs = self._save_browser_downloads(output_dir, records)
        if browser_docs:
            # Se baixou arquivos suficientes, retorna
            if len(browser_docs) >= len(records):
                return browser_docs
            # Caso parcial, mescla arquivos baixados com metadados restantes
            covered_cases = {d.case_id for d in browser_docs}
            for rec in records:
                cid = str(rec.get("case_id", ""))
                if cid not in covered_cases:
                    browser_docs.append(
                        DownloadedDocument(
                            case_id=cid or "não informado",
                            title=str(rec.get("title", "decisão judicial")),
                            source_url=str(rec.get("source_url", "https://esaj.tjsp.jus.br/cjpg/")),
                            local_path="",
                            sha256="",
                            text_excerpt="",
                            judge=str(rec.get("judge", "não informado")),
                            court=str(rec.get("court", "não informado")),
                            similarity_reason="metadados coletados; arquivo não baixado no navegador",
                            similarity_score=0.0,
                        )
                    )
            return browser_docs

        # 2. Fallback: download direto se URLs forem fornecidas
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        documents: list[DownloadedDocument] = []
        for index, record in enumerate(records[: plan.document_limit], start=1):
            if not isinstance(record, dict):
                continue
            pdf_url = str(record.get("pdf_url") or "")
            if not pdf_url or pdf_url == "null":
                documents.append(
                    DownloadedDocument(
                        case_id=str(record.get("case_id", "não informado")),
                        title=str(record.get("title", "decisão judicial")),
                        source_url=str(record.get("source_url", "https://esaj.tjsp.jus.br/cjpg/")),
                        local_path="",
                        sha256="",
                        text_excerpt="",
                        judge=str(record.get("judge", "não informado")),
                        court=str(record.get("court", "não informado")),
                        similarity_reason="metadados coletados na grade",
                        similarity_score=1.0,
                    )
                )
                continue

            safe_case = re.sub(r"[^0-9A-Za-z._-]+", "_", str(record.get("case_id", index))).strip("_")
            path = folder / f"{index:02d}_{safe_case or 'sem_numero'}.pdf"
            try:
                digest = self._download_pdf(pdf_url, path)
                documents.append(
                    DownloadedDocument(
                        case_id=str(record.get("case_id", "não informado")),
                        title=str(record.get("title", "decisão judicial")),
                        source_url=str(record.get("source_url") or pdf_url),
                        local_path=str(path.resolve()),
                        sha256=digest,
                        text_excerpt="",
                        judge=str(record.get("judge", "não informado")),
                        court=str(record.get("court", "não informado")),
                        similarity_reason="coletado e baixado com sucesso",
                        similarity_score=1.0,
                    )
                )
            except BrowserUseError as exc:
                documents.append(
                    DownloadedDocument(
                        case_id=str(record.get("case_id", "não informado")),
                        title=str(record.get("title", "decisão judicial")),
                        source_url=str(record.get("source_url") or pdf_url),
                        local_path="",
                        sha256="",
                        text_excerpt="",
                        judge=str(record.get("judge", "não informado")),
                        court=str(record.get("court", "não informado")),
                        similarity_reason=f"download falhou: {exc}",
                        similarity_score=0.0,
                    )
                )

        return documents
