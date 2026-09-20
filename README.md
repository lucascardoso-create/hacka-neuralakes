# Neuralake Frontend · Vercel

Branch isolada para publicar somente a interface React/Vite na Vercel.

## Configuração na Vercel

- Framework: **Vite**
- Build command: `npm run build`
- Output directory: `dist`
- Install command: `npm ci`

Se a API estiver publicada em outro endereço, cadastre a variável de ambiente:

```text
VITE_API_URL=https://seu-backend.exemplo.com/v1
```

Sem `VITE_API_URL`, a interface tenta acessar `/v1` no mesmo domínio da Vercel. A tela carrega, mas execução e status dependem de uma API compatível.

As variáveis `VITE_*` são incorporadas ao frontend e ficam visíveis no navegador. Nunca coloque chaves de LLM, Browser Use ou Google nelas.
