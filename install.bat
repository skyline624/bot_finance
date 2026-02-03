@echo off
title Installation Assistant Finance IA
color 0A

echo ===================================================
echo      INSTALLATION DE L'ENVIRONNEMENT FINANCE IA
echo ===================================================
echo.

:: 1. Vérification de Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Python n'est pas detecte !
    echo Veuillez installer Python depuis python.org et cocher "Add to PATH".
    pause
    exit
)
echo [OK] Python detecte.

:: 2. Création de l'environnement virtuel
if not exist "venv" (
    echo [INFO] Creation de l'environnement virtuel 'venv'...
    python -m venv venv
) else (
    echo [INFO] L'environnement 'venv' existe deja.
)

:: 3. Activation et Installation
echo [INFO] Activation de l'environnement et installation des librairies...
call venv\Scripts\activate

if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo [ATTENTION] Fichier requirements.txt introuvable. Installation manuelle...
    pip install yfinance pandas ta langchain-community duckduckgo-search
)

:: 4. Vérification d'Ollama
echo.
echo [VERIFICATION] Recherche d'Ollama...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [ATTENTION] Ollama n'est pas installe ou pas dans le PATH.
    echo Assurez-vous de l'installer depuis https://ollama.com pour que l'IA fonctionne.
) else (
    echo [OK] Ollama est present.
)

echo.
echo ===================================================
echo      INSTALLATION TERMINEE AVEC SUCCES
echo ===================================================
echo.
echo Pour lancer votre script d'analyse, tapez :
echo venv\Scripts\python.exe analyse_argent_complete.py
echo.
pause