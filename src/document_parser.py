from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from pypdf import PdfReader


class ParsedJudgment(TypedDict, total=False):
    case_id: str
    judge: str
    court: str
    action_class: str
    relatorio: str
    fundamentacao: str
    dispositivo: str
    clean_text: str
    char_count: int


def clean_boilerplate(text: str) -> str:
    """Remove carimbos, certidões de assinatura digital e cabeçalhos repetitivos do e-SAJ/TJSP."""
    if not text:
        return ""

    # Remove notas de conferência de documento digital do e-SAJ
    text = re.sub(
        r"Para conferir o original, acesse o site https?://esaj\.tjsp\.jus\.br/pastadigital/[^\n]+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"Este documento é cópia do original, assinado digitalmente por [^\n]+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"DOCUMENTO ASSINADO DIGITALMENTE NOS TERMOS DA LEI 11\.419/2006[^\n]*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove carimbos de folha (ex: 'fls. 268')
    text = re.sub(r"\bfls\.\s*\d+\b", "", text, flags=re.IGNORECASE)

    # Remove carimbos de página intermediária ('--- PÁGINA ---', 'lauda X')
    text = re.sub(r"---\s*PÁGINA\s*---", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d{7}-\d{2}\.\d{4}\.8\.26\.\d{4}\s*-\s*lauda\s*\d+\b", "", text)

    # Remove avisos de atendimento ao público
    text = re.sub(
        r"Horário de Atendimento ao Público:[^\n]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Normaliza quebras de linha múltiplas e espaços
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_judgment_sections(text: str) -> dict[str, str]:
    """Isola as seções fundamentais da sentença pelo Art. 489 do CPC."""
    cleaned = clean_boilerplate(text)
    
    sections = {
        "relatorio": "",
        "fundamentacao": "",
        "dispositivo": "",
    }

    # Padrões para identificar as seções
    rel_match = re.search(r"(?:1\.\s*RELATÓRIO|RELATÓRIO|Vistos\.)", cleaned, re.IGNORECASE)
    fund_match = re.search(r"(?:2\.\s*FUNDAMENTAÇÃO|FUNDAMENTAÇÃO|MOTIVAÇÃO|PASSO A DECIDIR|DECIDO)", cleaned, re.IGNORECASE)
    disp_match = re.search(r"(?:3\.\s*DISPOSITIVO|DISPOSITIVO|Ante o exposto|Posto isso|JULGO)", cleaned, re.IGNORECASE)

    if rel_match and fund_match:
        sections["relatorio"] = cleaned[rel_match.start() : fund_match.start()].strip()
    elif rel_match and disp_match:
        sections["relatorio"] = cleaned[rel_match.start() : disp_match.start()].strip()

    if fund_match and disp_match:
        sections["fundamentacao"] = cleaned[fund_match.start() : disp_match.start()].strip()
    elif fund_match:
        sections["fundamentacao"] = cleaned[fund_match.start() :].strip()

    if disp_match:
        sections["dispositivo"] = cleaned[disp_match.start() :].strip()

    return sections


def parse_judgment_pdf(pdf_path: str | Path, max_characters: int = 4000) -> str:
    """Processa o PDF da decisão, aplicando limpeza e extraindo um extrato focado e conciso."""
    path = Path(pdf_path)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return ""

    try:
        reader = PdfReader(str(path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        raw_text = "\n\n".join(pages_text)
    except Exception:
        return ""

    if not raw_text.strip():
        return ""

    sections = extract_judgment_sections(raw_text)
    
    # Se conseguiu isolar dispositivo ou relatório, monta o extrato cirúrgico
    if sections["dispositivo"] or sections["relatorio"]:
        parts = []
        if sections["relatorio"]:
            parts.append(f"[RELATÓRIO / FATOS]:\n{sections['relatorio'][:1200]}")
        if sections["fundamentacao"]:
            # Pega o início e o fim da fundamentação
            fund = sections["fundamentacao"]
            if len(fund) > 1200:
                fund_excerpt = f"{fund[:600]}\n[...]\n{fund[-600:]}"
            else:
                fund_excerpt = fund
            parts.append(f"[FUNDAMENTAÇÃO JURÍDICA]:\n{fund_excerpt}")
        if sections["dispositivo"]:
            parts.append(f"[DISPOSITIVO / RESULTADO]:\n{sections['dispositivo'][:1400]}")
        
        compact = "\n\n".join(parts)
        return compact[:max_characters].strip()

    # Fallback: se não encontrou seções marcadas, limpa o texto bruto
    cleaned = clean_boilerplate(raw_text)
    return cleaned[:max_characters].strip()
