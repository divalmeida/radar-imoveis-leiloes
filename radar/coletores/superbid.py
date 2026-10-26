"""Coletor da Superbid (superbid.net).

O site principal tem Cloudflare, mas a busca de ofertas que ele usa
(offer-query.superbid.net) responde normalmente.
Coleta as ofertas abertas de Tecnologia (informática, telefonia, eletrônicos)
e de Eletrodomésticos.
"""

import re
import unicodedata
from typing import List
from urllib.parse import urlencode

from radar.http import baixar_json
from radar.localidades import uf_da_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote

API = "https://offer-query.superbid.net/seo/offers/"
SITE = "https://www.superbid.net"
TIPOS_DE_PRODUTO = "[18,124]"  # 18 = Tecnologia, 124 = Eletrodomésticos
POR_PAGINA = 100
LIMITE_PAGINAS = 30

UF_POR_ESTADO = {
    "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA",
    "Ceará": "CE", "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO",
    "Maranhão": "MA", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
    "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE", "Piauí": "PI",
    "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS",
    "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP",
    "Sergipe": "SE", "Tocantins": "TO",
}

_SO_PJ = re.compile(r"somente\s+(para\s+)?(pessoa[s]?\s+jur[ií]dica|PJ|CNPJ)|exclusivo\s+(para\s+)?(pessoa[s]?\s+jur[ií]dica|CNPJ)", re.I)


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texto).strip("-")[:80]


def _cidade_uf(oferta: dict):
    local = (oferta.get("product") or {}).get("location") or {}
    cidade = (local.get("city") or "").strip()
    uf = UF_POR_ESTADO.get(local.get("state") or "", "")
    # A cidade costuma vir como "Capela do Alto - SP"
    m = re.match(r"^(.*?)\s*-\s*([A-Z]{2})$", cidade)
    if m:
        cidade, uf = m.group(1), uf or m.group(2)
    endereco = (oferta.get("auction") or {}).get("address") or {}
    if not cidade:
        cidade, uf = endereco.get("city") or "", uf or endereco.get("stateCode") or ""
    if not uf:
        # Cidade com nome repetido em vários estados: desempata pelo estado do leiloeiro
        uf = uf_da_cidade(cidade, preferida=endereco.get("stateCode") or "")
    return cidade, uf


def _pagina(numero: int) -> dict:
    parametros = {
        "portalId": "[2,15]",
        "locale": "pt_BR",
        "requestOrigin": "marketplace",
        "urlSeo": SITE + "/",
        "searchType": "opened",
        "orderBy": "endDate:asc",
        "filter": f"product.productType.id:{TIPOS_DE_PRODUTO}",
        "pageNumber": numero,
        "pageSize": POR_PAGINA,
    }
    return baixar_json(API + "?" + urlencode(parametros))


def coletar() -> List[Lote]:
    lotes: List[Lote] = []
    numero = 1
    while numero <= LIMITE_PAGINAS:
        dados = _pagina(numero)
        ofertas = dados.get("offers") or []
        if numero == 1:
            print(f"[Superbid] {dados.get('total')} ofertas abertas em Tecnologia e Eletrodomésticos")
        for oferta in ofertas:
            if (oferta.get("offerStatus") or {}).get("closedToBids"):
                continue
            produto = oferta.get("product") or {}
            titulo = (produto.get("shortDesc") or "").strip()
            descricao = (oferta.get("offerDescription") or {}).get("offerDescription") or ""
            cidade, uf = _cidade_uf(oferta)
            detalhe = oferta.get("offerDetail") or {}
            fotos = produto.get("galleryJson") or []
            categoria = ((produto.get("subCategory") or {}).get("category") or {}).get("description")
            so_pj = bool(_SO_PJ.search(descricao))
            lotes.append(
                Lote(
                    fonte="Superbid",
                    id=f"superbid-{oferta['id']}",
                    titulo=titulo[:250],
                    categoria=categoria or (produto.get("productType") or {}).get("description", ""),
                    lance_atual=oferta.get("price") or detalhe.get("currentMinBid"),
                    encerramento=(oferta.get("endDate") or "")[:16] or None,
                    cidade=cidade,
                    uf=uf,
                    publico=PUBLICO_SO_PJ if so_pj else PUBLICO_PF_PJ,
                    link=f"{SITE}/oferta/{_slug(titulo)}-{oferta['id']}",
                    imagem=fotos[0].get("thumbnailUrl") if fotos else None,
                    observacoes=[] if so_pj else ["Confirme nas condições do leilão se aceita pessoa física"],
                    detalhes={
                        "lances": oferta.get("totalBids") or 0,
                        "leiloeiro": (oferta.get("store") or {}).get("name"),
                        "leilao": (oferta.get("auction") or {}).get("desc"),
                    },
                )
            )
        # Pedir uma página além do total devolve erro 404
        if len(ofertas) < POR_PAGINA or numero * POR_PAGINA >= (dados.get("total") or 0):
            break
        numero += 1
    return lotes
