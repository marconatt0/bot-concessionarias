#!/bin/bash
# passo 1: inspeção dos nós do n8n instalado
clear
N=$(docker exec whatsapp-n8n-1 sh -c 'ls -d /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base*/node_modules/n8n-nodes-base/dist/nodes' | head -1)
ex() { docker exec whatsapp-n8n-1 sh -c "cd $N; $1"; }
echo "== clear/deleteRows"; ex "grep -hoE \"(name|value): '[a-zA-Z]+'\" DataTable/actions/table/clear.operation.js DataTable/actions/row/delete*.js DataTable/common/*.js 2>/dev/null | sort -u | tr '\n' ' '"; echo
echo "== extract"; ex "grep -hoE \"value: '[a-zA-Z]+'\" Files/ExtractFromFile/ExtractFromFile.node.js | tr '\n' ' '; grep -hoE \"name: '[a-zA-Z]+'\" Files/ExtractFromFile/actions/moveTo.operation.js | sort -u | tr '\n' ' '"; echo
echo "== versions"; ex "grep -hoE 'version: [^,}]+' Files/ReadWriteFile/ReadWriteFile.node.js Files/ExtractFromFile/ExtractFromFile.node.js RespondToWebhook/RespondToWebhook.node.js Webhook/Webhook.node.js | tr '\n' ' '"; echo
echo "== runners"; docker exec whatsapp-n8n-1 sh -c 'env | grep -i RUNNER'
echo "== cli"; docker exec whatsapp-n8n-1 n8n --help 2>/dev/null | grep -iE 'publish|import|activ|update' 
