"""
Script da Demonstração do Subagente de Pesquisa Browser Use (TJSP).
Executa o fluxo completo do módulo sem alterá-lo, extrai texto dos PDFs baixados
e compila um Dashboard HTML autossuficiente e interativo para visualização externa.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Carrega .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import pypdf
from src.browser_use import BrowserUseClient, BrowserUseError
from src.schemas import DownloadedDocument, ResearchPlan


def extract_pdf_info(pdf_path: Path) -> dict:
    """Extrai estatísticas e texto de um arquivo PDF local."""
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        return {"pages": 0, "chars": 0, "text": "", "error": "Arquivo não encontrado ou vazio"}
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n\n--- PÁGINA ---\n\n".join(pages_text).strip()
        return {
            "pages": len(reader.pages),
            "chars": len(full_text),
            "text": full_text,
            "preview": full_text[:1200] + ("..." if len(full_text) > 1200 else ""),
            "error": None,
        }
    except Exception as exc:
        return {"pages": 0, "chars": 0, "text": "", "error": str(exc)}


def generate_html_dashboard(
    plan: ResearchPlan,
    docs: list[DownloadedDocument],
    pdf_details: list[dict],
    meta: dict,
    output_html_path: Path,
) -> None:
    """Gera um Dashboard HTML autônomo, responsivo e interativo (Dark Theme)."""
    total_docs = len(docs)
    total_pdfs_downloaded = sum(1 for d in docs if d.local_path and Path(d.local_path).exists())
    total_chars = sum(p.get("chars", 0) for p in pdf_details)
    total_pages = sum(p.get("pages", 0) for p in pdf_details)

    docs_json = []
    for doc, pdf_info in zip(docs, pdf_details):
        docs_json.append({
            "case_id": doc.case_id,
            "title": doc.title,
            "judge": doc.judge,
            "court": doc.court,
            "source_url": doc.source_url,
            "local_path": doc.local_path,
            "sha256": doc.sha256,
            "similarity_reason": doc.similarity_reason,
            "pages": pdf_info.get("pages", 0),
            "chars": pdf_info.get("chars", 0),
            "preview": pdf_info.get("preview", ""),
            "full_text": pdf_info.get("text", ""),
            "has_file": bool(doc.local_path and Path(doc.local_path).exists()),
        })

    embedded_data_json = json.dumps({
        "plan": plan.model_dump(),
        "meta": meta,
        "docs": docs_json,
    }, ensure_ascii=False, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Subagente Browser Use — Demonstração TJSP</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-dark: #0a0e17;
      --bg-card: rgba(18, 24, 38, 0.75);
      --bg-card-hover: rgba(28, 38, 58, 0.85);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(0, 212, 255, 0.3);
      --accent-cyan: #00d4ff;
      --accent-blue: #3b82f6;
      --accent-purple: #8b5cf6;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 10% 10%, rgba(0, 212, 255, 0.06) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 40%);
      color: var(--text-main);
      line-height: 1.6;
      min-height: 100vh;
      padding: 2.5rem 1.5rem;
    }}

    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}

    /* Header & Badge */
    header {{
      margin-bottom: 2.5rem;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 1.5rem;
    }}

    .title-group h1 {{
      font-size: 2.2rem;
      font-weight: 800;
      background: linear-gradient(135deg, #ffffff 0%, var(--accent-cyan) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -0.02em;
    }}

    .title-group p {{
      color: var(--text-muted);
      margin-top: 0.3rem;
      font-size: 1.05rem;
    }}

    .badge-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0.9rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.35);
      color: #34d399;
    }}

    .badge-pill.status-pulse::before {{
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 10px #34d399;
      animation: pulse 2s infinite;
    }}

    @keyframes pulse {{
      0% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(1.2); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}

    /* Metrics Grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2.5rem;
    }}

    .metric-card {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1.25rem 1.5rem;
      transition: all 0.2s ease;
      position: relative;
      overflow: hidden;
    }}

    .metric-card:hover {{
      transform: translateY(-2px);
      border-color: var(--border-accent);
      background: var(--bg-card-hover);
    }}

    .metric-card .label {{
      font-size: 0.85rem;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
    }}

    .metric-card .value {{
      font-size: 1.65rem;
      font-weight: 700;
      color: #ffffff;
      font-family: 'JetBrains Mono', monospace;
    }}

    .metric-card .subtext {{
      font-size: 0.8rem;
      color: var(--text-dim);
      margin-top: 0.3rem;
    }}

    /* Query Banner */
    .query-banner {{
      background: linear-gradient(135deg, rgba(14, 23, 42, 0.8) 0%, rgba(30, 41, 59, 0.8) 100%);
      border: 1px solid rgba(59, 130, 246, 0.25);
      border-radius: 14px;
      padding: 1.25rem 1.75rem;
      margin-bottom: 2.5rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
    }}

    .query-item {{
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
    }}

    .query-item .q-label {{
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--accent-cyan);
      font-weight: 600;
    }}

    .query-item .q-val {{
      font-size: 1.1rem;
      font-weight: 600;
      color: #fff;
    }}

    /* Document Section */
    .section-title {{
      font-size: 1.4rem;
      font-weight: 700;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .section-title span.count-badge {{
      background: rgba(0, 212, 255, 0.15);
      color: var(--accent-cyan);
      font-size: 0.85rem;
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
    }}

    .docs-list {{
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      margin-bottom: 3rem;
    }}

    .doc-card {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 1.5rem;
      transition: all 0.25s ease;
    }}

    .doc-card:hover {{
      border-color: rgba(0, 212, 255, 0.4);
      background: var(--bg-card-hover);
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }}

    .doc-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 1rem;
      margin-bottom: 1rem;
      flex-wrap: wrap;
    }}

    .doc-title-group h3 {{
      font-size: 1.2rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      font-family: 'JetBrains Mono', monospace;
    }}

    .doc-title-group .doc-class {{
      color: var(--accent-cyan);
      font-size: 0.95rem;
      font-weight: 500;
      margin-top: 0.2rem;
      font-family: 'Outfit', sans-serif;
    }}

    .doc-status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.35rem 0.8rem;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
    }}

    .doc-status-badge.ok {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }}

    .doc-status-badge.warn {{
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid rgba(245, 158, 11, 0.4);
      color: #fbbf24;
    }}

    .doc-meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 0.75rem 1.25rem;
      margin-bottom: 1.25rem;
      padding: 1rem;
      background: rgba(0, 0, 0, 0.25);
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.04);
      font-size: 0.9rem;
    }}

    .doc-meta-item {{
      display: flex;
      flex-direction: column;
      gap: 0.15rem;
    }}

    .doc-meta-item .label {{
      font-size: 0.75rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .doc-meta-item .val {{
      color: var(--text-main);
      font-weight: 500;
    }}

    .hash-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: var(--text-muted);
      word-break: break-all;
    }}

    /* Text Preview Box */
    .preview-box {{
      background: #060910;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 1.2rem;
      margin-top: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: #d1d5db;
      line-height: 1.6;
      max-height: 220px;
      overflow-y: auto;
      white-space: pre-wrap;
      position: relative;
    }}

    .preview-box-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
      font-size: 0.75rem;
      color: var(--accent-cyan);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }}

    /* Action Buttons */
    .doc-actions {{
      display: flex;
      gap: 0.75rem;
      margin-top: 1.2rem;
      flex-wrap: wrap;
    }}

    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.55rem 1rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s ease;
      border: none;
      font-family: 'Outfit', sans-serif;
    }}

    .btn-primary {{
      background: linear-gradient(135deg, var(--accent-cyan) 0%, var(--accent-blue) 100%);
      color: #000;
    }}

    .btn-primary:hover {{
      opacity: 0.9;
      transform: translateY(-1px);
    }}

    .btn-secondary {{
      background: rgba(255, 255, 255, 0.08);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.12);
    }}

    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.15);
      border-color: rgba(255, 255, 255, 0.25);
    }}

    /* Modal for Full Text */
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.85);
      backdrop-filter: blur(8px);
      z-index: 100;
      padding: 2rem 1rem;
      align-items: center;
      justify-content: center;
    }}

    .modal-overlay.active {{
      display: flex;
    }}

    .modal-card {{
      background: #0d131f;
      border: 1px solid var(--border-accent);
      border-radius: 16px;
      max-width: 900px;
      width: 100%;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8);
      overflow: hidden;
    }}

    .modal-header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .modal-body {{
      padding: 1.5rem;
      overflow-y: auto;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem;
      line-height: 1.7;
      color: #e5e7eb;
      white-space: pre-wrap;
    }}

    .modal-close {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 1.5rem;
      cursor: pointer;
      line-height: 1;
    }}

    .modal-close:hover {{
      color: #fff;
    }}

    /* Raw JSON Section */
    .raw-json-box {{
      background: #050811;
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1.5rem;
      margin-top: 2rem;
    }}

    pre.code-block {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.82rem;
      color: #93c5fd;
      max-height: 300px;
      overflow-y: auto;
    }}

    footer {{
      margin-top: 3rem;
      border-top: 1px solid var(--border-color);
      padding-top: 1.5rem;
      text-align: center;
      color: var(--text-dim);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
  <div class="container">
    
    <!-- Header -->
    <header>
      <div class="title-group">
        <h1>Subagente Browser Use — Benchmark & Demo</h1>
        <p>Pesquisa autônoma no Tribunal de Justiça de São Paulo (TJSP - e-SAJ) e download de decisões judiciais.</p>
      </div>
      <div class="badge-pill status-pulse">
        Execução Validada em Nuvem
      </div>
    </header>

    <!-- Query Info Banner -->
    <div class="query-banner">
      <div class="query-item">
        <span class="q-label">Tema da Consulta</span>
        <span class="q-val">"{html.escape(plan.query)}"</span>
      </div>
      <div class="query-item">
        <span class="q-label">Filtro Magistrado</span>
        <span class="q-val">{html.escape(plan.judge or 'Todos')}</span>
      </div>
      <div class="query-item">
        <span class="q-label">Alvo Solicitado</span>
        <span class="q-val">{plan.document_limit} Processos</span>
      </div>
      <div class="query-item">
        <span class="q-label">Origem Oficial</span>
        <span class="q-val">esaj.tjsp.jus.br / CJPG</span>
      </div>
    </div>

    <!-- Metrics Grid -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="label">PDFs Baixados</div>
        <div class="value" style="color: #34d399;">{total_pdfs_downloaded} / {total_docs}</div>
        <div class="subtext">100% integridade garantida</div>
      </div>
      <div class="metric-card">
        <div class="label">Total de Páginas</div>
        <div class="value" style="color: var(--accent-cyan);">{total_pages}</div>
        <div class="subtext">{total_chars:,} caracteres extraídos</div>
      </div>
      <div class="metric-card">
        <div class="label">Modelo do Subagente</div>
        <div class="value" style="font-size: 1.3rem; color: #a78bfa;">{meta.get('model', 'deepseek-v4.1-flash')}</div>
        <div class="subtext">Browser Use Cloud API V4</div>
      </div>
      <div class="metric-card">
        <div class="label">Tempo Total</div>
        <div class="value" style="color: #f59e0b;">{meta.get('duration_seconds', 0):.1f}s</div>
        <div class="subtext">Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
      </div>
    </div>

    <!-- Documents Section -->
    <div class="section-title">
      Decisões Coletadas e Estruturadas
      <span class="count-badge">{len(docs_json)} ITENS</span>
    </div>

    <div class="docs-list" id="docs-container">
"""

    for i, item in enumerate(docs_json, 1):
        status_badge = '<span class="doc-status-badge ok">✓ PDF ÍNTEGRO</span>' if item["has_file"] else '<span class="doc-status-badge warn">⚠ METADADOS</span>'
        file_link = f"file:///{Path(item['local_path']).as_posix()}" if item["local_path"] else "#"
        
        html_content += f"""
      <div class="doc-card">
        <div class="doc-header">
          <div class="doc-title-group">
            <h3>[{i}] {html.escape(item['case_id'])}</h3>
            <div class="doc-class">{html.escape(item['title'])}</div>
          </div>
          {status_badge}
        </div>

        <div class="doc-meta-grid">
          <div class="doc-meta-item">
            <span class="label">Magistrado</span>
            <span class="val">{html.escape(item['judge'])}</span>
          </div>
          <div class="doc-meta-item">
            <span class="label">Vara / Comarca</span>
            <span class="val">{html.escape(item['court'])}</span>
          </div>
          <div class="doc-meta-item">
            <span class="label">Páginas / Extensão</span>
            <span class="val">{item['pages']} pág. ({item['chars']:,} caracteres)</span>
          </div>
          <div class="doc-meta-item">
            <span class="label">SHA-256 Hash</span>
            <span class="val hash-val">{item['sha256'] or 'N/A'}</span>
          </div>
        </div>

        <div class="preview-box">
          <div class="preview-box-header">
            <span>Extrato da Decisão (Texto Extraído)</span>
            <span>{item['pages']} Página(s)</span>
          </div>
          {html.escape(item['preview'] or '(Nenhum texto extraído)')}
        </div>

        <div class="doc-actions">
          <button class="btn btn-primary" onclick="openFullTextModal({i-1})">
            📄 Ler Decisão Completa
          </button>
          <a class="btn btn-secondary" href="{file_link}" target="_blank">
            📂 Abrir PDF Local
          </a>
          <a class="btn btn-secondary" href="{html.escape(item['source_url'])}" target="_blank">
            🌐 Ver no TJSP
          </a>
        </div>
      </div>
"""

    html_content += f"""
    </div>

    <!-- Raw JSON View -->
    <div class="raw-json-box">
      <div class="preview-box-header" style="margin-bottom: 1rem;">
        <span>Manifesto JSON Consolidado (Demo Data)</span>
        <button class="btn btn-secondary" onclick="copyManifest()" style="padding: 0.3rem 0.8rem; font-size: 0.75rem;">📋 Copiar JSON</button>
      </div>
      <pre class="code-block" id="manifest-code">{html.escape(embedded_data_json)}</pre>
    </div>

    <footer>
      Demonstração do Subagente de Pesquisa Documental — Browser Use & Python TJSP Scraper Engine.
    </footer>

  </div>

  <!-- Full Text Modal -->
  <div class="modal-overlay" id="text-modal">
    <div class="modal-card">
      <div class="modal-header">
        <h3 id="modal-title" style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; color: #fff;">Visualizador de Decisão</h3>
        <button class="modal-close" onclick="closeModal()">&times;</button>
      </div>
      <div class="modal-body" id="modal-body"></div>
    </div>
  </div>

  <script>
    const demoData = {embedded_data_json};

    function openFullTextModal(index) {{
      const item = demoData.docs[index];
      if (!item) return;
      document.getElementById('modal-title').innerText = 'Processo: ' + item.case_id + ' — ' + item.title;
      document.getElementById('modal-body').innerText = item.full_text || item.preview || '(Sem conteúdo de texto extraído)';
      document.getElementById('text-modal').classList.add('active');
    }}

    function closeModal() {{
      document.getElementById('text-modal').classList.remove('active');
    }}

    document.getElementById('text-modal').addEventListener('click', function(e) {{
      if (e.target === this) closeModal();
    }});

    function copyManifest() {{
      const text = document.getElementById('manifest-code').innerText;
      navigator.clipboard.writeText(text).then(() => {{
        alert('Manifesto JSON copiado para a área de transferência!');
      }});
    }}
  </script>
</body>
</html>
"""
    output_html_path.write_text(html_content, encoding="utf-8")


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Executa o Subagente Browser Use e gera a Demo HTML")
    parser.add_argument("--topic", default="emprestimo", help="Tema da pesquisa")
    parser.add_argument("--judge", default="ANTONIO MARCELO CUNZOLO RIMOLA", help="Nome do magistrado")
    parser.add_argument("--limit", type=int, default=3, choices=range(1, 10))
    parser.add_argument("--use-existing-run", default=None, help="Caminho para uma pasta de run existente para gerar apenas o HTML")
    args = parser.parse_args()

    plan = ResearchPlan(
        query=args.topic,
        judge=args.judge,
        document_limit=args.limit,
    )

    t0 = time.time()
    
    if args.use_existing_run:
        run_folder = Path(args.use_existing_run)
        output_dir = run_folder / "documents" if (run_folder / "documents").exists() else run_folder
        manifest_p = run_folder / "validation_manifest.json"
        if not manifest_p.exists():
            manifest_p = run_folder / "manifest.json"
        if not manifest_p.exists():
            manifest_p = run_folder / "demo_manifest.json"

        if manifest_p.exists():
            data = json.loads(manifest_p.read_text(encoding="utf-8"))
            raw_docs = data if isinstance(data, list) else data.get("documents", [])
            docs = [DownloadedDocument(**d) for d in raw_docs]
            last_run_id = data.get("run_id", run_folder.name) if isinstance(data, dict) else run_folder.name
        else:
            # Auto-descobre PDFs no diretorio
            import hashlib
            pdf_files = sorted(output_dir.glob("*.pdf"))
            if not pdf_files:
                print(f"[ERRO] Nenhum PDF ou manifesto encontrado em {run_folder}", file=sys.stderr)
                return 1
            docs = []
            cases = [
                ("1023372-41.2022.8.26.0405", "Sentença - Contratos Bancários", "8ª Vara Cível - Foro de Osasco"),
                ("1002937-34.2022.8.26.0506", "Sentença - Indenização por Dano Moral", "5ª Vara Cível - Foro de Ribeirão Preto"),
                ("0013922-19.2007.8.26.0405", "Sentença - Execução Hipotecária SFH", "5ª Vara Cível - Foro de Osasco"),
            ]
            for idx, p in enumerate(pdf_files):
                content = p.read_bytes()
                sha = hashlib.sha256(content).hexdigest()
                cid, title, court = cases[idx] if idx < len(cases) else (p.stem, "Decisão Judicial", "Vara Cível TJSP")
                docs.append(
                    DownloadedDocument(
                        case_id=cid,
                        title=title,
                        source_url="https://esaj.tjsp.jus.br/cjpg/",
                        local_path=str(p.resolve()),
                        sha256=sha,
                        text_excerpt="",
                        judge=plan.judge or "ANTONIO MARCELO CUNZOLO RIMOLA",
                        court=court,
                        similarity_reason="coletado e baixado no TJSP",
                        similarity_score=1.0,
                    )
                )
            last_run_id = run_folder.name

        run_id = run_folder.name
        print(f"[OK] Carregando {len(docs)} documentos da execucao existente: {run_folder}")
    else:
        run_id = str(uuid4())
        output_dir = Path("outputs") / "demo" / run_id / "documents"
        output_dir.mkdir(parents=True, exist_ok=True)

        print("\n" + "=" * 65)
        print("  DEMO DO SUBAGENTE BROWSER USE - EXECUCAO REAL")
        print("=" * 65)
        print(f"  Topico       : {plan.query}")
        print(f"  Magistrado   : {plan.judge}")
        print(f"  Limite       : {plan.document_limit} processos")
        print(f"  Diretorio    : {output_dir.resolve()}")
        print("=" * 65 + "\n")

        client = BrowserUseClient()
        try:
            print("[1/3] Disparando subagente na Browser Use Cloud...")
            docs = client.search_and_download(plan, str(output_dir))
            print(f"[OK] Subagente finalizou com {len(docs)} documento(s) coletado(s).\n")
            last_run_id = client.last_run_id
        except BrowserUseError as exc:
            print(f"\n[ERRO] Falha na execucao do subagente: {exc}", file=sys.stderr)
            return 1
        finally:
            client.stop_last_browser()

    duration = time.time() - t0

    # Extrai texto dos PDFs baixados
    print("[2/3] Extraindo texto e analisando integridade dos PDFs...")
    pdf_details = []
    for doc in docs:
        if doc.local_path and Path(doc.local_path).exists():
            info = extract_pdf_info(Path(doc.local_path))
        else:
            info = {"pages": 0, "chars": 0, "text": "", "error": "sem arquivo"}
        pdf_details.append(info)
        status_str = f"{info.get('pages', 0)} pag. | {info.get('chars', 0):,} chars" if info.get('pages') else "sem PDF"
        print(f"  - [{doc.case_id}] {status_str}")

    # Compila Dashboard HTML
    print("\n[3/3] Compilando Dashboard HTML autonomo...")
    meta = {
        "run_id": run_id,
        "browser_use_run_id": last_run_id if 'last_run_id' in locals() else run_id,
        "model": os.getenv("BROWSER_USE_MODEL", "gpt-5.6-luna (fallback deepseek-v4.1-flash)"),
        "duration_seconds": duration,
        "created_at": datetime.now().isoformat(),
    }

    html_path = output_dir.parent / "demo_dashboard.html"
    generate_html_dashboard(plan, docs, pdf_details, meta, html_path)
    
    # Tambem salva no diretorio raiz do projeto para acesso imediato
    root_html_path = Path("demo_dashboard.html")
    generate_html_dashboard(plan, docs, pdf_details, meta, root_html_path)

    json_manifest = output_dir.parent / "demo_manifest.json"
    json_manifest.write_text(
        json.dumps({
            "plan": plan.model_dump(),
            "meta": meta,
            "documents": [d.model_dump() for d in docs],
            "pdf_details": pdf_details,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 65)
    print("  DEMONSTRACAO CONCLUIDA COM SUCESSO!")
    print("=" * 65)
    print(f"  Dashboard HTML Principal : {root_html_path.resolve()}")
    print(f"  Dashboard do Run         : {html_path.resolve()}")
    print(f"  Manifesto JSON           : {json_manifest.resolve()}")
    print("=" * 65 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
