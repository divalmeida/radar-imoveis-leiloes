"""Coletor de apartamentos do QuintoAndar (quintoandar.com.br).

Usa a mesma busca que o site chama quando você clica em "Ver mais"
(apigw.prod.quintoandar.com.br), sem login e sem contornar nenhuma proteção.
O QuintoAndar só tem anúncios em algumas cidades (na Bahia, hoje, Salvador).
"""

import json
import time
import unicodedata
import re
import urllib.request
from typing import List

from radar.config import PAUSA_ENTRE_REQUISICOES
from radar.http import USER_AGENT

API = "https://apigw.prod.quintoandar.com.br/house-listing-search/v3/search/list"
SITE = "https://www.quintoandar.com.br"
POR_PAGINA = 60
LIMITE_PAGINAS = 40
CAMPOS = ["id", "salePrice", "rent", "area", "bedrooms", "bathrooms", "parkingSpaces", "address",
          "neighbourhood", "city", "iptuPlusCondominium", "coverImage", "isPrimaryMarket"]


def _slug(cidade: dict) -> str:
    texto = unicodedata.normalize("NFD", cidade["nome"]).encode("ascii", "ignore").decode().lower()
    return f"{re.sub(r'[^a-z0-9]+', '-', texto).strip('-')}-{cidade['uf'].lower()}-brasil"


def _pagina(negocio: str, slug: str, quartos: int, preco_max: int, offset: int) -> dict:
    corpo = {
        "context": {"isSSR": False, "listShowing": True, "mapShowing": True, "numPhotos": 1},
        "fields": CAMPOS,
        "filters": {
            "availability": "ANY", "occupancy": "ANY", "origin": "HYBRID",
            "businessContext": "SALE" if negocio == "compra" else "RENT",
            "houseSpecs": {"bedrooms": {"range": {"min": quartos, "max": 10}}, "houseTypes": ["APARTMENT"],
                           "area": {"range": {}}, "bathrooms": {"range": {}}, "parkingSpace": {"range": {}},
                           "suites": {"range": {}}, "amenities": [], "installations": []},
            "location": {"coordinate": {}, "countryCode": "BR", "neighborhoods": [], "viewport": {}},
            "priceRange": [{"costType": "SALE_PRICE" if negocio == "compra" else "RENT_PRICE",
                            "range": {"min": 0, "max": preco_max}}],
            "partnerIds": [], "specialConditions": [], "excludedSpecialConditions": [], "categories": [],
            "unknownSlugs": [], "enableFlexibleSearch": False, "selectedHouses": [], "blocklist": [],
        },
        "locationDescriptions": [{"description": slug}],
        "pagination": {"offset": offset, "pageSize": POR_PAGINA},
        "slug": slug,
        "sorting": {"criteria": "MOST_RECENT", "order": "DESC"},
        "topics": [],
    }
    pedido = urllib.request.Request(API, data=json.dumps(corpo).encode(), headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(pedido, timeout=40) as resposta:
        dados = json.loads(resposta.read())
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return dados.get("hits") or {}


def buscar(negocio: str, cidade: dict, quartos: int, preco_max: int) -> List[dict]:
    slug = _slug(cidade)
    anuncios = {}
    offset, total = 0, None
    for _ in range(LIMITE_PAGINAS):
        hits = _pagina(negocio, slug, quartos, preco_max, offset)
        if total is None:
            total = (hits.get("total") or {}).get("value", 0)
            print(f"[QuintoAndar] {negocio} {cidade['nome']}: {total} anúncios", flush=True)
        lista = hits.get("hits") or []
        for item in lista:
            s = item.get("_source") or {}
            if (s.get("city") or "") != cidade["nome"]:
                continue  # a busca às vezes traz cidades vizinhas
            preco = s.get("salePrice") if negocio == "compra" else s.get("rent")
            id_ = s.get("id")
            if not id_ or not preco:
                continue
            anuncios[id_] = {
                "id": f"qa-{id_}",
                "fonte": "QuintoAndar",
                "negocio": negocio,
                "titulo": f"Apartamento com {s.get('bedrooms')} quartos em {s.get('neighbourhood')}",
                "preco": float(preco),
                "quartos": s.get("bedrooms"),
                "banheiros": s.get("bathrooms"),
                "area": float(s["area"]) if s.get("area") else None,
                "bairro": (s.get("neighbourhood") or "").strip(),
                "cidade": cidade["nome"],
                "uf": cidade["uf"],
                "endereco": (s.get("address") or "").strip(),
                "imagem": f"https://www.quintoandar.com.br/img/v2/med/{s['coverImage']}" if s.get("coverImage") else None,
                "anunciante": "QuintoAndar",
                "na_planta": bool(s.get("isPrimaryMarket")),
                "condominio_iptu": s.get("iptuPlusCondominium"),  # o QuintoAndar informa os dois somados, por mês
                "link": f"{SITE}/imovel/{id_}/{'comprar' if negocio == 'compra' else 'alugar'}",
                # O QuintoAndar não informa na lista se aceita financiamento
                "detalhado": True,
                "financiamento": None,
            }
        offset += POR_PAGINA
        if not lista or offset >= (total or 0):
            break
    return list(anuncios.values())
