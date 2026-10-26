"""Configurações gerais do Radar Imóveis e Leilões.

Nada de senha ou token aqui: eles ficam nos Secrets do GitHub.
"""

# Estados que recebem destaque na aba Leilões
UFS_DESTAQUE = ["SP", "RJ", "DF", "SC", "BA"]

# Cidades prioritárias (imóveis da Caixa e anúncios de apartamentos)
CIDADES_PRIORITARIAS = ["SALVADOR", "FEIRA DE SANTANA", "CONCEICAO DO JACUIPE"]

# Busca diária de apartamentos (aba Imóveis)
# slug = como a cidade aparece no endereço dos portais
CIDADES_IMOVEIS = [
    {"nome": "Salvador", "uf": "BA", "slug": "ba-salvador"},
    {"nome": "Feira de Santana", "uf": "BA", "slug": "ba-feira-de-santana"},
    {"nome": "Conceição do Jacuípe", "uf": "BA", "slug": "ba-conceicao-do-jacuipe"},
]
QUARTOS_MINIMO = 2
PRECO_MAXIMO_COMPRA = 300_000
# Aluguel serve só de referência para estimar o rendimento das compras
PRECO_MAXIMO_ALUGUEL = 4_000
# Abaixo destes valores o anúncio está errado (ex.: aluguel cadastrado como venda)
PRECO_MINIMO_COMPRA = 40_000
PRECO_MINIMO_ALUGUEL = 300
# Quantas páginas de detalhe (financiamento, condomínio) buscar por coleta
DETALHES_POR_COLETA = 250
# Por quantos dias um anúncio aparece como "novo"
DIAS_NOVO = 3

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
