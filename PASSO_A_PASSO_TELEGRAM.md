# Passo a passo: alertas do Radar no Telegram

São 4 partes. Faça na ordem. Leva uns 15 minutos.
Nunca mande o token do robô em nenhum chat: ele vai só para o GitHub.

---

## Parte 1 — Criar o robô (no Telegram, celular ou computador)

1. No Telegram, toque na lupa e procure: `@BotFather`
   (é o perfil oficial, com selo azul de verificado). Abra e toque em **Iniciar**.
2. Envie esta mensagem:
   ```
   /newbot
   ```
3. Ele pede o **nome** do robô. Envie:
   ```
   Radar Imóveis e Leilões
   ```
4. Ele pede o **nome de usuário** (precisa terminar em "bot"). Envie:
   ```
   radar_divalmeida_bot
   ```
   Se disser que já existe, envie:
   ```
   radar_diva_lore_bot
   ```
5. Ele responde com uma mensagem que contém o **token** (algo como `123456789:ABCdef...`).
   Toque no token para copiar. **Guarde para a Parte 2.**

> Já criou o robô antes e perdeu o token? No @BotFather envie `/mybots`,
> escolha o robô, toque em **API Token** e copie.

---

## Parte 2 — Guardar o token no GitHub (no computador)

1. Abra:
   ```
   https://github.com/divalmeida/radar-imoveis-leiloes/settings/secrets/actions
   ```
2. Se já existir **TELEGRAM_TOKEN** na lista: clique no lápis ao lado dele, cole o token e clique **Update secret**.
   Se não existir: clique no botão verde **New repository secret**.
   - Em **Name**, digite:
     ```
     TELEGRAM_TOKEN
     ```
   - Em **Secret**, cole o token.
   - Clique **Add secret**.

---

## Parte 3 — Descobrir o número da sua conversa e da Lore

1. **Você e a Lore**, cada uma no seu celular: no Telegram, procurem o robô pelo nome de usuário
   (ex.: `@radar_divalmeida_bot`), abram, toquem **Iniciar** e mandem:
   ```
   oi
   ```
2. **No computador**, abra no navegador o endereço abaixo, **trocando SEU_TOKEN pelo token** da Parte 1
   (sem espaços, mantendo a palavra `bot` colada antes do token):
   ```
   https://api.telegram.org/botSEU_TOKEN/getUpdates
   ```
   Exemplo de como fica: `https://api.telegram.org/bot123456789:ABCdef.../getUpdates`
3. Vai aparecer um texto técnico. Procure trechos assim:
   - `"chat":{"id":123456789,"first_name":"Diva"` → o número **123456789** é o seu
   - `"chat":{"id":987654321,"first_name":"Lore"` → o número **987654321** é o da Lore

   Se aparecer só `{"ok":true,"result":[]}`, alguém ainda não mandou o "oi". Mande e recarregue a página.

---

## Parte 4 — Guardar os dois números no GitHub

1. Abra de novo:
   ```
   https://github.com/divalmeida/radar-imoveis-leiloes/settings/secrets/actions/new
   ```
   - **Name**:
     ```
     TELEGRAM_CHAT_VOCE
     ```
   - **Secret**: o **seu** número. Clique **Add secret**.
2. Abra de novo o mesmo endereço:
   - **Name**:
     ```
     TELEGRAM_CHAT_LORE
     ```
   - **Secret**: o número **da Lore**. Clique **Add secret**.
3. Confira: na lista de Secrets devem aparecer os três —
   `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_VOCE` e `TELEGRAM_CHAT_LORE`.

---

## Teste final

1. Abra:
   ```
   https://github.com/divalmeida/radar-imoveis-leiloes/actions/workflows/coleta-diaria.yml
   ```
2. Clique **Run workflow** e depois no botão verde **Run workflow**.
3. Espere de 20 a 25 minutos. Devem chegar:
   - para você: **🏠 Radar Imóveis** e **🔨 Radar Leilões**
   - para a Lore: **🏠 Radar Imóveis**

**Não chegou?** Confira: (a) o token foi colado inteiro; (b) os números são os da Parte 3;
(c) as duas tocaram em **Iniciar** no robô. Se continuar, avise a Claude com um print da execução.

## Depois de pronto

- 06:17 — resumo do dia (sempre chega)
- 12:17 e 18:17 — só se houver novidade (imóvel novo, preço que subiu/baixou, imóvel novo da Caixa)
- Você recebe imóveis e leilões; a Lore recebe imóveis.
