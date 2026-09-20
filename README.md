# Neuralake · Instanke Jurídica

Repositório da especificação e do frontend do desafio Neuralake.

## Conteúdo

- `01-produto.md` a `11-parsing-bootstrap.md`: especificação, contratos, governança e plano de implementação.
- `schemas/`: schemas JSON versionados.
- `frontend/`: canvas de workflow inspirado no n8n, com componentes conectáveis e integração REST.

## Executar o frontend

```bash
cd frontend
npm install
npm run dev:api   # API fixture local em localhost:8000
npm run dev       # frontend em localhost:5173
```

Para um Quick Tunnel com frontend e API no mesmo endereço:

```bash
cd frontend
npm run dev:api
npm run dev:tunnel
cloudflared tunnel --url http://localhost:5173
```

O modo `fixture` implementa o contrato local para demonstração. As integrações live de Browser Use, Jev e Neuralake continuam dependendo das credenciais e adapters descritos na especificação.

## Entrada por Google Drive via tools-mcp

O backend Python pode iniciar o servidor `tools-mcp-drive` por stdio, validar que o arquivo pertence à pasta autorizada, baixar o artefato por hash e encaminhá-lo ao parser local.

Configure no `.env`:

```bash
TOOLS_MCP_DIR=/caminho/para/tools-mcp
TOOLS_MCP_DATA_DIR=/caminho/para/hacka-neuralakes/data/tools_mcp
GOOGLE_ACCESS_TOKEN=...
```

Ou use `GOOGLE_SERVICE_ACCOUNT_FILE`/`GOOGLE_TOKEN_FILE`, conforme o README do `tools-mcp`. Execute um PDF selecionado:

```bash
source .venv/bin/activate
python -m src.main \
  --drive-folder-id ID_DA_PASTA \
  --drive-file-id ID_DO_PDF \
  --document-limit 1
```

O MVP atual aceita PDF nesse caminho. O teste sem credencial verifica o contrato MCP e retorna `missing_credential` sem expor segredos; o teste live precisa de uma credencial Google autorizada e dos IDs da pasta e do arquivo.
