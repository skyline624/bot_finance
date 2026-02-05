#!/bin/bash

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== INSTALLATION DE L'ENVIRONNEMENT FINANCE IA ===${NC}"

# 1. Vérification de Python
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}[ERREUR] Python3 n'est pas installé.${NC}"
    exit 1
fi
echo "[OK] Python3 détecté."

# 2. Création de l'environnement virtuel
if [ ! -d "venv" ]; then
    echo "Création de l'environnement virtuel 'venv'..."
    python3 -m venv venv
else
    echo "L'environnement 'venv' existe déjà."
fi

# 3. Activation et Installation
echo "Installation des dépendances..."
source venv/bin/activate

# Utiliser le nouveau requirements pour l'architecture LangGraph
if [ -f "updated_requirements.txt" ]; then
    echo "Installation des dépendances LangGraph..."
    pip install -r updated_requirements.txt
elif [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Fichier requirements.txt manquant, installation manuelle..."
    pip install yfinance pandas ta langchain langchain-community langgraph
fi

# 4. Vérification d'Ollama
if ! command -v ollama &> /dev/null
then
    echo -e "${RED}[ATTENTION] Ollama n'est pas détecté.${NC}"
    echo "Pensez à l'installer via : curl -fsSL https://ollama.com/install.sh"
else
    echo -e "${GREEN}[OK] Ollama est présent.${NC}"
    # Vérifie si le modèle est là, sinon le télécharge (optionnel)
    # ollama pull llama3
fi

echo -e "${GREEN}=== INSTALLATION TERMINÉE ===${NC}"
echo ""
echo "Nouvelle architecture LangGraph installée !"
echo ""
echo "Pour lancer l'analyse trading:"
echo "  ./venv/bin/python main.py"
echo ""
echo "Pour lancer le chatbot RAG:"
echo "  ./venv/bin/python cli_chatbot.py"
echo ""
echo "Pour configurer les variables d'environnement:"
echo "  cp .env.example .env"
echo "  # Éditez .env avec vos clés API"