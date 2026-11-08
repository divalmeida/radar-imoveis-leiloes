"""Coletor da Kwara (kwara.com.br): Informática & Telefonia e Eletrodomésticos & Eletrônicos.

A página de busca já vem com os dados dos lotes embutidos (formato do Next.js).
Cada busca traz até 24 lotes, então buscamos a categoria e cada subcategoria.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote

SITE = "https://www.kwara.com.br"
CATEGORIAS = ["informatica-e-telefonia", "eletrodomesticos-e-eletronicos"]
FUSO = timezone(timedelta(hours=-3))


def _lotes_da_pagina(pagina: str) -> Dict[str, dict]:
    """Lê os objetos de lote do payload do Next.js (self.__next_f.push)."""
    partes = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', pagina)
    payload = "".join(json.loads('"' + p + '"') for p in partes)
    achados: Dict[str, dict] = {}

    def andar(x):
        if isinstance(x, dict):
            if "slug" in x and "cachedPriceAmountCents" in x:
                achados[x["slug"]] = x
            for v in x.values():
                andar(v)
        elif isinstance(x, list):
            for v in x:
                andar(v)

    for linha in payload.split("\n"):
        m = re.match(r"^[0-9a-f]+:(.*)$", linha)
        if m:
            try:
                andar(json.loads(m.group(1)))
            except ValueError:
                pass
    return achados


def _horario(iso: str):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(FUSO).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return None


def coletar() -> List[Lote]:
    ids = set()
    for categoria in CATEGORIAS:
        pagina = baixar(f"{SITE}/categorias/{categoria}").decode("utf-8", "replace")
        ids.update(re.findall(r"/busca\?assetCategoryIds%5B%5D=(\d+)", pagina))
    todos: Dict[str, dict] = {}
    for ident in sorted(ids):
        pagina = baixar(f"{SITE}/busca?assetCategoryIds%5B%5D={ident}").decode("utf-8", "replace")
        todos.update(_lotes_da_pagina(pagina))

    lotes = []
    for x in todos.values():
        if x.get("isEnded") or x.get("status") not in (None, "ACTIVE"):
            continue
        listing = x.get("listing") or {}
        local = listing.get("location") or ""  # ex.: "Taboão da Serra/SP"
        m = re.match(r"\s*(.+?)\s*/\s*([A-Z]{2})\s*$", local)
        cidade, uf = (nome_cidade(m.group(1)), m.group(2)) if m else ("", x.get("propertyState") or x.get("pickUpState") or "")
        imagens = x.get("images") or []
        so_empresas = (x.get("acceptBuyersMode") or "ALL") not in ("ALL", "INDIVIDUALS_AND_COMPANIES")
        estimado = (x.get("estimatedValueCents") or 0) / 100 or None
        obs = []
        if x.get("buyerFeePercentage"):
            obs.append(f"Comissão do comprador: {x['buyerFeePercentage']}%")
        if x.get("sameStateOnlyBuyers"):
            obs.append("Só para compradores do mesmo estado")
        lotes.append(Lote(
            fonte="Kwara",
            id=f"kwara-{x.get('id') or x['slug']}",
            titulo=(x.get("title") or "").strip()[:250],
            categoria="Eletrônicos e eletrodomésticos",
            lance_atual=(x.get("cachedPriceAmountCents") or 0) / 100 or None,
            valor_avaliacao=estimado,
            encerramento=_horario(x.get("currentEndAt") or x.get("scheduledEndAt")),
            cidade=cidade,
            uf=uf,
            publico=PUBLICO_SO_PJ if so_empresas else PUBLICO_PF_PJ,
            link=f"{SITE}/bens/{x['slug']}",
            imagem=imagens[0].get("thumbnailUrl") if imagens else None,
            observacoes=obs,
            detalhes={"lances": x.get("cachedBidsCount"), "vendedor": (x.get("seller") or {}).get("displayName")},
        ))
    print(f"[Kwara] {len(ids)} buscas, {len(lotes)} lotes", flush=True)
    return lotes
