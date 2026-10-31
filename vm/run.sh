#!/bin/bash
# passo 4: limpa o lote de teste e baixa a imagem do ngrok
clear
rm -f /opt/planilhas/lotes/atual.json /opt/planilhas/lotes/atual.xlsx
cd /opt/bot-tunel
for f in Caddyfile docker-compose.yml; do
  curl -fsSL -H 'Accept: application/vnd.github.raw' "https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/$f?ref=main&t=$(date +%s)" -o $f
done
docker pull -q ngrok/ngrok:latest
docker compose up -d caddy 2>&1 | tail -1
docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w ' [%{http_code}]\n' \
  -H "X-Bot-Token: $(grep ^BOT_TOKEN= .env | cut -d= -f2)" http://caddy/webhook/bot-resultado
grep -c . .env; grep -o '^[A-Z_]*=' .env
echo PASSO4-OK
