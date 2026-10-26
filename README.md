# Radar Imóveis e Leilões

Coleta automática diária de leilões e anúncios de imóveis, com painel web e alertas no Telegram.

- **Coleta:** roda sozinha todo dia às 07:00 (horário de Brasília) pelo GitHub Actions (`.github/workflows/coleta-diaria.yml`).
- **Dados:** ficam em `docs/dados/` (o painel lê dali).
- **Senhas e tokens:** nunca no código, só nos Secrets do GitHub.

## Fontes de leilão já ativas

- Receita Federal (Sistema de Leilão Eletrônico)

## Rodar no próprio computador

```bash
python3 coletar_leiloes.py
```
