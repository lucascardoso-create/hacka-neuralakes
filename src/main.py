from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .graph import build_graph
from .mcp_drive import McpDriveClient, McpDriveError

SYNTHETIC_DEMO_DEMAND = """DEMANDA SINTÉTICA — NÃO É PETIÇÃO NEM CASO DE CLIENTE.
Consumidora aposentada relata descontos mensais não autorizados em benefício previdenciário por associação.
Os pedidos demonstrativos são: declaração de inexistência de relação jurídica, cessação dos descontos,
restituição simples do indébito e indenização por dano moral. O evento de êxito da demo é o acolhimento
dos três primeiros pedidos em primeiro grau; o dano moral deve ser analisado separadamente.
"""


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demand", help="Descrição inicial da demanda")
    source.add_argument("--synthetic-demo", action="store_true", help="Usa demanda sintética de demonstração; não recebe petição de cliente")
    source.add_argument("--pdf", help="Caminho absoluto ou relativo de uma petição em PDF")
    source.add_argument("--text-file", help="Caminho para texto extraído de uma petição/sentença")
    source.add_argument("--drive-file-id", help="ID de um PDF selecionado no Google Drive via tools-mcp")
    parser.add_argument("--drive-folder-id", help="Pasta autorizada que contém o arquivo selecionado")
    parser.add_argument("--tenant-id", default=os.getenv("TENANT_ID", "local-dev"))
    parser.add_argument("--tools-mcp-dir", default=os.getenv("TOOLS_MCP_DIR"))
    parser.add_argument(
        "--document-limit",
        type=int,
        default=3,
        choices=range(1, 11),
        metavar="1..10",
        help="Quantidade-alvo de sentenças semelhantes; a análise usa todos os PDFs disponíveis",
    )
    parser.add_argument("--offline", action="store_true", help="Não chama o provedor LLM")
    args = parser.parse_args()
    if args.offline:
        os.environ["OFFLINE_MODE"] = "true"
    run_id = str(uuid4())
    drive_artifact: dict | None = None
    source_pdf = args.pdf
    if args.drive_file_id:
        if not args.drive_folder_id:
            parser.error("--drive-file-id exige --drive-folder-id")
        try:
            if args.tools_mcp_dir:
                os.environ["TOOLS_MCP_DIR"] = args.tools_mcp_dir
            client = McpDriveClient.from_env()
            client.select_files(
                folder_id=args.drive_folder_id,
                file_ids=[args.drive_file_id],
                tenant_id=args.tenant_id,
                run_id=run_id,
                step_id="intake_drive",
                span_id=f"{run_id}:intake_drive",
            )
            drive_artifact = client.download_file(
                file_id=args.drive_file_id,
                tenant_id=args.tenant_id,
                run_id=run_id,
                step_id="intake_drive",
                span_id=f"{run_id}:intake_drive:download",
            )
            if drive_artifact.get("mime_type") != "application/pdf":
                parser.error("o MVP aceita arquivo PDF no fluxo Drive; DOCX exige parser adicional")
            source_pdf = drive_artifact["local_path"]
        except McpDriveError as exc:
            parser.error(f"falha no tools-mcp Drive: {exc}")
    state = build_graph().invoke(
        {
            "run_id": run_id,
            "original_demand": SYNTHETIC_DEMO_DEMAND if args.synthetic_demo else args.demand or "",
            "source_pdf": source_pdf,
            "source_text_file": args.text_file,
            "drive_artifact": drive_artifact or {},
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
