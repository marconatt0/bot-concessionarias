#!/bin/bash
# passo 11: regras novas da CEEE (fim 'Que bom', pesquisa 1-5, Clara reiniciando) + diagnóstico
clear
C=whatsapp-n8n-1
RAW="https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/patch"
for f in manutencao.json decidir_ceee.js decidir_rge.js; do curl -fsSL -H 'Accept: application/vnd.github.raw' "$RAW/$f?ref=main&t=$(date +%s)" -o /tmp/$f || exit 1; docker cp /tmp/$f $C:/tmp/$f; done
for CONC in CEEE RGE; do
  low=$(echo $CONC | tr A-Z a-z)
  CID=$(docker exec $C n8n list:workflow 2>/dev/null | grep "|bot-conversa-$CONC\$" | cut -d'|' -f1)
  docker exec $C n8n export:workflow --id=$CID --output=/tmp/conv.json >/dev/null 2>&1
  docker cp $C:/tmp/conv.json /opt/bot-tunel/backup/conversa-$CONC-$(date +%Y%m%d-%H%M).json
  docker exec $C node -e '
const fs=require("fs"); let w=JSON.parse(fs.readFileSync("/tmp/conv.json","utf8")); const arr=Array.isArray(w); if(arr) w=w[0];
const d=w.nodes.find(n=>n.name==="Decidir"); d.parameters.jsCode=fs.readFileSync(process.argv[1],"utf8");
fs.writeFileSync("/tmp/conv-novo.json", JSON.stringify(arr?[w]:w));
console.log(w.name, "atualizado:", !d.parameters.jsCode.includes("finalizada_sem_protocolo") && d.parameters.jsCode.includes("reiniciar_se_no_meio"), d.parameters.jsCode.includes("const CONC = \x27"+process.argv[2]+"\x27"));' /tmp/decidir_$low.js $CONC
  docker exec $C n8n import:workflow --input=/tmp/conv-novo.json >/dev/null 2>&1
  docker exec $C n8n publish:workflow --id=$CID >/dev/null 2>&1
done
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
  for l in d[k]:
    g=lambda x: str(l.get(x) or "")
    print("%3s %-8s %-24s %-20s rep=%s %s | %s" % (g("linha"), g("site"), g("situacao"), g("protocolo")[:20], g("rep"), g("em"), g("gatilho")[:45]))
    if g("desconhecida"): print("      ?? " + repr(g("desconhecida")[:300]))' < /opt/bot-tunel/backup/diagnostico.json
echo PASSO11-FIM
