"""Coletor da lista oficial de imóveis à venda da Caixa.

A Caixa publica uma planilha por estado:
  https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{UF}.csv

O site tem proteção anti-robô (Radware). Primeiro tentamos o acesso simples;
se cair no captcha, abrimos um navegador de verdade (Playwright/Chromium)
e baixamos a planilha de dentro dele.
"""

import csv
import io
import unicodedata
from typing import List, Optional

from radar.config import CIDADES_PRIORITARIAS, UFS_CAIXA
from radar.http import baixar
from radar.localidades import nome_cidade
from radar.modelo import PUBLICO_PF_PJ, Lote

SITE = "https://venda-imoveis.caixa.gov.br"
URL_LISTA = SITE + "/listaweb/Lista_imoveis_{uf}.csv"
PAGINA_DOWNLOAD = SITE + "/sistema/download-lista.asp"


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _numero(texto: str) -> Optional[float]:
    texto = (texto or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _eh_planilha(conteudo: bytes) -> bool:
    return b"Lista de Im" in conteudo[:300]


def _baixar_com_navegador(ufs: List[str]) -> dict:
    from playwright.sync_api import sync_playwright

    planilhas = {}
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(locale="pt-BR")
        pagina.set_default_timeout(90_000)
        pagina.goto(PAGINA_DOWNLOAD, wait_until="domcontentloaded")
        pagina.wait_for_timeout(5_000)  # tempo para o anti-robô liberar a página
        for uf in ufs:
            # O fetch tem limite de 60 s para nunca deixar a coleta travada
            bytes_lista = pagina.evaluate(
                """async (url) => {
                    const r = await fetch(url, {signal: AbortSignal.timeout(60000)});
                    return Array.from(new Uint8Array(await r.arrayBuffer()));
                }""",
                URL_LISTA.format(uf=uf),
            )
            planilhas[uf] = bytes(bytes_lista)
        navegador.close()
    return planilhas


def _baixar_planilhas(ufs: List[str]) -> dict:
    planilhas = {}
    for uf in ufs:
        try:
            conteudo = baixar(URL_LISTA.format(uf=uf))
        except RuntimeError:
            conteudo = b""
        if not _eh_planilha(conteudo):
            print("[Caixa] acesso simples bloqueado, abrindo navegador")
            return _baixar_com_navegador(ufs)
        planilhas[uf] = conteudo
    return planilhas


def _ler_planilha(conteudo: bytes) -> List[Lote]:
    texto = conteudo.decode("latin-1")
    linhas = [l for l in texto.splitlines() if l.strip()]
    # linha 0: título com data de geração; linha 1: cabeçalho
    leitor = csv.reader(io.StringIO("\n".join(linhas[2:])), delimiter=";")
    prioritarias = {_sem_acento(c) for c in CIDADES_PRIORITARIAS}

    lotes = []
    for campos in leitor:
        if len(campos) < 12:
            continue
        numero, uf, cidade, bairro, endereco, preco, avaliacao, desconto, financiamento, descricao, modalidade, link = (
            c.strip() for c in campos[:12]
        )
        tipo = descricao.split(",")[0].strip() or "Imóvel"
        aceita_financiamento = financiamento.lower().startswith("sim")
        lotes.append(
            Lote(
                fonte="Caixa",
                id=f"caixa-{numero}",
                titulo=f"{tipo} - {nome_cidade(bairro)}, {nome_cidade(cidade)}",
                categoria=f"Imóvel ({tipo})",
                lance_atual=_numero(preco),
                valor_avaliacao=_numero(avaliacao),
                encerramento=None,
                cidade=nome_cidade(cidade),
                uf=uf,
                publico=PUBLICO_PF_PJ,
                link=link,
                prioridade=_sem_acento(cidade.upper()) in prioritarias,
                observacoes=[modalidade, f"Desconto de {desconto}%"]
                + (["Aceita financiamento"] if aceita_financiamento else []),
                detalhes={
                    "bairro": nome_cidade(bairro),
                    "endereco": endereco,
                    "descricao": descricao,
                    "desconto_pct": _numero(desconto.replace(".", ",")),
                    "financiamento": aceita_financiamento,
                    "modalidade": modalidade,
                },
            )
        )
    return lotes


def coletar() -> List[Lote]:
    lotes: List[Lote] = []
    for uf, conteudo in _baixar_planilhas(UFS_CAIXA).items():
        if not _eh_planilha(conteudo):
            raise RuntimeError(f"planilha de {uf} bloqueada pelo anti-robô da Caixa")
        da_uf = _ler_planilha(conteudo)
        print(f"[Caixa] {uf}: {len(da_uf)} imóveis ({sum(l.prioridade for l in da_uf)} em cidades prioritárias)")
        lotes.extend(da_uf)
    return lotes
