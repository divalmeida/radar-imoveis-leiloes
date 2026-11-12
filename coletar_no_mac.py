"""Coleta, no Mac, os sites que recusam a nuvem (Caixa e João Emílio / Leilão Prime / Tudo Leilão)
e envia o resultado para o GitHub. A coleta da nuvem passa a manter essa lista.

Roda sozinha 2x por dia (agendada no Mac) numa cópia separada do projeto,
em ~/Library/Application Support/RadarLocal, para não mexer na sua pasta de trabalho.

Uso manual:  python3 coletar_no_mac.py
"""

import json
import multiprocessing
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from coletar_leiloes import ARQUIVO_SAIDA, COLETORES, FUSO_BRASILIA
from radar import historico

LOCAIS = ["Caixa", "João Emílio / Leilão Prime / Tudo Leilão"]
PASTA = Path(__file__).parent


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=PASTA, check=True, capture_output=True, text=True).stdout


def coletar() -> dict:
    """Roda cada site com seu limite de tempo; devolve {nome: [dicts]} só dos que deram certo."""
    contexto = multiprocessing.get_context("spawn")
    achados = {}
    for nome in LOCAIS:
        funcao, minutos = COLETORES[nome]
        pool = contexto.Pool(1)
        try:
            lotes = pool.apply_async(funcao).get(timeout=minutos * 60 + 120)
            achados[nome] = [dict(l.para_dict(), coletor=nome) for l in lotes]
            print(f"[{nome}] {len(lotes)} lotes", flush=True)
        except Exception as erro:
            print(f"[{nome}] falhou: {erro}", flush=True)
        finally:
            pool.terminate()
    return achados


def juntar(achados: dict) -> None:
    """Troca, no leiloes.json mais recente, a lista desses sites pela coletada agora."""
    dados = json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
    agora = datetime.now(FUSO_BRASILIA)
    for nome, novos in achados.items():
        antigos = [l for l in dados["lotes"] if (l.get("coletor") or l["fonte"]) == nome]
        por_id = {l["id"]: dict(l) for l in antigos}
        historico.aplicar(novos, por_id, agora.strftime("%Y-%m-%d"), "lance_atual")
        info_antes = dados["fontes"].get(nome, {})
        info = {"ok": True, "lotes": len(novos), "dados_de": agora.strftime("%Y-%m-%d %H:%M"), "local": True}
        # Para o aviso no Telegram da próxima coleta na nuvem: o que é novo ou mudou de preço
        info["novos_pendentes"] = sorted(set(info_antes.get("novos_pendentes", [])) | {l["id"] for l in novos if l["id"] not in por_id})
        precos = dict(info_antes.get("precos_pendentes", {}))
        for l in novos:
            antes = por_id.get(l["id"], {}).get("lance_atual")
            if antes and l.get("lance_atual") and antes != l["lance_atual"]:
                precos.setdefault(l["id"], antes)
        info["precos_pendentes"] = precos
        dados["lotes"] = [l for l in dados["lotes"] if (l.get("coletor") or l["fonte"]) != nome] + novos
        dados["fontes"][nome] = info
    ARQUIVO_SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    # Segurança: o "reset --hard" abaixo só pode rodar na cópia separada, nunca na sua pasta de trabalho
    if "RadarLocal" not in str(PASTA.resolve()):
        sys.exit("Rode este script pela cópia em ~/Library/Application Support/RadarLocal (veja instalar_coleta_no_mac.sh).")
    print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} ===", flush=True)
    git("fetch", "-q", "origin")
    git("reset", "-q", "--hard", "origin/main")
    achados = coletar()
    if not achados:
        print("Nenhum site respondeu; nada enviado.")
        return
    for tentativa in range(3):
        juntar(achados)
        git("add", str(ARQUIVO_SAIDA))
        git("commit", "-qm", f"Coleta no Mac {datetime.now():%Y-%m-%d %H:%M} ({', '.join(achados)})")
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=PASTA).returncode == 0:
            print("Enviado para o GitHub.")
            return
        # A nuvem gravou ao mesmo tempo: pega a versão nova e junta de novo
        git("fetch", "-q", "origin")
        git("reset", "-q", "--hard", "origin/main")
    sys.exit("Não consegui enviar depois de 3 tentativas.")


if __name__ == "__main__":
    main()
