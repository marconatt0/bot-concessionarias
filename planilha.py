"""Leitura do REPORT de protocolos e escrita dos protocolos de volta no arquivo.

Regras (combinadas com o usuário):
- Lê a aba TEMPLATE; o cabeçalho é a linha que tem "Sites com Falha" na coluna B.
- Vai para o robô: concessionária CEEE ou qualquer variação com "RGE", Protocolo vazio
  e UC NOVA numérica. O resto fica "fora do robô", com o motivo.
- Na volta, só a coluna Protocolo é alterada; o resto do arquivo fica como estava.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, asdict

import openpyxl
from lxml import etree

ABA = "TEMPLATE"
CAB_SITE = "sites com falha"
COLUNAS = {  # nome normalizado do cabeçalho -> chave interna
    "sites com falha de ac": "site",
    "concessionaria": "concessionaria",
    "uc antiga": "uc_antiga",
    "uc nova": "uc_nova",
    "protocolo": "protocolo",
    "endereco": "endereco",
    "cidade": "cidade",
    "regional": "regional",
}
MIN_DIGITOS_UC = 6


class PlanilhaInvalida(Exception):
    pass


def _norm(texto) -> str:
    s = unicodedata.normalize("NFD", str(texto or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def _texto(valor) -> str:
    """Converte o valor da célula em texto sem perder dígitos (números grandes, floats .0)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def concessionaria_robo(valor) -> str | None:
    n = _norm(valor).upper()
    if "RGE" in n:
        return "RGE"
    if n == "CEEE":
        return "CEEE"
    return None


@dataclass
class Linha:
    linha: int            # número da linha no Excel
    site: str
    concessionaria_original: str
    concessionaria: str | None   # CEEE / RGE / None
    uc_nova: str
    protocolo_atual: str
    endereco: str
    cidade: str
    vai_para_robo: bool
    motivo: str           # por que ficou fora (vazio se vai para o robô)

    def para_api(self) -> dict:
        return {"linha": self.linha, "site": self.site,
                "concessionaria": self.concessionaria, "uc_nova": self.uc_nova}

    def para_tabela(self) -> dict:
        d = asdict(self)
        d.pop("vai_para_robo")
        return d


def _achar_cabecalho(ws):
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 30)):
        for cell in row:
            if CAB_SITE in _norm(cell.value):
                mapa = {}
                for c in row:
                    chave = COLUNAS.get(_norm(c.value))
                    if chave:
                        mapa[chave] = c.column
                faltando = {"site", "concessionaria", "uc_nova", "protocolo"} - mapa.keys()
                if faltando:
                    raise PlanilhaInvalida(
                        "Não achei as colunas " + ", ".join(sorted(faltando)) + f" no cabeçalho da aba {ABA}.")
                return cell.row, mapa
    raise PlanilhaInvalida(f'Não achei o cabeçalho "Sites com Falha de AC" na aba {ABA}.')


def ler(conteudo: bytes) -> list[Linha]:
    """Lê os valores (resultado dos PROCV, já calculados pelo Excel) da aba TEMPLATE."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True)
    except Exception as e:  # arquivo corrompido, não é xlsx etc.
        raise PlanilhaInvalida(f"Não consegui abrir o arquivo como Excel (.xlsx): {e}") from e
    if ABA not in wb.sheetnames:
        raise PlanilhaInvalida(f'A planilha não tem a aba "{ABA}".')
    ws = wb[ABA]
    lin_cab, col = _achar_cabecalho(ws)

    linhas: list[Linha] = []
    sem_calculo = 0
    for r in range(lin_cab + 1, ws.max_row + 1):
        site = _texto(ws.cell(r, col["site"]).value)
        if not site:
            break  # primeira linha sem site encerra a lista
        conc_orig = _texto(ws.cell(r, col["concessionaria"]).value)
        conc = concessionaria_robo(conc_orig)
        uc = _texto(ws.cell(r, col["uc_nova"]).value)
        prot = _texto(ws.cell(r, col["protocolo"]).value)
        end = _texto(ws.cell(r, col["endereco"]).value) if "endereco" in col else ""
        cid = _texto(ws.cell(r, col["cidade"]).value) if "cidade" in col else ""
        if not conc_orig and not uc:
            sem_calculo += 1

        uc_ok = uc.isdigit() and len(uc) >= MIN_DIGITOS_UC
        if conc is None:
            motivo = f"concessionária fora do robô ({conc_orig or 'vazia'})"
        elif prot:
            motivo = "já tem protocolo"
        elif not uc_ok:
            motivo = f"UC NOVA inválida ({uc or 'vazia'}) — pesquisar pelo endereço"
        else:
            motivo = ""
        linhas.append(Linha(r, site, conc_orig, conc, uc, prot, end, cid, motivo == "", motivo))

    if linhas and sem_calculo == len(linhas):
        raise PlanilhaInvalida(
            "As colunas Concessionária e UC NOVA estão vazias em todas as linhas. "
            "Abra a planilha no Excel, deixe os PROCV calcularem, salve e envie de novo.")
    return linhas


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _col_letra(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _col_num(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n


def _caminho_aba(z: zipfile.ZipFile, nome: str) -> str:
    wb = etree.fromstring(z.read("xl/workbook.xml"))
    rid = None
    for sh in wb.iter(f"{{{NS}}}sheet"):
        if sh.get("name") == nome:
            rid = sh.get(f"{{{NS_REL}}}id")
    rels = etree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.iter(f"{{{NS_PKG}}}Relationship"):
        if rel.get("Id") == rid:
            alvo = rel.get("Target").lstrip("/")
            return alvo if alvo.startswith("xl/") else "xl/" + alvo
    raise PlanilhaInvalida(f'Não achei o XML da aba "{nome}".')


def _escrever_celulas(conteudo: bytes, aba: str, valores: dict[str, str]) -> bytes:
    """Altera só as células pedidas no XML da aba; o resto do pacote é copiado byte a byte."""
    entrada = zipfile.ZipFile(io.BytesIO(conteudo))
    caminho = _caminho_aba(entrada, aba)
    raiz = etree.fromstring(entrada.read(caminho))
    sheet_data = raiz.find(f"{{{NS}}}sheetData")
    linhas = {int(r.get("r")): r for r in sheet_data.findall(f"{{{NS}}}row")}

    for ref, texto in valores.items():
        num_linha = int(re.search(r"\d+", ref).group(0))
        row = linhas.get(num_linha)
        if row is None:
            row = etree.SubElement(sheet_data, f"{{{NS}}}row", r=str(num_linha))
            linhas[num_linha] = row
            # mantém as linhas em ordem
            sheet_data[:] = sorted(sheet_data, key=lambda e: int(e.get("r")))
        cel = next((c for c in row.findall(f"{{{NS}}}c") if c.get("r") == ref), None)
        if cel is None:
            cel = etree.Element(f"{{{NS}}}c", r=ref)
            pos = next((i for i, c in enumerate(row) if c.tag == f"{{{NS}}}c" and _col_num(c.get("r")) > _col_num(ref)), len(row))
            row.insert(pos, cel)
        for filho in list(cel):
            cel.remove(filho)
        cel.attrib.pop("t", None)
        if texto == "":
            continue  # célula vazia (mantém só o estilo)
        if texto.isdigit() and len(texto) < 16:
            etree.SubElement(cel, f"{{{NS}}}v").text = texto
        else:
            cel.set("t", "inlineStr")
            is_ = etree.SubElement(cel, f"{{{NS}}}is")
            etree.SubElement(is_, f"{{{NS}}}t").text = texto

    novo_xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            dados = novo_xml if info.filename == caminho else entrada.read(info.filename)
            z.writestr(info, dados, compress_type=info.compress_type)
    return saida.getvalue()


def preencher(conteudo: bytes, resultados: list[dict]) -> tuple[bytes, list[dict]]:
    """Escreve os protocolos na coluna Protocolo e devolve (arquivo, relatório).

    resultados: [{linha, site, uc_nova, protocolo}] — só os que têm protocolo.
    Casa por site + UC NOVA (primeiro na própria linha, depois procurando na aba),
    para não escrever na linha errada se a planilha mudou.
    Só a célula do protocolo é alterada; fórmulas, valores calculados, formatação
    e as outras abas ficam exatamente como vieram.
    """
    valores = openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True)[ABA]
    lin_cab, col = _achar_cabecalho(valores)
    letra_prot = _col_letra(col["protocolo"])

    indice = {}
    for r in range(lin_cab + 1, valores.max_row + 1):
        site = _texto(valores.cell(r, col["site"]).value)
        if not site:
            break
        indice.setdefault((site.upper(), _texto(valores.cell(r, col["uc_nova"]).value)), r)

    relatorio = []
    escrever: dict[str, str] = {}
    for res in resultados:
        prot = str(res.get("protocolo") or "").strip()
        if not prot:
            continue
        chave = (str(res.get("site", "")).strip().upper(), str(res.get("uc_nova", "")).strip())
        r = int(res.get("linha") or 0)
        ok_na_linha = r > lin_cab and (
            _texto(valores.cell(r, col["site"]).value).upper(),
            _texto(valores.cell(r, col["uc_nova"]).value)) == chave
        if not ok_na_linha:
            r = indice.get(chave)
        if not r:
            relatorio.append({**res, "escrito": False, "obs": "site + UC não encontrados na planilha"})
            continue
        if _texto(valores.cell(r, col["protocolo"]).value):
            relatorio.append({**res, "linha": r, "escrito": False, "obs": "célula Protocolo já estava preenchida"})
            continue
        escrever[f"{letra_prot}{r}"] = prot
        relatorio.append({**res, "linha": r, "escrito": True, "obs": ""})

    if not escrever:
        return conteudo, relatorio
    return _escrever_celulas(conteudo, ABA, escrever), relatorio
