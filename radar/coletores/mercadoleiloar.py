"""Coletor dos leiloeiros que usam a plataforma Mercado Leiloar:
Bolsa de Leilões e Hisa Leilões.

/leiloes lista os leilões abertos; cada leilão (/leilao/<id>/page:<n>) lista
50 lotes por página com lance, cidade e foto. A data vem no cabeçalho do leilão.
"""

import html as html_lib
import re
from typing import List, Optional

from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote
from radar.palavras import eh_de_interesse, so_pj

SITES = {
    "Bolsa de Leilões": "https://www.bolsadeleiloes.com.br",
    "Hisa Leilões": "https://www.hisaleiloes.com.br",
}
LIMITE_PAGINAS = 20

_CARTAO = re.compile(r'<div class="bem-card card(.*?)(?=<div class="bem-card card|<div class="clearfix|</section)', re.S)


def _texto(trecho: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", trecho, flags=re.S)
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _reais(texto: str) -> Optional[float]:
    m = re.search(r"R\$\s*([\d.]+,\d{2})", texto or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _coletar_site(nome: str, base: str) -> List[Lote]:
    lista = baixar(f"{base}/leiloes").decode("utf-8", "replace")
    leiloes = sorted(set(re.findall(r'href="(?:' + re.escape(base) + r'|https?://[^"]*)?/leilao/(\d+)/?"', lista)))
    lotes, vistos = [], set()
    for leilao in leiloes:
        cabecalho = None
        for pagina in range(1, LIMITE_PAGINAS + 1):
            url = f"{base}/leilao/{leilao}" + (f"/page:{pagina}" if pagina > 1 else "")
            pag = baixar(url).decode("utf-8", "replace")
            if cabecalho is None:
                t = _texto(pag)
                data = re.search(r"Data\s+(\d{2})/(\d{2})/(\d{4})\s+(?:a partir\s+|às\s+)?(\d{2}:\d{2})", t)
                cabecalho = {
                    "encerramento": f"{data.group(3)}-{data.group(2)}-{data.group(1)} {data.group(4)}" if data else None,
                    "so_pj": so_pj(t),
                }
            novos = 0
            for cartao in _CARTAO.findall(pag):
                ident = re.search(r'href="/lote/(\d+)"', cartao)
                if not ident or ident.group(1) in vistos:
                    continue
                vistos.add(ident.group(1))
                novos += 1
                titulo = re.search(r'bem-card-descricao">\s*<a[^>]*>(.*?)</a>', cartao, re.S)
                titulo = _texto(titulo.group(1)) if titulo else ""
                texto = _texto(cartao)
                if not eh_de_interesse(titulo) or re.search(r"\b(ENCERRADO|VENDIDO|ARREMATADO|CANCELADO)\b", texto):
                    continue
                local = re.search(r"fa-map-marker\"></i>\s*([^<,]+),\s*([A-Z]{2})", cartao)
                foto = re.search(r'<img src="([^"]+)"', cartao)
                lotes.append(Lote(
                    fonte=nome,
                    id=f"{nome.split()[0].lower()}-{ident.group(1)}",
                    titulo=titulo[:250],
                    categoria="Eletrônicos e eletrodomésticos",
                    lance_atual=_reais(texto),
                    encerramento=cabecalho["encerramento"],
                    cidade=nome_cidade(local.group(1)) if local else "",
                    uf=local.group(2) if local else "",
                    publico=PUBLICO_SO_PJ if cabecalho["so_pj"] else PUBLICO_PF_PJ,
                    link=f"{base}/lote/{ident.group(1)}",
                    imagem=foto.group(1) if foto else None,
                ))
            if novos == 0:
                break
    print(f"[{nome}] {len(leiloes)} leilões, {len(lotes)} lotes de eletrônicos/eletrodomésticos", flush=True)
    return lotes


def coletar() -> List[Lote]:
    lotes: List[Lote] = []
    for nome, base in SITES.items():
        try:
            lotes.extend(_coletar_site(nome, base))
        except Exception as erro:
            print(f"[{nome}] erro: {erro}", flush=True)
    return lotes
