import io
import zipfile

import openpyxl
import pytest

import planilha as P


def _report(linhas, extra_abas=("UCs",)):
    """Monta um REPORT parecido com o real: título, CPF no topo, cabeçalho na linha 4."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMPLATE"
    ws["B1"] = "REPORT PADRÃO PROTOCOLOS"
    ws["I1"], ws["J1"] = "CPF", "Numero"
    cab = ["Sites com Falha de AC", "Concessionária", "UC ANTIGA", "UC NOVA", "Protocolo", "Endereço", "Cidade", "Regional"]
    for i, c in enumerate(cab, start=2):
        ws.cell(4, i, c)
    for r, lin in enumerate(linhas, start=5):
        for i, v in enumerate(lin, start=2):
            ws.cell(r, i, v)
        ws.cell(r, 6).number_format = "@"  # estilo na coluna Protocolo, como no arquivo real
    for nome in extra_abas:
        wb.create_sheet(nome)["A1"] = "dados"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


LINHAS = [
    ("RS001", "CEEE", 111, 47921101087, None, "Rua A", "PELOTAS", "Pelotas"),
    ("RS002", "RGE SUL ", 222, 162996700103, None, "Rua B", "CANOAS", "POA"),
    ("RS003", "RGE", 333, 162996700104, "", "Rua C", "CANOAS", "POA"),
    ("RS004", "CEEE", 444, "#N/A", None, "Rua D", "BAGE", "Pelotas"),
    ("RS005", "COPREL", 555, 100178413, None, "Rua E", "ALTO", "PF"),
    ("RS006", "CEEE", 666, 47944601026, "protocolo já aberto", "Rua F", "RG", "Pelotas"),
    ("RS007", "ceee", 777, 47944601027.0, None, "Rua G", "RG", "Pelotas"),
]


def test_classifica_linhas():
    linhas = P.ler(_report(LINHAS))
    robo = {l.site: l for l in linhas if l.vai_para_robo}
    fora = {l.site: l.motivo for l in linhas if not l.vai_para_robo}
    assert set(robo) == {"RS001", "RS002", "RS003", "RS007"}
    assert robo["RS002"].concessionaria == "RGE"       # "RGE SUL " com espaço
    assert robo["RS003"].concessionaria == "RGE"       # só "RGE"
    assert robo["RS007"].uc_nova == "47944601027"      # float sem ".0"
    assert robo["RS001"].linha == 5
    assert "UC NOVA inválida" in fora["RS004"]
    assert "fora do robô" in fora["RS005"]
    assert fora["RS006"] == "já tem protocolo"


def test_para_na_primeira_linha_sem_site():
    conteudo = _report(LINHAS[:2] + [(None,) * 8] + LINHAS[2:])
    assert [l.site for l in P.ler(conteudo)] == ["RS001", "RS002"]


def test_erros_de_formato():
    with pytest.raises(P.PlanilhaInvalida):
        P.ler(b"isso nao e um excel")
    wb = openpyxl.Workbook()
    wb.active.title = "Outra"
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(P.PlanilhaInvalida, match="TEMPLATE"):
        P.ler(buf.getvalue())


def test_preenche_so_a_coluna_protocolo():
    original = _report(LINHAS)
    resultados = [
        {"linha": 5, "site": "RS001", "uc_nova": "47921101087", "protocolo": "2271468916"},
        {"linha": 6, "site": "RS002", "uc_nova": "162996700103", "protocolo": "protocolo já aberto"},
        {"linha": 2, "site": "RS003", "uc_nova": "162996700104", "protocolo": "123"},   # linha errada -> acha por site+UC
        {"linha": 10, "site": "RS006", "uc_nova": "47944601026", "protocolo": "999"},  # já preenchida
        {"linha": 5, "site": "XXX", "uc_nova": "1", "protocolo": "1"},                 # não existe
        {"linha": 11, "site": "RS007", "uc_nova": "47944601027", "protocolo": ""},     # sem protocolo: ignora
    ]
    saida, rel = P.preencher(original, resultados)
    ws = openpyxl.load_workbook(io.BytesIO(saida))["TEMPLATE"]
    assert ws["F5"].value == 2271468916
    assert ws["F6"].value == "protocolo já aberto"
    assert ws["F7"].value == 123
    assert ws["F10"].value == "protocolo já aberto"   # não sobrescreve
    assert ws["F11"].value is None
    assert ws["F5"].number_format == "@"               # estilo preservado
    escritos = [r for r in rel if r["escrito"]]
    assert len(escritos) == 3
    assert any("não encontrados" in r["obs"] for r in rel)
    assert any("já estava preenchida" in r["obs"] for r in rel)

    a, b = zipfile.ZipFile(io.BytesIO(original)), zipfile.ZipFile(io.BytesIO(saida))
    assert a.namelist() == b.namelist()
    alterados = [n for n in a.namelist() if a.read(n) != b.read(n)]
    assert alterados == ["xl/worksheets/sheet1.xml"]


def test_sem_nada_para_escrever_devolve_o_mesmo_arquivo():
    original = _report(LINHAS)
    saida, _ = P.preencher(original, [])
    assert saida == original


def test_celula_inexistente_e_criada_em_ordem():
    original = _report(LINHAS)
    saida = P._escrever_celulas(original, "TEMPLATE", {"K5": "abc", "A20": "1"})
    ws = openpyxl.load_workbook(io.BytesIO(saida))["TEMPLATE"]
    assert ws["K5"].value == "abc"
    assert ws["A20"].value == 1
    assert ws["F5"].value is None
