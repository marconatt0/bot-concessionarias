"""Gera os 4 workflows de webhook do n8n usados pelo Streamlit (vm/n8n/*.json).

bot-lote       POST  recebe a planilha + linhas, limpa as filas, grava tudo e liga as filas
bot-resultado  GET   devolve o lote atual e as linhas das duas filas
bot-arquivo    GET   devolve o xlsx original do lote atual (base64)
bot-cancelar   POST  cancela o lote atual (mantém os protocolos já obtidos)

O lote atual fica em /files/lotes/atual.json (metadados) e /files/lotes/atual.xlsx
(/files no container = /opt/planilhas na VM). Um lote novo sobrescreve os dois.
"""
import json
import pathlib
import uuid

PROJ = "g7NSooy85ZuYWBNa"
TAB = {"controle_bot": "AKvXsAZo4z5YlIEA", "fila_ceee": "mSPz4dkef1EPuy0Q", "fila_rge": "KItEV4M7mfBXuzS3"}
COLS_FILA = ["linha", "site", "uc_nova", "situacao", "protocolo", "previsao", "ultimo_gatilho",
             "repeticoes", "msg_desconhecida", "lote_id", "atualizado_em"]
COLS_CTRL = ["concessionaria", "jid", "numero", "status", "msg_inicial", "cpf", "nome", "email",
             "celular", "lote_id", "ultimo_envio_ms", "ultima_recebida_ms", "pausado_ate_ms",
             "pausas_seguidas", "pausa_loop_min"]
META = "/files/lotes/atual.json"
XLSX = "/files/lotes/atual.xlsx"
IDS = {"bot-lote": "botWebhookLote01", "bot-resultado": "botWebhookResul1",
       "bot-arquivo": "botWebhookArqui1", "bot-cancelar": "botWebhookCance1"}

ATIVOS_JS = "const ATIVOS = ['rodando', 'pausado', 'aguardando_expiracao'];"
AGORA_JS = "const agora = new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });"
FILAS_JS = "const FILAS = [['CEEE', 'Fila CEEE'], ['RGE', 'Fila RGE']];"
LER_META_JS = """let meta = null;
const b64 = $input.first().json.data;
if (b64) { try { meta = JSON.parse(Buffer.from(b64, 'base64').toString('utf8')); } catch (e) {} }
return [{ json: { meta } }];"""


def uid():
    return str(uuid.uuid4())


def rl(t):
    return {"__rl": True, "value": TAB[t], "mode": "list", "cachedResultName": t,
            "cachedResultUrl": f"/projects/{PROJ}/datatables/{TAB[t]}"}


def schema(cols):
    return [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True,
             "type": "string", "readOnly": False, "removed": False} for c in cols]


def node(name, type_, ver, pos, params, **extra):
    n = {"parameters": params, "type": type_, "typeVersion": ver, "position": pos, "id": uid(), "name": name}
    n.update(extra)
    return n


def code(name, js, pos):
    return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})


def webhook(path, metodo, pos):
    p = {"path": path, "responseMode": "responseNode", "options": {}}
    if metodo != "GET":
        p["httpMethod"] = metodo
    return node("Webhook", "n8n-nodes-base.webhook", 2, pos, p, webhookId=uid())


def responder(pos):
    return node("Responder", "n8n-nodes-base.respondToWebhook", 1.1, pos, {
        "respondWith": "json", "responseBody": "={{ JSON.stringify($json.resposta) }}",
        "options": {"responseCode": "={{ $json.codigo || 200 }}"}})


def dt_get(name, t, pos):
    return node(name, "n8n-nodes-base.dataTable", 1.1, pos,
                {"operation": "get", "dataTableId": rl(t), "returnAll": True},
                executeOnce=True, alwaysOutputData=True)


def dt_limpar(name, t, pos):
    return node(name, "n8n-nodes-base.dataTable", 1.1, pos,
                {"resource": "table", "operation": "clear", "dataTableId": rl(t)},
                executeOnce=True, alwaysOutputData=True)


def dt_insert(name, t, cols, pos):
    return node(name, "n8n-nodes-base.dataTable", 1.1, pos, {
        "operation": "insert", "dataTableId": rl(t),
        "columns": {"mappingMode": "defineBelow", "value": {c: "={{ $json." + c + " }}" for c in cols},
                    "matchingColumns": [], "schema": schema(cols),
                    "attemptToConvertTypes": False, "convertFieldsToString": False},
        "options": {}})


def dt_update(name, t, cols_tabela, cols, pos):
    return node(name, "n8n-nodes-base.dataTable", 1.1, pos, {
        "operation": "update", "dataTableId": rl(t),
        "filters": {"conditions": [{"keyValue": "={{ $json.id }}"}]},
        "columns": {"mappingMode": "defineBelow", "value": {c: "={{ $json." + c + " }}" for c in cols},
                    "matchingColumns": [], "schema": schema(cols_tabela),
                    "attemptToConvertTypes": False, "convertFieldsToString": False},
        "options": {}})


def ler_arquivo(name, caminho, pos):
    return node(name, "n8n-nodes-base.readWriteFile", 1, pos,
                {"operation": "read", "fileSelector": caminho, "options": {}},
                executeOnce=True, alwaysOutputData=True, onError="continueRegularOutput")


def para_base64(name, pos):
    return node(name, "n8n-nodes-base.extractFromFile", 1, pos,
                {"operation": "binaryToPropery", "binaryPropertyName": "data", "destinationKey": "data",
                 "options": {}}, executeOnce=True, alwaysOutputData=True, onError="continueRegularOutput")


def gravar_arquivo(name, caminho, pos):
    return node(name, "n8n-nodes-base.readWriteFile", 1, pos,
                {"operation": "write", "fileName": caminho, "dataPropertyName": "data", "options": {}})


def binario_js(expr_b64, nome, mime):
    return (f"return [{{ json: {{}}, binary: {{ data: {{ data: {expr_b64}, "
            f"mimeType: '{mime}', fileName: '{nome}' }} }} }}];")


def conecta(c, de, para):
    c.setdefault(de, {"main": [[]]})["main"][0].append({"node": para, "type": "main", "index": 0})


def cadeia(c, *nomes):
    for a, b in zip(nomes, nomes[1:]):
        conecta(c, a, b)


def wf(nome, nodes, conns):
    return {"id": IDS[nome], "name": nome, "nodes": nodes, "connections": conns, "active": False,
            "settings": {"executionOrder": "v1"}, "pinData": {}}


# ------------------------------------------------------------------ bot-lote
VALIDAR = ATIVOS_JS + "\n" + AGORA_JS + """
const body = $('Webhook').first().json.body || {};
const ctrl = $('Controle').all().map(i => i.json).filter(r => r.id);
const ocupada = ctrl.find(r => ATIVOS.includes(r.status));
const linhas = (Array.isArray(body.linhas) ? body.linhas : [])
  .filter(l => ['CEEE', 'RGE'].includes(l.concessionaria) && String(l.uc_nova || '').trim());
let erro = '', codigo = 200;
if (ocupada) { erro = `Já existe um lote em andamento (fila ${ocupada.concessionaria}: ${ocupada.status}).`; codigo = 409; }
else if (!body.lote_id || !linhas.length) { erro = 'Pedido sem lote_id ou sem linhas de CEEE/RGE.'; codigo = 400; }
else if (!body.arquivo_b64) { erro = 'Pedido sem o arquivo da planilha.'; codigo = 400; }
const lote_id = String(body.lote_id || '');
return [{ json: {
  ok: !erro, codigo,
  resposta: erro ? { ok: false, erro } : { ok: true, lote_id, linhas: linhas.length },
  lote_id, linhas,
  meta: { lote_id, arquivo_nome: String(body.arquivo_nome || 'planilha.xlsx'),
          enviado_por: String(body.enviado_por || ''), enviado_em: agora, cancelado: false },
} }];"""

NOVAS = AGORA_JS + """
const v = $('Validar').first().json;
return v.linhas.filter(l => l.concessionaria === '__CONC__').map(l => ({ json: {
  linha: String(l.linha ?? ''), site: String(l.site ?? ''), uc_nova: String(l.uc_nova ?? '').trim(),
  situacao: 'pendente', protocolo: '', previsao: '', ultimo_gatilho: '', repeticoes: '0',
  msg_desconhecida: '', lote_id: v.lote_id, atualizado_em: agora,
} }));"""

CTRL_NOVO = """const v = $('Validar').first().json;
return $('Controle').all().map(i => i.json)
  .filter(r => r.id && ['CEEE', 'RGE'].includes(r.concessionaria))
  .map(r => ({ json: {
    id: r.id, lote_id: v.lote_id, pausado_ate_ms: '', pausas_seguidas: '0', ultimo_envio_ms: '',
    status: v.linhas.some(l => l.concessionaria === r.concessionaria) ? 'rodando' : 'concluido',
  } }));"""


def bot_lote():
    n = [
        webhook("bot-lote", "POST", [-800, 0]),
        dt_get("Controle", "controle_bot", [-600, 0]),
        code("Validar", VALIDAR, [-400, 0]),
        code("Se ok", "return $json.ok ? $input.all() : [];", [-200, -200]),
        dt_limpar("Limpar fila CEEE", "fila_ceee", [0, -200]),
        dt_limpar("Limpar fila RGE", "fila_rge", [200, -200]),
        code("Linhas CEEE", NOVAS.replace("__CONC__", "CEEE"), [450, -500]),
        dt_insert("Inserir CEEE", "fila_ceee", COLS_FILA, [700, -500]),
        code("Linhas RGE", NOVAS.replace("__CONC__", "RGE"), [450, -350]),
        dt_insert("Inserir RGE", "fila_rge", COLS_FILA, [700, -350]),
        code("Arquivo", binario_js("$('Webhook').first().json.body.arquivo_b64", "atual.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), [450, -200]),
        gravar_arquivo("Gravar planilha", XLSX, [700, -200]),
        code("Metadados", binario_js("Buffer.from(JSON.stringify($('Validar').first().json.meta)).toString('base64')",
                                     "atual.json", "application/json"), [450, -50]),
        gravar_arquivo("Gravar metadados", META, [700, -50]),
        code("Ligar filas", CTRL_NOVO, [450, 100]),
        dt_update("Salvar controle", "controle_bot", COLS_CTRL,
                  ["lote_id", "status", "pausado_ate_ms", "pausas_seguidas", "ultimo_envio_ms"], [700, 100]),
        responder([-200, 300]),
    ]
    c = {}
    cadeia(c, "Webhook", "Controle", "Validar")
    conecta(c, "Validar", "Se ok")        # em cima: roda tudo primeiro
    conecta(c, "Validar", "Responder")    # embaixo: responde por último
    cadeia(c, "Se ok", "Limpar fila CEEE", "Limpar fila RGE")
    for a, b in [("Linhas CEEE", "Inserir CEEE"), ("Linhas RGE", "Inserir RGE"), ("Arquivo", "Gravar planilha"),
                 ("Metadados", "Gravar metadados"), ("Ligar filas", "Salvar controle")]:
        conecta(c, "Limpar fila RGE", a)
        conecta(c, a, b)
    return wf("bot-lote", n, c)


# ------------------------------------------------------------------ bot-resultado
MONTAR = ATIVOS_JS + "\n" + FILAS_JS + """
const meta = $('Lote atual').first().json.meta;
if (!meta || !meta.lote_id) return [{ json: { resposta: { lote: null } } }];
const ctrl = $('Controle').all().map(i => i.json).filter(r => r.id);
const filas = {};
for (const [conc, no] of FILAS) {
  const c = ctrl.find(r => r.concessionaria === conc) || {};
  const linhas = $(no).all().map(i => i.json).filter(r => r.id && r.lote_id === meta.lote_id)
    .sort((a, b) => (Number(a.linha) || 0) - (Number(b.linha) || 0))
    .map(r => ({ linha: Number(r.linha) || r.linha, site: r.site, concessionaria: conc, uc_nova: r.uc_nova,
                 situacao: r.situacao, protocolo: r.protocolo || '', previsao: r.previsao || '',
                 atualizado_em: r.atualizado_em || '' }));
  filas[conc] = { status: c.lote_id === meta.lote_id ? (c.status || '') : 'concluido', linhas };
}
const status = meta.cancelado ? 'cancelado'
  : Object.values(filas).some(f => ATIVOS.includes(f.status)) ? 'rodando' : 'concluido';
return [{ json: { resposta: { lote: {
  lote_id: meta.lote_id, arquivo_nome: meta.arquivo_nome, enviado_por: meta.enviado_por,
  enviado_em: meta.enviado_em, status }, filas } } }];"""


def bot_resultado():
    n = [
        webhook("bot-resultado", "GET", [-800, 0]),
        dt_get("Controle", "controle_bot", [-600, 0]),
        dt_get("Fila CEEE", "fila_ceee", [-400, 0]),
        dt_get("Fila RGE", "fila_rge", [-200, 0]),
        ler_arquivo("Ler metadados", META, [0, 0]),
        para_base64("Metadados em texto", [200, 0]),
        code("Lote atual", LER_META_JS, [400, 0]),
        code("Montar resposta", MONTAR, [600, 0]),
        responder([800, 0]),
    ]
    c = {}
    cadeia(c, "Webhook", "Controle", "Fila CEEE", "Fila RGE", "Ler metadados", "Metadados em texto",
           "Lote atual", "Montar resposta", "Responder")
    return wf("bot-resultado", n, c)


# ------------------------------------------------------------------ bot-arquivo
ARQ = """const meta = $('Lote atual').first().json.meta;
const b64 = $input.first().json.data;
if (!meta || !b64) return [{ json: { resposta: { lote_id: meta?.lote_id || '', arquivo_nome: '', arquivo_b64: '' } } }];
return [{ json: { resposta: { lote_id: meta.lote_id, arquivo_nome: meta.arquivo_nome, arquivo_b64: b64 } } }];"""


def bot_arquivo():
    n = [
        webhook("bot-arquivo", "GET", [-800, 0]),
        ler_arquivo("Ler metadados", META, [-600, 0]),
        para_base64("Metadados em texto", [-400, 0]),
        code("Lote atual", LER_META_JS, [-200, 0]),
        ler_arquivo("Ler planilha", XLSX, [0, 0]),
        para_base64("Planilha em base64", [200, 0]),
        code("Montar resposta", ARQ, [400, 0]),
        responder([600, 0]),
    ]
    c = {}
    cadeia(c, "Webhook", "Ler metadados", "Metadados em texto", "Lote atual", "Ler planilha",
           "Planilha em base64", "Montar resposta", "Responder")
    return wf("bot-arquivo", n, c)


# ------------------------------------------------------------------ bot-cancelar
PLANO = ATIVOS_JS + "\n" + AGORA_JS + "\n" + FILAS_JS + """
const meta = $('Lote atual').first().json.meta;
const plano = { meta: null, CEEE: [], RGE: [], controle: [] };
if (meta && meta.lote_id) {
  plano.meta = { ...meta, cancelado: true, cancelado_em: agora };
  for (const [conc, no] of FILAS) {
    for (const r of $(no).all().map(i => i.json).filter(r => r.id && r.lote_id === meta.lote_id)) {
      const s = String(r.situacao || '');
      let nova = null;
      if (s.startsWith('aguardando_fim:')) nova = s.slice('aguardando_fim:'.length);
      else if (s === 'em_andamento') nova = 'interrompida';
      if (nova) plano[conc].push({ id: r.id, situacao: nova, atualizado_em: agora });
    }
  }
  plano.controle = $('Controle').all().map(i => i.json)
    .filter(r => r.id && ATIVOS.includes(r.status))
    .map(r => ({ id: r.id, status: 'cancelado', pausado_ate_ms: '' }));
}
return [{ json: { plano, resposta: { ok: true } } }];"""


def bot_cancelar():
    n = [
        webhook("bot-cancelar", "POST", [-1000, 0]),
        dt_get("Controle", "controle_bot", [-800, 0]),
        dt_get("Fila CEEE", "fila_ceee", [-600, 0]),
        dt_get("Fila RGE", "fila_rge", [-400, 0]),
        ler_arquivo("Ler metadados", META, [-200, 0]),
        para_base64("Metadados em texto", [0, 0]),
        code("Lote atual", LER_META_JS, [200, 0]),
        code("Plano", PLANO, [400, 0]),
        code("Linhas CEEE", "return $json.plano.CEEE.map(r => ({ json: r }));", [650, -450]),
        dt_update("Atualizar CEEE", "fila_ceee", COLS_FILA, ["situacao", "atualizado_em"], [900, -450]),
        code("Linhas RGE", "return $json.plano.RGE.map(r => ({ json: r }));", [650, -300]),
        dt_update("Atualizar RGE", "fila_rge", COLS_FILA, ["situacao", "atualizado_em"], [900, -300]),
        code("Filas a parar", "return $json.plano.controle.map(r => ({ json: r }));", [650, -150]),
        dt_update("Parar filas", "controle_bot", COLS_CTRL, ["status", "pausado_ate_ms"], [900, -150]),
        code("Metadados", "if (!$json.plano.meta) return [];\n" + binario_js(
            "Buffer.from(JSON.stringify($json.plano.meta)).toString('base64')", "atual.json", "application/json"),
            [650, 0]),
        gravar_arquivo("Gravar metadados", META, [900, 0]),
        responder([650, 200]),
    ]
    c = {}
    cadeia(c, "Webhook", "Controle", "Fila CEEE", "Fila RGE", "Ler metadados", "Metadados em texto",
           "Lote atual", "Plano")
    for a, b in [("Linhas CEEE", "Atualizar CEEE"), ("Linhas RGE", "Atualizar RGE"),
                 ("Filas a parar", "Parar filas"), ("Metadados", "Gravar metadados")]:
        conecta(c, "Plano", a)
        conecta(c, a, b)
    conecta(c, "Plano", "Responder")
    return wf("bot-cancelar", n, c)


if __name__ == "__main__":
    out = pathlib.Path(__file__).parent / "n8n"
    out.mkdir(exist_ok=True)
    for f in (bot_lote, bot_resultado, bot_arquivo, bot_cancelar):
        w = f()
        (out / f"{w['name']}.json").write_text(json.dumps(w, ensure_ascii=False, indent=1))
        print(w["name"], len(w["nodes"]), "nós")
