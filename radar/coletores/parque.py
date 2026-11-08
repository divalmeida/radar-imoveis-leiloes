"""Coletor do Parque dos Leilões (parquedosleiloes.com.br, Brasília-DF):
lotes de eletrônicos, informática e eletrodomésticos dos leilões abertos."""

import html as html_lib
import json
import re
from typing import List

from radar.http import baixar
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote
from radar.palavras import eh_de_interesse, so_pj

SITE = "https://www.parquedosleiloes.com.br"
MESES = {"jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
         "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12"}
CATEGORIAS = re.compile(r"ELETR|INFORM|CELULAR|TELEF|ELETRODOM|TV|SOM", re.I)


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def _reais(texto: str):
    m = re.search(r"R\$\s*([\d.]+,\d{2})", texto or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


def coletar() -> List[Lote]:
    lista = baixar(f"{SITE}/leiloes").decode("utf-8", "replace")
    leiloes = sorted(set(re.findall(r"/leilao/(\d+)/detalhes", lista)))
    lotes = []
    for leilao in leiloes:
        pag = baixar(f"{SITE}/leilao/{leilao}/detalhes").decode("utf-8", "replace")
        # Data do leilão no cabeçalho: "Data 13 de nov de 2026 às 10:00"
        cab = re.search(r"(\d{1,2})\s+(?:de\s+)?(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\w*\s+(?:de\s+)?(\d{4}),?\s*(?:às\s*)?(\d{2}:\d{2})", _texto(pag), re.I)
        data_leilao = f"{cab.group(3)}-{MESES[cab.group(2).lower()]}-{int(cab.group(1)):02d} {cab.group(4)}" if cab else None
        for cartao in pag.split('class="card auction-lot-card"')[1:]:
            link = re.search(r'href="(' + re.escape(SITE) + r'/leilao/\d+/lote/(\d+))"', cartao)
            status = re.search(r'data-lot-status-id="(\d+)"', cartao)
            categoria = re.search(r'<span class="name">([^<]+)</span>', cartao)
            desc = re.search(r"<label>Informações</label>\s*<p>(.*?)</p>", cartao, re.S)
            if not link or (status and status.group(1) == "7"):  # 7 = lote encerrado
                continue
            categoria = categoria.group(1).strip() if categoria else ""
            descricao = _texto(desc.group(1)) if desc else ""
            if not (CATEGORIAS.search(categoria) or eh_de_interesse(descricao)):
                continue
            detalhe = baixar(link.group(1)).decode("utf-8", "replace")
            t = _texto(re.sub(r"<script.*?</script>", " ", detalhe, flags=re.S))
            maior = re.search(r"Maior lance\s*R\$\s*[\d.,]+", t)
            inicial = re.search(r"Lance inicial\s*R\$\s*[\d.,]+", t)
            fim = re.search(r'"finished_at":"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', detalhe)
            # Antes de abrir, a data vem no texto: "... a 13 de nov de 2026 às 10:00" (fica a última)
            datas = re.findall(r"(\d{1,2}) de (\w{3}) de (\d{4}) às (\d{2}:\d{2})", t)
            quando = fim.group(1) if fim else data_leilao
            if not quando and datas:
                d, mes, a, h = datas[-1]
                quando = f"{a}-{MESES.get(mes.lower(), '01')}-{int(d):02d} {h}"
            estado = re.search(r'"status_name":"([^"]+)"', detalhe)
            if estado and estado.group(1).lower().startswith("encerr"):
                continue
            foto = re.search(r'<img src="([^"]+)"', cartao)
            lotes.append(Lote(
                fonte="Parque dos Leilões",
                id=f"parque-{link.group(2)}",
                titulo=descricao[:250],
                categoria=categoria.title() or "Eletrônicos",
                lance_atual=_reais(maior.group(0) if maior else inicial.group(0) if inicial else ""),
                encerramento=quando,
                cidade="Brasília",
                uf="DF",
                publico=PUBLICO_SO_PJ if so_pj(t) else PUBLICO_PF_PJ,
                link=link.group(1),
                imagem=foto.group(1) if foto else None,
            ))
    print(f"[Parque dos Leilões] {len(leiloes)} leilões, {len(lotes)} lotes", flush=True)
    return lotes
