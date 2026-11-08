"""Coletor da Freitas Leiloeiro (freitasleiloeiro.com.br): celulares/tablets,
eletrônicos e eletrodomésticos.

A busca devolve os cartões dos lotes; a cidade do pátio vem na página de
detalhe, que buscamos uma vez por leilão.
"""

import html as html_lib
import re
from typing import Dict, List

from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote
from radar.palavras import so_pj

SITE = "https://www.freitasleiloeiro.com.br"
SUBTIPOS = {153: "Celulares / Tablets", 169: "Eletrônicos", 137: "Eletrodomésticos"}
POR_PAGINA = 50
LIMITE_PAGINAS = 20


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def _local_do_leilao(url_detalhe: str) -> dict:
    t = _texto(re.sub(r"<script.*?</script>", " ", baixar(url_detalhe).decode("utf-8", "replace"), flags=re.S))
    info = {"so_pj": so_pj(t)}
    # "Local de retirada dos lotes : Pátio Utinga - ... - Santo André/SP"
    m = re.search(r"Local de retirada dos lotes\s*:[^/]{0,160}?-\s*([A-Za-zÀ-ú' ]{3,40})\s*/\s*([A-Z]{2})", t) \
        or re.search(r"Local do leil[ãa]o:[^()]*\(([^/()]+)/([A-Z]{2})\)", t)
    if m:
        info["cidade"], info["uf"] = nome_cidade(m.group(1)), m.group(2)
    return info


def coletar() -> List[Lote]:
    lotes, vistos = [], set()
    locais: Dict[str, dict] = {}
    for subtipo, nome in SUBTIPOS.items():
        for pagina in range(1, LIMITE_PAGINAS + 1):
            pag = baixar(f"{SITE}/Leiloes/PesquisarLotes?Categoria=3&TipoLoteId={subtipo}&PageNumber={pagina}&TopRows={POR_PAGINA}").decode("utf-8", "replace")
            cartoes = pag.split('<div class="cardlote">')[1:]
            for cartao in cartoes:
                link = re.search(r'href="(/Leiloes/LoteDetalhes\?leilaoId=(\d+)&(?:amp;)?loteNumero=(\d+))"', cartao)
                if not link:
                    continue
                chave = f"{link.group(2)}-{link.group(3)}"
                status = re.search(r'cardLote-btn[^>]*>([^<]+)<', cartao)
                if chave in vistos or (status and "ABERTO" not in status.group(1).upper()):
                    continue
                vistos.add(chave)
                leilao = link.group(2)
                url = SITE + html_lib.unescape(link.group(1))
                if leilao not in locais:
                    try:
                        locais[leilao] = _local_do_leilao(url)
                    except Exception:
                        locais[leilao] = {}
                local = locais[leilao]
                data = re.findall(r'<span class="fw-bold">([^<]+)</span>', cartao)
                quando = None
                if len(data) >= 2 and re.match(r"\d{2}/\d{2}/\d{4}", data[0]):
                    d, m, a = data[0].split("/")
                    quando = f"{a}-{m}-{d} {data[1].strip()}"
                desc = re.search(r'cardLote-descBens">\s*<span[^>]*>(.*?)</span>', cartao, re.S)
                valor = re.search(r'cardLote-vlr">\s*R\$\s*([\d.]+,\d{2})', cartao)
                foto = re.search(r'<img src="([^"]+/FOTOS/[^"]+)"', cartao)
                lotes.append(Lote(
                    fonte="Freitas",
                    id=f"freitas-{chave}",
                    titulo=re.sub(r"^\(B\d+\)\s*", "", _texto(desc.group(1)) if desc else "")[:250],
                    categoria=nome,
                    lance_atual=float(valor.group(1).replace(".", "").replace(",", ".")) if valor else None,
                    encerramento=quando,
                    cidade=local.get("cidade", ""),
                    uf=local.get("uf", ""),
                    publico=PUBLICO_SO_PJ if local.get("so_pj") else PUBLICO_PF_PJ,
                    link=url,
                    imagem=foto.group(1) if foto else None,
                    observacoes=["Comissão do leiloeiro: 5%"],
                ))
            if len(cartoes) < POR_PAGINA:
                break
    print(f"[Freitas] {len(lotes)} lotes", flush=True)
    return lotes
