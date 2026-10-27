"""Configurações gerais do Radar Imóveis e Leilões.

Nada de senha ou token aqui: eles ficam nos Secrets do GitHub.
"""

# Estados que recebem destaque na aba Leilões
UFS_DESTAQUE = ["SP", "RJ", "DF", "SC", "BA"]

# Busca diária de apartamentos (aba Imóveis), agrupada por região no app.
# slug = como a cidade aparece no endereço do Chaves na Mão.
# Abrantes e Nova Abrantes são distritos de Camaçari; a Linha Verde passa por
# Mata de São João (Praia do Forte, Imbassaí), Entre Rios (Porto de Sauípe),
# Esplanada, Conde (Sítio do Conde) e Jandaíra (Mangue Seco).
CIDADES_IMOVEIS = [
    {"nome": "Salvador", "uf": "BA", "slug": "ba-salvador", "regiao": "Salvador"},
    {"nome": "Lauro de Freitas", "uf": "BA", "slug": "ba-lauro-de-freitas", "regiao": "Lauro de Freitas"},
    {"nome": "Camaçari", "uf": "BA", "slug": "ba-camacari", "regiao": "Camaçari e Abrantes"},
    {"nome": "Mata de São João", "uf": "BA", "slug": "ba-mata-de-sao-joao", "regiao": "Linha Verde"},
    {"nome": "Entre Rios", "uf": "BA", "slug": "ba-entre-rios", "regiao": "Linha Verde"},
    {"nome": "Esplanada", "uf": "BA", "slug": "ba-esplanada", "regiao": "Linha Verde"},
    {"nome": "Conde", "uf": "BA", "slug": "ba-conde", "regiao": "Linha Verde"},
    {"nome": "Jandaíra", "uf": "BA", "slug": "ba-jandaira", "regiao": "Linha Verde"},
    {"nome": "Feira de Santana", "uf": "BA", "slug": "ba-feira-de-santana", "regiao": "Feira de Santana"},
    {"nome": "Conceição do Jacuípe", "uf": "BA", "slug": "ba-conceicao-do-jacuipe", "regiao": "Conceição do Jacuípe"},
]

# Cidades prioritárias nos imóveis da Caixa (as mesmas da aba Imóveis)
CIDADES_PRIORITARIAS = [c["nome"].upper() for c in CIDADES_IMOVEIS]
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
