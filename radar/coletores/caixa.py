"""Coletor da lista oficial de imóveis à venda da Caixa.

A Caixa publica uma planilha por estado:
  https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{UF}.csv

O site tem proteção anti-robô (Radware). Usamos só o acesso normal: se a
Caixa mostrar o captcha, a coleta é marcada como falha (não tentamos burlar).
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


def _baixar_planilhas(ufs: List[str]) -> dict:
    planilhas = {}
    for uf in ufs:
        try:
            planilhas[uf] = baixar(URL_LISTA.format(uf=uf))
        except RuntimeError:
            planilhas[uf] = b""
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
            raise RuntimeError(f"a Caixa pediu captcha (anti-robô) para a planilha de {uf}")
        da_uf = _ler_planilha(conteudo)
        print(f"[Caixa] {uf}: {len(da_uf)} imóveis ({sum(l.prioridade for l in da_uf)} em cidades prioritárias)")
        lotes.extend(da_uf)
    return lotes
