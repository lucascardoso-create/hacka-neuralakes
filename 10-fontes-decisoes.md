# 10 — Fontes, ADRs e pendências

Consulta documental em 19/09/2026. Nenhuma chamada paga de Browser Use/Jev ou inferência Neuralake foi executada para produzir esta spec. Nenhum resultado empírico foi medido. Os arquivos Drive foram inventariados por metadados; seu conteúdo não foi analisado nesta entrega.

## Fontes primárias

Revisão 0.3: desenvolvimento local primeiro; a infraestrutura de deploy será decidida após o benchmark do pipeline. [Documentação oficial pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) consultada: extração textual e modo layout; imagens sem texto não são transcritas; conteúdo PDF pode exigir memória elevada. Não há comparação de latência executada neste projeto; velocidade é hipótese do benchmark. OCR retirado do roadmap, sem fallback automático.

| Fonte | Verificado | Limite da verificação |
|---|---|---|
| [TypeSafe Introduction](https://docs.typesafe.ai/introduction) | perguntas tipadas | não valida domínio jurídico |
| [Noul](https://docs.typesafe.ai/primitives/noul) | saída 0–1 sem confidence separado | probabilidade não garante calibração local |
| [Quickstart Jev](https://docs.typesafe.ai/introduction/quickstart) | endpoint e envelope state/model/questions | acesso/saldo da conta não consultados |
| [Browser Use Cloud](https://docs.browser-use.com/cloud/quickstart) | Agent Cloud V4 e biblioteca local separados | disponibilidade da conta não testada |
| [Índice Browser Use](https://docs.browser-use.com/llms.txt) | recursos de eventos, crédito e lifecycle | schema completo de cada operação precisa ser validado no adapter |
| [Get Run](https://docs.browser-use.com/cloud/api-v4/runs/get-run) | referência de leitura de execução | não executado |
| [Neuralake API](https://www.neuralake.com.br/api) | base URL, modelo por capacidade e exemplo compatible | recursos opcionais e franquia não testados |
| [Runflow SDK](https://www.npmjs.com/package/%40runflow-ai/sdk) | pacote TypeScript, agentes/workflows/tools/traces | install não executado; consulta npm local falhou por cache |
| [Runflow contexto](https://docs.runflow.ai/core-concepts/context-management) | associação de contexto a memória/traces | divergência de versões docs/pacote: fixar versão no spike |
| [TJSP CJPG](https://esaj.tjsp.jus.br/cjpg/) | formulário e filtros correspondentes ao projeto | busca interativa não executada |

## Inventário Drive observado

[Pasta raiz](https://drive.google.com/drive/folders/17eJOtLW3E6e0SLHpC4QVEwg50cVBY_Aw) contém instruções PDF/DOCX, materiais centrais, complementares e modelos opcionais. [Materiais centrais](https://drive.google.com/drive/folders/14hW8F0wKpQ3AE50XVDzeYfS1fS2IyaKi) contém planilha, Caso 01 e Caso 02. Não usar a planilha como gold antes de examinar campos, rótulos e datas.

[Caso 01](https://drive.google.com/drive/folders/1CxDaU3hFrXa-yjztg_a9UXA-fI-R58aD): sete PDFs identificados por nome — autos, contrato, extrato bancário, comprovante de crédito, dossiê, demonstrativo de dívida e laudo referenciado. Os nomes informam formatos de entrada, não confirmam fatos ou autenticidade.

Não há base nesta inspeção para afirmar que o Caso 01 seja do TJSP. O adapter deve verificar jurisdição no documento; se pesquisar TJSP para outro tribunal, marcar `cross_jurisdiction=true`, `scope=analogous` e impedir declaração de histórico do próprio juiz. O corpus da demo pode usar demanda sintética contextualizada para TJSP ou pesquisa analógica explicitada, sem reescrever fatos do material original.

## Decisões arquiteturais

| ADR | Decisão | Razão e alternativa |
|---|---|---|
| 001 | Jev é o decisor central do MVP | preserva desenho do usuário; modelo treinado separado é melhoria futura, não dependência |
| 002 | Noul para p de êxito definido | evita binning arbitrário; Choice só para distribuição opcional |
| 003 | Python/FastAPI + SQLite | menos infra e compatibilidade futura com Browser Use local; Postgres/queue depois |
| 004 | Runflow opcional | sugerido pelo usuário como base possível; SDK TypeScript adicionaria runtime ao MVP Python |
| 005 | Browser Use Cloud primeiro | menor setup; adapter permite trocar para local e comparar |
| 006 | corpus pequeno sem vetores | até 20 decisões cabem em comparação direta; medir antes de ampliar |
| 007 | replay + telemetria próprios | reduzir gasto e manter números auditáveis independentemente do SDK |
| 008 | backend somente nesta entrega | frontend no-code posterior por REST/eventos |
| 009 | HTML/PDF textual por parser local, sem OCR | bootstrap de baixa latência; ausência de texto gera status explícito |
| 010 | desenvolvimento local antes de deploy | medir pipeline e contratos primeiro; shape, tarifa e operação serão decididos depois |

Se equipe já domina Runflow, alternativa válida é TypeScript end-to-end com runtime do SDK e SQLite, preservando exatamente os contratos, políticas e artefatos. No spike confirmar custom base URL Neuralake, exportação de eventos, retries, contexto isolado por run, persistência e lifecycle. Não adotar RPA do SDK em substituição silenciosa ao Browser Use, pois alteraria a tese medida.

## Pendências que não bloqueiam começar fixtures

Confirmar tribunal real do caso selecionado; definição de êxito e parte representada; rótulos históricos disponíveis; chaves/saldo e política de dados dos fornecedores; billing/free credits específicos da conta; versões efetivas dos modelos; esquema final de lifecycle/custos Browser Use; suporte Neuralake a non-stream e usage; escolha de frontend no-code posterior.

Créditos Browser Use não são tratados como tier gratuito ilimitado. Benefício Neuralake informado pelo usuário é hipótese de faturamento a conferir, sem remover timeouts/limites de execução. O objetivo atual é preparar documentação e contratos; chamadas live pertencem à etapa de implementação T07.
