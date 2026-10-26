"""Roda todos os coletores de leilão e grava o resultado em docs/dados/leiloes.json.

Uso:  python3 coletar_leiloes.py
"""

import json
import multiprocessing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.coletores import caixa, receita, superbid

# Fonte: (função de coleta, tempo máximo em minutos)
COLETORES = {
    "Receita Federal": (receita.coletar, 15),
    "Superbid": (superbid.coletar, 8),
    "Caixa": (caixa.coletar, 5),
}

ARQUIVO_SAIDA = Path(__file__).parent / "docs" / "dados" / "leiloes.json"
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _rodar_com_limite(coletar, minutos: int):
    """Roda o coletor em um processo separado; se passar do tempo, ele é encerrado."""
    with multiprocessing.get_context("spawn").Pool(1) as pool:
        tarefa = pool.apply_async(coletar)
        try:
            return tarefa.get(timeout=minutos * 60)
        except multiprocessing.TimeoutError:
            pool.terminate()
            raise RuntimeError(f"passou de {minutos} minutos e foi interrompido")


def main() -> None:
    lotes = []
    status = {}
    for nome, (coletar, minutos) in COLETORES.items():
        inicio = datetime.now()
        print(f"\n=== {nome} ===", flush=True)
        try:
            encontrados = _rodar_com_limite(coletar, minutos)
            lotes.extend(encontrados)
            status[nome] = {"ok": True, "lotes": len(encontrados)}
        except Exception as erro:  # uma fonte com problema não derruba as outras
            print(f"[ERRO] {nome}: {erro}", flush=True)
            status[nome] = {"ok": False, "erro": str(erro)}
        segundos = (datetime.now() - inicio).seconds
        status[nome]["segundos"] = segundos
        print(f"=== {nome}: {segundos} s ===", flush=True)

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
