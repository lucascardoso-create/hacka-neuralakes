# 04 — Dados, persistência e invariantes

## Convenções

IDs UUID/ULID opacos, datas UTC ISO-8601, textos UTF-8, valores monetários em centavos + moeda, durações em milissegundos. `null` = desconhecido/não medido; 0 é valor observado. Probabilidades números finitos [0,1]. `schema_version`, `tenant_id`, `run_id` e proveniência obrigatórios. Exemplos deste pacote são sintéticos.

## Entidades

| Entidade | Campos essenciais |
|---|---|
| CaseInput | id, tenant_id, title, represented_side, success_definition, target_stage, target_claim_id, as_of_date, document_ids, source_refs |
| DocumentArtifact | id, origin, mime_type, size_bytes, sha256, storage_ref, source_version, extracted_text_ref, extraction_method, page_count, pii_categories |
| ParsedDocument | artifact_id, parser_name, parser_version, parser_config_hash, extraction_status, pages_or_blocks[], missing_units[], quality_flags[], cache_key, content_coverage_status |
| CaseProfile | case_id, court, division, judge, class, subjects[], facts[], claims[], values[], stage, legal_issues[], missing_fields[], source_refs[] |
| ResearchPlan | case_id, target_site, rationale, filters, queries[], expansion_order[], cutoff_date, max_candidates, budget, cross_jurisdiction |
| Evidence | id, source_url, final_url, fetched_at, decision_date, available_at, process_ref, court, division, judge, text_ref, quotes[], sha256, scope, source_verified |
| ComparativeAssessment | evidence_id, factual_similarity, legal_similarity, procedural_similarity, request_similarity, relevant, reasons[], distinctions[], evidence_refs[] |
| EvidencePack | id, version, case_profile_ref, cutoff_date, included_ids[], excluded_with_reason[], facts_for[], facts_against[], missing[], statistics, serialized_hash |
| RawDecision | provider, model_requested, model_returned, prompt_version, pack_hash, raw_response_ref, usage, evaluated_at |
| AnalysisResult | repetitividade, exito, outcome_probabilities opcional, abstention_reasons, evidence_ids, calibration_status, provenance |
| Report | version, result_ref, sections[], claims_with_refs[], numeric_fields, markdown_ref, verification_status |
| Review | reviewer_id, report_version, status, corrections[], rationale, reviewed_at |

Referência é `{artifact_id, page?, char_start?, char_end?, quote}`. Campo extraído não tem evidência só porque possui score alto. Registrar proveniência e texto verificável.

`extraction_method`: html_dom, pdf_text ou docx_text. Cada página/bloco tem ordinal, texto, contagem de caracteres, status e localização; conservar páginas vazias no mapa. Status: extracted, partial_text, unsupported_text_layer, encrypted_pdf, parse_failed, parse_timeout. Sem modalidade OCR. Cobertura distingue texto útil, parcial e completude desconhecida: caracteres não comprovam ausência de imagens relevantes. Tabelas ambíguas geram quality_flags, sem reconstrução inventada.

Cache de parsing: SHA-256 dos bytes + parser/version/config + tenant. Não há cache de decisão Jev no MVP. Mudança do parser invalida derivados. Sem deduplicação que exponha texto entre tenants. TTL padrão: 24 horas; registrar created_at, last_accessed_at, expires_at e bytes.

## Similaridade e estatística

No P0 até 20 candidatos, fazer comparação estruturada Neuralake sem banco vetorial. Scores de similaridade são escores de uma rubrica, não probabilidades. Peso exploratório: 0,35 fatos + 0,30 questão jurídica + 0,20 pedido + 0,15 fase. Rubricas/pesos versionados, escolhidos no conjunto de desenvolvimento. Divergência crítica de pedido/fase pode excluir mesmo com score alto.

Selecionar até 10 comparáveis, incluindo evidência contrária relevante. Se houver mais candidatos pertinentes do que contexto, declarar seleção e excluídos. Não truncar silenciosamente. Contar processos únicos e decisões únicas separadamente. Decisões de mesmo processo não são observações independentes.

Estatística descritiva por juiz, vara e tribunal: n_processes_unique, n_decisions, período, conhecidos/desconhecidos, favoráveis/desfavoráveis segundo a mesma definição de êxito. Taxa `favoráveis / desfechos conhecidos`; não dividir por documentos nem misturar desconhecidos no denominador. Não apresentar essa taxa como probabilidade calibrada do novo caso.

## Tabelas SQLite propostas

`cases`, `documents`, `case_documents`, `runs`, `steps`, `jobs`, `provider_calls`, `evidence`, `comparisons`, `evidence_packs`, `decisions`, `reports`, `reviews`, `events`, `policy_decisions`, `benchmark_cases`, `benchmark_runs`, `price_catalog`.

PK id; tenant_id em tabelas de negócio. FK para run/case/artefato. Índices `(tenant_id, case_id)`, `(run_id, sequence)`, `(job_status, lease_until)`, `(provider, external_id)`, `(document_sha256, tenant_id)`. Unique `(run_id, sequence)` em eventos e `(tenant_id, idempotency_key)` em solicitações. Foreign keys habilitadas. Transação curta ao reivindicar job; não segurar transação durante rede.

Texto grande/HTML/PDF fica em storage com SHA-256 e caminho relativo validado. JSON canônico no banco para versões de schema. Evitar embeddings até haver necessidade medida.

## Invariantes testáveis

1. Probabilidade ausente não vira 0,5; erro de parse não vira zero.
2. Noul não possui `confidence` separado; não inventar esse campo.
3. Dois Noul de resultados distintos não precisam somar 1. Não normalizar artificialmente.
4. Distribuição opcional Choice deve cobrir categorias exclusivas e totalizar 1 dentro de tolerância 0,001.
5. Mudança em entrada, pergunta, política, modelo ou pacote invalida cache de decisão.
6. Citação de juiz exige metadado verificado; sem juiz, scope não pode ser `judge`.
7. Resultados experimentais sempre marcam `calibration_status=not_validated` até avaliação independente.
8. Relatório referencia exatamente a versão de resultado revisada; alteração invalida revisão anterior.
