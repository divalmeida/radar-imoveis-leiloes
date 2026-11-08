"""Imóveis em leilão de bancos e judiciais (além da Caixa), na Bahia:
- Zuk (portalzuk.com.br)
- Frazão Leilões (frazaoleiloes.com.br)

Respeita o robots.txt de cada site (a Zuk proíbe /ajax-lote*; usamos só as
páginas de lista).
"""

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from radar.config import CIDADES_PRIORITARIAS
from radar.http import baixar
from radar.localidades import chave_texto, nome_cidade
from radar.modelo import PUBLICO_PF_PJ, Lote

UF = "BA"
FUSO = timezone(timedelta(hours=-3))
_PRIORITARIAS = {chave_texto(c) for c in CIDADES_PRIORITARIAS}


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def _reais(texto: str) -> Optional[float]:
    m = re.search(r"R\$\s*([\d.]+,\d{2})", texto or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _proxima(datas: List[str]) -> Optional[str]:
    agora = datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")
    futuras = sorted(d for d in datas if d >= agora)
    return futuras[0] if futuras else (max(datas) if datas else None)


def _area(texto: str) -> Optional[float]:
    m = re.search(r"([\d.]+,\d{1,2}|\d+)\s*m²", texto)
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def zuk() -> List[Lote]:
    pag = baixar(f"https://www.portalzuk.com.br/leilao-de-imoveis/u/todos-imoveis/{UF.lower()}").decode("utf-8", "replace")
    lotes = []
    for cartao in pag.split('class="card-property card_lotes_div"')[1:]:
        link = re.search(r'href="(https://www\.portalzuk\.com\.br/imovel/[^"]+)"', cartao)
        if not link:
            continue
        titulo_attr = re.search(r'title="([^"]+)"', cartao)
        tipo = re.search(r'card-property-price-lote">([^<]+)<', cartao)
        local = re.search(r"<a href='[^']*'>([^<]+?)\s*/\s*([A-Z]{2})</a>\s*-\s*([^<]*)</span>", cartao)
        texto = _texto(cartao)
        precos = re.findall(r"R\$\s*([\d.]+,\d{2})", texto)
        datas = [f"{a}-{m}-{d} {h}" for d, m, a, h in re.findall(r"(\d{2})/(\d{2})/(\d{4})\s*às\s*(\d{2}:\d{2})", texto)]
        desconto = re.search(r"R\$\s*[\d.,]+\s+(\d{1,2})\s", texto)
        quartos = re.search(r'#icon-bed.*?card-property-info-label">(\d+)<', cartao, re.S)
        banco = re.search(r"-\s*([^-|]+?)\s*\|\s*Z\d+", titulo_attr.group(1)) if titulo_attr else None
        cidade = nome_cidade(local.group(1)) if local else ""
        tipo_txt = tipo.group(1).strip() if tipo else "Imóvel"
        lotes.append(Lote(
            fonte="Zuk",
            id="zuk-" + link.group(1).rsplit("/", 1)[-1],
            titulo=f"{tipo_txt} - {local.group(3).strip() if local else ''}, {cidade}".strip(" -,"),
            categoria=f"Imóvel ({tipo_txt})",
            lance_atual=float(precos[-1].replace(".", "").replace(",", ".")) if precos else None,
            encerramento=_proxima(datas),
            cidade=cidade,
            uf=local.group(2) if local else UF,
            publico=PUBLICO_PF_PJ,
            link=link.group(1),
            imagem=(re.search(r'<img src="([^"]+)"', cartao) or [None, None])[1],
            prioridade=chave_texto(cidade) in _PRIORITARIAS,
            observacoes=[f"Vendedor: {banco.group(1).strip()}"] if banco else [],
            detalhes={"bairro": local.group(3).strip() if local else "", "area": _area(texto),
                      "quartos": int(quartos.group(1)) if quartos else None,
                      "desconto_pct": float(desconto.group(1)) if desconto else None,
                      "modalidade": "Leilão"},
        ))
    print(f"[Zuk] {len(lotes)} imóveis na {UF}", flush=True)
    return lotes


def frazao() -> List[Lote]:
    pag = baixar("https://www.frazaoleiloes.com.br/Sale/LotListSearch?start=0&limit=1000&loteAtivo=true&page=").decode("utf-8", "replace")
    lotes = []
    for cartao in pag.split('id="card-lote"')[1:]:
        link = re.search(r'href="(/lote/(\d+)-[^"]+)"', cartao)
        titulo = re.search(r'<b title="([^"]+)"', cartao)
        if not link or not titulo:
            continue
        titulo = html_lib.unescape(titulo.group(1)).strip()
        # A cidade vem no fim do título ("..., Salvador BA") e no endereço do link ("-salvador-ba")
        m = re.search(r"([A-Za-zÀ-ú' ]+?)\s*[/-]?\s+([A-Z]{2})\s*$", titulo)
        if not m or m.group(2) != UF:
            continue
        cidade = nome_cidade(m.group(1).split(",")[-1].strip())
        texto = _texto(cartao)
        datas = [f"{a}-{mes}-{d} {h}:{mi}" for d, mes, a, h, mi in re.findall(r"(\d{2})/(\d{2})/(\d{4})\s*às\s*(\d{2})h(\d{2})", texto)]
        precos = re.findall(r"R\$\s*([\d.]+,\d{2})", texto)
        tipo = re.search(r'data-tipo="([^"]*)"', cartao)
        tipo_txt = (tipo.group(1) if tipo else "") or "Imóvel"
        lotes.append(Lote(
            fonte="Frazão",
            id=f"frazao-{link.group(2)}",
            titulo=titulo[:250],
            categoria=f"Imóvel ({tipo_txt})",
            lance_atual=float(precos[-1].replace(".", "").replace(",", ".")) if precos else None,
            encerramento=_proxima(datas),
            cidade=cidade,
            uf=UF,
            publico=PUBLICO_PF_PJ,
            link="https://www.frazaoleiloes.com.br" + link.group(1),
            imagem=(re.search(r'<img loading="lazy" src="([^"]+)"', cartao) or [None, None])[1],
            prioridade=chave_texto(cidade) in _PRIORITARIAS,
            detalhes={"area": _area(texto), "modalidade": "Leilão"},
        ))
    print(f"[Frazão] {len(lotes)} imóveis na {UF}", flush=True)
    return lotes


def coletar() -> List[Lote]:
    lotes: List[Lote] = []
    for funcao in (zuk, frazao):
        try:
            lotes.extend(funcao())
        except Exception as erro:
            print(f"[{funcao.__name__}] erro: {erro}", flush=True)
    return lotes
