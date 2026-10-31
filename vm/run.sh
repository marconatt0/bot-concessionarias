#!/bin/bash
# passo 8: grava a regra 250 e marca RSHVL01 como protocolo já aberto (workflow temporário, só interno)
clear
C=whatsapp-n8n-1
curl -fsSL -H 'Accept: application/vnd.github.raw' "https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/patch/manutencao.json?ref=main&t=$(date +%s)" -o /tmp/manutencao.json || exit 1
docker cp /tmp/manutencao.json $C:/tmp/manutencao.json
docker exec $C n8n import:workflow --input=/tmp/manutencao.json 2>&1 | grep -iE 'import|error' | tail -1
docker exec $C n8n publish:workflow --id=botManutencao001 2>&1 | tail -1
sleep 3
echo "== resultado:"
docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w ' [%{http_code}]\n' http://n8n:5678/webhook/bot-manutencao-7f3a
docker exec $C n8n unpublish:workflow --id=botManutencao001 2>&1 | tail -1
echo PASSO8-FIM
