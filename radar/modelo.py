"""Formato único de um lote de leilão, igual para todas as fontes."""

from dataclasses import asdict, dataclass, field
from typing import List, Optional

from radar.config import UFS_DESTAQUE

PUBLICO_PF_PJ = "PF e PJ"
PUBLICO_SO_PJ = "Só PJ (CNPJ)"


@dataclass
class Lote:
    fonte: str
    id: str
    titulo: str
    categoria: str
    lance_atual: Optional[float]
    encerramento: Optional[str]  # "AAAA-MM-DD HH:MM", horário de Brasília
    cidade: str
    uf: str
    publico: str  # PUBLICO_PF_PJ ou PUBLICO_SO_PJ
    link: str
    valor_avaliacao: Optional[float] = None
    imagem: Optional[str] = None
    observacoes: List[str] = field(default_factory=list)

    @property
    def destaque(self) -> bool:
        return self.uf in UFS_DESTAQUE

    def para_dict(self) -> dict:
        dados = asdict(self)
        dados["destaque"] = self.destaque
        return dados
