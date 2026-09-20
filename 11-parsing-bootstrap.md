# 11 — Scraping, parsing e desenvolvimento local

## Caminho padrão

1. Coletar metadados e inteiro teor HTML já acessível; se completo, preservar snapshot/blocos e evitar download redundante.
2. Para arquivo PDF necessário, baixar uma vez, validar MIME/tamanho e calcular hash.
3. Consultar cache local segregado por tenant, bytes, parser, versão e opções.
4. Executar `pypdf` local em subprocesso, extraindo texto por página. DOCX segue leitor textual próprio.
5. Preservar texto bruto, gerar texto normalizado com mapeamento de localização e registrar lacunas.
6. Enviar texto à Neuralake para interpretação; consolidar evidências e seguir para Jev e relatório.

Sem OCR, rasterização ou transcrição por visão documental. PDF só imagem não contém texto extraível; retorna unsupported_text_layer. PDF com camada textual preexistente pode ser lido pelo parser, mesmo quando sua origem foi escaneada; isso não significa executar OCR neste sistema.

## Parser e qualidade

Escolha inicial `pypdf`; fixar versão após smoke test. `plain` é default. Testar `layout` como variante para tabelas/colunas difíceis, sem repetir extração em todos os arquivos. Escore simples de qualidade observa caracteres inválidos, vazio, linhas fragmentadas e ordem suspeita; baixo número de caracteres é sinal, não diagnóstico definitivo de imagem ou falha. Página em branco pode ser legítima.

Conservar todas as páginas e seus status. Valores monetários, datas e negações nunca são corrigidos por adivinhação. Quando texto não permite reconstruir uma tabela, marcar ambiguidade e preservar original. Se houver parte textual e parte ilegível, a análise pode prosseguir apenas sobre o que existe, com lacuna citada; decisão que dependa da parte ausente deve abster-se.

Pseudofluxo: validate → hash → cache → parse_pages → quality_flags → persist → semantic_extract. Nada de chamar LLM para extrair o que já está disponível como texto. Versão textual alternativa deve ter identidade e cobertura verificadas antes de substituir o documento.

## Cache deliberadamente pequeno

Usar arquivos locais para o ParsedDocument e SQLite para o índice. Redis não entra no MVP: acrescentaria processo, operação e dependência sem ganho relevante para uma API e um worker em uma VM, executando três vezes. O cache persiste entre a primeira, segunda e terceira análise do mesmo arquivo e reduz parsing a uma leitura local.

Chave: SHA-256 dos bytes + tenant + parser + versão + configuração. TTL de 24 horas. Na primeira execução, `cache_hit=false`; nas duas seguintes, `cache_hit=true` se bytes/configuração forem iguais. Limpar no fim da demo ou por TTL. Não cachear Browser Use ou Jev; usar `replay` com artefatos versionados quando a intenção for não gastar créditos.

## Local sem infraestrutura excessiva

Usar a máquina local, SQLite e diretório por run. No P0, API e execução podem compartilhar o processo; o worker persistente entra ao preparar deploy. Não expor storage diretamente a interfaces externas. Sem provisionamento nesta tarefa.

Configuração inicial proposta: pool de 2 processos de parsing, 60 segundos por documento, limite de 512 MiB por processo, 20 MB de upload e 100 páginas. São limites exploratórios configuráveis, não capacidade certificada. Contêiner/cgroup ou supervisão equivalente impõe teto real; excedentes retornam parse_timeout/parse_failed com motivo. CPU alta não elimina PDFs patológicos, latência de rede ou bloqueios do portal.

Separar concorrência CPU de concorrência Browser Use. Subir parsing acima de 1 só após medir pico de memória e throughput; não multiplicar chamadas pagas por haver capacidade local disponível. Capturar inventário efetivo de arquitetura, memória e CPU no manifesto.

## Medição

Para cada documento registrar download_ms, queue_ms, parse_ms, normalize_ms, cpu_ms, peak_rss_bytes, bytes, páginas, text_char_count, coverage_status, cache_hit, parser/version. Para pipeline, medir semantic_extraction_ms, decision_ms e report_ms à parte.

Documento pronto = texto e referências úteis persistidos; run pronto = relatório disponível para revisão. Comparar essas duas latências separadamente. Não somar duração de tarefas paralelas como duração do usuário.

Conjunto de 30 documentos versionados, com trechos de referência e tipos variados. Mesmos bytes nos testes plain/layout, 5 repetições por variante, warmup isolado, cache explícito. HTML só é comparável ao PDF quando conteúdo equivalente foi verificado. Exibir qualidade de campos/citações junto de desempenho e cobertura. Não afirmar parser mais rápido por uma medição que removeu páginas difíceis.

O benchmark do projeto mede execução de tarefas judiciais e processamento documental. Rankings públicos de modelos/provedores, quando citados, são contexto externo e não substituem estes números. Na etapa local, custo de compute fica nulo; custos de infraestrutura entram apenas no benchmark de deploy, com tarifa/hora, período, storage e tráfego atribuíveis.

## Pronto para implementação

T03 entrega parser/cache/contrato; T11 implanta na VM existente e roda medição. Sem backend implementado nem benchmark executado nesta revisão. Sem requisito de instalar OCR agora ou depois.
