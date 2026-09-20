# 07 — Benchmark e números da tese

## Hipóteses falsificáveis

H1: adicionar `saj_claw` aumenta conclusão verificada de pesquisas judiciais em comparação ao agente sem navegação. H2: o conector especializado melhora custo por pesquisa válida em relação a Browser Use com instrução genérica. H3: evidências recuperadas melhoram repetitividade/êxito em relação a avaliar só a demanda. H4: o relatório reduz esforço humano mantendo cobertura de citações. H5: governança limita ações e custos sem impedir pesquisas permitidas.

Nenhuma hipótese está comprovada nesta documentação. Campos de resultados começam vazios. Demonstração de uma tarefa comprova viabilidade pontual; não generalizar confiabilidade ou calibração.

## Variantes

| Código | Variante | Isola |
|---|---|---|
| A | Neuralake sem claw, mesmos objetivos e orçamento | capacidade sem ferramenta web |
| B | Browser Use com tarefa genérica | valor do navegador sem especialização |
| C | `saj_claw` + verificações + fluxo completo | valor da garra especializada |
| D | Mesma C com snapshots em replay | custo/qualidade das etapas posteriores |
| E | Mesmo EvidencePack decidido por Neuralake | ablação do Jev |
| F | Jev sobre demanda sem comparáveis | contribuição da evidência |
| H | Analista humano com mesma tarefa e janela | tempo e qualidade de referência |

A comparação A × C mede acesso à ferramenta; não demonstra que o conector é melhor que navegação genérica. B × C é necessária para essa segunda afirmação. E × C deve usar pacote idêntico, mesma pergunta e mesmos rótulos. Não comparar live com replay como se ambos tivessem pago navegação.

## Plano econômico de experimentos

1. Criar 12 tarefas de navegação: busca por tema, filtro por juiz, vara, data, leitura de decisão e ausência de resultados; duas instâncias de cada família. Registrar IDs-alvo/critério esperado por inspeção humana.
2. Desenvolver com 30 demandas sintéticas ou desidentificadas e fixtures; Neuralake pode gerar variações, mas não verdade jurídica. Separar desenvolvimento e teste antes de ajustar prompts.
3. Smoke test live de 1 tarefa Browser Use e 1 Jev sobre contexto sintético. Conferir payload, saída, custo e limpeza de recursos.
4. Piloto real: 3 tarefas B e C, depois expandir para 12 pareadas se saldo permitir. Ordem aleatória/intercalada para reduzir efeito do horário do portal. 3 repetições são desejáveis; com 1, reportar exatamente n e ausência de medida de estabilidade.
5. Salvar evidências uma vez; executar D/E/F em replay sem recolher o mesmo corpus. Limitar inicialmente a 1 chamada Jev consolidada por pacote e a 10 chamadas Jev no experimento piloto.
6. Para avaliar probabilidade de êxito, usar casos históricos com resultado conhecido e cutoff anterior ao desfecho. Sem rótulos suficientes, medir pipeline e deixar Brier/calibração como indisponíveis.

## Rótulos e prevenção de vazamento

Cada item possui `dataset_version`, `case_id`, `group_id`, `split`, `as_of_date`, `represented_side`, `success_definition`, `gold_repetitive`, `gold_success`, `gold_relevant_evidence_ids`, `annotator_ids`, `adjudication_status`. Dois revisores nos casos de teste e resolução de divergência; se um só estiver disponível, registrar limitação. Desfecho ausente não recebe rótulo negativo.

Dividir por processo/família, não por PDF: documentos do mesmo caso não atravessam splits. Avaliação temporal exclui sentença-alvo, documentos posteriores e evidências não disponíveis no cutoff. `available_at` desconhecido exclui do benchmark temporal estrito. Ocultar respostas de referência dos prompts e da geração do relatório. Casos repetidos não aumentam n independente.

## Instrumentação por chamada

Registrar: trace_id, run_id, span_id, parent_span_id, agent_id, plugin_id, claw_id, provider, operation, mode, model_requested/returned, prompt_version, input_hash, cache_hit, attempt, queue_ms, request_ms, ttft_ms, total_ms, browser_seconds, tokens_in/out/cached, token_source, bytes_in/out, steps_observed, pages_visited, candidates, unique_evidence, verified_evidence, status, error_code, intervention_count e cost_status.

Quando fornecedor não expõe passos/tokens, usar null. Estimativa por tokenizer deve ser marcada `estimated`, sem fingir contagem faturada. UTC para correlação; relógio monotônico para duração. Parallelismo: tempo total é parede, não soma de spans. Soma de spans é trabalho acumulado. Não somar custo do span pai ao das chamadas filhas.

## Fórmulas

- Sucesso de pesquisa = tarefas com critério externo satisfeito / todas as tarefas tentadas, incluindo falhas.
- Cobertura autônoma = tarefas concluídas sem intervenção / tentadas.
- Precisão@k = evidências relevantes entre as k revisadas / k (k efetivamente retornado informado).
- Recall apenas contra pool de referência definido; não chamar “recall de todo o tribunal”.
- Cobertura de citação = afirmações materiais com referência verificada / afirmações materiais totais.
- Repetitividade: matriz de confusão, macro-F1, precisão/recall por classe; abstenção separada. Reportar cobertura de decisões e erro condicionado à não abstenção.
- Êxito: Brier = média((p-y)^2), log loss com epsilon 1e-6, gráfico de calibração com bins e n por bin. Brier avalia acurácia probabilística global, não calibração isolada. Comparar à prevalência do conjunto de treino; não estimar baseline a partir do teste.
- Economia de tempo = 1 - tempo_assistido/tempo_manual em tarefas pareadas. Tempo assistido inclui revisão humana, espera e correções.
- Custo por tarefa válida = custo de todas as tentativas / tarefas verificadas com sucesso. Se zero sucessos, métrica indefinida, não zero.
- Latência p50/p95, dispersão e n; para amostras muito pequenas publicar tempos individuais e marcar p95 instável.

Incerteza: intervalo Wilson para taxa de sucesso, bootstrap por caso para diferenças pareadas e métricas agregadas. Não tratar várias chamadas do mesmo caso como amostras independentes. Estratificar por assunto/juiz apenas quando há amostra identificável; não divulgar ranking pessoal.

## Custo pago, consumo de crédito e custo de referência

### Parsing e infraestrutura local

Adicionar spans download, parse, normalize e inferência; medir wall_ms, cpu_ms, peak_rss_bytes, bytes, páginas totais/com texto, qualidade e cache_hit. Registrar shape, arquitetura CPU, vCPUs/OCPUs conforme provedor, RAM, SO, versão do parser e concorrência. Nenhum benchmark de parser foi executado nesta revisão.

Comparar HTML completo, PDF textual sem cache e o mesmo PDF com cache; comparar também pypdf plain/layout sobre bytes idênticos. Para o MVP, medir um cold run e duas repetições warm por documento — exatamente o padrão de três execuções previsto. Expandir para 30 documentos, aquecimento separado e 5 repetições só se houver tempo. Testar concorrências 1, 2 e 4 se houver capacidade. Fixar arquivos e reportar cache do aplicativo e do SO; não chamar warm run de cold. Download medido à parte evita atribuir lentidão do portal ao parser. OCR não integra estas variantes.

Qualidade: checar pedidos, valores, negações, identificação do juiz e citações contra trechos de referência revisados. Publicar completude/ordem de leitura e taxa de documentos aceitos junto de p50/p95, páginas/s, documentos/s e CPU/RAM. Documentos de imagem recusados entram na taxa de cobertura; não removê-los do denominador silenciosamente. Tokens gratuitos não dispensam avaliar tempo de inferência nem capacidade máxima de contexto.

Custo local: registrar SO, CPU, memória, versões e concorrência para reprodutibilidade, mas manter `compute_allocated_usd=null`. Não atribuir custo de uma máquina pessoal ao custo do navegador ou da inferência. Quando o deploy for escolhido, adicionar tarifa/hora, storage/tráfego atribuíveis e regra de rateio sem reescrever resultados do piloto local.

Manter `billed_usd`, `credits_consumed_usd`, `reference_usd`, `price_version`, `measurement_source` e `reconciled_at`. Hackathon pode ter billed=0 confirmado, mas reference continua estimado. Ausência de fatura = billed null.

Custo de inferência estimado = tokens_entrada × tarifa_entrada/1e6 + tokens_saída × tarifa_saída/1e6. Adicionar custos de cache/raciocínio quando expostos. Browser Use: separar inferência do agente, navegador, tráfego e orquestração conforme cobrança efetiva; preço global reportado não pode ser somado de novo a seus componentes. Acesso ilimitado Neuralake não cobre os outros fornecedores.

Catálogo de preços manual versionado por provedor/modelo/moeda/data/fonte. Se tarifa não validada, reference=null e `pricing_unavailable`; nenhuma tarifa inventada. Reconciliar métricas imediatas com painel/fatura; consumo pode chegar atrasado.

## Critérios do piloto (metas, não resultados)

100% de probabilidades válidas e origem rastreável; 100% de chamadas caras com span; zero segredos em exportações; zero evidências inventadas no relatório aceito; >=80% conclusão verificada de navegação como meta exploratória em 12 tarefas; reportar intervalo e falhas mesmo se a meta não for alcançada. Não estabelecer meta de acurácia judicial sem dataset rotulado.

Entregáveis do benchmark: `manifest.json`, `runs.jsonl`, `provider_calls.csv`, `quality_labels.csv`, `summary.json`, `benchmark-report.md`. Manifesto contém commit, versões/config/prompts/hashes, período, hardware se local, regras de seleção, divisão e despesas. Todas as tabelas da apresentação vêm desses arquivos.
