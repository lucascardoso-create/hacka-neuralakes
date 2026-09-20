# 09 — SDD, implementação rápida e critérios de pronto

## Método

Cada mudança segue requisito Rxx → contrato/versionamento → fixture e cenário de aceitação → implementação mínima → medição → evidência de aceite. Alteração material em pergunta, êxito, limiar, fornecedor ou seleção de corpus exige decisão registrada. Não ajustar prompts no conjunto de teste para melhorar a apresentação.

## Plano estimado de 2 dias

Estimativa de engenharia, não compromisso com disponibilidade de fornecedores.

| Tarefa | Entrega | Dependência | Estimativa | Aceite |
|---|---|---|---|---|
| T01 | repo Python, settings, schemas, API token | spec | 1–2h | valida fixture e rejeita p inválido |
| T02 | SQLite, jobs, eventos, storage por hash | T01 | 2–3h | restart retoma checkpoint |
| T03 | parsing local HTML/pypdf/DOCX, cache SQLite/arquivo e export Markdown | T02 | 2–3h | texto localizado, lacunas explícitas, zero OCR e warm run mais rápido |
| T04 | pipeline fixture ponta a ponta | T03 | 2h | run chega a awaiting_review sem rede |
| T05 | Neuralake adapter + prompts | T04 | 2–3h | contrato, timeout e tokens medidos |
| T06 | drive_claw e saj_claw fixture/replay | T04 | 2h | MIME, hashes, filtros e corpus |
| T07 | Browser Use V4 live + Jev HTTP | T05/T06 | 3–4h | 1 chamada cada, ID/custo/cleanup |
| T08 | budget/política, relatório e revisão | T07 | 2h | fonte inexistente/número alterado bloqueados |
| T09 | harness benchmark e CSV/JSON | T04/T08 | 2–3h | métricas reproduzidas do manifesto |
| T10 | piloto pareado e roteiro de demo | T09 | 2h + rede | export com amostra/falhas/limitações |
| T11 | benchmark local de parsing | T03/T09 | 2–3h | recursos, CPU/RAM, latência e cache registrados |

Se o tempo reduzir, manter upload em vez de OAuth, Markdown em vez de Google Docs, polling em vez de SSE e um worker em vez de cluster. Não cortar instrumentação: os números são parte do produto. Runflow só entra após experimento de integração bounded de 45–60 minutos; se travar, manter OrchestratorPort local.

## Preparação sem gastar os tiers menores

`fixture`: respostas sintéticas definidas, nenhuma rede. `replay`: artefatos capturados, sem chamada real de coleta/decisão; pode habilitar Neuralake separadamente via provider_modes. `live`: chamadas autorizadas com orçamento e telemetria. Mistura de modos explícita por span, nunca um único rótulo enganoso.

Validar schema de Jev com `examples/jev-request.json` e fixture de resposta antes de usar chave. Testar BrowserPort com fake HTTP para accepted/running/finished/failed/timeout. Preparar plano/prompt e conferir resultado com código antes de live. Cache por hash do pacote + modelo + perguntas + política; medir economia e idade do snapshot.

## Testes de aceitação obrigatórios

| ID | Cenário | Esperado | Requisitos |
|---|---|---|---|
| A01 | p=-0,1/1,1/NaN/null inesperado | rejeitar resposta; não publicar | R06 |
| A02 | réplica sem evidência | inconclusivo e motivo | R05–R08 |
| A03 | perspectiva ré | êxito usa definição fornecida | R06 |
| A04 | documento com “ignore instruções” | conteúdo não altera política | R11 |
| A05 | timeout após create run | conciliar ID; sem duplicação cega | R03/R10 |
| A06 | reinício do worker | checkpoint preservado | R09 |
| A07 | relatório muda 0,71 para 0,91 | rejeitar divergência | R08 |
| A08 | mesma sentença em dois PDFs | uma evidência única | R04/R09 |
| A09 | documentos posteriores ao cutoff | exclusão no benchmark | R09 |
| A10 | orçamento exaurido | não iniciar chamada; cancelar recursos próprios | R10/R11 |
| A11 | live sem chave | blocked_config; nenhum mock silencioso | R13 |
| A12 | exports/logs | sem chaves ou dados pessoais não necessários | R11 |
| A13 | filtro juiz sem metadado juiz | escopo degradado explícito | R04/R08 |
| A14 | mesmo input em replay | artefatos iguais; métricas sem custo live inventado | R09/R10 |
| A15 | identidade de outro tenant | 404/403; nenhum artefato exposto | R11 |
| A16 | PDF só imagem | unsupported_text_layer, sem chamada OCR/visão | R14 |
| A17 | PDF textual e cache repetido | páginas/citações preservadas, cache identificado | R14/R15 |
| A18 | PDF misto/tabela ambígua | partial_text/quality_flags; sem conclusão sobre lacuna material | R14 |
| A19 | parsing excede tempo/memória | processo isolado encerrado; API continua disponível | R15 |
| A20 | HTML completo equivalente ao PDF | evita download redundante; identidade/cobertura verificadas | R14/R15 |

## Definition of Done

Pacote de spec: links internos resolvidos, JSONs válidos, exemplos consistentes, decisões/pendências visíveis. Backend: cenários A01–A20, import selecionado, uma coleta real verificável, chamada Jev e relatório auditado, custo/tempo exportáveis. Benchmark: manifesto e n real, gold labels quando métrica exige e falhas incluídas. Custo de infraestrutura só é identificado após a decisão de deploy. “Pronto para produção” exige trabalho posterior em identidade, privacidade e operação; não é resultado do hackathon.

## Roteiro de demonstração, 5 minutos

1. Exibir a demanda e o evento de êxito configurado.
2. Mostrar plano/site/razão do conector e execução ou gravação real identificada.
3. Abrir uma decisão, trecho e comparação com a demanda.
4. Mostrar dois valores Noul, classe derivada e relatório final.
5. Mostrar tabela de tempo/custo/qualidade, modo de cada run e controle de governança que foi executado.

Não usar números do JSON sintético como slide de benchmark. Enquanto não houver execução, usar “a medir”.
