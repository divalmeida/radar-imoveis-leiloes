"""Monta o resumo do dia e envia pelos canais configurados (Telegram).

- Imóveis (você e a Lore): apartamentos novos e que baixaram de preço hoje.
- Leilões (só você): imóveis novos da Caixa nas cidades prioritárias e lotes
  que encerram nas próximas 48 horas nos estados em destaque.

Uso:  python3 enviar_alertas.py [pasta_com_dados_da_coleta_anterior]
      python3 enviar_alertas.py --previa    (só mostra as mensagens, não envia)
"""

import html
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.alertas import canais_configurados
from radar.config import UFS_DESTAQUE
from radar.localidades import chave_texto

PASTA = Path(__file__).parent / "docs" / "dados"
SITE = "https://divalmeida.github.io/radar-imoveis-leiloes/"
FUSO = timezone(timedelta(hours=-3))
MAX_ITENS = 8


def _ler(caminho: Path) -> dict:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _reais(valor) -> str:
    return "R$ " + f"{valor:,.0f}".replace(",", ".") if valor else "—"


def _e(texto) -> str:
    return html.escape(str(texto or ""))


# ---------- aluguel estimado (mesma regra do painel) ----------

def _indice_alugueis(alugueis: list) -> dict:
    indice = {}
    for a in alugueis:
        if a.get("preco") and a.get("bairro"):
            indice.setdefault(f"{chave_texto(a['cidade'])}|{chave_texto(a['bairro'])}", []).append(a)
    return indice


def _aluguel_estimado(indice: dict, cidade, bairro, area, quartos):
    do_bairro = indice.get(f"{chave_texto(cidade or '')}|{chave_texto(bairro or '')}", [])
    comps = [a for a in do_bairro if (not quartos or a.get("quartos") == quartos)
             and (not area or (a.get("area") and area * 0.7 <= a["area"] <= area * 1.3))]
    if len(comps) >= 3:
        return statistics.median(a["preco"] for a in comps)
    if area:
        por_m2 = [a for a in do_bairro if (not quartos or a.get("quartos") == quartos) and (a.get("area") or 0) >= 25]
        if len(por_m2) >= 3 and area <= max(a["area"] for a in por_m2) * 1.3:
            return min(statistics.median(a["preco"] / a["area"] for a in por_m2) * area, max(a["preco"] for a in por_m2))
    return None


def _linha_renda(estimado, preco) -> str:
    if not estimado or not preco:
        return ""
    rendimento = str(round(estimado * 12 / preco * 100, 1)).replace(".", ",")
    return f"\n   Aluguel estimado {_reais(round(estimado / 50) * 50)}/mês · {rendimento}% ao ano"


# ---------- mensagens ----------

def _variacao_texto(antes: float, agora: float) -> str:
    """'▼ R$ 15.000 (−6,8%)' ou '▲ R$ 10.000 (+4,2%)'."""
    diferenca = agora - antes
    pct = str(round(abs(diferenca) / antes * 100, 1)).replace(".", ",")
    return f"{'▼' if diferenca < 0 else '▲'} {_reais(abs(diferenca))} ({'−' if diferenca < 0 else '+'}{pct}%)"


def mensagem_imoveis(dados: dict, anterior: dict, sempre: bool) -> str:
    """Compara com a coleta anterior: o que apareceu e o que mudou de preço desde então.
    Se não houver novidade, só manda mensagem quando `sempre` for verdadeiro (resumo da manhã)."""
    if not dados:
        return ""
    indice = _indice_alugueis(dados.get("alugueis", []))
    antes = {a["id"]: a for a in anterior.get("anuncios", [])}
    grupos_antes = {a.get("grupo") for a in antes.values()}
    grupos = {}
    for a in dados.get("anuncios", []):
        grupos.setdefault(a.get("grupo") or a["id"], []).append(a)

    novos, baixaram, subiram = [], [], []
    portais_antes = {a.get("fonte") for a in antes.values()}
    if antes:  # sem coleta anterior não dá para saber o que mudou
        for grupo, lista in grupos.items():
            lista.sort(key=lambda a: a.get("preco") or 1e12)
            # Portal recém-incluído: tudo dele seria "novo"; só conta a partir da próxima coleta
            if not any(a.get("fonte") in portais_antes for a in lista):
                continue
            if grupo not in grupos_antes and not any(a["id"] in antes for a in lista):
                novos.append(lista[0])
                continue
            for a in lista:
                velho = antes.get(a["id"])
                if velho and velho.get("preco") and a.get("preco") and velho["preco"] != a["preco"]:
                    (baixaram if a["preco"] < velho["preco"] else subiram).append((a, velho["preco"]))
                    break

    def item(a, preco_antes=None):
        est = _aluguel_estimado(indice, a["cidade"], a.get("bairro"), a.get("area"), a.get("quartos"))
        ficha = " · ".join(filter(None, [a.get("quartos") and f"{a['quartos']} qts", a.get("area") and f"{a['area']:.0f} m²"]))
        if preco_antes:
            preco = f"<s>{_reais(preco_antes)}</s> → <b>{_reais(a['preco'])}</b>  {_variacao_texto(preco_antes, a['preco'])}"
        else:
            preco = f"<b>{_reais(a.get('preco'))}</b>"
        fin = " · aceita financiamento" if a.get("financiamento") is True else ""
        texto = (f"• {preco}\n   {_e(a.get('bairro'))}, {_e(a['cidade'])} ({ficha}){fin}"
                 f"{_linha_renda(est, a.get('preco'))}\n   <a href=\"{_e(a['link'])}\">ver anúncio</a>")
        return texto, (est * 12 / a["preco"] if est and a.get("preco") else 0)

    agora = datetime.now(FUSO)
    partes = [f"🏠 <b>Radar Imóveis — {agora.strftime('%d/%m %H:%M')}</b>"]
    if novos:
        itens = sorted((item(a) for a in novos), key=lambda x: -x[1])
        partes.append(f"<b>🆕 {len(novos)} apartamento{'s' if len(novos) > 1 else ''} novo{'s' if len(novos) > 1 else ''}</b> (maior rendimento primeiro):\n\n" +
                      "\n\n".join(t for t, _ in itens[:MAX_ITENS]))
    if baixaram:
        baixaram.sort(key=lambda x: (x[0]["preco"] - x[1]) / x[1])
        partes.append(f"<b>📉 {len(baixaram)} {'baixaram' if len(baixaram) > 1 else 'baixou'} de preço:</b>\n\n" + "\n\n".join(item(a, p)[0] for a, p in baixaram[:MAX_ITENS]))
    if subiram:
        subiram.sort(key=lambda x: -(x[0]["preco"] - x[1]) / x[1])
        partes.append(f"<b>📈 {len(subiram)} {'subiram' if len(subiram) > 1 else 'subiu'} de preço:</b>\n\n" + "\n\n".join(item(a, p)[0] for a, p in subiram[:MAX_ITENS]))
    if not (novos or baixaram or subiram):
        if not sempre:
            return ""
        partes.append("Nenhum apartamento novo e nenhuma mudança de preço desde a última coleta.")
    partes.append(f"{len(grupos)} apartamentos acompanhados. <a href=\"{SITE}\">Abrir o Radar</a>")
    return "\n\n".join(partes)


def mensagem_leiloes(dados: dict, anterior: dict, sempre: bool) -> str:
    """Imóveis novos da Caixa em toda coleta; a lista do que encerra em 48h só no resumo da manhã."""
    if not dados:
        return ""
    agora = datetime.now(FUSO).replace(tzinfo=None)
    ids_antes = {l["id"] for l in anterior.get("lotes", [])}
    lotes = dados.get("lotes", [])

    caixa_novos = [l for l in lotes if l["fonte"] == "Caixa" and l.get("prioridade") and anterior and l["id"] not in ids_antes]
    encerrando = []
    for l in (lotes if sempre else []):
        if l["fonte"] == "Caixa" or not l.get("encerramento") or l.get("uf") not in UFS_DESTAQUE:
            continue
        fim = datetime.strptime(l["encerramento"], "%Y-%m-%d %H:%M")
        if agora <= fim <= agora + timedelta(hours=48):
            encerrando.append(l)

    def desconto(l):
        if l.get("valor_avaliacao") and l.get("lance_atual"):
            return 1 - l["lance_atual"] / l["valor_avaliacao"]
        return 0

    partes = [f"🔨 <b>Radar Leilões — {datetime.now(FUSO).strftime('%d/%m %H:%M')}</b>"]
    if caixa_novos:
        caixa_novos.sort(key=lambda l: -(l.get("detalhes") or {}).get("desconto_pct", 0))
        partes.append(f"<b>{len(caixa_novos)} imóve{'is' if len(caixa_novos) > 1 else 'l'} novo{'s' if len(caixa_novos) > 1 else ''} da Caixa</b> (Salvador, Feira, Conceição):\n\n" + "\n\n".join(
            f"• <b>{_reais(l['lance_atual'])}</b> — {_e(l['titulo'])} · {(l.get('detalhes') or {}).get('desconto_pct', 0):.0f}% de desconto"
            f"{' · aceita financiamento' if (l.get('detalhes') or {}).get('financiamento') else ''}\n   <a href=\"{_e(l['link'])}\">ver na Caixa</a>"
            for l in caixa_novos[:MAX_ITENS]))
    if encerrando:
        # Quem tem valor de avaliação e desconto grande vem primeiro; depois, o que encerra antes
        encerrando.sort(key=lambda l: (-round(desconto(l), 1), l["encerramento"]))
        partes.append(f"<b>{len(encerrando)} lotes encerram em até 48h</b> (SP, RJ, DF, SC, BA):\n\n" + "\n\n".join(
            f"• <b>{_reais(l['lance_atual'])}</b> — {_e(l['titulo'][:90])}\n   {_e(l['cidade'])}-{_e(l['uf'])} · {_e(l['publico'])} · encerra {l['encerramento'][8:10]}/{l['encerramento'][5:7]} {l['encerramento'][11:]}"
            f" · <a href=\"{_e(l['link'])}\">{_e(l['fonte'])}</a>"
            for l in encerrando[:MAX_ITENS]))
    if not caixa_novos and not encerrando:
        if not sempre:
            return ""
        partes.append("Nada novo da Caixa nas cidades prioritárias e nenhum lote encerrando em 48h nos estados em destaque.")
    falhas = [n for n, s in dados.get("fontes", {}).items() if not s.get("ok")]
    if falhas:
        partes.append("⚠️ Fontes com problema hoje: " + ", ".join(falhas))
    partes.append(f"{len(lotes)} lotes acompanhados. <a href=\"{SITE}\">Abrir o Radar</a>")
    return "\n\n".join(partes)


def main() -> None:
    previa = "--previa" in sys.argv
    pasta_anterior = next((Path(a) for a in sys.argv[1:] if not a.startswith("--")), None)
    anterior = (lambda nome: _ler(pasta_anterior / nome)) if pasta_anterior else (lambda nome: {})
    # A coleta da manhã (e o botão "Run workflow") sempre manda um resumo;
    # as outras só quando há novidade
    sempre = datetime.now(FUSO).hour < 11 or os.environ.get("ALERTA_SEMPRE") == "1"

    mensagens = {
        "imoveis": mensagem_imoveis(_ler(PASTA / "imoveis.json"), anterior("imoveis.json"), sempre),
        "leiloes": mensagem_leiloes(_ler(PASTA / "leiloes.json"), anterior("leiloes.json"), sempre),
    }

    if previa:
        for assunto, texto in mensagens.items():
            print(f"===== {assunto} =====\n{texto}\n")
        return

    canais = canais_configurados()
    if not canais:
        print("Alertas desligados: nenhum canal configurado nos Secrets.")
        return
    for canal, destino, assuntos in canais:
        for assunto in ("imoveis", "leiloes"):
            if assunto in assuntos and mensagens[assunto]:
                try:
                    canal.enviar(destino, mensagens[assunto])
                    print(f"Enviado: {assunto} por {canal.nome}")
                except Exception as erro:  # um destino com problema não impede os outros
                    print(f"[ERRO] {assunto} por {canal.nome}: {erro}")


if __name__ == "__main__":
    main()
