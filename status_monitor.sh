#!/bin/bash
# Check status of the alert monitor

SESSION_NAME="trading_bot"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Statut du Trading Bot Monitor ===${NC}"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}❌ tmux n'est pas installé${NC}"
    exit 1
fi

# Check if session exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${GREEN}✅ Monitor ACTIF${NC}"
    echo ""

    # Get session info
    echo -e "📊 ${BLUE}Informations:${NC}"
    echo -e "   • Session tmux: ${YELLOW}$SESSION_NAME${NC}"

    # Get list of windows
    windows=$(tmux list-windows -t $SESSION_NAME -F "#W" 2>/dev/null)
    echo -e "   • Fenêtres: ${YELLOW}$windows${NC}"

    # Check PID file
    if [ -f "./data/alert_monitor.pid" ]; then
        pid=$(cat "./data/alert_monitor.pid")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "   • Processus: ${YELLOW}PID $pid (actif)${NC}"
        else
            echo -e "   • Processus: ${YELLOW}PID $pid (inactif)${NC}"
        fi
    fi

    echo ""
    echo -e "📈 ${BLUE}Performance (7 jours):${NC}"
    ./venv/bin/python alert_monitor.py --performance 2>/dev/null | grep -A 20 "PERFORMANCE TRACKER" || echo "   Aucune donnée disponible"

    echo ""
    echo -e "📌 ${BLUE}Commandes disponibles:${NC}"
    echo -e "   • Voir le monitor:    ${YELLOW}tmux attach -t $SESSION_NAME${NC}"
    echo -e "   • Arrêter:            ${YELLOW}./stop_monitor.sh${NC}"
    echo -e "   • Redémarrer:         ${YELLOW}./start_monitor.sh${NC}"

else
    echo -e "${RED}❌ Monitor INACTIF${NC}"
    echo ""
    echo -e "📌 ${YELLOW}Pour démarrer:${NC} ./start_monitor.sh"

    # Show last performance anyway
    if [ -f "./data/signal_performance.json" ]; then
        echo ""
        echo -e "📈 ${BLUE}Dernière performance enregistrée:${NC}"
        ./venv/bin/python alert_monitor.py --performance 2>/dev/null | grep -A 10 "Résumé global" || echo "   Aucune donnée"
    fi
fi

echo ""
