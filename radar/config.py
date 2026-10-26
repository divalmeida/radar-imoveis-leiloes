"""Configurações gerais do Radar Imóveis e Leilões.

Nada de senha ou token aqui: eles ficam nos Secrets do GitHub.
"""

# Estados que recebem destaque na aba Leilões
UFS_DESTAQUE = ["SP", "RJ", "DF", "SC", "BA"]

# Cidades prioritárias (imóveis da Caixa e anúncios de apartamentos)
CIDADES_PRIORITARIAS = ["SALVADOR", "FEIRA DE SANTANA", "CONCEICAO DO JACUIPE"]

# Estados baixados da lista oficial de imóveis da Caixa
UFS_CAIXA = ["BA"]

# Palavras que indicam lotes de eletrônicos, eletrodomésticos e celulares
CATEGORIAS_INTERESSE = [
    "CELULAR",
    "ELETRÔNICO",
    "ELETRODOMÉSTICO",
    "INFORMÁTICA",
    "NOTEBOOK",
    "VIDEOGAME",
    "APARELHO DE SOM",
    "MÁQUINA FOTOGRÁFICA",
    "FILMADORA",
    "COMPONENTE ELETRÔNICO",
]

# Pausa entre requisições ao mesmo site, em segundos (para não sobrecarregar)
PAUSA_ENTRE_REQUISICOES = 0.3
