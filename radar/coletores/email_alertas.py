"""Imóveis dos portais que bloqueiam robôs (ZAP, Viva Real, OLX, Imovelweb),
lidos dos ALERTAS DE E-MAIL que os próprios portais enviam.

Como funciona:
- Você cria alertas de busca em cada portal, usando um Gmail só para isso.
- A nuvem entra nesse Gmail (IMAP, com uma "senha de app" guardada nos
  Secrets GMAIL_USUARIO e GMAIL_SENHA_APP), lê os alertas dos últimos dias
  e tira de cada um: link, preço, quartos, área e bairro/cidade.
- Só leitura: nenhum e-mail é apagado ou marcado.
"""

import email
import html as html_lib
import imaplib
import os
import re
from datetime import date, timedelta
from email.header import decode_header, make_header
from typing import Dict, List, Optional

# Portal -> (remetente contém, domínios dos links dos anúncios)
PORTAIS = {
    "ZAP Imóveis": ("zapimoveis", ("zapimoveis.com.br",)),
    "Viva Real": ("vivareal", ("vivareal.com.br",)),
    "OLX": ("olx", ("olx.com.br",)),
    "Imovelweb": ("imovelweb", ("imovelweb.com.br",)),
}
DIAS = 7  # alertas dos últimos dias


def configurado() -> bool:
    return bool(os.environ.get("GMAIL_USUARIO") and os.environ.get("GMAIL_SENHA_APP"))


def _html_da_mensagem(msg) -> str:
    partes = msg.walk() if msg.is_multipart() else [msg]
    for parte in partes:
        if parte.get_content_type() == "text/html":
            bruto = parte.get_payload(decode=True) or b""
            return bruto.decode(parte.get_content_charset() or "utf-8", "replace")
    return ""


def _texto(trecho: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", trecho))).strip()


def _numero(texto: Optional[str]) -> Optional[float]:
    if not texto:
        return None
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _anuncios_do_html(html: str, portal: str, dominios) -> List[dict]:
    """Cada anúncio do alerta é um bloco com link para o portal e um preço em R$.
    Os e-mails mudam de formato com o tempo: a leitura é tolerante e ignora o que não entende."""
    anuncios: Dict[str, dict] = {}
    # Quebra o e-mail em blocos (linhas de tabela ou divs), do menor para o maior
    blocos = re.findall(r"<(?:tr|td|div)[^>]*>(?:(?!<(?:tr|td|div)[\s>]).)*?R\$.*?</(?:tr|td|div)>", html, re.S | re.I)
    for bloco in blocos or [html]:
        links = [html_lib.unescape(h) for h in re.findall(r'href="([^"]+)"', bloco)]
        link = next((h for h in links if any(d in h for d in dominios) and re.search(r"\d{5,}", h)), None) \
            or next((h for h in links if any(d in h for d in dominios)), None)
        texto = _texto(bloco)
        preco = re.search(r"R\$\s*([\d.]{4,}(?:,\d{2})?)", texto)
        if not link or not preco:
            continue
        ident = re.search(r"(\d{6,})", link)
        chave = ident.group(1) if ident else link.split("?")[0]
        if chave in anuncios:
            continue
        quartos = re.search(r"(\d+)\s*(?:quartos?|qts?|dormit)", texto, re.I)
        area = re.search(r"(\d+(?:[.,]\d+)?)\s*m²", texto)
        anuncios[chave] = {
            "id": f"email-{portal.split()[0].lower()}-{chave}"[:80],
            "fonte": portal,
            "negocio": "compra",
            "tipo": "Casa" if re.search(r"\bcasa\b", texto, re.I) else "Apartamento",
            "titulo": texto[:160],
            "preco": _numero(preco.group(1)),
            "quartos": int(quartos.group(1)) if quartos else None,
            "area": _numero(area.group(1)) if area else None,
            "texto": texto,  # usado só para descobrir cidade e bairro; não vai para o app
            "link": link,
            "anunciante": portal,
            "detalhado": True,
            "financiamento": None,
            "via_email": True,
        }
    return list(anuncios.values())


def coletar() -> List[dict]:
    """Lê os alertas dos últimos dias. Devolve anúncios ainda sem cidade/bairro definidos."""
    caixa = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=60)
    caixa.login(os.environ["GMAIL_USUARIO"], os.environ["GMAIL_SENHA_APP"])
    caixa.select("INBOX", readonly=True)
    desde = (date.today() - timedelta(days=DIAS)).strftime("%d-%b-%Y")
    todos: List[dict] = []
    resumo = {}
    for portal, (remetente, dominios) in PORTAIS.items():
        ok, dados = caixa.search(None, f'(SINCE "{desde}" FROM "{remetente}")')
        ids = dados[0].split() if ok == "OK" and dados and dados[0] else []
        achados = 0
        for num in ids[-60:]:  # os 60 alertas mais recentes de cada portal
            ok, partes = caixa.fetch(num, "(BODY.PEEK[])")  # PEEK: não marca como lido
            if ok != "OK" or not partes or not isinstance(partes[0], tuple):
                continue
            msg = email.message_from_bytes(partes[0][1])
            anuncios = _anuncios_do_html(_html_da_mensagem(msg), portal, dominios)
            assunto = str(make_header(decode_header(msg.get("Subject", ""))))
            for a in anuncios:
                a["assunto_alerta"] = assunto[:120]
            todos.extend(anuncios)
            achados += len(anuncios)
        resumo[portal] = {"emails": len(ids), "anuncios": achados}
    caixa.logout()
    print(f"[Alertas por e-mail] {resumo}", flush=True)
    return todos
