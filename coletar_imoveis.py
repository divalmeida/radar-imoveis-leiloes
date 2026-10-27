"""Coleta apartamentos à venda (e aluguéis de referência) e grava em docs/dados/imoveis.json.

- Compara com a coleta anterior para marcar anúncios NOVOS e QUEDAS DE PREÇO.
- Junta o mesmo imóvel anunciado em portais diferentes (quando houver mais portais).
- Calcula o aluguel estimado de TODO imóvel à venda (e dos apartamentos da
  Caixa) e o custo mensal (condomínio + IPTU).

Uso:  python3 coletar_imoveis.py
"""

import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar.config import (
    CIDADES_IMOVEIS,
    DETALHES_POR_COLETA,
    DIAS_NOVO,
    PRECO_MAXIMO_ALUGUEL,
    PRECO_MAXIMO_COMPRA,
    PRECO_MINIMO_ALUGUEL,
    PRECO_MINIMO_COMPRA,
    QUARTOS_MINIMO,
)
from radar.aluguel import Referencia
from radar.coletores import chavesnamao, quintoandar
from radar.localidades import chave_texto

PASTA = Path(__file__).parent / "docs" / "dados"
ARQUIVO = PASTA / "imoveis.json"
FUSO_BRASILIA = timezone(timedelta(hours=-3))
TEMPO_MAXIMO_DETALHES = 12 * 60  # segundos

# Portais coletados todo dia (cada um com a função buscar(negocio, cidade, quartos, preco_max))
PORTAIS = {
    "Chaves na Mão": chavesnamao,
    "QuintoAndar": quintoandar,
}


def _anterior() -> dict:
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return {a["id"]: a for a in dados.get("anuncios", [])}
    except (OSError, ValueError):
        return {}


def _chave_imovel(a: dict) -> str:
    """Identifica o mesmo apartamento em portais diferentes."""
    area = round((a.get("area") or 0) / 2) * 2
    preco = round((a.get("preco") or 0) / 5000)
    return f"{chave_texto(a['cidade'])}|{chave_texto(a.get('bairro') or '')}|{a.get('quartos')}|{area}|{preco}"


def _custos(a: dict) -> None:
    """Custo mensal fixo do imóvel: condomínio + IPTU.
    Alguns anúncios informam o IPTU do ano inteiro; quando o valor é alto demais
    para ser mensal, dividimos por 12."""
    if a.get("condominio_iptu"):  # QuintoAndar informa os dois somados, por mês
        a["custo_mensal"] = a["condominio_iptu"]
        return
    iptu = a.get("iptu")
    a["iptu_anual"] = bool(iptu and iptu > max(600, 2 * (a.get("condominio") or 0)))
    a["iptu_mensal"] = round(iptu / 12) if a["iptu_anual"] else iptu
    partes = [v for v in (a.get("condominio"), a["iptu_mensal"]) if v]
    a["custo_mensal"] = round(sum(partes)) if partes else None


def _aluguel_caixa(referencia: Referencia) -> dict:
    """Aluguel estimado dos apartamentos da Caixa (aba Leilões), pela mesma regra."""
    try:
        leiloes = json.loads((PASTA / "leiloes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    estimativas = {}
    for lote in leiloes.get("lotes", []):
        det = lote.get("detalhes") or {}
        if lote.get("fonte") != "Caixa" or "apartamento" not in (lote.get("categoria") or "").lower():
            continue
        descricao = det.get("descricao") or ""
        m = re.search(r"([\d.]+) de área privativa", descricao) or re.search(r"([\d.]+) de área total", descricao)
        q = re.search(r"(\d+) qto", descricao)
        est = referencia.estimar(lote["cidade"], det.get("bairro"), float(m.group(1)) if m else None, int(q.group(1)) if q else None)
        if est:
            estimativas[lote["id"]] = est
    return estimativas


def _variacao(a: dict) -> None:
    """Compara o preço atual com o anterior: subiu, baixou, quanto e quando."""
    historico = [h for h in a.get("historico_precos", []) if h.get("preco")]
    a["preco_anterior"] = a["variacao"] = a["variacao_pct"] = a["variacao_em"] = None
    if len(historico) > 1:
        antes, agora = historico[-2], historico[-1]
        a["preco_anterior"] = antes["preco"]
        a["variacao"] = agora["preco"] - antes["preco"]
        a["variacao_pct"] = round(a["variacao"] / antes["preco"] * 100, 1)
        a["variacao_em"] = agora["data"]
    a["baixou_preco"] = bool(a["variacao"] and a["variacao"] < 0)
    a["subiu_preco"] = bool(a["variacao"] and a["variacao"] > 0)


def _marcar_repetidos(anuncios: list) -> None:
    """O mesmo imóvel costuma ser anunciado por várias imobiliárias e portais.
    Todos ficam guardados (para manter o histórico de cada um), com o mesmo
    'grupo'; o painel mostra um cartão por grupo."""
    for a in anuncios:
        a["grupo"] = _chave_imovel(a)


def main() -> None:
    hoje = date.today().isoformat()
    anterior = _anterior()
    # Um portal ou cidade que aparece pela primeira vez não marca tudo como "novo"
    buscas_antes = {(a.get("fonte"), a.get("cidade")) for a in anterior.values()}

    compras, alugueis, status = [], [], {}
    buscas = [
        (portal, modulo, cidade, negocio, preco_min, preco_max, destino)
        for portal, modulo in PORTAIS.items()
        for cidade in CIDADES_IMOVEIS
        for negocio, preco_min, preco_max, destino in (
            ("compra", PRECO_MINIMO_COMPRA, PRECO_MAXIMO_COMPRA, compras),
            ("aluguel", PRECO_MINIMO_ALUGUEL, PRECO_MAXIMO_ALUGUEL, alugueis),
        )
    ]
    for portal, modulo, cidade, negocio, preco_min, preco_max, destino in buscas:
        chave = f"{portal} - {negocio} - {cidade['nome']}"
        try:
            encontrados = modulo.buscar(negocio, cidade, QUARTOS_MINIMO, preco_max)
            encontrados = [a for a in encontrados if a.get("preco") and a["preco"] >= preco_min]
            destino.extend(encontrados)
            status[chave] = {"ok": True, "anuncios": len(encontrados)}
        except Exception as erro:
            print(f"[ERRO] {chave}: {erro}", flush=True)
            status[chave] = {"ok": False, "erro": str(erro)}

    regiao_da_cidade = {c["nome"]: c["regiao"] for c in CIDADES_IMOVEIS}
    for a in compras + alugueis:
        a["regiao"] = regiao_da_cidade.get(a["cidade"], a["cidade"])

    # Histórico: novos, quedas de preço e detalhes já buscados antes
    for a in compras:
        antes = anterior.get(a["id"])
        if antes:
            for campo in ("primeiro_visto", "historico_precos", "detalhado", "financiamento", "publicado_em"):
                if campo in antes:
                    a[campo] = antes[campo]
            for campo in ("condominio", "iptu"):  # vale o da coleta de hoje; o antigo só se hoje não veio
                if a.get(campo) is None and antes.get(campo) is not None:
                    a[campo] = antes[campo]
            historico = a.setdefault("historico_precos", [])
            if a["preco"] and historico and historico[-1]["preco"] != a["preco"]:
                historico.append({"data": hoje, "preco": a["preco"]})
        else:
            a["primeiro_visto"] = hoje if (a["fonte"], a["cidade"]) in buscas_antes else None
            a["historico_precos"] = [{"data": hoje, "preco": a["preco"]}]

        visto = a.get("primeiro_visto")
        a["novo"] = bool(visto) and (date.fromisoformat(visto) >= date.today() - timedelta(days=DIAS_NOVO))
        _variacao(a)

    # Detalhes (financiamento, condomínio): primeiro os novos, com limite de tempo
    pendentes = sorted((a for a in compras if not a.get("detalhado")), key=lambda a: not a["novo"])
    inicio = time.monotonic()
    feitos = 0
    for a in pendentes[:DETALHES_POR_COLETA]:
        if time.monotonic() - inicio > TEMPO_MAXIMO_DETALHES:
            break
        try:
            a.update(chavesnamao.detalhes(a))
            feitos += 1
        except Exception as erro:
            print(f"[detalhe] {a['id']}: {erro}", flush=True)
    print(f"[Chaves na Mão] detalhes buscados: {feitos} (faltam {len(pendentes) - feitos})", flush=True)

    # Se uma busca falhou, mantém os anúncios dela da coleta anterior
    falhas = {k for k, s in status.items() if not s["ok"]}
    ids = {a["id"] for a in compras}
    for a in anterior.values():
        if a["id"] not in ids and f"{a.get('fonte')} - compra - {a['cidade']}" in falhas:
            compras.append(a)

    _marcar_repetidos(compras)
    referencia = Referencia(alugueis, {c["nome"]: c["regiao"] for c in CIDADES_IMOVEIS})
    for a in compras:
        _custos(a)
        a["aluguel"] = referencia.estimar(a["cidade"], a.get("bairro"), a.get("area"), a.get("quartos"))
    resultado = {
        "atualizado_em": datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d %H:%M"),
        "filtros": {"quartos_minimo": QUARTOS_MINIMO, "preco_maximo_compra": PRECO_MAXIMO_COMPRA,
                    "preco_maximo_aluguel": PRECO_MAXIMO_ALUGUEL, "cidades": [c["nome"] for c in CIDADES_IMOVEIS],
                    "regioes": [{"nome": r, "cidades": [c["nome"] for c in CIDADES_IMOVEIS if c["regiao"] == r]}
                                for r in dict.fromkeys(c["regiao"] for c in CIDADES_IMOVEIS)]},
        "fontes": status,
        "aluguel_caixa": _aluguel_caixa(referencia),
        "anuncios": compras,
        "alugueis": alugueis,
    }
    PASTA.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(json.dumps(resultado, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    novos = sum(a["novo"] for a in resultado["anuncios"])
    baixaram = sum(a["baixou_preco"] for a in resultado["anuncios"])
    subiram = sum(a["subiu_preco"] for a in resultado["anuncios"])
    imoveis = len({a["grupo"] for a in compras})
    print(f"\nTotal: {len(compras)} anúncios à venda de {imoveis} imóveis ({novos} novos, {baixaram} baixaram e {subiram} subiram de preço), "
          f"{len(alugueis)} aluguéis de referência")


if __name__ == "__main__":
    main()
