#!/bin/bash
# passo 9: diagnóstico das filas + CEEE "terminou sem protocolo" = protocolo já aberto
clear
C=whatsapp-n8n-1
RAW="https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/patch"
for f in manutencao.json decidir_ceee.js; do curl -fsSL -H 'Accept: application/vnd.github.raw' "$RAW/$f?ref=main&t=$(date +%s)" -o /tmp/$f || exit 1; docker cp /tmp/$f $C:/tmp/$f; done
CID=$(docker exec $C n8n list:workflow 2>/dev/null | grep '|bot-conversa-CEEE$' | cut -d'|' -f1)
docker exec $C n8n export:workflow --id=$CID --output=/tmp/ceee.json >/dev/null 2>&1
docker cp $C:/tmp/ceee.json /opt/bot-tunel/backup/conversa-CEEE-$(date +%Y%m%d-%H%M).json
docker exec $C node -e '
const fs=require("fs"); let w=JSON.parse(fs.readFileSync("/tmp/ceee.json","utf8")); const arr=Array.isArray(w); if(arr) w=w[0];
const d=w.nodes.find(n=>n.name==="Decidir"); d.parameters.jsCode=fs.readFileSync("/tmp/decidir_ceee.js","utf8");
fs.writeFileSync("/tmp/ceee-novo.json", JSON.stringify(arr?[w]:w)); console.log("Decidir CEEE atualizado:", d.parameters.jsCode.includes("valorFim"));'
docker exec $C n8n import:workflow --input=/tmp/ceee-novo.json >/dev/null 2>&1
docker exec $C n8n publish:workflow --id=$CID >/dev/null 2>&1
docker exec $C n8n import:workflow --input=/tmp/manutencao.json >/dev/null 2>&1
docker exec $C n8n publish:workflow --id=botManutencao001 >/dev/null 2>&1
for i in $(seq 1 12); do
  R=$(docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -w '\n%{http_code}' http://n8n:5678/webhook/bot-manutencao-7f3a)
  [ "$(echo "$R" | tail -1)" = "404" ] && sleep 5 || break
done
docker exec $C n8n unpublish:workflow --id=botManutencao001 >/dev/null 2>&1
echo "$R" | head -n -1 > /opt/bot-tunel/backup/diagnostico.json
docker run --rm -i python:3.12-slim python -c 'import json,sys
d=json.load(sys.stdin)
for c in d["controle"]: print("CTRL", c)
for k in ("CEEE","RGE"):
  print("==", k)
  for l in d[k]: print(f"{l[\"linha\"]:>3} {l[\"site\"]:8} {l[\"situacao\"]:22} {l[\"protocolo\"][:20]:20} rep={l[\"rep\"]} {l[\"em\"]} | {l[\"gatilho\"][:45]}" + (f"\n      ?? {l[\"desconhecida\"][:300]!r}" if l["desconhecida"] else ""))' < /opt/bot-tunel/backup/diagnostico.json
echo PASSO9-FIM
