#!/bin/bash
# passo 2: importa e publica os webhooks no n8n e testa pelo Caddy
clear
RAW="https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm"
get() { curl -fsSL -H 'Accept: application/vnd.github.raw' "$RAW/$1?ref=main&t=$(date +%s)" -o "$2"; }
mkdir -p /opt/bot-tunel/n8n && cd /opt/bot-tunel
for w in bot-lote bot-resultado bot-arquivo bot-cancelar; do get n8n/$w.json n8n/$w.json || exit 1; done
echo "== status atual das filas:"
docker exec whatsapp-n8n-1 sh -c 'true'
docker cp n8n/. whatsapp-n8n-1:/tmp/bot-webhooks/
docker exec whatsapp-n8n-1 n8n import:workflow --separate --input=/tmp/bot-webhooks --projectId=g7NSooy85ZuYWBNa 2>&1 | tail -4
for id in botWebhookLote01 botWebhookResul1 botWebhookArqui1 botWebhookCance1; do
  docker exec whatsapp-n8n-1 n8n publish:workflow --id=$id 2>&1 | tail -1
done
sleep 3
T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
echo "== resultado com token:"; docker compose exec -T caddy wget -qSO- --header "X-Bot-Token: $T" http://localhost/webhook/bot-resultado 2>&1 | head -5
echo; echo "== resultado sem token:"; docker compose exec -T caddy wget -qSO- http://localhost/webhook/bot-resultado 2>&1 | head -2
