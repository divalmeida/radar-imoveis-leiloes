"""Descobre o estado (UF) de uma cidade pela lista oficial de municípios do IBGE.

A lista fica guardada em radar/dados/municipios.json porque o site do IBGE
não responde bem para os servidores do GitHub (que ficam fora do Brasil).
"""

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Set

ARQUIVO_MUNICIPIOS = Path(__file__).parent / "dados" / "municipios.json"


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
    for nome, ufs in json.loads(ARQUIVO_MUNICIPIOS.read_text(encoding="utf-8")).items():
        mapa.setdefault(_chave(nome), set()).update(ufs)
    return mapa


def uf_da_cidade(cidade: str, preferida: str = "") -> str:
    """Devolve a UF da cidade. Se o nome existir em mais de um estado,
    usa a UF `preferida` quando ela for uma das opções; senão, vazio."""
    ufs = _ufs_por_cidade().get(_chave(cidade), set())
    if len(ufs) == 1:
        return next(iter(ufs))
    return preferida if preferida in ufs else ""
