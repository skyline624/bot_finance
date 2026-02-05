#!/bin/bash
# Start the alert monitor in a tmux session

SESSION_NAME="trading_bot"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Démarrage du Trading Bot Monitor ===${NC}"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}Erreur: tmux n'est pas installé${NC}"
    echo "Installez-le avec: sudo apt-get install tmux"
    exit 1
fi

# Check if session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Le monitor est déjà en cours d'exécution${NC}"
    echo -e "   Session tmux: ${SESSION_NAME}"
    echo -e "   Pour voir: tmux attach -t $SESSION_NAME"
    echo -e "   Pour arrêter: ./stop_monitor.sh"
    exit 1
fi

# Create tmux session and run monitor
echo -e "${GREEN}📊 Lancement du monitor dans tmux...${NC}"
cd "$SCRIPT_DIR"

# Create new detached session
tmux new-session -d -s $SESSION_NAME -n "monitor"

# Send commands to the session
tmux send-keys -t $SESSION_NAME "cd $SCRIPT_DIR" C-m
tmux send-keys -t $SESSION_NAME "./venv/bin/python alert_monitor.py" C-m

# Create a second window for performance logs
tmux new-window -t $SESSION_NAME -n "logs"
tmux send-keys -t $SESSION_NAME:logs "cd $SCRIPT_DIR" C-m
tmux send-keys -t $SESSION_NAME:logs "echo 'Utilisez Ctrl+b puis w pour basculer entre les fenêtres'" C-m

# Go back to first window
tmux select-window -t $SESSION_NAME:0

echo -e "${GREEN}✅ Monitor démarré avec succès!${NC}"
echo ""
echo -e "📌 Commandes utiles:"
echo -e "   • Voir le monitor:    ${YELLOW}tmux attach -t $SESSION_NAME${NC}"
echo -e "   • Arrêter:            ${YELLOW}./stop_monitor.sh${NC}"
echo -e "   • Voir les logs:      ${YELLOW}tmux attach -t $SESSION_NAME:logs${NC}"
echo -e "   • Voir rapport:       ${YELLOW}./venv/bin/python alert_monitor.py --performance${NC}"
echo ""
echo -e "📝 Dans tmux:"
echo -e "   • ${YELLOW}Ctrl+b puis d${NC}  = détacher (laisser tourner en arrière-plan)"
echo -e "   • ${YELLOW}Ctrl+b puis w${NC}  = changer de fenêtre"
echo -e "   • ${YELLOW}Ctrl+b puis c${NC}  = nouvelle fenêtre"
echo -e "   • ${YELLOW}Ctrl+b puis [${NC}  = mode scroll (flèches pour naviguer, q pour quitter)"
echo ""

# Optionally attach immediately
read -p "Voulez-vous voir le monitor maintenant? (o/n): " response
if [[ "$response" =~ ^[Oo]$ ]]; then
    tmux attach -t $SESSION_NAME
fi
