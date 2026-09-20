"""
Validação isolada do módulo Browser Use.
Dispara somente o nó `research` com um plano fixo (sem LLM, sem intake).
Imprime todos os documentos retornados com seus caminhos locais.

Uso:
    python validate_browser_use.py
    python validate_browser_use.py --judge "Nome do Magistrado" --topic "empréstimo" --limit 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

# Carrega .env se existir
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from src.browser_use import BrowserUseClient, BrowserUseError
from src.schemas import ResearchPlan


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida o módulo Browser Use isoladamente")
    parser.add_argument("--topic", default="empréstimo", help="Tema da pesquisa livre no CJPG")
    parser.add_argument("--judge", default=None, help="Nome do magistrado para filtrar")
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11), metavar="1..10")
    args = parser.parse_args()

    plan = ResearchPlan(
        query=args.topic,
        judge=args.judge,
        document_limit=args.limit,
    )

    run_id = str(uuid4())
    output_dir = Path("outputs") / "runs" / run_id / "documents"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  BROWSER USE — VALIDAÇÃO")
    print(f"{'='*60}")
    print(f"  Tópico    : {plan.query}")
    print(f"  Magistrado: {plan.judge or '(todos)'}")
    print(f"  Limite    : {plan.document_limit}")
    print(f"  Run ID    : {run_id}")
    print(f"  Saída     : {output_dir.resolve()}")
    print(f"{'='*60}\n")

    client = BrowserUseClient()
    try:
        docs = client.search_and_download(plan, str(output_dir))
    except BrowserUseError as exc:
        print(f"\n[ERRO] {exc}", file=sys.stderr)
        if client.last_result:
            print("\n[RAW RESULT do agente]")
            print(json.dumps(client.last_result, ensure_ascii=False, indent=2))
        return 1
    finally:
        client.stop_last_browser()

    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if not docs:
        print("[AVISO] Nenhum documento retornado.")
        return 2

    print(f"\n{'='*60}")
    print(f"  {len(docs)} DOCUMENTO(S) COLETADO(S)")
    print(f"{'='*60}")
    for i, doc in enumerate(docs, 1):
        has_file = doc.local_path and Path(doc.local_path).exists()
        status = "[OK] PDF BAIXADO" if has_file else "[!] SEM ARQUIVO"
        print(f"\n  [{i}] {status}")
        print(f"       Processo  : {doc.case_id}")
        print(f"       Titulo    : {doc.title}")
        print(f"       Magistrado: {doc.judge}")
        print(f"       Vara      : {doc.court}")
        print(f"       Origem    : {doc.source_url}")
        if doc.local_path:
            print(f"       Arquivo   : {doc.local_path}")
        if doc.sha256:
            print(f"       SHA-256   : {doc.sha256[:16]}...")
        if "falhou" in doc.similarity_reason or "ausente" in doc.similarity_reason or "não baixado" in doc.similarity_reason:
            print(f"       [!] {doc.similarity_reason}")

    # Salva manifest da validacao
    manifest = output_dir.parent / "validation_manifest.json"
    manifest.write_text(
        json.dumps([d.model_dump() for d in docs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  Manifest salvo em: {manifest.resolve()}")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
