"""Roda todos os coletores de leilão e grava o resultado em docs/dados/leiloes.json.

Uso:  python3 coletar_leiloes.py
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.coletores import caixa, receita, superbid

COLETORES = {
    "Receita Federal": receita.coletar,
    "Superbid": superbid.coletar,
    "Caixa": caixa.coletar,
}

ARQUIVO_SAIDA = Path(__file__).parent / "docs" / "dados" / "leiloes.json"
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def main() -> None:
    lotes = []
    status = {}
    for nome, coletar in COLETORES.items():
        try:
            encontrados = coletar()
            lotes.extend(encontrados)
            status[nome] = {"ok": True, "lotes": len(encontrados)}
        except Exception as erro:  # uma fonte com problema não derruba as outras
            print(f"[ERRO] {nome}: {erro}")
            status[nome] = {"ok": False, "erro": str(erro)}

    lotes.sort(key=lambda l: (not l.prioridade, not l.destaque, l.encerramento or "9999"))
    resultado = {
        "atualizado_em": datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d %H:%M"),
        "fontes": status,
        "lotes": [l.para_dict() for l in lotes],
    }
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTotal: {len(lotes)} lotes gravados em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
