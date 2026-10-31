"""Workflow temporário: reseta as filas (limpa fila_ceee/fila_rge, para o controle) e confere o formato do CPF."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from manutencao import n, get, upd, code, rl, sch  # noqa: E402

CC = ["concessionaria", "jid", "numero", "status", "msg_inicial", "cpf", "nome", "email", "celular", "lote_id",
      "ultimo_envio_ms", "ultima_recebida_ms", "pausado_ate_ms", "pausas_seguidas", "pausa_loop_min"]
CTRL = """return $('Controle').all().map(i => i.json).filter(x => x.id && ['CEEE', 'RGE'].includes(x.concessionaria))
  .map(x => ({ json: { id: x.id, status: 'parado', lote_id: '', ultimo_envio_ms: '', pausado_ate_ms: '', pausas_seguidas: '0' } }));"""
INFO = """const c = $('Controle').all().map(i => i.json).filter(x => x.id);
return [{ json: { dados: c.map(x => ({ conc: x.concessionaria, cpf_tamanho: String(x.cpf || '').length,
  cpf_so_digitos: /^\\d+$/.test(String(x.cpf || '')), cpf_tem_espaco: /\\s/.test(String(x.cpf || '')),
  nome_ok: !!String(x.nome || '').trim(), email_ok: /@/.test(String(x.email || '')), celular_tamanho: String(x.celular || '').length })) } }];"""


def limpar(name, t, pos):
    return n(name, "n8n-nodes-base.dataTable", 1.1, pos, {"resource": "table", "operation": "clear", "dataTableId": rl(t)},
             executeOnce=True, alwaysOutputData=True)


nodes = [
    n("Webhook", "n8n-nodes-base.webhook", 2, [0, 0], {"path": "bot-manutencao-7f3a", "responseMode": "lastNode", "options": {}},
      webhookId="5d1c1d2e-0c1a-4a55-9a51-reset0000001"),
    get("Controle", "controle_bot", [200, 0]),
    limpar("Limpar CEEE", "fila_ceee", [400, -150]), limpar("Limpar RGE", "fila_rge", [600, -150]),
    code("Parar filas", CTRL, [400, 0]), upd("Salvar controle", "controle_bot", CC,
                                             ["status", "lote_id", "ultimo_envio_ms", "pausado_ate_ms", "pausas_seguidas"], [600, 0]),
    code("Conferir dados", INFO, [400, 150]),
]
C = {}
for a, b in [("Webhook", "Controle"), ("Controle", "Limpar CEEE"), ("Limpar CEEE", "Limpar RGE"),
             ("Controle", "Parar filas"), ("Parar filas", "Salvar controle"), ("Controle", "Conferir dados")]:
    C.setdefault(a, {"main": [[]]})["main"][0].append({"node": b, "type": "main", "index": 0})
wf = {"id": "botManutencao001", "name": "bot-manutencao", "active": False, "settings": {"executionOrder": "v1"},
      "pinData": {}, "nodes": nodes, "connections": C}
pathlib.Path(__file__).parent.joinpath("patch", "reset.json").write_text(json.dumps(wf, ensure_ascii=False, indent=1))
