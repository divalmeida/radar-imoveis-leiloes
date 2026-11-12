"""Roda todos os coletores de leilão e grava o resultado em docs/dados/leiloes.json.

Uso:  python3 coletar_leiloes.py
"""

import json
import multiprocessing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import historico
from radar.coletores import bancos_imoveis, caixa, freitas, kwara, megaleiloes, mercadoleiloar, palacio, parque, receita, soleon, superbid

# Fonte: (função de coleta, tempo máximo em minutos)
# A chave é o nome da fonte no app; coletores que juntam vários sites usam o nome do grupo
COLETORES = {
    "Receita Federal": (receita.coletar, 15),
    "Superbid": (superbid.coletar, 8),
    "Caixa": (caixa.coletar, 5),
    "Kwara": (kwara.coletar, 6),
    "Mega Leilões": (megaleiloes.coletar, 6),
    "Freitas": (freitas.coletar, 8),
    "Palácio dos Leilões": (palacio.coletar, 8),
    "Parque dos Leilões": (parque.coletar, 6),
    "João Emílio / Leilão Prime / Tudo Leilão": (soleon.coletar, 14),
    "Bolsa de Leilões / Hisa": (mercadoleiloar.coletar, 6),
    "Zuk / Frazão (imóveis BA)": (bancos_imoveis.coletar, 5),
}

ARQUIVO_SAIDA = Path(__file__).parent / "docs" / "dados" / "leiloes.json"
FUSO_BRASILIA = timezone(timedelta(hours=-3))


def _ler_saida() -> dict:
    try:
        return json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _anteriores() -> dict:
    """Lotes da coleta anterior, por coletor (usados quando um coletor falha)."""
    dados = _ler_saida()
    if not dados:
        return {}
    por_coletor: dict = {}
    for lote in dados.get("lotes", []):
        por_coletor.setdefault(lote.get("coletor") or lote["fonte"], []).append(lote)
    for nome, info in dados.get("fontes", {}).items():
        for lote in por_coletor.get(nome, []):
            lote.setdefault("_coletado_em", info.get("dados_de") or dados.get("atualizado_em"))
    return por_coletor


def main() -> None:
    lotes = []  # (nome do coletor, Lote)
    status = {}
    anteriores = _anteriores()
    fontes_antes = _ler_saida().get("fontes", {})
    # Cópia por id, antes de qualquer alteração, para o histórico de preço
    por_id = {l["id"]: dict(l) for lista in anteriores.values() for l in lista}
    guardados = []  # lotes mantidos da coleta anterior (já em formato de dicionário)

    # Todos os coletores rodam ao mesmo tempo, cada um em seu processo e com seu limite de tempo
    contexto = multiprocessing.get_context("spawn")
    rodando = []
    for nome, (coletar, minutos) in COLETORES.items():
        pool = contexto.Pool(1)
        rodando.append((nome, pool, pool.apply_async(coletar), minutos))
    inicio = datetime.now()
    for nome, pool, tarefa, minutos in rodando:
        restante = max(1, minutos * 60 - (datetime.now() - inicio).seconds)
        try:
            encontrados = tarefa.get(timeout=restante)
            lotes.extend((nome, l) for l in encontrados)
            status[nome] = {"ok": True, "lotes": len(encontrados)}
        except Exception as erro:  # uma fonte com problema não derruba as outras
            if isinstance(erro, multiprocessing.TimeoutError):
                erro = RuntimeError(f"passou de {minutos} minutos e foi interrompido")
            print(f"[ERRO] {nome}: {erro}", flush=True)
            status[nome] = {"ok": False, "erro": str(erro)}
            # Mantém a última lista boa desse coletor, avisando de quando ela é
            antigos = anteriores.get(nome, [])
            if antigos:
                status[nome]["dados_de"] = antigos[0].pop("_coletado_em", None)
                for lote in antigos:
                    lote.pop("_coletado_em", None)
                guardados.extend(antigos)
                status[nome]["lotes"] = len(antigos)
                if fontes_antes.get(nome, {}).get("local"):
                    # Site que recusa a nuvem: a lista vem da coleta feita no Mac (coletar_no_mac.py)
                    status[nome] = {"ok": True, "lotes": len(antigos), "dados_de": status[nome]["dados_de"], "local": True}
                print(f"[{nome}] mantidos {len(antigos)} lotes da coleta de {status[nome]['dados_de']}", flush=True)
        finally:
            pool.terminate()
        status[nome]["segundos"] = (datetime.now() - inicio).seconds
        print(f"=== {nome}: pronto em {status[nome]['segundos']} s ===", flush=True)

    lotes.sort(key=lambda x: (not x[1].prioridade, not x[1].destaque, x[1].encerramento or "9999"))
    agora = datetime.now(FUSO_BRASILIA)
    novos = [dict(l.para_dict(), coletor=nome) for nome, l in lotes]
    # Histórico de preço (lance atual / preço da Caixa) em relação às coletas anteriores
    historico.aplicar(novos, por_id, agora.strftime("%Y-%m-%d"), "lance_atual")
    resultado = {
        "atualizado_em": agora.strftime("%Y-%m-%d %H:%M"),
        "fontes": status,
        "lotes": novos + guardados,
    }
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTotal: {len(lotes)} lotes gravados em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
