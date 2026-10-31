"""Workflow temporário de manutenção (webhook interno bot-manutencao-7f3a): diagnóstico + ajustes pontuais."""
import json, uuid, pathlib
PROJ = "g7NSooy85ZuYWBNa"
T = {"regras_conversa": "Wbmg2rgEHlUh6fTW", "fila_ceee": "mSPz4dkef1EPuy0Q", "fila_rge": "KItEV4M7mfBXuzS3",
     "controle_bot": "AKvXsAZo4z5YlIEA"}
RC = ["concessionaria", "ordem", "gatilho", "tipo", "acao", "resposta", "valor_planilha", "ativo", "observacao"]
FC = ["linha", "site", "uc_nova", "situacao", "protocolo", "previsao", "ultimo_gatilho", "repeticoes",
      "msg_desconhecida", "lote_id", "atualizado_em"]


def rl(t):
    return {"__rl": True, "value": T[t], "mode": "list", "cachedResultName": t,
            "cachedResultUrl": f"/projects/{PROJ}/datatables/{T[t]}"}


def sch(cols):
    return [{"id": c, "displayName": c, "required": False, "defaultMatch": False, "display": True, "type": "string",
             "readOnly": False, "removed": False} for c in cols]


def n(name, t, v, pos, p, **e):
    d = {"parameters": p, "type": t, "typeVersion": v, "position": pos, "id": str(uuid.uuid4()), "name": name}
    d.update(e)
    return d


def get(name, t, pos):
    return n(name, "n8n-nodes-base.dataTable", 1.1, pos, {"operation": "get", "dataTableId": rl(t), "returnAll": True},
             executeOnce=True, alwaysOutputData=True)


def upd(name, t, cols, w, pos):
    return n(name, "n8n-nodes-base.dataTable", 1.1, pos, {
        "operation": "update", "dataTableId": rl(t), "filters": {"conditions": [{"keyValue": "={{ $json.id }}"}]},
        "columns": {"mappingMode": "defineBelow", "value": {c: "={{ $json." + c + " }}" for c in w},
                    "matchingColumns": [], "schema": sch(cols), "attemptToConvertTypes": False,
                    "convertFieldsToString": False}, "options": {}})


def code(name, js, pos):
    return n(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})


DIAG = """const f = no => $(no).all().map(i => i.json).filter(x => x.id).map(x => ({ linha: x.linha, site: x.site,
  situacao: x.situacao, protocolo: x.protocolo, gatilho: x.ultimo_gatilho, rep: x.repeticoes,
  desconhecida: String(x.msg_desconhecida || '').slice(0, 400), em: x.atualizado_em }));
const ctrl = $('Controle').all().map(i => i.json).filter(x => x.id).map(x => ({ c: x.concessionaria, status: x.status,
  ate: x.pausado_ate_ms ? new Date(Number(x.pausado_ate_ms)).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '',
  pausas: x.pausas_seguidas,
  envio: x.ultimo_envio_ms ? new Date(Number(x.ultimo_envio_ms)).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '',
  recebida: x.ultima_recebida_ms ? new Date(Number(x.ultima_recebida_ms)).toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : '' }));
return [{ json: { controle: ctrl, CEEE: f('Fila CEEE'), RGE: f('Fila RGE') } }];"""

NOVAS = "[{\"concessionaria\": \"CEEE\", \"ordem\": \"85\", \"gatilho\": \"Fico muito feliz de te ajudar\", \"tipo\": \"contem\", \"acao\": \"proxima\", \"resposta\": \"\", \"valor_planilha\": \"protocolo já aberto\", \"ativo\": \"sim\", \"observacao\": \"fim da conversa depois da pesquisa\"}, {\"concessionaria\": \"CEEE\", \"ordem\": \"225\", \"gatilho\": \"Muito satisfeito\", \"tipo\": \"contem\", \"acao\": \"responder\", \"resposta\": \"5\", \"valor_planilha\": \"\", \"ativo\": \"sim\", \"observacao\": \"pesquisa de satisfação com opções 1 a 5\"}, {\"concessionaria\": \"CEEE\", \"ordem\": \"950\", \"gatilho\": \"Eu sou a Clara\", \"tipo\": \"contem\", \"acao\": \"reiniciar_se_no_meio\", \"resposta\": \"\", \"valor_planilha\": \"\", \"ativo\": \"sim\", \"observacao\": \"saudação no meio da conversa = Clara reiniciou; recomeça a mesma UC\"}]"

REGRA80 = """const r = $input.all().map(i => i.json).find(x => x.id && x.concessionaria === 'CEEE' && String(x.ordem) === '80');
return r ? [{ json: { id: r.id, valor_planilha: 'protocolo já aberto',
  observacao: 'fim da conversa: começa a próxima UC; sem protocolo novo = já existia chamado' } }] : [];"""

FINALIZADAS = """const agora = new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });
return $('__FILA__').all().map(i => i.json).filter(x => x.id && x.situacao === 'finalizada_sem_protocolo')
  .map(x => ({ json: { id: x.id, situacao: 'ja_aberto', protocolo: 'protocolo já aberto', atualizado_em: agora } }));"""


def wf():
    nodes = [
        n("Webhook", "n8n-nodes-base.webhook", 2, [0, 0],
          {"path": "bot-manutencao-7f3a", "responseMode": "responseNode", "options": {}}, webhookId=str(uuid.uuid4())),
        get("Controle", "controle_bot", [200, 0]), get("Fila CEEE", "fila_ceee", [400, 0]),
        get("Fila RGE", "fila_rge", [600, 0]), code("Diagnóstico", DIAG, [800, 0]),
        n("Responder", "n8n-nodes-base.respondToWebhook", 1.1, [1000, -200],
          {"respondWith": "json", "responseBody": "={{ JSON.stringify($json) }}", "options": {}}),
        get("Regras", "regras_conversa", [1000, 0]), code("Regra 80", REGRA80, [1200, 0]),
        upd("Salvar regra", "regras_conversa", RC, ["valor_planilha", "observacao"], [1400, 0]),
        code("Regras novas", "const novas = " + NOVAS + ";\nconst tem = $('Regras').all().map(i => i.json).filter(x => x.id).map(x => x.concessionaria + '|' + x.ordem);\nreturn novas.filter(r => !tem.includes(r.concessionaria + '|' + r.ordem)).map(r => ({ json: r }));", [1200, -200]),
        n("Inserir regras", "n8n-nodes-base.dataTable", 1.1, [1400, -200], {"operation": "insert", "dataTableId": rl("regras_conversa"),
          "columns": {"mappingMode": "defineBelow", "value": {c: "={{ $json." + c + " }}" for c in RC}, "matchingColumns": [],
                      "schema": sch(RC), "attemptToConvertTypes": False, "convertFieldsToString": False}, "options": {}}),
        code("Finalizadas CEEE", FINALIZADAS.replace("__FILA__", "Fila CEEE"), [1000, 200]),
        upd("Salvar linhas", "fila_ceee", FC, ["situacao", "protocolo", "atualizado_em"], [1200, 200]),
        code("Finalizadas RGE", FINALIZADAS.replace("__FILA__", "Fila RGE"), [1000, 400]),
        upd("Salvar linhas RGE", "fila_rge", FC, ["situacao", "protocolo", "atualizado_em"], [1200, 400]),
    ]
    C = {}
    def c(a, b):
        C.setdefault(a, {"main": [[]]})["main"][0].append({"node": b, "type": "main", "index": 0})
    for a, b in [("Webhook", "Controle"), ("Controle", "Fila CEEE"), ("Fila CEEE", "Fila RGE"),
                 ("Fila RGE", "Diagnóstico"), ("Diagnóstico", "Responder"), ("Diagnóstico", "Regras"),
                 ("Regras", "Regras novas"), ("Regras novas", "Inserir regras"), ("Regras", "Regra 80"), ("Regra 80", "Salvar regra"), ("Diagnóstico", "Finalizadas CEEE"),
                 ("Finalizadas CEEE", "Salvar linhas"), ("Diagnóstico", "Finalizadas RGE"),
                 ("Finalizadas RGE", "Salvar linhas RGE")]:
        c(a, b)
    return {"id": "botManutencao001", "name": "bot-manutencao", "active": False,
            "settings": {"executionOrder": "v1"}, "pinData": {}, "nodes": nodes, "connections": C}


if __name__ == "__main__":
    pathlib.Path(__file__).parent.joinpath("patch", "manutencao.json").write_text(
        json.dumps(wf(), ensure_ascii=False, indent=1))
