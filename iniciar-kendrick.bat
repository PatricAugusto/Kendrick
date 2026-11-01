@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python e tente novamente.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Preparando o ambiente virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente virtual.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import telegram, dotenv" >nul 2>nul
if errorlevel 1 (
    echo Instalando as dependencias do Kendrick...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Nao foi possivel instalar as dependencias.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Arquivo .env criado a partir do exemplo.
    echo Preencha TELEGRAM_BOT_TOKEN e TELEGRAM_ALLOWED_USER_IDS e execute este atalho novamente.
    start "" notepad ".env"
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m kendrick_bot
if errorlevel 1 pause
