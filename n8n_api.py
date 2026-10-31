"""Comunicação com os webhooks do n8n (via ngrok + Caddy).

Contrato (o n8n precisa responder exatamente assim — ver docs/API.md):
  POST bot-lote       {lote_id, enviado_por, arquivo_nome, arquivo_b64, linhas[]} -> {ok, lote_id} | 409 {ok:false, erro}
  GET  bot-resultado  -> {lote: null} | {lote: {...}, filas: {CEEE: {...}, RGE: {...}}}
  GET  bot-arquivo    -> {lote_id, arquivo_nome, arquivo_b64}
  POST bot-cancelar   -> {ok}
Todas as chamadas levam o header X-Bot-Token.
"""
from __future__ import annotations

import base64
import random
import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

FUSO = ZoneInfo("America/Sao_Paulo")
TIMEOUT = 60

SITUACOES = {
    "pendente": "Na fila",
    "em_andamento": "Conversando",
    "protocolo": "Protocolo aberto",
    "ja_aberto": "Já tinha chamado aberto",
    "sem_resposta": "Sem resposta",
    "loop": "Travou (loop)",
    "uc_nao_encontrada": "UC não encontrada",
    "finalizada_sem_protocolo": "Já tinha chamado aberto",
    "interrompida": "Cancelada",
}
FINAIS = {"protocolo", "ja_aberto", "sem_resposta", "loop", "uc_nao_encontrada",
          "finalizada_sem_protocolo", "interrompida"}
COM_PROTOCOLO = {"protocolo", "ja_aberto"}


def descrever_situacao(s: str) -> str:
    s = s or ""
    if s.startswith("aguardando_fim:"):
        return "Conversando (finalizando)"
    return SITUACOES.get(s, s or "—")


def agora_txt() -> str:
    return datetime.now(FUSO).strftime("%d/%m/%Y %H:%M")


class ErroAPI(Exception):
    pass


class LoteEmAndamento(ErroAPI):
    pass


class N8nAPI:
    def __init__(self, url_base: str, token: str):
        self.url = url_base.rstrip("/") + "/webhook/"
        self.headers = {"X-Bot-Token": token, "ngrok-skip-browser-warning": "1"}

    def _req(self, metodo: str, caminho: str, **kw):
        try:
            r = requests.request(metodo, self.url + caminho, headers=self.headers, timeout=TIMEOUT, **kw)
        except requests.RequestException as e:
            raise ErroAPI(f"Não consegui falar com o robô ({e.__class__.__name__}). "
                          "A VM, o n8n ou o ngrok podem estar fora do ar.") from e
        if r.status_code == 409:
            raise LoteEmAndamento(_erro(r) or "Já existe um lote em andamento.")
        if r.status_code in (401, 403):
            raise ErroAPI("O robô recusou o acesso (token inválido). Confira o token nos secrets do Streamlit.")
        if r.status_code == 404:
            raise ErroAPI(f"O webhook {caminho} não existe ou não está publicado no n8n.")
        if not r.ok:
            raise ErroAPI(f"O robô respondeu com erro {r.status_code}: {_erro(r) or r.text[:200]}")
        try:
            return r.json()
        except ValueError as e:
            raise ErroAPI(f"Resposta inesperada do robô em {caminho}: {r.text[:200]}") from e

    def enviar_lote(self, linhas: list[dict], arquivo: bytes, arquivo_nome: str, usuario: str) -> str:
        lote_id = datetime.now(FUSO).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        corpo = {"lote_id": lote_id, "enviado_por": usuario, "arquivo_nome": arquivo_nome,
                 "arquivo_b64": base64.b64encode(arquivo).decode(), "linhas": linhas}
        resp = self._req("POST", "bot-lote", json=corpo)
        return resp.get("lote_id") or lote_id

    def resultado(self) -> dict:
        return self._req("GET", "bot-resultado")

    def arquivo(self) -> tuple[str, bytes]:
        resp = self._req("GET", "bot-arquivo")
        if not resp.get("arquivo_b64"):
            raise ErroAPI("O robô não tem o arquivo original deste lote.")
        return resp.get("arquivo_nome") or "planilha.xlsx", base64.b64decode(resp["arquivo_b64"])

    def cancelar(self) -> None:
        self._req("POST", "bot-cancelar", json={"pedido_em": agora_txt()})


def _erro(r) -> str:
    try:
        return r.json().get("erro", "")
    except ValueError:
        return ""


class DemoAPI:
    """Imita o n8n em memória para testar a tela sem a VM (BOT_MODO_DEMO)."""

    PASSO_SEG = 6  # a cada ~6 s uma UC termina

    def __init__(self):
        self._trava = threading.Lock()
        self._lote = None

    def enviar_lote(self, linhas, arquivo, arquivo_nome, usuario):
        with self._trava:
            if self._lote and self._lote["lote"]["status"] == "rodando":
                raise LoteEmAndamento("Já existe um lote em andamento.")
            lote_id = datetime.now(FUSO).strftime("%Y%m%d-%H%M%S-demo")
            filas = {"CEEE": [], "RGE": []}
            for l in linhas:
                filas[l["concessionaria"]].append({**l, "situacao": "pendente", "protocolo": "",
                                                   "previsao": "", "atualizado_em": ""})
            self._lote = {"lote": {"lote_id": lote_id, "arquivo_nome": arquivo_nome, "enviado_por": usuario,
                                   "enviado_em": agora_txt(), "status": "rodando"},
                          "filas": {c: {"status": "rodando" if v else "concluido", "linhas": v} for c, v in filas.items()},
                          "_arquivo": arquivo, "_inicio": time.time()}
            return lote_id

    def _avancar(self):
        d = self._lote
        if not d or d["lote"]["status"] != "rodando":
            return
        passos = int((time.time() - d["_inicio"]) / self.PASSO_SEG)
        for conc, fila in d["filas"].items():
            rnd = random.Random(conc)
            for i, l in enumerate(fila["linhas"]):
                if l["situacao"] in FINAIS:
                    continue
                if i < passos:
                    sorte = rnd.random()
                    if sorte < 0.6:
                        l.update(situacao="protocolo", protocolo=str(2271400000 + rnd.randint(0, 99999)),
                                 previsao="31/10/2026 01:08")
                    elif sorte < 0.8:
                        l.update(situacao="ja_aberto",
                                 protocolo="protocolo já aberto" if conc == "CEEE" else str(2271300000 + i))
                    else:
                        l.update(situacao="sem_resposta")
                    l["atualizado_em"] = agora_txt()
                elif i == passos:
                    l["situacao"] = "em_andamento"
            if all(l["situacao"] in FINAIS for l in fila["linhas"]):
                fila["status"] = "concluido"
        if all(f["status"] in ("concluido", "parado", "cancelado") for f in d["filas"].values()):
            d["lote"]["status"] = "concluido"

    def resultado(self):
        with self._trava:
            self._avancar()
            if not self._lote:
                return {"lote": None}
            return {k: v for k, v in self._lote.items() if not k.startswith("_")}

    def arquivo(self):
        if not self._lote:
            raise ErroAPI("Nenhum lote.")
        return self._lote["lote"]["arquivo_nome"], self._lote["_arquivo"]

    def cancelar(self):
        with self._trava:
            if not self._lote:
                return
            for f in self._lote["filas"].values():
                for l in f["linhas"]:
                    if l["situacao"] not in FINAIS:
                        l["situacao"] = "interrompida" if l["situacao"] != "pendente" else "pendente"
                if f["status"] == "rodando":
                    f["status"] = "cancelado"
            self._lote["lote"]["status"] = "cancelado"
