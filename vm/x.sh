#!/bin/bash
# Baixa a versão mais nova de vm/run.sh do GitHub (sem cache) e executa.
set -e
curl -fsSL -H 'Accept: application/vnd.github.raw' -H 'Cache-Control: no-cache' \
  "https://api.github.com/repos/marconatt0/bot-concessionarias/contents/vm/run.sh?ref=main&t=$(date +%s)" -o /tmp/bot-run.sh
bash /tmp/bot-run.sh "$@" 2>&1 | tee /tmp/bot-run.log
