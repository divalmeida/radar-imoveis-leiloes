"""Coletor de apartamentos do Chaves na Mão (chavesnamao.com.br).

Cada página de busca traz 15 anúncios em um bloco de dados organizado
(schema.org/ld+json). A página de cada anúncio traz a descrição, de onde
tiramos se aceita financiamento, além de condomínio, IPTU e data de publicação.
"""

import json
import math
import re
from typing import Dict, List, Optional

from radar.http import baixar

SITE = "https://www.chavesnamao.com.br"
POR_PAGINA = 15
LIMITE_PAGINAS = 200

_BLOCO_LD = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
_ACEITA_FIN = re.compile(r"aceita\w*\s+(o\s+)?financiamento|financi[áa]vel|aceita\s+fgts|minha casa,? minha vida|mcmv|financiamento banc[áa]rio", re.I)
_NAO_ACEITA_FIN = re.compile(r"n[ãa]o\s+aceita\w*\s+financiamento|somente\s+[àa]\s+vista|apenas\s+[àa]\s+vista|s[óo]\s+[àa]\s+vista", re.I)


def _url_busca(negocio: str, slug: str, quartos: int, preco_max: int, pagina: int) -> str:
    caminho = "apartamentos-a-venda" if negocio == "compra" else "apartamentos-para-alugar"
    url = f"{SITE}/{caminho}/{slug}/{quartos}-quartos/?filtro=pmax:{preco_max}"
    return url + (f"&pg={pagina}" if pagina > 1 else "")


def _listagem(html: str) -> Optional[dict]:
    for bloco in _BLOCO_LD.findall(html):
        try:
            dados = json.loads(bloco)
        except ValueError:
            continue
        if isinstance(dados, dict) and dados.get("@type") == "RealEstateListing":
            return dados
    return None


def _numero(texto) -> Optional[float]:
    m = re.search(r"[\d.,]+", str(texto or ""))
    if not m:
        return None
    try:
        return float(m.group().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _anuncio(oferta: dict, negocio: str, cidade: dict) -> Optional[dict]:
    imovel = oferta.get("itemOffered") or {}
    if imovel.get("@type") != "Apartment":
        return None
    endereco = imovel.get("address") or {}
    if not (endereco.get("addressRegion") or "").startswith(cidade["nome"]):
        return None  # o site às vezes completa a lista com cidades vizinhas
    url = oferta.get("url") or ""
    m = re.search(r"/id-(\d+)/", url)
    if not m:
        return None
    geo = imovel.get("geo") or {}
    return {
        "id": f"cnm-{m.group(1)}",
        "fonte": "Chaves na Mão",
        "negocio": negocio,
        "titulo": (oferta.get("name") or "").strip(),
        "preco": _numero(oferta.get("price")),
        "quartos": imovel.get("numberOfBedrooms"),
        "banheiros": imovel.get("numberOfBathroomsTotal"),
        "area": _numero((imovel.get("floorSize") or {}).get("unitText")),
        "bairro": (endereco.get("addressLocality") or "").strip(),
        "cidade": cidade["nome"],
        "uf": cidade["uf"],
        "endereco": (endereco.get("streetAddress") or "").strip(" ,"),
        "cep": endereco.get("postalCode"),
        "lat": float(geo["latitude"]) if geo.get("latitude") else None,
        "lon": float(geo["longitude"]) if geo.get("longitude") else None,
        "imagem": imovel.get("image"),
        "anunciante": ((oferta.get("offeredBy") or {}).get("name") or "").strip(),
        "na_planta": "/lancamento/" in url,
        "link": url,
    }


def buscar(negocio: str, cidade: dict, quartos: int, preco_max: int) -> List[dict]:
    """Percorre todas as páginas de uma busca e devolve os anúncios."""
    anuncios: Dict[str, dict] = {}
    pagina, total_paginas = 1, 1
    while pagina <= min(total_paginas, LIMITE_PAGINAS):
        html = baixar(_url_busca(negocio, cidade["slug"], quartos, preco_max, pagina)).decode("utf-8", "replace")
        listagem = _listagem(html)
        if not listagem:
            break
        ofertas = (listagem.get("offers") or {})
        if pagina == 1:
            total = ofertas.get("numberOfItems") or 0
            total_paginas = math.ceil(total / POR_PAGINA)
            print(f"[Chaves na Mão] {negocio} {cidade['nome']}: {total} anúncios ({total_paginas} páginas)", flush=True)
        for oferta in ofertas.get("itemListElement") or []:
            anuncio = _anuncio(oferta, negocio, cidade)
            if anuncio:
                anuncios[anuncio["id"]] = anuncio
        pagina += 1
    return list(anuncios.values())


def detalhes(anuncio: dict) -> dict:
    """Abre a página do anúncio: financiamento, condomínio, IPTU e datas."""
    html = baixar(anuncio["link"]).decode("utf-8", "replace")
    texto = html.replace('\\"', '"')
    info: dict = {"detalhado": True}

    def procurar(no):
        """Acha o pedaço dos dados que tem a data de publicação (pode estar aninhado)."""
        if isinstance(no, dict):
            if no.get("datePosted"):
                return no
            no = list(no.values())
        if isinstance(no, list):
            for item in no:
                achado = procurar(item)
                if achado:
                    return achado
        return None

    descricao = ""
    for bloco in _BLOCO_LD.findall(html):
        try:
            anuncio_ld = procurar(json.loads(bloco))
        except ValueError:
            continue
        if anuncio_ld:
            descricao = anuncio_ld.get("description") or ""
            info["publicado_em"] = (anuncio_ld.get("datePosted") or "")[:10]
            break

    # O resumo acima costuma ser genérico; o texto escrito pelo anunciante vem
    # nos dados da página. A página também traz imóveis parecidos (cada um com
    # outra "reference"), então só vale o que aparece antes do primeiro deles.
    def decodificar(trecho: str) -> str:
        try:
            return json.loads(f'"{trecho}"')
        except ValueError:
            return trecho

    referencias = list(re.finditer(r'"reference":"([^"]*)"', texto))
    limite = len(texto)
    if referencias:
        propria = referencias[0].group(1)
        limite = next((r.start() for r in referencias if r.group(1) != propria), len(texto))
    proprias = [decodificar(m.group(1)) for m in re.finditer(r'"description":"((?:[^"\\]|\\.){20,})"', texto) if m.start() < limite]
    descricao = re.sub(r"<[^>]+>", " ", max(proprias + [descricao], key=len))
    descricao = re.sub(r"\\u003c[^>]*?\\u003e|<[^>]+>|\\u003cbr/\\u003e", " ", descricao)

    if _NAO_ACEITA_FIN.search(descricao):
        info["financiamento"] = False
    elif _ACEITA_FIN.search(descricao):
        info["financiamento"] = True
    else:
        info["financiamento"] = None  # o anúncio não diz

    m = re.search(r'"condominiumFee":"([^"]*)"', texto)
    info["condominio"] = _numero(m.group(1)) if m else None
    m = re.search(r'"iptuValue":"([^"]*)"', texto)
    info["iptu"] = _numero(m.group(1)) if m else None
    return info
