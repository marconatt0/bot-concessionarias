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

## Falta (lado da VM)

- Webhooks `bot-lote`, `bot-resultado`, `bot-arquivo`, `bot-cancelar` no n8n — contrato em [docs/API.md](docs/API.md).
- Caddy + ngrok no docker-compose da VM (domínio estático do ngrok, `BOT_TOKEN` e `NGROK_AUTHTOKEN` no `.env`).

> Não versione planilhas reais: elas têm CPF, telefone e endereços (`*.xlsx` está no `.gitignore`).
