#!/bin/bash
# Stop the alert monitor tmux session

SESSION_NAME="trading_bot"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Arrêt du Trading Bot Monitor ===${NC}"

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}Erreur: tmux n'est pas installé${NC}"
    exit 1
fi

# Check if session exists
if ! tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Le monitor n'est pas en cours d'exécution${NC}"
    echo -e "   Aucune session tmux '$SESSION_NAME' trouvée"
    exit 0
fi

echo -e "${YELLOW}🛑 Arrêt de la session tmux: $SESSION_NAME${NC}"

# Show current status before stopping
echo -e "${BLUE}📊 Statut actuel:${NC}"
./venv/bin/python alert_monitor.py --performance 2>/dev/null || echo "   (Impossible d'afficher le rapport)"

# Send Ctrl+C to gracefully stop the monitor
tmux send-keys -t $SESSION_NAME C-c

# Wait a moment for graceful shutdown
sleep 2

# Kill the tmux session
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    tmux kill-session -t $SESSION_NAME
    echo -e "${GREEN}✅ Session tmux arrêtée${NC}"
else
    echo -e "${GREEN}✅ Monitor déjà arrêté${NC}"
fi

# Also clean up PID file if exists
if [ -f "./data/alert_monitor.pid" ]; then
    rm -f "./data/alert_monitor.pid"
    echo -e "${GREEN}🧹 Fichier PID nettoyé${NC}"
fi

echo ""
echo -e "${GREEN}👋 Monitor arrêté avec succès!${NC}"
echo ""
echo -e "📌 Pour redémarrer: ${YELLOW}./start_monitor.sh${NC}"
