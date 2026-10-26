"""Canais de alerta. Hoje: Telegram. Pronto para incluir WhatsApp depois.

Os tokens e números ficam nos Secrets do GitHub e chegam aqui como
variáveis de ambiente — nunca escritos no código.
"""

import json
import os
import urllib.parse
import urllib.request
from typing import List

LIMITE_TELEGRAM = 4000  # o Telegram aceita até 4096 caracteres por mensagem


def _partes(texto: str, limite: int) -> List[str]:
    """Divide mensagens longas em blocos, quebrando entre parágrafos."""
    partes, atual = [], ""
    for bloco in texto.split("\n\n"):
        if atual and len(atual) + len(bloco) + 2 > limite:
            partes.append(atual)
            atual = ""
        atual = f"{atual}\n\n{bloco}" if atual else bloco
    if atual:
        partes.append(atual)
    return partes


class Telegram:
    nome = "Telegram"

    def __init__(self, token: str):
        self.token = token

    def enviar(self, destino: str, texto: str) -> None:
        for parte in _partes(texto, LIMITE_TELEGRAM):
            dados = urllib.parse.urlencode({
                "chat_id": destino,
                "text": parte,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }).encode()
            pedido = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/sendMessage", data=dados)
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                if not json.loads(resposta.read()).get("ok"):
                    raise RuntimeError("Telegram recusou a mensagem")


# Para incluir o WhatsApp depois: criar uma classe com o mesmo método
# enviar(destino, texto) e ligá-la em canais_configurados().


def canais_configurados():
    """Devolve [(canal, destino, assuntos)] a partir das variáveis de ambiente.

    TELEGRAM_TOKEN      token do robô (criado no @BotFather)
    TELEGRAM_CHAT_VOCE  recebe imóveis e leilões
    TELEGRAM_CHAT_LORE  recebe imóveis
    """
    saida = []
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    if token:
        telegram = Telegram(token)
        voce = os.environ.get("TELEGRAM_CHAT_VOCE", "").strip()
        lore = os.environ.get("TELEGRAM_CHAT_LORE", "").strip()
        if voce:
            saida.append((telegram, voce, {"imoveis", "leiloes"}))
        if lore:
            saida.append((telegram, lore, {"imoveis"}))
    return saida
