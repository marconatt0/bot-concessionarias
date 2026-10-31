#!/bin/bash
# passo 5: grava o domínio, pede o authtoken (sem mostrar), liga o túnel e testa de fora
cd /opt/bot-tunel
DOM=swaddling-okay-ligament.ngrok-free.dev
sed -i "s|^NGROK_DOMAIN=.*|NGROK_DOMAIN=$DOM|" .env
clear
echo "Domínio gravado: $DOM"
echo
while true; do
  read -rsp ">>> Cole aqui o Authtoken do ngrok e aperte Enter: " TOK; echo
  TOK=$(echo "$TOK" | tr -d '[:space:]')
  [ ${#TOK} -ge 30 ] && break
  echo "    Não parece um authtoken (${#TOK} caracteres). Tente de novo."
done
sed -i "s|^NGROK_AUTHTOKEN=.*|NGROK_AUTHTOKEN=$TOK|" .env
unset TOK
echo "Authtoken gravado no .env."
docker compose --profile tunel up -d 2>&1 | tail -2
sleep 8
docker compose logs --tail 5 ngrok 2>&1 | grep -oE 'msg="[^"]*"|err=[^ ]*' | tail -5
T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
echo "== de fora, com token:"; curl -s -w ' [%{http_code}]\n' -H "X-Bot-Token: $T" -H 'ngrok-skip-browser-warning: 1' https://$DOM/webhook/bot-resultado
echo "== de fora, sem token:"; curl -s -o /dev/null -w '[%{http_code}]\n' https://$DOM/webhook/bot-resultado
echo "== editor do n8n de fora:"; curl -s -o /dev/null -w '[%{http_code}]\n' https://$DOM/
echo PASSO5-FIM
