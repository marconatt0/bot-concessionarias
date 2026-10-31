#!/bin/bash
# passo 6: monta o bloco de Secrets do Streamlit Cloud (url, token e hash da senha do gerente)
cd /opt/bot-tunel
clear
read -rp ">>> Usuário do gerente no site [gerente]: " U; U=${U:-gerente}; U=$(echo "$U" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9._-')
while true; do
  read -rsp ">>> Senha do gerente (não aparece): " S1; echo
  read -rsp ">>> Repita a senha: " S2; echo
  [ -n "$S1" ] && [ "$S1" = "$S2" ] && break
  echo "    As senhas não conferem ou estão vazias. De novo."
done
echo "Gerando o hash (pode levar uns segundos)..."
H=$(SENHA="$S1" docker run --rm -e SENHA python:3.12-slim sh -c \
  'pip -q install --disable-pip-version-check --root-user-action=ignore bcrypt >/dev/null 2>&1 && python -c "import bcrypt,os;print(bcrypt.hashpw(os.environ[\"SENHA\"].encode(),bcrypt.gensalt()).decode())"')
unset S1 S2
[ -z "$H" ] && { echo "Falhou ao gerar o hash."; exit 1; }
DOM=$(grep ^NGROK_DOMAIN= .env | cut -d= -f2); T=$(grep ^BOT_TOKEN= .env | cut -d= -f2)
cat > streamlit-secrets.toml <<EOT
[n8n]
url = "https://$DOM"
token = "$T"

[usuarios]
$U = "$H"
EOT
chmod 600 streamlit-secrets.toml
clear
echo "======== copie da linha [n8n] até o fim e cole em Settings > Secrets no Streamlit Cloud ========"
echo
cat streamlit-secrets.toml
echo
echo "================================================================================================"
echo "(salvo também em /opt/bot-tunel/streamlit-secrets.toml)"
