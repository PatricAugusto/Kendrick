# Kendrick

Assistente pessoal de compras no Telegram. Organize sua lista e despensa,
acompanhe o que está acabando e planeje reposições — com confirmações antes de
alterar a lista.

## Comece aqui

### 1. Prepare o bot no Telegram

1. Crie um bot com o [@BotFather](https://t.me/BotFather) e copie o token.
2. Descubra seu ID numérico do Telegram. Somente os IDs configurados poderão
   usar o Kendrick.

### 2. Configure e inicie

No Windows, dê duplo clique em `iniciar-kendrick.bat`. Na primeira execução,
ele prepara o ambiente e cria o arquivo `.env` a partir do exemplo. Preencha
nele o token e seu ID:

```dotenv
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_ALLOWED_USER_IDS=123456789
```

Salve o arquivo e execute `iniciar-kendrick.bat` novamente. Quando o bot
conectar, abra a conversa no Telegram e envie `/start`.

Para autorizar mais pessoas, separe os IDs por vírgula. Não compartilhe o
token: ele permite controlar o bot.

## Use pelo menu

O `/start` abre um menu persistente:

| Botão | O que faz |
|---|---|
| **Lista** | Mostra os itens que você pretende comprar. |
| **Despensa** | Consulta seus itens e quantidades em estoque. |
| **Planejar (7 dias)** | Estima o que pode faltar na próxima semana. |
| **Ajuda** | Mostra atalhos e instruções. |

Você também pode enviar o nome de um item, como `tomates`. O Kendrick pergunta
o estoque atual, o consumo diário e quando será a próxima compra; se houver
falta, propõe a quantidade a adicionar. Responda usando os botões ou escreva
Sim/Não. A lista só muda após sua confirmação.

## Atalhos

Use `/ajuda` no Telegram para consultar as instruções. Os principais comandos
são:

| Comando | Exemplo | Ação |
|---|---|---|
| `/estoque` | `/estoque arroz integral 2,5 kg` | Cadastra ou atualiza o estoque. |
| `/consumo` | `/consumo arroz integral 0,1 kg/dia` | Define o consumo diário de um item da despensa. |
| `/usei` | `/usei arroz integral 0,2` | Registra o consumo e desconta do estoque. |
| `/planejar` | `/planejar 14` | Prevê reposições para até 365 dias. |
| `/comprado` | `/comprado tomates 2` | Registra uma compra e desconta da lista. |
| `/kendrickindica` | `/kendrickindica jantar para 4 pessoas` | Sugere itens para uma ocasião; pede confirmação antes de incluí-los. |
| `/prioridades` | `/prioridades` | Ordena itens pelo tempo estimado até o estoque acabar. |
| `/historico` | `/historico 30` | Exibe até 20 compras registradas no período escolhido. |
| `/remover_despensa` | `/remover_despensa arroz confirmar` | Remove um item da despensa, sem alterar a lista. |
| `/perguntar` | `/perguntar como organizar as compras?` | Responde dúvidas gerais sobre compras. |
| `/cancelar` | `/cancelar` | Interrompe uma análise ou confirmação pendente. |

Use a mesma unidade para o estoque e o consumo, como `kg`. Quantidades decimais
aceitam vírgula ou ponto. Marcar um item como comprado não atualiza a despensa:
use `/estoque` para informar o novo saldo.

## Sugestões com Ollama (opcional)

O Ollama habilita `/kendrickindica` e `/perguntar`; os demais recursos funcionam
sem ele. Instale e inicie o [Ollama](https://ollama.com/) no computador que
executa o Kendrick e baixe um modelo:

```powershell
ollama pull llama3.2
```

Por padrão, o Kendrick usa `http://localhost:11434` e o modelo `llama3.2`.
Para alterar, configure `OLLAMA_BASE_URL` ou `OLLAMA_MODEL` no `.env`.

## Dados e privacidade

- O bot aceita apenas mensagens privadas de usuários listados em
  `TELEGRAM_ALLOWED_USER_IDS`.
- A lista, a despensa e o histórico são guardados localmente em
  `kendrick.sqlite3`, separados por usuário.
- Análises e confirmações pendentes ficam na memória e são perdidas quando o
  processo é reiniciado.
- O arquivo `.env` contém o token e não deve ser compartilhado. Ele é ignorado
  pelo Git.

## Testes e execução pelo terminal

Com o Python 3.10 ou superior instalado, abra o PowerShell na pasta do projeto.
O atalho é a forma mais simples de iniciar; se preferir, use:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m kendrick_bot
```

`requirements.txt` contém as dependências para executar o bot; `requirements-dev.txt`
inclui também as ferramentas de teste.
