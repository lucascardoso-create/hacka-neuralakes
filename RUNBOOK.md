# Fluxo de triagem jurídica

## Configuração local

Copie `.env.example` para `.env` e configure `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` e `BROWSER_USE_API_KEY`. Credenciais ficam somente no ambiente local.

## Execução

```powershell
python -m src.main --demand "texto que chegou do Browser Use" --document-limit 3
```

O grafo executa: entrada da demanda → normalização → plano de busca → Browser Use baixa a quantidade configurada de PDFs → extração do texto → Neuralake classifica → manifesto da execução.

O arquivo `outputs/runs/<run_id>/manifest.json` contém `assessment` com:

- `repetitividade.label`: `sim`, `nao` ou `inconclusivo`;
- `exito.probability`: número de 0 a 1 ou `null` se não houver evidência suficiente;
- `evidence_ids`, limitações e trilha de auditoria.

A inferência acontece com um ou mais PDFs baixados e texto extraível, usando todos os que estiverem disponíveis. Sem nenhum texto extraível, ela se abstém. A classificação permanece experimental (`calibration_status: not_validated`) e exige revisão humana.
