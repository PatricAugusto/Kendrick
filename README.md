# Bot de compras no Telegram

## Etapa 1: primeira conversa

Esta etapa inicia o bot e responde ao comando `/start`. A lista de compras será
implementada nas próximas etapas.

1. Crie um bot no Telegram conversando com o `@BotFather` e copie o token.
2. Na pasta do projeto, copie `.env.example` para `.env` e coloque o token em
   `TELEGRAM_BOT_TOKEN`.
3. Instale as dependências: `python -m pip install -r requirements.txt`.
4. Inicie o bot: `python main.py`.
5. Abra a conversa com seu bot no Telegram e envie `/start`.

O arquivo `.env` contém um segredo e é ignorado pelo Git. Não compartilhe nem
publique seu token.
