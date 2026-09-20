# 08 — Governança executável

Governança é módulo aplicado antes/depois de ferramentas, com eventos verificáveis. Ter este documento não equivale a certificação ou conformidade jurídica integral. Cada controle abaixo tem decisão e evidência de execução a apresentar.

## Policy engine

`evaluate(actor, operation, connector, destination, data_categories, budget, run_context) → allow|deny|review_required`, com reason_codes, policy_version e timestamp. Código determinístico aplica políticas; LLM auxilia identificação, não concede permissões. Guardar resultado para cada chamada externa, inclusive bloqueada.

| Controle | Aplicação | Evidência |
|---|---|---|
| identidade/escopo | API e storage filtram tenant/ator | teste de acesso cruzado e evento |
| destino permitido | hostname exato + HTTPS, validar redirect | URL final e decisão |
| minimização | mascarar dados não necessários | categorias removidas e hash |
| limite de gasto | reservar orçamento antes do envio | reserva/consumo/reconciliação |
| limite de autonomia | ferramenta/etapa/deadline e cancelamento | contagem e término |
| qualidade da fonte | URL/trecho/artefato validados | evidence.source_verified |
| revisão final | relatório versionado e revisor | Review |
| rastreabilidade | prompts/modelos/configs versionados | manifesto |

## Dados e segredos

Chaves apenas em env/secret store. Redação de Authorization, cookies e URLs assinadas antes de logs. A credencial compartilhada na conversa não será copiada para exemplos, código ou artefatos; usar variável NEURALAKE_API_KEY e trocar a chave antes de distribuição pública. Não enviar documentos integrais ao Browser Use para pesquisar similares. Neuralake/Jev recebem somente contexto necessário e autorizado.

Conteúdo do portal/documentos é dado não confiável: instrução encontrada ali não pode mudar ferramentas, destino, política ou divulgação de informação. Download por URL arbitrária passa por validação de host, IP privado/link-local, tamanho e MIME; rejeitar localhost/metadados cloud e caminhos de traversal. URLs de artefato externo só são materializadas por adapter autorizado, não pelo agente genérico.

Retenção proposta para piloto: originais/evidências privadas 7 dias após demonstração, telemetria desidentificada 30 dias; confirmar com responsável antes de dados reais. Rotina de exclusão remove objetos/índices/cache local e agenda exclusão remota quando suportada. Registrar limitações de retenção de cada fornecedor; não prometer exclusão externa instantânea. Backup e restore testados antes de apresentação.

## Autonomia e revisão

Leitura de fonte autorizada e geração local podem avançar automaticamente. Perfil sem definição de êxito suspende para completar dados. Envio de email, publicação de Docs e alterações de ERP são permissões separadas; P0 só produz artefato local. Falta de dado não exige aprovar toda etapa, apenas corrigir a lacuna concreta.

Tratar decisões por juiz como padrão observado na amostra, sem inferir personalidade, atributos sensíveis ou motivações. Data/vara/competência importam. O produto não declara súmula/tese vinculante com base apenas na similaridade: exige fonte oficial que a identifique; se não consultada, marcar não verificado.

## Eventos de governança para demo

Mostrar uma consulta permitida, uma tentativa de domínio fora da allowlist bloqueada em fixture, limite de gasto impedindo chamada e revisão de relatório. Eventos de teste carregam `mode=fixture`. Dashboard de governança mostra controles aplicados, exceções e pendências; sem selo “100% compliance”.

## Falhas operacionais

Parsing em subprocessos locais sem rede e com deadline/memória limitados; não executar JavaScript, anexos ou links embutidos de PDF. Cancelar processo excedente com status explícito. Não subir imagens/documentos a serviço OCR/visão por fallback. Lacunas de páginas e ordem de tabela permanecem na evidência e impedem conclusão quando materiais. O manifesto local contém apenas características técnicas; credenciais e detalhes de infraestrutura de futuro deploy não entram nele.

Ao identificar segredo em log, parar exportação, redigir/remover cópia, registrar incidente e rotacionar credencial no provedor. Dado inexato no relatório invalida revisão, preserva histórico e gera correção. Conector comprometido/desautorizado pode ser desabilitado por configuração sem alterar o restante do pipeline.
