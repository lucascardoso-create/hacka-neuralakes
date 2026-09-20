"""Coletor mínimo: tema + magistrado -> PDFs públicos do TJSP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from .browser_use import BrowserUseClient, BrowserUseError
from .schemas import ResearchPlan


def main() -> int:
    parser = argparse.ArgumentParser(description="Baixa PDFs públicos da consulta de julgados do TJSP")
    parser.add_argument("--tema", required=True, help="Texto para Pesquisa Livre")
    parser.add_argument("--magistrado", required=True, help="Nome exato do magistrado")
    parser.add_argument("--limite", type=int, default=10, choices=range(1, 11), metavar="1..10", help="Teto técnico; todos os resultados retornados até esse número serão baixados")
    args = parser.parse_args()

    run_id = str(uuid4())
    folder = Path("outputs") / "pdf_collection" / run_id
    plan = ResearchPlan(
        query=args.tema,
        judge=args.magistrado,
        similarity_criteria=[],
        document_limit=args.limite,
    )
    client: BrowserUseClient | None = None
    try:
        client = BrowserUseClient()
        documents = client.search_and_download(plan, str(folder / "documents"))
        manifest = {
            "theme": args.tema,
            "judge": args.magistrado,
            "requested": args.limite,
            "covers": (client.last_result or {}).get("covers", []),
            "downloaded": len(documents),
            "documents": [item.model_dump() for item in documents],
        }
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(folder.resolve())
        return 0 if len(documents) == args.limite else 2
    except BrowserUseError as exc:
        print(f"Erro: {exc}")
        return 2
    finally:
        if client is not None:
            client.stop_last_browser()


if __name__ == "__main__":
    raise SystemExit(main())
