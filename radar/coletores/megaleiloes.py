"""Coletor da Mega Leilões (megaleiloes.com.br): eletrônicos, eletrodomésticos e diversos."""

import html as html_lib
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote
from radar.palavras import eh_de_interesse, so_pj

SITE = "https://www.megaleiloes.com.br"
# (caminho, filtrar pela descrição?) — "diversos" mistura de tudo
CATEGORIAS = [("bens-de-consumo/eletronicos", False), ("bens-de-consumo/eletrodomesticos", False), ("outros/diversos", True)]
LIMITE_PAGINAS = 15
FUSO = timezone(timedelta(hours=-3))


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def _reais(texto: str) -> Optional[float]:
    m = re.search(r"R\$\s*([\d.]+,\d{2})", texto or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _proxima_praca(texto: str):
    """Data da próxima praça (1ª ou 2ª) que ainda não passou."""
    agora = datetime.now(FUSO).strftime("%Y-%m-%d %H:%M")
    for d, mes, a, h in re.findall(r"Pra[çc]a:\s*(\d{2})/(\d{2})/(\d{4})\s*(?:às)?\s*(\d{2}:\d{2})", texto):
        quando = f"{a}-{mes}-{d} {h}"
        if quando >= agora:
            return quando
    return None


def coletar() -> List[Lote]:
    lotes, vistos = [], set()
    for caminho, filtrar in CATEGORIAS:
        for pagina in range(1, LIMITE_PAGINAS + 1):
            pag = baixar(f"{SITE}/{caminho}?pagina={pagina}").decode("utf-8", "replace")
            cartoes = re.split(r'<div class="col-[^"]*" data-key="', pag)[1:]
            for cartao in cartoes:
                ident = re.match(r"(\d+)", cartao).group(1)
                if ident in vistos:
                    continue
                vistos.add(ident)
                titulo = re.search(r'class="card-title"[^>]*>(.*?)</a>', cartao, re.S)
                titulo = _texto(titulo.group(1)) if titulo else ""
                texto = _texto(cartao)
                if (filtrar and not eh_de_interesse(titulo)) or re.search(r"\b(Encerrado|Arrematado|Vendido|Cancelado|Suspenso)\b", texto):
                    continue
                link = re.search(r'class="card-title" href="([^"?]+)', cartao)
                local = re.search(r'class="card-locality"[^>]*>([^<,]+),\s*([A-Z]{2})<', cartao)
                foto = re.search(r'data-bg="([^"]+)"', cartao)
                preco = re.search(r'class="card-price">([^<]+)<', cartao)
                tipo = re.search(r'class="card-instance-title"><a[^>]*>([^<]+)<', cartao)
                lotes.append(Lote(
                    fonte="Mega Leilões",
                    id=f"mega-{ident}",
                    titulo=titulo[:250],
                    categoria="Eletrônicos e eletrodomésticos",
                    lance_atual=_reais(preco.group(1)) if preco else _reais(texto),
                    encerramento=_proxima_praca(texto),
                    cidade=nome_cidade(local.group(1)) if local else "",
                    uf=local.group(2) if local else "",
                    publico=PUBLICO_SO_PJ if so_pj(texto) else PUBLICO_PF_PJ,
                    link=link.group(1) if link else SITE,
                    imagem=None if not foto or "no-image" in foto.group(1) else foto.group(1),
                    observacoes=[f"Leilão {tipo.group(1).strip().lower()}"] if tipo else [],
                ))
            total = re.search(r"Página\s*<b>\d+</b>\s*de\s*<b>(\d+)</b>", pag)
            if not cartoes or (total and pagina >= int(total.group(1))):
                break
    print(f"[Mega Leilões] {len(lotes)} lotes", flush=True)
    return lotes
