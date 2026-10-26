"""Descobre o estado (UF) de uma cidade pela lista oficial de municípios do IBGE."""

import json
import unicodedata
from functools import lru_cache
from typing import Dict, Set

from radar.http import baixar

URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"


def nome_cidade(cidade: str) -> str:
    """'RIO DE JANEIRO' -> 'Rio de Janeiro'."""
    minusculas = {"De", "Do", "Da", "Dos", "Das", "E"}
    return " ".join(p.lower() if p in minusculas else p for p in cidade.strip().title().split())


def _chave(cidade: str) -> str:
    texto = unicodedata.normalize("NFD", cidade).encode("ascii", "ignore").decode()
    return " ".join(texto.upper().replace("'", " ").split())


@lru_cache(maxsize=1)
def _ufs_por_cidade() -> Dict[str, Set[str]]:
    mapa: Dict[str, Set[str]] = {}
    for m in json.loads(baixar(URL_MUNICIPIOS, timeout=60)):
        mapa.setdefault(_chave(m["municipio-nome"]), set()).add(m["UF-sigla"])
    return mapa


def uf_da_cidade(cidade: str, preferida: str = "") -> str:
    """Devolve a UF da cidade. Se o nome existir em mais de um estado,
    usa a UF `preferida` quando ela for uma das opções; senão, vazio."""
    try:
        ufs = _ufs_por_cidade().get(_chave(cidade), set())
    except RuntimeError:
        return ""
    if len(ufs) == 1:
        return next(iter(ufs))
    return preferida if preferida in ufs else ""
