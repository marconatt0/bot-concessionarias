#!/bin/bash
# passo 12: reseta as filas CEEE e RGE para um teste novo
clear
C=whatsapp-n8n-1
curl -fsSL -H 'Accept: application/vnd.github.raw' "https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/patch/reset.json?ref=main&t=$(date +%s)" -o /tmp/reset.json || exit 1
docker cp /tmp/reset.json $C:/tmp/reset.json
docker exec $C n8n import:workflow --input=/tmp/reset.json >/dev/null 2>&1
docker exec $C n8n publish:workflow --id=botManutencao001 >/dev/null 2>&1
for i in $(seq 1 12); do
  R=$(docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w '\n%{http_code}' http://n8n:5678/webhook/bot-manutencao-7f3a)
  [ "$(echo "$R" | tail -1)" = "404" ] && sleep 5 || break
done
docker exec $C n8n unpublish:workflow --id=botManutencao001 >/dev/null 2>&1
echo "== dados do controle (sem mostrar valores):"; echo "$R" | head -n -1
rm -f /opt/planilhas/lotes/atual.json /opt/planilhas/lotes/atual.xlsx
cd /opt/bot-tunel; T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
echo "== resultado agora:"; docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w ' [%{http_code}]\n' -H "X-Bot-Token: $T" http://caddy/webhook/bot-resultado
echo PASSO12-FIM
