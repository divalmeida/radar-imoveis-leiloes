"""Coletor dos leiloeiros que usam a plataforma Soleon:
João Emílio, Leilão Prime e Tudo Leilão.

A lista "/lotes/diversos" traz descrição, foto e lance; para os lotes de
eletrônicos/eletrodomésticos/celulares, abrimos o detalhe para pegar
encerramento, cidade e comissão.
"""

import html as html_lib
import re
from typing import List, Optional

from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote
from radar.palavras import eh_de_interesse, so_pj

SITES = {
    "João Emílio": "https://www.joaoemilio.com.br",
    "Leilão Prime": "https://www.leilaoprime.com.br",
    "Tudo Leilão": "https://www.tudoleilao.com.br",
}
LIMITE_PAGINAS = 40

_CARTAO = re.compile(r'<div class="lote\s*">(.*?)<!-- \./card -->', re.S)


def _texto(trecho: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", trecho, flags=re.S)
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def _reais(texto: Optional[str]) -> Optional[float]:
    m = re.search(r"R\$\s*([\d.]+,\d{2})", texto or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def _local(t: str):
    """Cidade e UF do lote: o site escreve de jeitos diferentes conforme o leiloeiro."""
    padroes = [
        r"Local de Exposi[çc][ãa]o:\s*([A-Za-zÀ-ú .']{3,40}?)\s*[-/]\s*([A-Z]{2})\b",
        r"\b([A-ZÀ-Ú][A-ZÀ-Ú .'-]{2,40})-([A-Z]{2})\s+\+\s*Comiss",
        r"Local do Leil[ãa]o:[^:]{0,120}?-\s*([A-Za-zÀ-ú .']{3,40}?)\s*-\s*([A-Z]{2})\b",
        r"\(([A-ZÀ-Ú][A-ZÀ-Ú .']{2,40})\s*[-/]\s*([A-Z]{2})\)",
        # "Rio de Janeiro/RJ": até 4 palavras com inicial maiúscula (com "de", "do"... no meio)
        r"\b([A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][a-zà-ú]+){0,3})\s*/\s*([A-Z]{2})\b",
    ]
    for padrao in padroes:
        m = re.search(padrao, t)
        if m:
            return nome_cidade(m.group(1)), m.group(2)
    return "", ""


def _detalhe(url: str) -> dict:
    t = _texto(baixar(url).decode("utf-8", "replace"))
    info = {}
    m = re.search(r"(?:Encerramento|Data do Leil[ãa]o):\s*(\d{2})/(\d{2})/(\d{4})\s+(\d{2}:\d{2})", t)
    if m:
        d, mes, a, h = m.groups()
        info["encerramento"] = f"{a}-{mes}-{d} {h}"
    info["cidade"], info["uf"] = _local(t)
    m = re.search(r"Comiss[ãa]o(?:\s*\(|:)\s*([\d,]+)\s*%", t)
    if m:
        info["comissao_pct"] = float(m.group(1).replace(",", "."))
    info["so_pj"] = so_pj(t)
    return info


def _coletar_site(nome: str, base: str) -> List[Lote]:
    lotes = []
    for pagina in range(1, LIMITE_PAGINAS + 1):
        pag = baixar(f"{base}/lotes/diversos?page={pagina}").decode("utf-8", "replace")
        cartoes = _CARTAO.findall(pag)
        if not cartoes:
            break
        for cartao in cartoes:
            link = re.search(r'href="([^"]*/item/(\d+)/detalhes[^"]*)"', cartao)
            if not link:
                continue
            texto = _texto(cartao)
            descricao = re.search(r"Descri[çc][ãa]o:\s*(.*?)(?:Local de Exposi|Aberto para|Maior Lance|Lance Inicial|Encerrado|$)", texto)
            descricao = (descricao.group(1) if descricao else texto)[:300].strip()
            if not eh_de_interesse(descricao) or re.search(r"Encerrado|Arrematado|Vendido", texto):
                continue
            foto = re.search(r"url\('([^']+)'\)", cartao)
            lance = _reais(re.search(r"(Maior Lance|Lance Inicial|Lance Atual).{0,80}", texto).group(0)) if re.search(r"(Maior Lance|Lance Inicial|Lance Atual)", texto) else None
            try:
                det = _detalhe(link.group(1))
            except Exception:
                det = {}
            lotes.append(Lote(
                fonte=nome,
                id=f"{nome.lower().replace(' ', '').replace('ã', 'a').replace('í', 'i')}-{link.group(2)}",
                titulo=descricao[:250],
                categoria="Eletrônicos e eletrodomésticos",
                lance_atual=lance,
                encerramento=det.get("encerramento"),
                cidade=det.get("cidade") or "",
                uf=det.get("uf") or "",
                publico=PUBLICO_SO_PJ if det.get("so_pj") else PUBLICO_PF_PJ,
                link=link.group(1).split("?")[0],
                imagem=foto.group(1) if foto else None,
                observacoes=[f"Comissão do leiloeiro: {det['comissao_pct']:.0f}%"] if det.get("comissao_pct") else [],
            ))
        total = re.search(r"Total\s+(\d+)\s+Lotes", _texto(pag))
        if total and pagina * len(cartoes) >= int(total.group(1)):
            break
    print(f"[{nome}] {len(lotes)} lotes de eletrônicos/eletrodomésticos", flush=True)
    return lotes


def coletar() -> List[Lote]:
    lotes: List[Lote] = []
    for nome, base in SITES.items():
        try:
            lotes.extend(_coletar_site(nome, base))
        except Exception as erro:  # um site fora do ar não derruba os outros
            print(f"[{nome}] erro: {erro}", flush=True)
    return lotes
