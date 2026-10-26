"""Acesso à internet com novas tentativas e pausa entre chamadas."""

import gzip
import json
import time
import urllib.error
import urllib.request

from radar.config import PAUSA_ENTRE_REQUISICOES

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def baixar(url: str, tentativas: int = 3, timeout: int = 40) -> bytes:
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            pedido = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            )
            with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
                conteudo = resposta.read()
            if conteudo[:2] == b"\x1f\x8b":  # alguns sites mandam compactado sem pedir
                conteudo = gzip.decompress(conteudo)
            time.sleep(PAUSA_ENTRE_REQUISICOES)
            return conteudo
        except (urllib.error.URLError, TimeoutError) as erro:
            ultimo_erro = erro
            time.sleep(2 * tentativa)
    raise RuntimeError(f"Falha ao acessar {url}: {ultimo_erro}")


def baixar_json(url: str):
    return json.loads(baixar(url).decode("utf-8"))
