#!/bin/bash
# passo 7: CEEE "Pronto, reforçamos sua solicitação" -> protocolo já aberto e próxima UC
clear
RAW="https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/patch"
get() { curl -fsSL -H 'Accept: application/vnd.github.raw' "$RAW/$1?ref=main&t=$(date +%s)" -o "/tmp/$1"; }
get decidir_ceee.js && get ajuste-regra-250.json || exit 1
C=whatsapp-n8n-1
docker cp /tmp/decidir_ceee.js $C:/tmp/decidir_ceee.js
docker cp /tmp/ajuste-regra-250.json $C:/tmp/ajuste-regra-250.json
CID=$(docker exec $C n8n list:workflow 2>/dev/null | grep '|bot-conversa-CEEE$' | cut -d'|' -f1)
echo "== conversa-CEEE: $CID"
mkdir -p /opt/bot-tunel/backup
docker exec $C n8n export:workflow --id=$CID --output=/tmp/ceee.json 2>&1 | tail -1
docker cp $C:/tmp/ceee.json /opt/bot-tunel/backup/conversa-CEEE-$(date +%Y%m%d-%H%M).json
docker exec $C node -e '
const fs=require("fs"); let w=JSON.parse(fs.readFileSync("/tmp/ceee.json","utf8")); const arr=Array.isArray(w); if(arr) w=w[0];
const d=w.nodes.find(n=>n.name==="Decidir"); if(!d) {console.log("SEM NÓ Decidir"); process.exit(1);}
d.parameters.jsCode=fs.readFileSync("/tmp/decidir_ceee.js","utf8");
fs.writeFileSync("/tmp/ceee-novo.json", JSON.stringify(arr?[w]:w)); console.log("Decidir atualizado:", d.parameters.jsCode.includes("ja_aberto_e_proxima"));'
docker exec $C n8n import:workflow --input=/tmp/ceee-novo.json 2>&1 | grep -iE 'import|error' | tail -2
docker exec $C n8n publish:workflow --id=$CID 2>&1 | tail -1
echo "== regra 250:"
docker exec $C n8n import:workflow --input=/tmp/ajuste-regra-250.json 2>&1 | grep -iE 'import|error' | tail -1
docker exec $C n8n execute --id=botAjusteRegra01 2>&1 | grep -oE '"(acao|valor_planilha)": *"[^"]*"|Error[^"]*|error[^"]*' | head -4
cd /opt/bot-tunel; T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
echo "== estado do lote:"
docker run --rm --network whatsapp_default curlimages/curl:8.10.1 -s -H "X-Bot-Token: $T" http://caddy/webhook/bot-resultado \
 | docker run --rm -i python:3.12-slim python -c 'import json,sys
d=json.load(sys.stdin); print("lote:", (d.get("lote") or {}).get("status"))
for c,f in (d.get("filas") or {}).items():
  print(c, f["status"]); [print("  ", l["linha"], l["site"], l["situacao"], l["protocolo"]) for l in f["linhas"]]'
echo PASSO7-FIM
