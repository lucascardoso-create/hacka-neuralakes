# 06 — API do backend e contrato com front no-code

Base `/v1`; JSON UTF-8; token servidor; tenant derivado da identidade autenticada, nunca confiado do corpo. Não entregar chaves de fornecedores ao front. Versionar OpenAPI gerada pelo FastAPI junto aos schemas. Os contratos desta seção são a base normativa da primeira implementação.

| Método/rota | Entrada | Resposta |
|---|---|---|
| POST /cases | title, text/document_ids, represented_side, success_definition, target_stage, target_claim_id, as_of_date | 201 CaseInput |
| POST /documents | multipart file + origin | 201 DocumentArtifact sem conteúdo sensível nos logs |
| POST /imports/drive | folder_id, selected_file_ids | 202 job_id |
| GET /cases/{id} | — | perfil + runs disponíveis |
| POST /cases/{id}/runs | mode, policy_version, budget, experiment_id? | 202 run_id, status_url |
| GET /runs/{id} | — | status, step, progress, result_ref, blockers |
| GET /runs/{id}/events?after=cursor | cursor, limit <= 100 | eventos ordenados + next_cursor |
| GET /runs/{id}/evidence | scope?, cursor? | evidências + comparações |
| GET /runs/{id}/result | — | AnalysisResult ou 409 result_not_ready |
| GET /runs/{id}/report | format=json/markdown | relatório versionado ou 409 |
| GET /runs/{id}/metrics | — | latência, chamadas, custo, qualidade disponível |
| POST /runs/{id}/cancel | reason | 202 cancel_requested |
| POST /runs/{id}/reviews | report_version, accepted/corrected/rejected, rationale, corrections | 201 Review |
| GET /connectors | — | catálogo, capabilities, configured, mode_supported |
| POST /benchmarks | dataset_id, variants, repeats, mode, budget | 202 experiment_id |
| GET /benchmarks/{id}/export | format=json/csv | manifesto e agregados sem dados pessoais |

Mutações de criação de runs/imports exigem Idempotency-Key. Respostas 401 identidade, 403 escopo, 404 inacessível/inexistente, 409 conflito, 413 tamanho, 422 contrato, 429 cota local, 503 dependência. Erro uniforme `{error:{code,message,retryable,request_id,details_safe}}`. Nunca incluir header Authorization ou resposta privada integral em erro.

## Interface futura

Ingestão expõe extraction_status, parser_name/version, missing_units e quality_flags. Erros definitivos sem texto utilizável: `unsupported_text_layer`; criptografia: `encrypted_pdf`. Documento parcialmente legível pode seguir com lacunas explícitas, mas ausência material bloqueia a decisão final. O front permite anexar versão textual alternativa; não oferece botão de OCR. Métricas incluem download_ms, parse_ms, normalize_ms, inference_ms, cpu_ms e peak_rss_bytes.

Tela de entrada pede documentos, parte representada e definição de êxito. Perfil extraído permite corrigir campos desconhecidos antes de iniciar coleta cara. Tela de execução apresenta nós/arestas do fluxo e eventos com status, tempo e custo por componente. Tela de resultado mostra p_repetitividade, classe derivada, p_exito, evidências e relatório. Tela benchmark compara variantes sobre o mesmo dataset. Tela governança mostra políticas efetivamente executadas e revisão.

Polling a cada 2–5 segundos no front é suficiente no P0; não depende de WebSocket. Eventos com sequence monotônica para reentrada. SSE pode ser implementado depois sobre o mesmo EventSink. `progress` é etapa concluída/etapas planejadas, não percentagem de tempo prometida.

## Evento estável

`{event_id,sequence,timestamp,run_id,step_id,parent_span_id,kind,status,message_safe,artifact_refs,metrics_delta}`. Tipos: run_started, step_started, tool_requested, tool_completed, evidence_collected, policy_evaluated, decision_ready, report_ready, review_recorded, run_blocked, run_finished. Mensagens sem texto integral dos autos.

## Exemplo de interação

Criar documento → criar caso → iniciar run `fixture` → consultar status/eventos → ler resultado/relatório → registrar revisão. Em `live`, missing_credential aparece antes de chamadas pagas. Revisar não reexecuta Browser Use/Jev. Corrigir o caso gera nova versão e novo run explicitamente.
