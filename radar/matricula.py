"""Leitura e análise da matrícula do imóvel (PDF escaneado da Caixa ou certidão).

1. OCR: transforma as páginas em texto (poppler + tesseract, instalados na nuvem).
2. Separa os atos (R-1, AV-2, ...) e classifica cada um.
3. Aponta riscos: ônus que continuam depois da consolidação da Caixa e não
   foram cancelados, terreno de marinha (laudêmio), documento antigo etc.

Por privacidade, o resultado guardado NÃO inclui nomes nem documentos de
pessoas: só o número, o tipo, o título e a data de cada ato.
"""

import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import List, Optional

# Palavras do título do ato -> (tipo, é ônus/risco?)
TIPOS = [
    (r"CANCELAMENTO|BAIXA|LEVANTAMENTO", "cancelamento", False),
    (r"CONSOLIDA", "consolidação da propriedade (Caixa)", False),
    (r"LEIL[AÃ]O|LEIL[OÕ]ES", "leilões negativos", False),
    (r"ALIEN\w*\W+FIDUC|FIDUCI[AÁ]RI", "alienação fiduciária", True),
    (r"HIPOTECA", "hipoteca", True),
    (r"PENHORA", "penhora", True),
    (r"INDISPONIBILIDADE", "indisponibilidade", True),
    (r"ARRESTO", "arresto", True),
    (r"SEQUESTRO|SEQ[UÜ]ESTRO", "sequestro", True),
    (r"USUFRUTO", "usufruto", True),
    # \b evita confundir com palavras como "RENUMERAÇÃO" ou "INSERÇÃO"
    (r"\bCITA[CÇ][AÃ]O\b|\bA[CÇ][AÃ]O\b|\bPROTESTO\b|\bEXECU[CÇ][AÃ]O\b", "ação judicial / execução", True),
    (r"INALIENABILIDADE|IMPENHORABILIDADE|INCOMUNICABILIDADE", "cláusula restritiva", True),
    (r"COMPRA E VENDA|VENDA E COMPRA|HA[VZ]IDO\s+[PF]OR\s+COMPR|\bCOMPRA\b|TRANSMISS|ADJUDICA|ARREMATA|DOA[CÇ][AÃ]O|PARTILHA|PERMUTA", "transmissão (troca de dono)", False),
    (r"CONSTRU[CÇ][AÃ]O|HABITE|INSTITUI[CÇ][AÃ]O|CONVEN[CÇ][AÃ]O|ESPECIFICA", "construção / condomínio", False),
]

# Cabeçalho de ato no começo da linha. Aceita os formatos "AV-8/125.401 - TÍTULO - Prenotado...",
# "R.01-124.401 - ..." (numeração antiga) e erros comuns de OCR ("AV-S5" em vez de "AV-5").
_ATO = re.compile(
    # o traço depois do número da matrícula é obrigatório: separa "R.01- 124.401-" de valores como "R$12.324,00"
    r"^.{0,3}?(R|AV)\s*[-.,$]?\s*[SO]?0*(\d{1,3})\s*[-–—/.,]\s*\d{1,3}(?:[.,]?\d{3})+\s*[-–—]\s*([^\n:]{0,90})",
    re.I | re.M,
)
_DATA = re.compile(r"(\d{2})/(\d{2})/(\d)\.?(\d{3})")  # aceita "30/01/2.012" das matrículas antigas


def ocr_pdf(pdf: bytes, paginas_max: int = 30) -> str:
    """Converte o PDF em texto. Precisa de pdftoppm e tesseract (com português)."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        raise RuntimeError("OCR indisponível: faltam pdftoppm/tesseract (só existem na nuvem)")
    with tempfile.TemporaryDirectory() as pasta:
        arq = Path(pasta) / "m.pdf"
        arq.write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", "200", "-gray", "-l", str(paginas_max), "-png", str(arq), str(Path(pasta) / "pg")],
                       check=True, timeout=300)
        textos = []
        # Páginas digitadas têm texto embutido: lê direto (mais fiel que o OCR)
        if shutil.which("pdftotext"):
            r = subprocess.run(["pdftotext", "-layout", str(arq), "-"], capture_output=True, text=True, timeout=120)
            textos.append(r.stdout)
        for img in sorted(Path(pasta).glob("pg*.png")):
            r = subprocess.run(["tesseract", str(img), "-", "-l", "por", "--psm", "4"], capture_output=True, text=True, timeout=300)
            textos.append(r.stdout)
        return "\n".join(textos)


def _classificar(titulo: str):
    for padrao, tipo, onus in TIPOS:
        if re.search(padrao, titulo, re.I):
            return tipo, onus
    return "outro", False


def _data_do_ato(trecho: str) -> Optional[str]:
    m = _DATA.search(trecho)
    if not m:
        return None
    d, mes, mil, resto = m.groups()
    return f"{mil}{resto}-{mes}-{d}"


def analisar_texto(texto: str, data_documento: Optional[str] = None) -> dict:
    """Separa os atos e calcula os riscos."""
    achados = list(_ATO.finditer(texto))
    atos: List[dict] = []
    for i, m in enumerate(achados):
        corpo = texto[m.end(): achados[i + 1].start() if i + 1 < len(achados) else len(texto)]
        titulo = re.split(r"\s[-–]\s*(?:Prenotad|Protocol)", m.group(3), flags=re.I)[0]
        titulo = re.sub(r"\s+", " ", titulo).strip(" -–,.")
        # O título classifica; se ele não disser nada, olha o começo do texto do ato
        tipo, onus = _classificar(titulo)
        if tipo == "outro":
            # junta palavras quebradas no fim da linha ("fidu-\nciariamente")
            tipo, onus = _classificar(re.sub(r"-\s*\n\s*", "", m.group(3) + corpo[:450]).replace("\n", " "))
        # Matrículas antigas não têm título: "R.01- 124.401- DAJ Número ..." vira o tipo do ato
        if re.match(r"DAJ|N[uú]mero|\d", titulo, re.I) or not titulo:
            titulo = tipo
        # Atos de cancelamento: quais registros eles cancelam (ex.: "R-3", "R.03", "AV-2")
        cancela = []
        if tipo == "cancelamento":
            cancela = [f"{a.upper()}-{int(n)}" for a, n in re.findall(r"\b(R|AV)\s*[-.]?\s*0*(\d{1,3})\b", corpo[:600], re.I)]
        atos.append({
            "ato": f"{m.group(1).upper()}-{int(m.group(2))}",
            "titulo": titulo.title()[:80],
            "tipo": tipo,
            "onus": onus,
            "data": _data_do_ato(m.group(0) + corpo[:400]),
            "cancela": cancela,
        })

    vistos, unicos = set(), []
    for a in atos:
        if a["ato"] not in vistos:
            vistos.add(a["ato"])
            unicos.append(a)
    numero = lambda a: (int(a["ato"].split("-")[1]), a["ato"])  # noqa: E731
    atos = sorted(unicos, key=numero)

    cancelados = {c for a in atos for c in a["cancela"]}
    pos_consolidacao = False
    riscos, ok = [], []
    for a in atos:
        a["cancelado"] = a["ato"] in cancelados
        if a["tipo"].startswith("consolidação"):
            pos_consolidacao = True
        a["depois_da_consolidacao"] = pos_consolidacao and not a["tipo"].startswith("consolidação")

    consolidou = any(a["tipo"].startswith("consolidação") for a in atos)
    leilao_neg = any(a["tipo"] == "leilões negativos" for a in atos)
    if consolidou:
        ok.append("Propriedade consolidada em nome da Caixa (retomada por falta de pagamento): normal neste tipo de venda.")
    if leilao_neg:
        ok.append("Leilões negativos averbados: a Caixa pode vender livremente.")

    for a in atos:
        if not a["onus"] or a["cancelado"]:
            continue
        if a["tipo"] == "alienação fiduciária" and consolidou:
            continue  # é a dívida que deu origem à retomada; some com a consolidação
        nivel = "alto" if (a["depois_da_consolidacao"] or not consolidou) else "medio"
        riscos.append({"nivel": nivel, "texto": f"{a['tipo'].capitalize()} no {a['ato']}{' (depois da consolidação)' if a['depois_da_consolidacao'] else ''} sem cancelamento encontrado."})

    corrido = re.sub(r"\s+", " ", texto)
    if re.search(r"terreno de marinha|foreiro|aforamento|enfiteuse|laud[eê]mio|dom[ií]nio [uú]til", corrido, re.I):
        riscos.append({"nivel": "medio", "texto": "Possível terreno de marinha/foreiro: pode haver laudêmio (cerca de 5%) e taxa anual à União (SPU)."})
    if re.search(r"ocupad[oa]|invas|esbulho|reintegra[cç][aã]o|imiss[aã]o na posse", corrido, re.I):
        riscos.append({"nivel": "medio", "texto": "A matrícula menciona ocupação/posse (ex.: imissão na posse): confira a situação do imóvel."})
    if not atos:
        riscos.append({"nivel": "alto", "texto": "Não consegui separar os atos da matrícula (texto ilegível). Leia o PDF ou peça a certidão atualizada."})
    # Os atos são numerados em sequência (R-1, R-2, AV-3...): números que faltam não foram lidos
    numeros = {int(a["ato"].split("-")[1]) for a in atos}
    faltando = [n for n in range(1, max(numeros, default=0) + 1) if n not in numeros]
    if faltando:
        riscos.append({"nivel": "medio", "texto": f"Não consegui ler {'o ato' if len(faltando) == 1 else 'os atos'} nº {', '.join(map(str, faltando))} "
                                                  "(OCR). Confira no PDF da matrícula se há penhora, hipoteca ou outro ônus."})

    if data_documento:
        try:
            idade = (date.today() - date.fromisoformat(data_documento)).days
            if idade > 30:
                riscos.append({"nivel": "medio", "texto": f"A matrícula disponível é de {data_documento[8:10]}/{data_documento[5:7]}/{data_documento[:4]} ({idade // 30} meses). Peça a certidão atualizada (ONR) antes de comprar."})
        except ValueError:
            pass

    area = re.search(r"[áa]rea\s+(?:real\s+)?privativa\s+(?:de\s+)?([\d.]+,\d{1,2})\s*m", corrido, re.I)
    # Linhas com cara de cabeçalho de ato que o padrão não reconheceu (sem nomes:
    # só os primeiros caracteres, que trazem número, título e data do ato)
    nao_reconhecidos = []
    for linha in texto.splitlines():
        if (re.search(r"Prenota", linha, re.I) or re.match(r".{0,3}?(R|AV)\W{0,2}\w{0,2}\d", linha)) and not _ATO.search(linha) \
                and not re.match(r".{0,3}?R\$\s*\d{1,3}[.,]\d{3}", linha):  # valores em reais
            nao_reconhecidos.append(re.sub(r"\s+", " ", linha).strip()[:70])
    altos = sum(r["nivel"] == "alto" for r in riscos)
    medios = sum(r["nivel"] == "medio" for r in riscos)
    nota = max(0, 10 - 4 * altos - 1.5 * medios)
    return {
        "atos": atos,
        "riscos": riscos,
        "pontos_ok": ok,
        "nota_risco": round(nota, 1),  # 10 = sem riscos encontrados
        "resumo": ("Risco alto" if altos else "Atenção" if medios else "Sem riscos encontrados na matrícula"),
        "area_registrada": area.group(1) if area else None,
        "data_documento": data_documento,
        "caracteres_lidos": len(texto),
        "atos_nao_lidos": faltando,
        "cabecalhos_nao_reconhecidos": nao_reconhecidos[:30],
    }


def data_do_pdf(pdf: bytes) -> Optional[str]:
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", pdf)
    return f"{m.group(1).decode()}-{m.group(2).decode()}-{m.group(3).decode()}" if m else None
