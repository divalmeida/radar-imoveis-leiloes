"""Coletor dos leilões da Receita Federal (Sistema de Leilão Eletrônico - SLE).

Usa a API pública que o próprio portal consome:
  /api/portal                 -> lista de editais abertos e próximos
  /api/edital/{edle}          -> lotes do edital (tipo, valor mínimo, PF/PJ)
  /api/lote/{edle}/{numero}   -> descrição dos itens do lote

Na Receita não existe "lance atual" público: as propostas são fechadas.
Por isso o campo lance_atual recebe o valor mínimo do lote.
"""

from typing import List

from radar.config import CATEGORIAS_INTERESSE
from radar.http import baixar_json
from radar.modelo import PUBLICO_PF_PJ, PUBLICO_SO_PJ, Lote

API = "https://www25.receita.fazenda.gov.br/sle-sociedade/api"
PORTAL = "https://www25.receita.fazenda.gov.br/sle-sociedade/portal"

# A API informa só a cidade do edital; o estado vem desta tabela.
UF_POR_CIDADE = {
    "ARACAJU": "SE", "BELÉM": "PA", "BELO HORIZONTE": "MG", "BOA VISTA": "RR",
    "BRASÍLIA": "DF", "CAMPINAS": "SP", "CAMPO GRANDE": "MS", "CORUMBÁ": "MS",
    "CUIABÁ": "MT", "CURITIBA": "PR", "FLORIANÓPOLIS": "SC", "FOZ DO IGUAÇU": "PR",
    "FORTALEZA": "CE", "GOIÂNIA": "GO", "GUARULHOS": "SP", "ITAJAÍ": "SC",
    "ITAGUAÍ": "RJ", "JOÃO PESSOA": "PB", "JUIZ DE FORA": "MG", "MACAPÁ": "AP",
    "MACEIÓ": "AL", "MANAUS": "AM", "NATAL": "RN", "NITERÓI": "RJ",
    "PALMAS": "TO", "PARANAGUÁ": "PR", "PONTA PORÃ": "MS", "PORTO ALEGRE": "RS",
    "PORTO VELHO": "RO", "RECIFE": "PE", "RIBEIRÃO PRETO": "SP", "RIO BRANCO": "AC",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE": "RS", "SALVADOR": "BA", "SANTOS": "SP",
    "SÃO FRANCISCO DO SUL": "SC", "SÃO JOSÉ DOS CAMPOS": "SP", "SÃO LUÍS": "MA",
    "SÃO PAULO": "SP", "SOROCABA": "SP", "TERESINA": "PI", "URUGUAIANA": "RS",
    "VITÓRIA": "ES", "VIRACOPOS": "SP", "CAXIAS DO SUL": "RS", "LONDRINA": "PR",
    "MARINGÁ": "PR", "CASCAVEL": "PR", "SANTA MARIA": "RS", "PELOTAS": "RS",
    "JOINVILLE": "SC", "FEIRA DE SANTANA": "BA", "ILHÉUS": "BA", "UBERLÂNDIA": "MG",
    "VARGINHA": "MG", "BAURU": "SP", "SÃO JOSÉ DO RIO PRETO": "SP", "SANTANA DO LIVRAMENTO": "RS",
    "DIONÍSIO CERQUEIRA": "SC", "GUAÍRA": "PR", "TABATINGA": "AM", "PACARAIMA": "RR",
}


def _eh_categoria_de_interesse(tipo: str) -> bool:
    tipo = tipo.upper()
    return any(palavra in tipo for palavra in CATEGORIAS_INTERESSE)


def _nome_cidade(cidade: str) -> str:
    """'RIO DE JANEIRO' -> 'Rio de Janeiro'."""
    minusculas = {"De", "Do", "Da", "Dos", "Das"}
    return " ".join(p.lower() if p in minusculas else p for p in cidade.title().split())


def _titulo_do_lote(detalhe: dict) -> str:
    itens = detalhe.get("itensDetalhesLote") or []
    if not itens:
        return detalhe.get("tipo", "Lote")
    titulo = (itens[0].get("descricao") or "").strip(" /")
    if len(itens) > 1:
        titulo += f" (e mais {len(itens) - 1} itens)"
    return titulo[:250]


def coletar() -> List[Lote]:
    portal = baixar_json(f"{API}/portal")
    editais = [edital for situacao in portal["situacoes"] for edital in situacao["lista"]]
    print(f"[Receita] {len(editais)} editais abertos ou próximos")

    lotes: List[Lote] = []
    for edital in editais:
        edle = edital["edle"]
        cidade = edital["cidade"]
        uf = UF_POR_CIDADE.get(cidade, "")
        encerramento = edital.get("dataFimPropostas")

        try:
            dados_edital = baixar_json(f"{API}/edital/{edle}")
        except RuntimeError as erro:
            print(f"[Receita] edital {edle} ignorado: {erro}")
            continue

        escolhidos = [l for l in dados_edital["listaLotes"] if _eh_categoria_de_interesse(l["tipo"])]
        print(f"[Receita] {edle} {cidade}: {len(escolhidos)} de {len(dados_edital['listaLotes'])} lotes de interesse")

        for resumo in escolhidos:
            numero = resumo["nrAtribuido"]
            try:
                detalhe = baixar_json(f"{API}/lote/{edle}/{numero}")
            except RuntimeError:
                detalhe = {"tipo": resumo["tipo"]}

            imagens = detalhe.get("imagens") or []
            lotes.append(
                Lote(
                    fonte="Receita Federal",
                    id=f"receita-{edle}-{numero}",
                    titulo=_titulo_do_lote(detalhe),
                    categoria=resumo["tipo"],
                    lance_atual=resumo.get("valorMinimo"),
                    valor_avaliacao=resumo.get("valorAvaliacao"),
                    encerramento=encerramento,
                    cidade=_nome_cidade(cidade),
                    uf=uf,
                    publico=PUBLICO_PF_PJ if resumo.get("permitePF") else PUBLICO_SO_PJ,
                    link=f"{PORTAL}/edital/{edle}/lote/{numero}",
                    imagem=imagens[0].get("min") if imagens else None,
                    observacoes=["Proposta fechada: valor mostrado é o lance mínimo"],
                )
            )
    return lotes
