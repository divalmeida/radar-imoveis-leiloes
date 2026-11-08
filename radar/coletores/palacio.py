"""Coletor do Palácio dos Leilões (palaciodosleiloes.com.br): categoria ELETRO.

O site carrega a lista por uma chamada ao próprio servidor
(camada_ajax/coluna_esquerda_m_home.php, opcao=listar_lote), 8 lotes por vez.
O parâmetro "paginacao" é a posição do primeiro lote (0, 8, 16...).
"""

import html as html_lib
import re
import urllib.request
from typing import List

from radar.config import PAUSA_ENTRE_REQUISICOES
from radar.http import USER_AGENT
from radar.localidades import nome_cidade, uf_da_cidade
from radar.modelo import PUBLICO_PF_PJ, Lote
from radar.palavras import eh_de_interesse, eh_peca_de_carro

SITE = "https://www.palaciodosleiloes.com.br/site"
CATEGORIA_ELETRO = "15"
POR_VEZ = 8
LIMITE = 3000  # lotes


def _pagina(posicao: int) -> str:
    import time
    dados = f"opcao=listar_lote&categoria_pesquisa={CATEGORIA_ELETRO}&paginacao={posicao}&total_paginas=1&somente_pesquisa=0".encode()
    pedido = urllib.request.Request(f"{SITE}/camada_ajax/coluna_esquerda_m_home.php", data=dados, headers={
        "User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(pedido, timeout=40) as r:
        texto = r.read().decode("latin-1", "replace")
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    return texto


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def coletar() -> List[Lote]:
    lotes, vistos = [], set()
    for posicao in range(0, LIMITE, POR_VEZ):
        pag = _pagina(posicao)
        cartoes = pag.split("resultado-lote-card")[1:]
        if not cartoes:
            break
        for cartao in cartoes:
            ident = re.search(r"exibir_lote\((\d+),\s*(\d+)\)", cartao)
            if not ident or ident.group(1) in vistos:
                continue
            vistos.add(ident.group(1))
            titulo = re.search(r"resultado-lote-titulo'>(.*?)</div>", cartao, re.S)
            titulo = re.sub(r"^\d+-\s*", "", _texto(titulo.group(1)) if titulo else "")
            # A categoria ELETRO também tem peças de carro, janelas, colchões...: fica só eletrônico/eletrodoméstico
            if eh_peca_de_carro(titulo) or not eh_de_interesse(titulo):
                continue
            cidade_data = re.search(r"<div class='inf small'>([^<]+?)\s*<div class='float-right'>(\d{2})/(\d{2})/(\d{2})</div>", cartao)
            preco = re.search(r"resultado-lote-preco'>.*?([\d.]+,\d{2})\s*<div class='peq'>([^<]+)<", cartao, re.S)
            numero = re.search(r"Lote <div class='float-right'>(\d+)<", cartao)
            comitente = re.search(r"resultado-lote-comitente'>.*?>\s*([^<]+)</div>", cartao, re.S)
            foto = re.search(r"<img src='([^']+)' class='i-p-l'", cartao)
            cidade = nome_cidade(cidade_data.group(1)) if cidade_data else ""
            if cidade.lower() == "externo":
                cidade = ""  # lote fora dos pátios do Palácio: local no edital
            quando = f"20{cidade_data.group(4)}-{cidade_data.group(3)}-{cidade_data.group(2)} 10:00" if cidade_data else None
            lotes.append(Lote(
                fonte="Palácio dos Leilões",
                id=f"palacio-{ident.group(1)}",
                titulo=titulo[:250],
                categoria="Eletrônicos e eletrodomésticos",
                lance_atual=(float(preco.group(1).replace(".", "").replace(",", ".")) or None) if preco else None,
                encerramento=quando,
                cidade=cidade,
                uf=uf_da_cidade(cidade, "MG") if cidade else "",
                publico=PUBLICO_PF_PJ,
                link=f"{SITE}/index.php?leilao_pesquisa={ident.group(2)}",
                imagem=None if not foto or "preparacao" in foto.group(1) else f"{SITE}/{foto.group(1)}",
                observacoes=[f"Lote {numero.group(1)} do leilão {ident.group(2)} (horário aproximado; confira no site)"] if numero else [],
                detalhes={"comitente": comitente.group(1).strip() if comitente else None,
                          "tipo_lance": preco.group(2).strip() if preco else None},
            ))
    print(f"[Palácio dos Leilões] {len(lotes)} lotes", flush=True)
    return lotes
