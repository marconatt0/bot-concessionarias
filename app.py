"""Interface do robô de protocolos (CEEE e RGE/CPFL).

Fluxo: login -> sobe o REPORT -> confere o que vai para o robô -> inicia -> acompanha
-> baixa a mesma planilha com a coluna Protocolo preenchida.
"""
from __future__ import annotations

import os
import time

import bcrypt
import pandas as pd
import streamlit as st

import planilha
from n8n_api import (COM_PROTOCOLO, DemoAPI, ErroAPI, FINAIS, LoteEmAndamento, N8nAPI,
                     descrever_situacao)

st.set_page_config(page_title="Protocolos Concessionárias", page_icon="⚡", layout="wide")

ATUALIZAR_SEG = 20
CONC_NOME = {"CEEE": "CEEE (Clara)", "RGE": "RGE / CPFL"}


# ---------------------------------------------------------------- configuração
def _secret(caminho: str, padrao=None):
    try:
        atual = st.secrets
        for parte in caminho.split("."):
            atual = atual[parte]
        return atual
    except (KeyError, FileNotFoundError, AttributeError):
        return padrao


MODO_DEMO = bool(_secret("demo", False)) or os.environ.get("BOT_MODO_DEMO") == "1"


@st.cache_resource
def _demo_api():
    return DemoAPI()


def api():
    if MODO_DEMO:
        return _demo_api()
    url, token = _secret("n8n.url"), _secret("n8n.token")
    if not url or not token:
        st.error("Faltam `n8n.url` e `n8n.token` nos secrets do Streamlit.")
        st.stop()
    return N8nAPI(url, token)


# ---------------------------------------------------------------- login
def login() -> str:
    if st.session_state.get("usuario"):
        return st.session_state["usuario"]
    usuarios = dict(_secret("usuarios", {}) or {})
    if MODO_DEMO and not usuarios:
        usuarios = {"demo": bcrypt.hashpw(b"demo", bcrypt.gensalt()).decode()}

    st.title("⚡ Protocolos das concessionárias")
    if not usuarios:
        st.error("Nenhum usuário configurado. Adicione a seção [usuarios] nos secrets.")
        st.stop()
    with st.form("login"):
        usuario = st.text_input("Usuário").strip().lower()
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")
    if MODO_DEMO:
        st.caption("Modo demonstração: usuário `demo`, senha `demo`.")
    if entrar:
        tentativas = st.session_state.get("tentativas", 0)
        if tentativas >= 5:
            time.sleep(min(30, 2 ** (tentativas - 4)))
        nome = next((n for n in usuarios if n.lower() == usuario), None)
        hash_ = usuarios.get(nome) if nome else None
        if hash_ and bcrypt.checkpw(senha.encode(), str(hash_).encode()):
            st.session_state["usuario"] = nome
            st.session_state["tentativas"] = 0
            st.rerun()
        st.session_state["tentativas"] = tentativas + 1
        st.error("Usuário ou senha incorretos.")
    st.stop()


# ---------------------------------------------------------------- telas
def tela_envio(cliente, usuario: str, aviso_lote_anterior: bool = False):
    st.subheader("Enviar planilha")
    if aviso_lote_anterior:
        st.warning("Ao iniciar um lote novo, o lote anterior e o arquivo dele são apagados do robô. "
                   "Baixe a planilha preenchida antes, se ainda não baixou.")
    arq = st.file_uploader("REPORT de protocolos (.xlsx)", type=["xlsx"], key="upload")
    if not arq:
        st.caption("A planilha precisa ter a aba TEMPLATE com as colunas Sites com Falha de AC, "
                   "Concessionária, UC NOVA e Protocolo.")
        return
    conteudo = arq.getvalue()
    try:
        linhas = planilha.ler(conteudo)
    except planilha.PlanilhaInvalida as e:
        st.error(str(e))
        return

    robo = [l for l in linhas if l.vai_para_robo]
    fora = [l for l in linhas if not l.vai_para_robo]
    c1, c2, c3 = st.columns(3)
    c1.metric("CEEE", sum(l.concessionaria == "CEEE" for l in robo))
    c2.metric("RGE / CPFL", sum(l.concessionaria == "RGE" for l in robo))
    c3.metric("Fora do robô", len(fora))

    if robo:
        st.markdown("**Vão para o robô**")
        st.dataframe(pd.DataFrame([{"Linha": l.linha, "Site": l.site, "Concessionária": CONC_NOME[l.concessionaria],
                                    "UC NOVA": l.uc_nova, "Cidade": l.cidade} for l in robo]),
                     hide_index=True, use_container_width=True)
    if fora:
        with st.expander(f"Fora do robô ({len(fora)}) — ficam como estão na planilha"):
            st.dataframe(pd.DataFrame([{"Linha": l.linha, "Site": l.site, "Concessionária": l.concessionaria_original,
                                        "UC NOVA": l.uc_nova, "Protocolo atual": l.protocolo_atual, "Motivo": l.motivo}
                                       for l in fora]), hide_index=True, use_container_width=True)

    if not robo:
        st.info("Nenhuma linha precisa do robô: todas já têm protocolo, são de outra concessionária "
                "ou estão sem UC NOVA.")
        return
    minutos = max(len([l for l in robo if l.concessionaria == c]) for c in ("CEEE", "RGE")) * 7
    st.caption(f"Tempo estimado: cerca de {minutos // 60}h{minutos % 60:02d}min "
               "(as duas concessionárias rodam ao mesmo tempo, ~7 min por UC).")
    if st.button(f"Iniciar lote com {len(robo)} UCs", type="primary"):
        try:
            cliente.enviar_lote([l.para_api() for l in robo], conteudo, arq.name, usuario)
        except LoteEmAndamento as e:
            st.error(str(e))
            return
        except ErroAPI as e:
            st.error(str(e))
            return
        st.session_state.pop("download", None)
        st.success("Lote enviado. O robô já começou a conversar com as concessionárias.")
        time.sleep(1)
        st.rerun()


def _tabela_fila(fila: dict) -> pd.DataFrame:
    return pd.DataFrame([{
        "Linha": l.get("linha"), "Site": l.get("site"), "UC NOVA": l.get("uc_nova"),
        "Situação": descrever_situacao(l.get("situacao")), "Protocolo": l.get("protocolo") or "",
        "Previsão": l.get("previsao") or "", "Atualizado": l.get("atualizado_em") or "",
    } for l in fila.get("linhas", [])])


def _resumo_filas(estado: dict):
    filas = estado.get("filas") or {}
    cols = st.columns(len(filas) or 1)
    for col, (conc, fila) in zip(cols, filas.items()):
        linhas = fila.get("linhas", [])
        if not linhas:
            continue
        feitas = sum(l.get("situacao") in FINAIS for l in linhas)
        prot = sum(l.get("situacao") in COM_PROTOCOLO and bool(l.get("protocolo")) for l in linhas)
        problemas = feitas - prot - sum(l.get("situacao") == "interrompida" for l in linhas)
        with col:
            st.markdown(f"#### {CONC_NOME.get(conc, conc)}")
            st.progress(feitas / len(linhas), text=f"{feitas} de {len(linhas)} UCs")
            a, b = st.columns(2)
            a.metric("Com protocolo", prot)
            b.metric("Sem protocolo", problemas)
            if fila.get("status") == "parado":
                st.error("Esta fila parou porque a conversa travou duas vezes seguidas. "
                         "As UCs que faltaram ficam em branco na planilha.")
            st.dataframe(_tabela_fila(fila), hide_index=True, use_container_width=True)


@st.fragment(run_every=ATUALIZAR_SEG)
def painel_andamento(cliente):
    try:
        estado = cliente.resultado()
    except ErroAPI as e:
        st.warning(f"{e} Tentando de novo em {ATUALIZAR_SEG} s.")
        return
    lote = estado.get("lote") or {}
    if lote.get("status") != "rodando":
        st.rerun(scope="app")
    _resumo_filas(estado)
    st.caption(f"Atualiza sozinho a cada {ATUALIZAR_SEG} s. Pode fechar a página: o robô continua "
               "e o resultado fica disponível quando você voltar.")


def tela_andamento(cliente, lote: dict):
    st.subheader("Lote em andamento")
    st.caption(f"Enviado por {lote.get('enviado_por', '?')} em {lote.get('enviado_em', '?')} · "
               f"{lote.get('arquivo_nome', '')}")
    painel_andamento(cliente)
    with st.expander("Cancelar lote"):
        st.write("Para as duas filas agora. Os protocolos já obtidos continuam valendo e entram na planilha; "
                 "as UCs que faltaram ficam em branco.")
        confirma = st.checkbox("Entendi, quero cancelar")
        if st.button("Cancelar lote", disabled=not confirma):
            try:
                cliente.cancelar()
            except ErroAPI as e:
                st.error(str(e))
                return
            st.rerun()


def _resultados_para_planilha(estado: dict) -> list[dict]:
    saida = []
    for fila in (estado.get("filas") or {}).values():
        for l in fila.get("linhas", []):
            if l.get("situacao") in COM_PROTOCOLO and l.get("protocolo"):
                saida.append({"linha": l.get("linha"), "site": l.get("site"),
                              "uc_nova": str(l.get("uc_nova", "")), "protocolo": str(l["protocolo"])})
    return saida


def tela_resultado(cliente, estado: dict):
    lote = estado["lote"]
    cancelado = lote.get("status") == "cancelado"
    st.subheader("Lote cancelado" if cancelado else "Lote concluído")
    st.caption(f"Enviado por {lote.get('enviado_por', '?')} em {lote.get('enviado_em', '?')} · "
               f"{lote.get('arquivo_nome', '')}")
    _resumo_filas(estado)

    lote_id = lote.get("lote_id")
    pronto = st.session_state.get("download")
    if not pronto or pronto["lote_id"] != lote_id:
        if st.button("Gerar planilha preenchida", type="primary"):
            try:
                nome, original = cliente.arquivo()
                arquivo, relatorio = planilha.preencher(original, _resultados_para_planilha(estado))
            except (ErroAPI, planilha.PlanilhaInvalida) as e:
                st.error(str(e))
                return
            st.session_state["download"] = {"lote_id": lote_id, "nome": nome, "arquivo": arquivo,
                                            "relatorio": relatorio}
            st.rerun()
    else:
        escritos = [r for r in pronto["relatorio"] if r["escrito"]]
        st.success(f"Planilha pronta: {len(escritos)} protocolos escritos na coluna Protocolo. "
                   "O resto do arquivo está igual ao que foi enviado.")
        st.download_button("Baixar planilha preenchida", pronto["arquivo"], file_name=pronto["nome"],
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary")
        nao = [r for r in pronto["relatorio"] if not r["escrito"]]
        if nao:
            with st.expander(f"{len(nao)} protocolos não foram escritos"):
                st.dataframe(pd.DataFrame(nao), hide_index=True, use_container_width=True)

    st.divider()
    with st.expander("Enviar uma planilha nova"):
        tela_envio(cliente, st.session_state["usuario"], aviso_lote_anterior=True)


# ---------------------------------------------------------------- principal
def main():
    usuario = login()
    cliente = api()
    with st.sidebar:
        st.write(f"Conectado como **{usuario}**")
        if MODO_DEMO:
            st.info("Modo demonstração: nada é enviado para as concessionárias.")
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    st.title("⚡ Protocolos das concessionárias")
    try:
        estado = cliente.resultado()
    except ErroAPI as e:
        st.error(str(e))
        if st.button("Tentar de novo"):
            st.rerun()
        return

    lote = estado.get("lote")
    if not lote:
        tela_envio(cliente, usuario)
    elif lote.get("status") == "rodando":
        tela_andamento(cliente, lote)
    else:
        tela_resultado(cliente, estado)


main()
