"""Leitura da página de detalhe de um imóvel da Caixa (um imóvel por vez).

Usa só o acesso normal. Se a Caixa pedir captcha, avisa e para: não tentamos burlar.
"""

import html as html_lib
import re
from typing import Optional

from radar.http import baixar

SITE = "https://venda-imoveis.caixa.gov.br"
URL_DETALHE = SITE + "/sistema/detalhe-imovel.asp?hdnimovel={numero}"
URL_MATRICULA = SITE + "/editais/matricula/{uf}/{numero}.pdf"


class Bloqueado(RuntimeError):
    """A Caixa respondeu com o captcha anti-robô."""


def _texto(pagina: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", pagina, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", t, flags=re.I)
    t = html_lib.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"[ \t\xa0]+", " ", t)


def _campo(texto: str, rotulo: str) -> Optional[str]:
    m = re.search(rotulo + r"\s*:?\s*([^\n]+)", texto, re.I)
    return m.group(1).strip() if m else None


def _reais(valor: Optional[str]) -> Optional[float]:
    if not valor:
        return None
    m = re.search(r"([\d.]+,\d{2})", valor)
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def baixar_detalhe(numero: str) -> str:
    pagina = baixar(URL_DETALHE.format(numero=numero)).decode("utf-8", "replace")
    if "Radware" in pagina or "captcha" in pagina.lower()[:3000]:
        raise Bloqueado("a Caixa pediu captcha (anti-robô) para a página do imóvel")
    return pagina


def ler_detalhe(pagina: str) -> dict:
    """Extrai os dados da página. Devolve {"disponivel": False} se o imóvel saiu da venda."""
    texto = _texto(pagina)
    if "Valor de avalia" not in texto:
        return {"disponivel": False}
    # Os campos ficam um por linha; juntamos as linhas para os textos longos
    corrido = re.sub(r"\s*\n\s*", "\n", texto)
    pagamento = re.search(r"FORMAS DE PAGAMENTO ACEITAS:(.*?)(?:REGRAS PARA PAGAMENTO|Corretores credenciados)", corrido, re.S)
    pagamento = re.sub(r"\s+", " ", pagamento.group(1)).strip() if pagamento else ""
    condominio = re.search(r"Condom[ií]nio:\s*([^\n]+)", corrido)
    tributos = re.search(r"Tributos:\s*([^\n]+)", corrido)
    descricao = re.search(r"Descri[cç][aã]o:\s*(.*?)(?:FORMAS DE PAGAMENTO|$)", corrido, re.S)
    area = re.search(r"[ÁA]rea privativa\s*=\s*([\d.,]+)", corrido)
    area_terreno = re.search(r"[ÁA]rea do terreno\s*=\s*([\d.,]+)", corrido)
    visivel = re.sub(r"\s+", " ", corrido)
    ocupacao = None
    if re.search(r"im[óo]vel\s+desocupado|situa[cç][aã]o:\s*desocupad", visivel, re.I):
        ocupacao = "desocupado"
    elif re.search(r"im[óo]vel\s+ocupado|situa[cç][aã]o:\s*ocupad", visivel, re.I):
        ocupacao = "ocupado"
    # O botão de agendar visita chama Imovel_Ocupado() quando a Caixa marca o imóvel como ocupado
    if ocupacao is None and re.search(r"(?<!function )Imovel_Ocupado\(\)", pagina):
        ocupacao = "ocupado"
    numero_area = lambda m: float(m.group(1).replace(".", "").replace(",", ".")) if m else None  # noqa: E731
    return {
        "disponivel": True,
        "valor_avaliacao": _reais(_campo(corrido, r"Valor de avalia[cç][aã]o")),
        "valor_minimo": _reais(_campo(corrido, r"Valor m[ií]nimo de venda")),
        "tipo": _campo(corrido, r"Tipo de im[óo]vel"),
        "quartos": _campo(corrido, r"Quartos"),
        "matricula": _campo(corrido, r"Matr[ií]cula\(s\)"),
        "comarca": _campo(corrido, r"Comarca"),
        "oficio": _campo(corrido, r"Of[ií]cio"),
        "inscricao_imobiliaria": _campo(corrido, r"Inscri[cç][aã]o imobili[aá]ria"),
        "leiloes_negativos": _campo(corrido, r"Averba[cç][aã]o dos leil[oõ]es negativos"),
        "area_privativa": numero_area(area),
        "area_terreno": numero_area(area_terreno),
        "endereco": _campo(corrido, r"Endere[cç]o"),
        "descricao": re.sub(r"\s+", " ", descricao.group(1)).strip(" .") if descricao else None,
        "formas_pagamento": pagamento,
        "aceita_financiamento": bool(re.search(r"financiamento", pagamento, re.I)) and not re.search(r"exclusivamente [àa] vista", pagamento, re.I),
        "aceita_fgts": bool(re.search(r"FGTS", pagamento)) and not re.search(r"n[ãa]o permite.{0,20}FGTS", pagamento, re.I),
        "aceita_parcelamento": bool(re.search(r"parcelamento", pagamento, re.I)) and not re.search(r"n[ãa]o (aceita|permite).{0,15}parcelamento", pagamento, re.I),
        "regra_condominio": condominio.group(1).strip() if condominio else None,
        "regra_tributos": tributos.group(1).strip() if tributos else None,
        "ocupacao": ocupacao,
    }


def baixar_matricula(numero: str, uf: str = "BA") -> bytes:
    conteudo = baixar(URL_MATRICULA.format(uf=uf, numero=numero), timeout=90)
    if not conteudo.startswith(b"%PDF"):
        if b"Radware" in conteudo[:5000]:
            raise Bloqueado("a Caixa pediu captcha (anti-robô) para a matrícula")
        raise RuntimeError("a Caixa não tem a matrícula deste imóvel para baixar")
    return conteudo
