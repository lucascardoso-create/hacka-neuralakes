from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from .graph import build_graph

SYNTHETIC_DEMO_DEMAND = """DEMANDA SINTÉTICA — NÃO É PETIÇÃO NEM CASO DE CLIENTE.
Consumidora aposentada relata descontos mensais não autorizados em benefício previdenciário por associação.
Os pedidos demonstrativos são: declaração de inexistência de relação jurídica, cessação dos descontos,
restituição simples do indébito e indenização por dano moral. O evento de êxito da demo é o acolhimento
dos três primeiros pedidos em primeiro grau; o dano moral deve ser analisado separadamente.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demand", help="Descrição inicial da demanda")
    source.add_argument("--synthetic-demo", action="store_true", help="Usa demanda sintética de demonstração; não recebe petição de cliente")
    source.add_argument("--pdf", help="Caminho absoluto ou relativo de uma petição em PDF")
    source.add_argument("--text-file", help="Caminho para texto extraído de uma petição/sentença")
    parser.add_argument("--document-limit", type=int, default=3, choices=range(1, 11), metavar="1..10", help="Quantidade-alvo de sentenças semelhantes; a análise usa todos os PDFs disponíveis")
    parser.add_argument("--offline", action="store_true", help="Não chama o provedor LLM")
    args = parser.parse_args()
    if args.offline:
        os.environ["OFFLINE_MODE"] = "true"
    run_id = str(uuid4())
    state = build_graph().invoke(
        {
            "run_id": run_id,
            "original_demand": SYNTHETIC_DEMO_DEMAND if args.synthetic_demo else args.demand or "",
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
