# Robô de protocolos — CEEE e RGE/CPFL

Interface em Streamlit para o gerente subir o **REPORT PADRÃO PROTOCOLOS**, mandar as UCs
para o robô do n8n (WhatsApp da Clara/CEEE e da CPFL/RGE) e baixar a **mesma planilha**
com a coluna **Protocolo** preenchida.

```
Streamlit Cloud ──HTTPS──> ngrok (domínio estático) ──> Caddy ──> n8n (VM)
                           só /webhook/bot-lote, bot-resultado, bot-arquivo, bot-cancelar
                           + header X-Bot-Token
```

## O que vai para o robô

Aba `TEMPLATE`, a partir do cabeçalho "Sites com Falha de AC", até a primeira linha sem site.

| Situação da linha | O que acontece |
|---|---|
| Concessionária CEEE, ou qualquer valor com "RGE" (RGE, RGE SUL…) | vai para o robô |
| Outra concessionária | fica como está |
| Protocolo já preenchido | fica como está |
| UC NOVA vazia, `#N/A` ou não numérica | fica em branco (pesquisar pelo endereço) |

Na volta só a célula Protocolo das linhas com protocolo é escrita. Fórmulas, PROCV,
formatação e as outras abas ficam byte a byte iguais ao arquivo enviado.

## Rodar localmente

```bash
pip install -r requirements.txt
BOT_MODO_DEMO=1 streamlit run app.py      # simulação, login demo/demo
pytest
```

## Publicar no Streamlit Cloud

1. New app → este repositório → `app.py`.
2. Settings → Secrets: cole o conteúdo de `.streamlit/secrets.toml.example` com os valores reais
   (URL do ngrok, token, hash bcrypt da senha do gerente).

## Lado da VM

Tudo em [`vm/`](vm/):

- `gerar_webhooks.py` gera os workflows `bot-lote`, `bot-resultado`, `bot-arquivo` e `bot-cancelar` (`vm/n8n/`),
  importados com `n8n import:workflow` e publicados com `n8n publish:workflow`. Contrato em [docs/API.md](docs/API.md).
- `docker-compose.yml` + `Caddyfile`: stack separada `bot-tunel` em `/opt/bot-tunel`, na rede `whatsapp_default`.
  O Caddy só deixa passar os 4 webhooks com o header `X-Bot-Token`; o ngrok publica o Caddy no domínio estático.
- `/opt/bot-tunel/.env` (não versionado): `BOT_TOKEN` (gerado na VM), `NGROK_DOMAIN`, `NGROK_AUTHTOKEN`.

Ligar o túnel depois de preencher o `.env`:

```bash
cd /opt/bot-tunel && docker compose --profile tunel up -d
```

> Não versione planilhas reais: elas têm CPF, telefone e endereços (`*.xlsx` está no `.gitignore`).
