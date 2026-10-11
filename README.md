# Bot de compras no Telegram

## Estrutura

```text
kendrick_bot/
  config.py                 # lê e valida as configurações
  telegram/
    application.py          # monta a aplicação e registra comandos
    handlers.py             # avalia itens e responde às mensagens
  __main__.py               # ponto de entrada do processo
tests/                      # testes unitários, sem chamadas à API do Telegram
```

As dependências seguem separadas por finalidade: `requirements.txt` contém o
necessário para executar o bot; `requirements-dev.txt` adiciona o pytest.

## Avaliar itens

Envie o nome de um item, por exemplo `cotonete`. O bot perguntará se o estoque
atual dura até a próxima compra. Responda `Sim` para não adicionar o item ou
`Não` para incluí-lo. Use `/lista` para consultar os itens considerados
necessários e `/cancelar` para interromper uma avaliação.

Nesta primeira versão, a lista fica somente na memória do processo e é apagada
quando o bot é reiniciado.

## Executar e testar

1. Crie um bot no Telegram conversando com o `@BotFather` e copie o token.
2. Na pasta do projeto, copie `.env.example` para `.env` e coloque o token em
   `TELEGRAM_BOT_TOKEN`.
3. Instale as dependências de desenvolvimento, incluindo as do bot e o pytest:
   `python -m pip install -r requirements-dev.txt`.
4. Rode os testes unitários: `python -m pytest -q`.
5. Inicie o bot: `python -m kendrick_bot`.
6. Abra a conversa com seu bot no Telegram e envie `/start`.

O arquivo `.env` contém um segredo e é ignorado pelo Git. Não compartilhe nem
publique seu token.
