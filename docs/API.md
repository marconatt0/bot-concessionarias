# Contrato entre o Streamlit e o n8n

O Streamlit chama 4 webhooks do n8n pela URL do ngrok (`{url}/webhook/<nome>`).
Na VM, o Caddy só deixa passar esses 4 caminhos e confere o header `X-Bot-Token`
(qualquer outro caminho, incluindo o editor do n8n, responde 404).

Todas as chamadas levam:

```
X-Bot-Token: <token>
ngrok-skip-browser-warning: 1
```

## POST /webhook/bot-lote

Cria um lote novo. Apaga o lote anterior (linhas das filas e arquivo salvo).

```json
{
  "lote_id": "20261030-142501-a1b2c3",
  "enviado_por": "gerente",
  "arquivo_nome": "REPORT PADRÃO PROTOCOLOS.xlsx",
  "arquivo_b64": "<xlsx original em base64>",
  "linhas": [
    {"linha": 5, "site": "RSCAN01", "concessionaria": "RGE",  "uc_nova": "162996700103"},
    {"linha": 7, "site": "RSPEL02", "concessionaria": "CEEE", "uc_nova": "47921101087"}
  ]
}
```

O n8n deve:
1. Responder **409** `{"ok": false, "erro": "..."}` se `controle_bot` de alguma fila estiver `rodando`, `pausado` ou `aguardando_expiracao`.
2. Salvar o arquivo em `/files/lotes/<lote_id>.xlsx` e apagar o anterior.
3. Limpar `fila_ceee` / `fila_rge` e inserir as linhas (situacao `pendente`), guardando `linha` e `lote_id`.
4. Gravar o lote em `controle_bot` (lote_id, arquivo_nome, enviado_por, enviado_em) e colocar as duas filas com linhas em `rodando`.

Resposta: `200 {"ok": true, "lote_id": "..."}`

## GET /webhook/bot-resultado

```json
{
  "lote": {
    "lote_id": "20261030-142501-a1b2c3",
    "arquivo_nome": "REPORT PADRÃO PROTOCOLOS.xlsx",
    "enviado_por": "gerente",
    "enviado_em": "30/10/2026 14:25",
    "status": "rodando"
  },
  "filas": {
    "CEEE": {"status": "rodando", "linhas": [
      {"linha": 7, "site": "RSPEL02", "concessionaria": "CEEE", "uc_nova": "47921101087",
       "situacao": "protocolo", "protocolo": "protocolo já aberto", "previsao": "", "atualizado_em": "30/10/2026 14:31"}
    ]},
    "RGE": {"status": "pausado", "linhas": []}
  }
}
```

- Sem lote: `{"lote": null}`.
- `lote.status`: `rodando` enquanto alguma fila estiver `rodando`/`pausado`/`aguardando_expiracao`; `cancelado` após bot-cancelar; senão `concluido`.
- `situacao`: `pendente`, `em_andamento`, `aguardando_fim:<x>`, `protocolo`, `ja_aberto`, `sem_resposta`, `loop`, `uc_nao_encontrada`, `finalizada_sem_protocolo`, `interrompida`.
- Só `protocolo` e `ja_aberto` (com `protocolo` preenchido) são escritos na planilha.

## GET /webhook/bot-arquivo

`{"lote_id": "...", "arquivo_nome": "...", "arquivo_b64": "..."}` — o xlsx exatamente como foi enviado.

## POST /webhook/bot-cancelar

Coloca as duas filas em `cancelado`, marca as linhas `em_andamento` como `interrompida`
e mantém os protocolos já obtidos. Resposta: `{"ok": true}`.
