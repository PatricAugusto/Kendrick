# Bot de compras no Telegram

## Estrutura

```text
kendrick_bot/
  config.py                 # lê e valida as configurações
  llm/ollama.py             # consulta um modelo local via Ollama
  shopping/pantry_store.py  # persiste estoque e consumo da despensa
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
Use `/lista` para consultar os itens e quantidades. Quando comprar parte ou
toda a quantidade de um item, use `/comprado <item> <quantidade>` (por exemplo,
`/comprado tomates 2`); nomes com espaços são aceitos, e quantidades decimais
podem usar vírgula. O Kendrick desconta a quantidade comprada e remove o item
quando não houver saldo restante. Não é possível registrar uma quantidade maior
que a da lista. Use `/cancelar` para interromper uma análise.

Ao executar `/start`, o Kendrick envia uma saudação com a lista de comandos
disponíveis e uma instrução para iniciar uma análise. Use `/ajuda` para
consultar novamente os comandos e as instruções de uso. Para dúvidas e
sugestões sobre compras, use `/perguntar <dúvida>`; por exemplo,
`/perguntar como organizar as compras da semana?`. As respostas são geradas por
um modelo local via Ollama. O assistente não consulta nem altera sua lista ou
seu estoque; análises e alterações continuam seguindo o fluxo validado do bot.

## Despensa pessoal

Cadastre ou atualize o estoque atual com `/estoque <item> <quantidade>
<unidade>`, por exemplo `/estoque arroz integral 2,5 kg`. O nome pode ter
espaços e o estoque pode ser zero. Registre o consumo habitual diário com
`/consumo <item> <quantidade> <unidade>/dia`, por exemplo
`/consumo arroz integral 0,1 kg/dia`; primeiro, o item precisa existir na
despensa. A unidade do consumo deve corresponder à unidade do estoque.

Use `/despensa` para consultar os itens, estoque e consumo cadastrado. Use
`/remover_despensa <item> confirmar` para excluir um registro após confirmação;
isso não remove nem altera o item correspondente na lista de compras. Para
trocar a unidade de um item, remova-o da despensa e cadastre-o novamente,
incluindo o consumo habitual.
Esses registros são persistidos no banco local e isolados por usuário do
Telegram. Eles ainda não preenchem automaticamente a análise de estoque nem
alteram a lista de compras.

Instale o Ollama na máquina que executa o bot, inicie o serviço e baixe um
modelo, por exemplo, no PowerShell:

```powershell
ollama pull llama3.2
```

`OLLAMA_BASE_URL` e `OLLAMA_MODEL` são configurações opcionais no `.env`; por
padrão, o Kendrick usa `http://localhost:11434` e `llama3.2`. Se o Ollama
estiver indisponível, os outros comandos do bot continuam funcionando e
`/perguntar` informa que não conseguiu obter resposta.

A análise em andamento fica somente na memória do processo e é apagada quando o
bot é reiniciado. A lista de compras é salva localmente no arquivo
`kendrick.sqlite3`, na pasta do projeto, e continua disponível após reiniciar o
bot. Cada usuário autorizado tem sua própria lista; para removê-la, apague o
arquivo com o bot parado.

## Executar e testar

1. Crie um bot no Telegram conversando com o `@BotFather` e copie o token.
2. Descubra seu ID numérico do Telegram (por exemplo, consultando um bot de
   informações de perfil) e use somente IDs das pessoas que terão acesso.
3. Na pasta do projeto, copie `.env.example` para `.env`, coloque o token em
   `TELEGRAM_BOT_TOKEN` e seu ID em `TELEGRAM_ALLOWED_USER_IDS`. Para mais de
   uma pessoa autorizada, separe os IDs por vírgula.
4. Instale as dependências de desenvolvimento, incluindo as do bot e o pytest:
   `python -m pip install -r requirements-dev.txt`.
5. Rode os testes unitários: `python -m pytest -q`.
6. Inicie o bot: `python -m kendrick_bot`.
7. Abra a conversa com seu bot no Telegram e envie `/start`.

O arquivo `.env` contém um segredo e é ignorado pelo Git. Não compartilhe nem
publique seu token. O bot só aceita mensagens privadas dos IDs autorizados; os
demais usuários não podem acessar comandos, análises ou lista de compras. Sem
uma lista válida em `TELEGRAM_ALLOWED_USER_IDS`, o bot não inicia. O token é
redigido dos logs, e os logs informativos do `httpx` (que incluem a URL da API)
são suprimidos.
