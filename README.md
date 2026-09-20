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
