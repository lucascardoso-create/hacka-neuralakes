from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from .graph import build_graph


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demand", help="Descrição inicial da demanda")
    source.add_argument("--pdf", help="Caminho absoluto ou relativo de uma petição em PDF")
    source.add_argument("--text-file", help="Caminho para texto extraído de uma petição/sentença")
    parser.add_argument("--document-limit", type=int, default=10, choices=range(1, 11), metavar="1..10", help="Quantidade-alvo de sentenças semelhantes")
    parser.add_argument("--offline", action="store_true", help="Não chama o provedor LLM")
    args = parser.parse_args()
    if args.offline:
        os.environ["OFFLINE_MODE"] = "true"
    run_id = str(uuid4())
    state = build_graph().invoke(
        {
            "run_id": run_id,
            "original_demand": args.demand or "",
            "source_pdf": args.pdf,
            "source_text_file": args.text_file,
            "document_limit": args.document_limit,
            "errors": [],
            "audit": [],
            "status": "running",
        }
    )
    path = Path("outputs") / "runs" / run_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
    return 0 if state["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
