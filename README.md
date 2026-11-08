# Radar Imóveis e Leilões

Coleta automática (3x ao dia, 06:17, 12:17 e 18:17) de imóveis e leilões, com painel web
(app no iPhone), alertas no Telegram e análise de matrícula sob demanda.

- **Site:** https://divalmeida.github.io/radar-imoveis-leiloes/
- **Coleta:** `.github/workflows/coleta-diaria.yml` (roda `coletar_leiloes.py`, `coletar_imoveis.py` e `enviar_alertas.py`)
- **Análise de imóvel da Caixa:** `.github/workflows/analise.yml` (botão "Pedir análise" no app)
- **Senhas e tokens:** só nos Secrets do GitHub (TELEGRAM_TOKEN, TELEGRAM_CHAT_VOCE, TELEGRAM_CHAT_LORE)

## Fontes

**Imóveis (compra até R$ 300 mil, 2+ quartos; aluguel até R$ 4 mil como referência):**
Chaves na Mão e QuintoAndar — Salvador, Lauro de Freitas, Camaçari/Abrantes, Linha Verde
(Mata de São João, Entre Rios, Esplanada, Conde, Jandaíra; com casas), Feira de Santana e
Conceição do Jacuípe.

**Leilões:** Receita Federal, Superbid, Caixa (BA), Kwara, Mega Leilões, Freitas, Palácio dos
Leilões, Parque dos Leilões, João Emílio, Leilão Prime, Tudo Leilão, Bolsa de Leilões, Hisa,
Zuk e Frazão (imóveis na BA).

Não coletamos sites que bloqueiam robôs (ZAP, Viva Real, OLX, Imovelweb, Sodré Santoro) nem
contornamos captchas: quando uma fonte bloqueia, o app mostra a última lista boa e a data dela.

## Rodar no próprio computador

```bash
python3 coletar_leiloes.py
python3 coletar_imoveis.py
```
