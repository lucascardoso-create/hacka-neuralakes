from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from .schemas import AuditEvent, ResearchState


def intake_document(state: ResearchState) -> dict:
    """Converte o PDF recebido em texto verificável antes de qualquer inferência."""
    source_pdf = state.get("source_pdf")
    source_text_file = state.get("source_text_file")
    if source_text_file:
        path = Path(source_text_file).resolve()
        if not path.is_file():
            return {
                "errors": [*state.get("errors", []), "Arquivo de texto de entrada não encontrado"],
                "audit": [
                    *state.get("audit", []),
                    AuditEvent(node="intake_document", message="Arquivo de texto ausente").model_dump(),
                ],
            }
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return {
                "errors": [*state.get("errors", []), "Arquivo de texto de entrada está vazio"],
                "audit": [
                    *state.get("audit", []),
                    AuditEvent(node="intake_document", message="Arquivo de texto vazio").model_dump(),
                ],
            }
        return {
            "original_demand": text,
            "source_document": {
                "kind": "text_file",
                "path": str(path),
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "extracted_characters": len(text),
            },
            "audit": [
                *state.get("audit", []),
                AuditEvent(node="intake_document", message="Texto de processo carregado").model_dump(),
            ],
        }
    if not source_pdf:
        return {
            "source_document": {"kind": "text", "page_count": 0},
            "audit": [
                *state.get("audit", []),
                AuditEvent(node="intake_document", message="Entrada textual recebida").model_dump(),
            ],
        }

    path = Path(source_pdf).resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return {
            "errors": [*state.get("errors", []), "Arquivo de entrada não é um PDF legível"],
            "audit": [
                *state.get("audit", []),
                AuditEvent(node="intake_document", message="PDF inválido ou ausente").model_dump(),
            ],
        }

    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:  # pypdf expõe vários tipos de erro de documento
        return {
            "errors": [*state.get("errors", []), f"Falha ao extrair PDF: {exc}"],
            "audit": [
                *state.get("audit", []),
                AuditEvent(node="intake_document", message="Extração de PDF falhou").model_dump(),
            ],
        }

    extracted_text = "\n\n".join(text for text in pages if text)
    if not extracted_text:
        return {
            "errors": [*state.get("errors", []), "PDF não possui texto extraível; OCR ainda não foi configurado"],
            "audit": [
                *state.get("audit", []),
                AuditEvent(node="intake_document", message="PDF requer OCR").model_dump(),
            ],
        }
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "original_demand": extracted_text,
        "source_document": {
            "kind": "pdf",
            "path": str(path),
            "filename": path.name,
            "page_count": len(pages),
            "sha256": digest,
            "extracted_characters": len(extracted_text),
        },
        "audit": [
            *state.get("audit", []),
            AuditEvent(node="intake_document", message=f"PDF extraído: {len(pages)} páginas").model_dump(),
        ],
    }
