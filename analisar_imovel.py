"""Análise completa de UM imóvel da Caixa, sob demanda.

Lê a página do imóvel e a matrícula (OCR), aponta os riscos e grava em
docs/dados/analises/<numero>.json (o app mostra na ficha do imóvel).
Quando roda a partir de um pedido no GitHub (Issue), responde no próprio pedido.

Uso:  python3 analisar_imovel.py 8444400798566
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.caixa_detalhe import Bloqueado, baixar_detalhe, baixar_matricula, ler_detalhe
from radar.matricula import analisar_texto, data_do_pdf, ocr_pdf

PASTA = Path(__file__).parent / "docs" / "dados" / "analises"
FUSO = timezone(timedelta(hours=-3))
SITE_APP = "https://divalmeida.github.io/radar-imoveis-leiloes/"


def analisar(numero: str) -> dict:
    resultado = {"numero": numero, "analisado_em": datetime.now(FUSO).strftime("%Y-%m-%d %H:%M"), "avisos": []}
    try:
        resultado["detalhe"] = ler_detalhe(baixar_detalhe(numero))
    except Bloqueado as erro:
        resultado["avisos"].append(f"Página do imóvel: {erro}. Tente de novo mais tarde.")
    except Exception as erro:
        resultado["avisos"].append(f"Página do imóvel: não consegui ler ({erro}).")
    if resultado.get("detalhe", {}).get("disponivel") is False:
        resultado["avisos"].append("A Caixa informa que este imóvel não está mais à venda.")
        return resultado
    try:
        pdf = baixar_matricula(numero)
        resultado["matricula_url"] = f"https://venda-imoveis.caixa.gov.br/editais/matricula/BA/{numero}.pdf"
        texto = ocr_pdf(pdf)
        resultado["matricula"] = analisar_texto(texto, data_do_pdf(pdf))
    except Bloqueado as erro:
        resultado["avisos"].append(f"Matrícula: {erro}. Tente de novo mais tarde.")
    except Exception as erro:
        resultado["avisos"].append(f"Matrícula: {erro}.")
    return resultado


def resumo_texto(r: dict) -> str:
    """Resumo em texto (para responder no pedido do GitHub)."""
    linhas = [f"## Análise do imóvel {r['numero']} ({r['analisado_em']})", ""]
    d = r.get("detalhe") or {}
    if d.get("disponivel"):
        linhas += [
            f"- **Endereço:** {d.get('endereco')}",
            f"- **Matrícula:** {d.get('matricula')} · {d.get('oficio')}º ofício · {d.get('comarca')}",
            f"- **Ocupação:** {d.get('ocupacao') or 'não informada pela Caixa (trate como ocupado)'}",
            f"- **Pagamento:** {d.get('formas_pagamento')}",
            f"- **Condomínio atrasado:** {d.get('regra_condominio')}",
            f"- **IPTU atrasado:** {d.get('regra_tributos')}",
        ]
    m = r.get("matricula")
    if m:
        linhas += ["", f"### Matrícula: {m['resumo']} (nota {m['nota_risco']}/10)"]
        linhas += [f"- ✅ {t}" for t in m["pontos_ok"]]
        linhas += [f"- {'🔴' if x['nivel'] == 'alto' else '🟡'} {x['texto']}" for x in m["riscos"]]
        linhas += ["", "Atos encontrados: " + ", ".join(f"{a['ato']} ({a['tipo']}{', cancelado' if a['cancelado'] else ''})" for a in m["atos"])]
    linhas += [f"- ⚠️ {a}" for a in r["avisos"]]
    linhas += ["", f"Ver no app: {SITE_APP}", "",
               "_Análise automática de apoio. Não substitui a leitura do edital, da matrícula atualizada e a orientação de um advogado._"]
    return "\n".join(linhas)


def gravar(r: dict) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{r['numero']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    indice_arq = PASTA / "indice.json"
    try:
        indice = json.loads(indice_arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        indice = {}
    m = r.get("matricula") or {}
    indice[f"caixa-{r['numero']}"] = {"numero": r["numero"], "analisado_em": r["analisado_em"],
                                      "resumo": m.get("resumo"), "nota_risco": m.get("nota_risco"),
                                      "ocupacao": (r.get("detalhe") or {}).get("ocupacao"), "avisos": len(r["avisos"])}
    indice_arq.write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")


def responder_pedido(texto: str) -> None:
    """Comenta e fecha o pedido (Issue) no GitHub, quando a análise veio de lá."""
    token, repo, issue = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY"), os.environ.get("ISSUE_NUMBER")
    if not (token and repo and issue):
        return
    base = f"https://api.github.com/repos/{repo}/issues/{issue}"
    cab = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}
    for url, dados, metodo in ((base + "/comments", {"body": texto}, "POST"), (base, {"state": "closed"}, "PATCH")):
        urllib.request.urlopen(urllib.request.Request(url, data=json.dumps(dados).encode(), headers=cab, method=metodo), timeout=30)


def main() -> None:
    entrada = " ".join(sys.argv[1:])
    m = re.search(r"\d{8,15}", entrada)  # aceita o número, "caixa-<número>" ou o link do imóvel
    if not m:
        print("Informe o número do imóvel da Caixa (ex.: 8444400798566).")
        responder_pedido("Não encontrei o número do imóvel no pedido. Use o botão **Pedir análise** no app.")
        sys.exit(1)
    numero = m.group(0)
    r = analisar(numero)
    gravar(r)
    texto = resumo_texto(r)
    print(texto)
    responder_pedido(texto)


if __name__ == "__main__":
    main()
