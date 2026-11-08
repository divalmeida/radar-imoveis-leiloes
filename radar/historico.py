"""Histórico de preço entre coletas: quando o item apareceu, quando o preço
mudou, se subiu ou caiu e quanto. Usado nos leilões (lance/preço)."""

from typing import Dict, List


def variacao(item: dict) -> None:
    """Preenche preco_anterior, variacao, variacao_pct, variacao_em, baixou_preco e subiu_preco."""
    historico = [h for h in item.get("historico_precos", []) if h.get("preco")]
    item["preco_anterior"] = item["variacao"] = item["variacao_pct"] = item["variacao_em"] = None
    if len(historico) > 1:
        antes, agora = historico[-2], historico[-1]
        item["preco_anterior"] = antes["preco"]
        item["variacao"] = round(agora["preco"] - antes["preco"], 2)
        item["variacao_pct"] = round(item["variacao"] / antes["preco"] * 100, 1)
        item["variacao_em"] = agora["data"]
        # Do primeiro preço visto até hoje
        primeiro = historico[0]["preco"]
        item["variacao_total_pct"] = round((agora["preco"] - primeiro) / primeiro * 100, 1)
    item["baixou_preco"] = bool(item["variacao"] and item["variacao"] < 0)
    item["subiu_preco"] = bool(item["variacao"] and item["variacao"] > 0)


def aplicar(itens: List[dict], anteriores: Dict[str, dict], hoje: str, campo_preco: str) -> None:
    """Junta o histórico da coleta anterior a cada item e registra mudança de preço."""
    for item in itens:
        preco = item.get(campo_preco)
        antes = anteriores.get(item["id"])
        if antes:
            item["primeiro_visto"] = antes.get("primeiro_visto") or hoje
            historico = list(antes.get("historico_precos") or [])
        else:
            item["primeiro_visto"] = hoje
            historico = []
        if preco and (not historico or historico[-1]["preco"] != preco):
            historico.append({"data": hoje, "preco": preco})
        item["historico_precos"] = historico
        variacao(item)
