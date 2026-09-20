# 03 — Plugins e conectores claw

## Vocabulário

Plugin agrupa uma capacidade de negócio. Agente decide dentro dessa capacidade. Claw é o adaptador executável de uma ferramenta externa. Provider é o transporte/modelo subjacente. `saj_claw` não é um produto oficial do TJSP nem um protocolo judicial oficial; é o nome do nosso conector.

| Plugin | Claw/provider | Responsabilidade | MVP |
|---|---|---|---|
| legal_intake | `drive` | listar pasta autorizada e ler arquivos selecionados | P0; upload é fallback explícito |
| legal_intake | `document_parser` local | HTML/PDF textual/DOCX, páginas/blocos e hashes; sem OCR | P0 |
| judicial_research | `saj_claw` → Browser Use Cloud V4 | consulta de julgados em interface legada | P0 real |
| evidence_analysis | Neuralake | extração, plano, similitude | P0 |
| decision | Jev | probabilidades Noul | P0 |
| reporting | `docs_claw` | gerar Markdown/JSON; depois exportar Google Docs | local P0, remoto P1 |
| communications | `email_claw` | entrada de mensagem selecionada; rascunho de resumo | P2 |
| enterprise_context | `erp_claw` | contratos/faturas vinculados à demanda, via API | P2 |

A demo mínima já contém três ferramentas distintas: Drive, e-SAJ via navegador e relatório em arquivo. Não declarar email, ERP ou exportação Docs implementados por estarem no catálogo.

## Manifesto de conector

Campos: `id`, `version`, `plugin_id`, `transport` (api/browser/local), `operations`, `input_schema`, `output_schema`, `allowed_origins`, `credential_ref`, `read_only`, `timeout_s`, `max_attempts`, `budget_class`, `capabilities`, `data_categories`, `retention_policy`. Não incluir valor de credenciais. Toda operação recebe run_id/step_id/span_id, deadline e policy_context.

## saj_claw

Destino inicial: https://esaj.tjsp.jus.br/cjpg/ — Consulta de Julgados de Primeiro Grau do TJSP. Adequação: filtros de assunto, classe, magistrado, vara e intervalo temporal correspondem à hipótese. Consulta de julgados publicados não equivale a universo completo de processos e não comprova trânsito em julgado. Viés de publicação deve constar no relatório.

Operações: `search_decisions(ResearchPlan)`, `read_decision(candidate)`. O plano começa por tema + classe + juiz se conhecido; escopo pode ampliar para vara e depois tribunal. Registrar cada ampliação e manter os resultados separados por escopo. Não trocar tribunal silenciosamente. Máximo inicial: 2 planos, 3 páginas por plano, 20 candidatos únicos e 10 decisões aprofundadas. São parâmetros do aplicativo; não presumir suporte como campos do SDK.

Browser Use executa navegação com instrução delimitada e URL inicial conhecida. Saída esperada: filtros aplicados, resultados, URLs finais, metadados, trechos e artefatos acessíveis. “Concluído” do agente não basta: verificar formato, host, fonte e identidade da decisão. HTML da busca sozinho não é prova do teor da sentença.

Pesquisa não exige enviar toda a demanda: transmitir termos e filtros minimizados. Não enviar nomes/CPFs da demanda para consultas de similares. Não preencher peticionamento, protocolos ou ações de escrita. Em desafio de acesso ou login não autorizado, retornar `blocked_access`; registrar intervenção humana se ocorrer.

API confirmada pelo quickstart: `POST https://api.browser-use.com/api/v4/runs`, header `X-Browser-Use-API-Key`, corpo mínimo `{ "task": "..." }`. Usar SDK V4 para wait/status ou validar as rotas REST antes da implementação. Guardar ID remoto; tratar resposta final como dado não confiável. Polling, cancelamento, eventos, cobrança e encerramento devem ser testados contra a versão instalada. Webhook não é requisito P0; não assumir que webhook V2/V3 cobre V4.

A versão local implementará a mesma BrowserPort em worker Python com biblioteca Browser Use. Repetir o benchmark Cloud × local sobre as mesmas tarefas; reportar modelo de navegação, máquina e diferenças. Inferência Neuralake ilimitada não torna o agente hospedado Browser Use gratuito.

## drive_claw

Regra compartilhada de coleta: extrair inteiro teor do HTML/DOM já carregado quando disponível, guardando URL, bloco e snapshot. Ementa ou página de resultados não substitui decisão completa. Baixar PDF quando necessário e processar localmente. Downloads devem usar acesso autorizado, sem registrar cookies. Reutilizar sessão e artefatos para reduzir latência. HTML/PDF equivalentes são uma decisão, não duas observações. Screenshot comprova navegação, não é enviado a OCR documental. Essa regra não altera a eventual visão interna do agente de navegação do fornecedor.

Pasta de entrada fornecida: https://drive.google.com/drive/folders/17eJOtLW3E6e0SLHpC4QVEwg50cVBY_Aw . Listar metadados com paginação e selecionar arquivos; não ingerir a pasta inteira automaticamente. MIME determina leitor. Usar ID+versão/hash para deduplicar PDF/DOCX equivalentes. Arquivos sem acesso geram erro explícito. OAuth limitado à operação e pasta autorizadas; service account só se houver compartilhamento apropriado.

## docs_claw / email_claw / erp_claw

`docs_claw.render_report` local produz UTF-8 Markdown e JSON. Exportação remota separada (`publish_report`), com destino e revisão. Email futuro lê apenas mensagens selecionadas e gera rascunho; envio é operação distinta. ERP futuro lê contrato/fatura por ID conhecido e jamais altera saldo/cadastro no fluxo de pesquisa. Usar APIs quando disponíveis; reservar Browser Use para operações que realmente necessitam da interface.

## Tratamento de falhas comum

Envelope: `{code, message_safe, retryable, provider_status, external_id, artifact_refs, cost_status}`. Códigos: `missing_credential`, `blocked_access`, `budget_exceeded`, `rate_limited`, `timeout`, `external_status_unknown`, `invalid_output`, `no_results`, `source_unverifiable`. `no_results` não é falha técnica nem prova de não repetitividade.
