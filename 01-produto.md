# 01 — Proposta e requisitos

## Tese e unidade de valor

Uma garra (`claw`) encapsula acesso, ações permitidas, interpretação da interface e validação de evidência de uma ferramenta. A tese é que essa camada amplia as tarefas executáveis por agentes em sistemas sem integração utilizável para o caso de uso. Não afirmar que um tribunal não possui APIs apenas porque a interface é complexa.

Primeira instância vertical: departamentos jurídicos brasileiros, consulta de julgados de primeiro grau no TJSP. “DJs” é interpretado como departamentos jurídicos; a sigla não designa, nesta versão, um conector de Diário de Justiça. Nome de trabalho preservado: Instanke Jurídica.

Dois produtos de saída: repetitividade operacional e probabilidade de êxito na perspectiva da parte representada. Um relatório executivo une resultados, evidências e limitações. Repetitividade operacional não equivale ao reconhecimento formal de um tema repetitivo, IRDR ou precedente vinculante.

## Escopo P0

Entrada por texto, PDF textual, DOCX ou arquivo selecionado em pasta Drive. Um caso por execução. Extração de fatos/pedidos/valores/fase, plano de busca, coleta real `saj_claw`, seleção de comparáveis, Jev e relatório Markdown/JSON. Consulta de inteiro teor acessível e fontes citáveis. Logs e métricas por etapa e conector. Revisão humana final. API independente da interface.

P1: exportação Google Docs, biblioteca Browser Use local, mais portais. P2: email/ERP com leituras autorizadas e rascunhos. OCR não faz parte do MVP nem do roadmap contratado. Não construir marketplace, SSO multiempresa, banco vetorial, Kubernetes, treinamento preditivo ou agentes recursivos no hackathon.

Bootstrap: inteiro teor HTML quando acessível; PDF necessário segue para parser local `pypdf`, preservando páginas; DOCX por parser. Arquivo sem texto utilizável retorna `unsupported_text_layer`: buscar versão textual autorizada ou solicitar documento alternativo. Não disparar OCR/visão. O MVP roda na máquina local de desenvolvimento; desempenho e infraestrutura de deploy são hipótese a medir posteriormente.

## Requisitos rastreáveis

| ID | Requisito | Critério verificável |
|---|---|---|
| R01 | Preservar a demanda original e origem | hash, MIME, ID e versão presentes |
| R02 | Extração estruturada com lacunas explícitas | cada fato usado tem localização; desconhecidos são null |
| R03 | Pesquisa automática em site declarado | URL, filtros, horário e run externo registrados |
| R04 | Coleta verificável | evidência contém trecho, URL e artefato de origem |
| R05 | Comparação jurídica contextual | distingue fatos, pedido, tese e fase; registra diferenças |
| R06 | Jev retorna probabilidades contínuas | Noul finito no intervalo [0,1] para repetitividade e êxito |
| R07 | Triagem sim/não/inconclusivo | regra versionada deriva rótulo sem perder probabilidade |
| R08 | Relatório final Neuralake | números copiados do resultado validado; afirmações citadas |
| R09 | Benchmark reprodutível | fixtures/snapshots, versão, variante e manifesto exportáveis |
| R10 | Custos e tempo por chamada | falhas/retries incluídos; desconhecido não é zero |
| R11 | Governança observável | decisões de política, revisão e bloqueios em trilha |
| R12 | Frontend posterior desacoplado | REST documentada e sequência de eventos estável |
| R13 | Preservar integrações econômicas | replay não chama Browser Use/Jev; live tem orçamento |
| R14 | Parsing local sem OCR | ausência de texto explícita; documentos não são rasterizados para leitura |
| R15 | Medir processamento local | tempo de parsing, CPU, memória e cache exportáveis; custo de infraestrutura só entra após deploy definido |

## Definição de êxito

Obrigatório confirmar `represented_side` e `success_definition` antes da avaliação. Ex.: empresa ré, êxito = rejeição integral do pedido de indenização em primeiro grau. Procedência pode ser perda para a empresa; procedência parcial não é automaticamente vitória. Fixar `target_stage`, pedido-alvo e `as_of_date`. Havendo vários pedidos, o MVP escolhe um pedido-alvo ou suspende para desambiguação.

Não perguntar “a chance é alta?” para representar a chance de ganhar: isso mede a probabilidade de outra proposição. A pergunta Jev deve ser sobre a ocorrência do evento de êxito definido.

## Cenários de aceitação

- Caso completo e comparáveis pertinentes: pipeline produz probabilidades, evidências e relatório para revisão.
- Ausência de juiz: amplia pesquisa para vara/tribunal, registra escopo e não inventa comportamento do juiz.
- Portal indisponível: run parcial ou bloqueado; replay somente se explicitamente identificado.
- Evidência insuficiente: rótulo inconclusivo, probabilidade pública null com motivo; resposta bruta permanece auditável.
- Relatório com número diferente do resultado: rejeitar, regenerar uma vez e retornar relatório parcial estruturado se persistir.

## O que a demonstração deve mostrar

Uma demanda entra, o plano explica por que consultar o TJSP, `saj_claw` opera a interface, evidências aparecem, Jev decide, relatório fica pronto e o benchmark mostra custo/tempo/qualidade por componente. Sem benchmark executado, painel deve mostrar “não medido”.
