"""Estimativa de aluguel de um imóvel à venda, a partir dos aluguéis coletados.

Sempre devolve um valor, indo do mais preciso ao mais geral:
  1. mesmo bairro, mesmos quartos e área parecida (±30%)
  2. mesmo bairro, valor do m² (mesmos quartos; depois qualquer quarto)
  3. mesma cidade, valor do m² (mesmos quartos; depois qualquer quarto)
  4. mesma região, valor do m²
  5. todos os aluguéis coletados, valor do m²
Sem área no anúncio, usa a mediana do aluguel em vez do valor do m².
O painel (docs/index.html) repete esta mesma regra para os imóveis da Caixa.
"""

import statistics
from typing import Dict, List, Optional

from radar.localidades import chave_texto

MIN_COMPARAVEIS = 3


class Referencia:
    def __init__(self, alugueis: List[dict], regiao_da_cidade: Dict[str, str]):
        self.regiao_da_cidade = {chave_texto(c): r for c, r in regiao_da_cidade.items()}
        self.por_bairro: Dict[str, list] = {}
        self.por_cidade: Dict[str, list] = {}
        self.por_regiao: Dict[str, list] = {}
        self.todos = [a for a in alugueis if a.get("preco")]
        for a in self.todos:
            cidade = chave_texto(a.get("cidade") or "")
            self.por_cidade.setdefault(cidade, []).append(a)
            self.por_regiao.setdefault(self.regiao_da_cidade.get(cidade, cidade), []).append(a)
            if a.get("bairro"):
                self.por_bairro.setdefault(f"{cidade}|{chave_texto(a['bairro'])}", []).append(a)

    @staticmethod
    def _por_m2(lista, area, quartos, minimo):
        comps = [a for a in lista if (a.get("area") or 0) >= 25 and (not quartos or a.get("quartos") == quartos)]
        if len(comps) < minimo or area > max(a["area"] for a in comps) * 1.3:
            return None
        valor = statistics.median(a["preco"] / a["area"] for a in comps) * area
        return min(valor, max(a["preco"] for a in comps)), len(comps)

    @staticmethod
    def _mediana(lista, quartos, minimo):
        comps = [a for a in lista if not quartos or a.get("quartos") == quartos]
        if len(comps) < minimo:
            return None
        return statistics.median(a["preco"] for a in comps), len(comps)

    def estimar(self, cidade: str, bairro: Optional[str], area: Optional[float], quartos: Optional[int]) -> Optional[dict]:
        c = chave_texto(cidade or "")
        do_bairro = self.por_bairro.get(f"{c}|{chave_texto(bairro or '')}", [])
        da_cidade = self.por_cidade.get(c, [])
        da_regiao = self.por_regiao.get(self.regiao_da_cidade.get(c, c), [])
        area = area if area and area >= 20 else None

        tentativas = []
        if area:
            parecidos = [a for a in do_bairro if (not quartos or a.get("quartos") == quartos)
                         and a.get("area") and area * 0.7 <= a["area"] <= area * 1.3]
            if len(parecidos) >= MIN_COMPARAVEIS:
                return self._resultado(statistics.median(a["preco"] for a in parecidos), len(parecidos),
                                       "bairro", "mesmo bairro, mesmos quartos e área parecida")
            tentativas = [
                (do_bairro, quartos, MIN_COMPARAVEIS, "bairro", "mesmo bairro, pelo valor do m²"),
                (do_bairro, None, MIN_COMPARAVEIS, "bairro", "mesmo bairro, pelo valor do m²"),
                (da_cidade, quartos, 5, "cidade", "mesma cidade, pelo valor do m²"),
                (da_cidade, None, 5, "cidade", "mesma cidade, pelo valor do m²"),
                (da_regiao, None, 5, "regiao", "mesma região, pelo valor do m²"),
                (self.todos, None, 5, "geral", "média geral (poucos aluguéis na região)"),
            ]
            for lista, q, minimo, nivel, texto in tentativas:
                achado = self._por_m2(lista, area, q, minimo)
                if achado:
                    return self._resultado(achado[0], achado[1], nivel, texto)
        for lista, q, minimo, nivel, texto in [
            (do_bairro, quartos, MIN_COMPARAVEIS, "bairro", "mesmo bairro e quartos (anúncio sem área)"),
            (da_cidade, quartos, 5, "cidade", "mesma cidade e quartos (anúncio sem área)"),
            (da_regiao, quartos, 5, "regiao", "mesma região e quartos (anúncio sem área)"),
            (self.todos, quartos, 5, "geral", "média geral (anúncio sem área)"),
            (self.todos, None, 1, "geral", "média geral (anúncio sem área)"),
        ]:
            achado = self._mediana(lista, q, minimo)
            if achado:
                return self._resultado(achado[0], achado[1], nivel, texto)
        return None

    @staticmethod
    def _resultado(valor, n, nivel, texto):
        return {"valor": round(valor / 50) * 50, "amostras": n, "nivel": nivel, "base": texto}
