"""Reconhece lotes de eletrônicos, eletrodomésticos e celulares pela descrição.

Usado pelos sites de leilão que não separam essas categorias.
"""

import re

_INTERESSE = re.compile(
    r"\b(celular(es)?|smartphones?|iphones?|ipads?|tablets?|galaxy|xiaomi|redmi|motorola|"
    r"notebooks?|laptops?|macbook|computador(es)?|desktops?|monitor(es)?|impressora|"
    r"televis(or|ores|ão)|tv\b|smart ?tv|som|caixa de som|fone|headphone|"
    r"videogames?|playstation|ps[45]|xbox|nintendo|c[âa]meras?|drone|"
    r"eletr[ôo]nicos?|eletrodom[ée]sticos?|eletroport[áa]teis|inform[áa]tica|"
    r"geladeiras?|refrigerador(es)?|freezers?|fog[ãa]o|fog[õo]es|micro-?ondas|lava-?lou[çc]as|"
    r"m[áa]quinas? de lavar|lavadoras?|secadoras?|ar[- ]condicionado|split|ventiladores?|"
    r"liquidificador|airfryer|air fryer|cafeteira|aspirador)\b",
    re.I,
)
# Lotes enormes de sucata ou de equipamentos industriais mencionam "monitor" ou
# "ventilador" no meio de dezenas de itens: ficam de fora
_EXCLUIR = re.compile(r"\b(sucata|ve[íi]culo|caminh[ãa]o|[ôo]nibus|empilhadeira|im[óo]vel|terreno|apartamento)\b", re.I)


def eh_de_interesse(texto: str) -> bool:
    return bool(_INTERESSE.search(texto or "")) and not _EXCLUIR.search(texto or "")


def so_pj(texto: str) -> bool:
    """O lote é só para empresas (CNPJ)?"""
    return bool(re.search(r"(somente|exclusivamente|apenas)\s+(para\s+)?(pessoas?\s+jur[íi]dicas?|PJ|CNPJ|empresas)", texto or "", re.I))
