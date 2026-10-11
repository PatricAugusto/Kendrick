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

Envie o nome de um item, por exemplo `tomates`. O Kendrick perguntará, em
sequência, o estoque atual, o consumo por dia e em quantos dias será a próxima
compra. Use a mesma unidade nas quantidades (por exemplo, unidades ou kg).
Com esses dados, ele estima o consumo até a compra e a quantidade que faltará.
Se houver falta, pede confirmação antes de adicionar essa quantidade à lista.
Use `/lista` para consultar os itens e quantidades, ou `/cancelar` para
interromper uma análise.

As análises e a lista ficam somente na memória do processo e são apagadas quando
o bot é reiniciado.

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
