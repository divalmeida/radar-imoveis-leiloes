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


def _anteriores() -> dict:
    """Lotes da coleta anterior, por fonte (usados quando uma fonte falha)."""
    try:
        dados = json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    por_fonte: dict = {}
    for lote in dados.get("lotes", []):
        por_fonte.setdefault(lote["fonte"], []).append(lote)
    for nome, info in dados.get("fontes", {}).items():
        for lote in por_fonte.get(nome, []):
            lote.setdefault("_coletado_em", info.get("dados_de") or dados.get("atualizado_em"))
    return por_fonte


def main() -> None:
    lotes = []
    status = {}
    anteriores = _anteriores()
    guardados = []  # lotes mantidos da coleta anterior (já em formato de dicionário)
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
            # Mantém a última lista boa dessa fonte, avisando de quando ela é
            antigos = anteriores.get(nome, [])
            if antigos:
                status[nome]["dados_de"] = antigos[0].pop("_coletado_em", None)
                for lote in antigos:
                    lote.pop("_coletado_em", None)
                guardados.extend(antigos)
                status[nome]["lotes"] = len(antigos)
                print(f"[{nome}] mantidos {len(antigos)} lotes da coleta de {status[nome]['dados_de']}", flush=True)
        segundos = (datetime.now() - inicio).seconds
        status[nome]["segundos"] = segundos
        print(f"=== {nome}: {segundos} s ===", flush=True)

    lotes.sort(key=lambda l: (not l.prioridade, not l.destaque, l.encerramento or "9999"))
    resultado = {
        "atualizado_em": datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d %H:%M"),
        "fontes": status,
        "lotes": [l.para_dict() for l in lotes] + guardados,
    }
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTotal: {len(lotes)} lotes gravados em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
