#!/bin/bash
# passo 3: teste de ponta a ponta dos webhooks (com o bot-vigia desligado durante o teste)
clear
cd /opt/bot-tunel
T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
req() { docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w ' [%{http_code}]' \
  -H "X-Bot-Token: $T" -H 'Content-Type: application/json' "$@" | cut -c1-400; echo; }
VID=$(docker exec whatsapp-n8n-1 n8n list:workflow 2>/dev/null | grep '|bot-vigia$' | cut -d'|' -f1)
echo "== vigia $VID: $(docker exec whatsapp-n8n-1 n8n unpublish:workflow --id=$VID 2>&1 | tail -1)"
docker pull -q curlimages/curl:8.10.1 >/dev/null
B64=$(printf 'arquivo-de-teste' | base64)
BODY='{"lote_id":"teste-1","enviado_por":"teste","arquivo_nome":"teste.xlsx","arquivo_b64":"'$B64'","linhas":[{"linha":5,"site":"TESTE1","concessionaria":"CEEE","uc_nova":"000000"},{"linha":6,"site":"TESTE2","concessionaria":"RGE","uc_nova":"111111"}]}'
echo "== lote:";          req -X POST -d "$BODY" http://caddy/webhook/bot-lote
echo "== lote de novo:";  req -X POST -d "$BODY" http://caddy/webhook/bot-lote
echo "== resultado:";     req http://caddy/webhook/bot-resultado
echo "== arquivo (esperado $B64):"; req http://caddy/webhook/bot-arquivo
echo "== cancelar:";      req -X POST -d '{}' http://caddy/webhook/bot-cancelar
echo "== resultado:";     req http://caddy/webhook/bot-resultado
echo "== sem token:";     docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -o /dev/null -w '%{http_code}\n' http://caddy/webhook/bot-resultado
ls -la /opt/planilhas/lotes
echo "== vigia: $(docker exec whatsapp-n8n-1 n8n publish:workflow --id=$VID 2>&1 | tail -1)"
