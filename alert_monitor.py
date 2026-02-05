#!/usr/bin/env python3
"""
Alert Monitor - Surveillance continue pour alertes Discord automatiques.

Ce script tourne en arrière-plan et surveille les marchés selon la configuration
(.env). Il envoie des alertes Discord uniquement quand de nouveaux signaux forts
sont détectés.

Usage:
    python alert_monitor.py              # Démarrer la surveillance
    python alert_monitor.py --daemon     # Mode daemon (background)
    python alert_monitor.py --status     # Voir le statut
    python alert_monitor.py --stop       # Arrêter la surveillance
"""

import argparse
import sys
import time
import signal
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from pathlib import Path

from config import get_settings
from graph.state import create_initial_state
from graph.builder import build_trading_graph
from agents.signal_performance import get_performance_tracker, PerformanceTracker

# Fichier pour persister l'état entre les redémarrages
STATE_FILE = Path("./data/alert_monitor_state.json")
PID_FILE = Path("./data/alert_monitor.pid")


class AlertMonitor:
    """Alert monitor for continuous market surveillance."""

    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self.last_signals: Dict[str, str] = {}  # ticker -> action
        self.stats = {
            "started_at": None,
            "checks_count": 0,
            "alerts_sent": 0,
            "last_check": None,
        }

        # Initialize performance tracker if enabled
        self.performance_tracker: Optional[PerformanceTracker] = None
        if self.settings.PERFORMANCE_TRACKING_ENABLED:
            self.performance_tracker = get_performance_tracker()

        # Charger l'état précédent si existe
        self._load_state()

    def _load_state(self):
        """Load previous state from file."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.last_signals = state.get('last_signals', {})
                    self.stats = state.get('stats', self.stats)
                print(f"📂 État chargé: {len(self.last_signals)} signaux précédents")
            except Exception as e:
                print(f"⚠️ Erreur chargement état: {e}")

    def _save_state(self):
        """Save current state to file."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, 'w') as f:
                json.dump({
                    'last_signals': self.last_signals,
                    'stats': self.stats,
                    'saved_at': datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde état: {e}")

    def _is_monitoring_time(self) -> bool:
        """Check if current time is within monitoring hours."""
        now = datetime.now()

        # Check day (1=Monday, 7=Sunday)
        if not (self.settings.ALERT_DAYS_START <= now.isoweekday() <= self.settings.ALERT_DAYS_END):
            return False

        # Check hour
        hour = now.hour
        if not (self.settings.ALERT_HOURS_START <= hour < self.settings.ALERT_HOURS_END):
            return False

        return True

    def _is_new_signal(self, ticker: str, action: str) -> bool:
        """Check if this is a new or changed signal."""
        if not self.settings.ALERT_ONLY_NEW_SIGNALS:
            return True  # Alert on all strong signals

        previous_action = self.last_signals.get(ticker)
        if previous_action != action:
            return True  # New or changed signal

        return False  # Same signal as before

    def _update_signals(self, signals: List):
        """Update tracked signals."""
        # Reset signals that are no longer present
        current_tickers = {s.ticker for s in signals}
        self.last_signals = {
            k: v for k, v in self.last_signals.items()
            if k in current_tickers
        }

        # Update with current signals
        for signal in signals:
            self.last_signals[signal.ticker] = signal.action

    def run_analysis(self) -> bool:
        """
        Run trading analysis and send alerts if needed.

        Returns:
            True if alerts were sent, False otherwise
        """
        print(f"\n🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyse en cours...")

        try:
            # Create initial state
            state = create_initial_state(
                tickers=self.settings.DEFAULT_TICKERS.split(',') if isinstance(self.settings.DEFAULT_TICKERS, str) else self.settings.DEFAULT_TICKERS,
                chat_mode=False
            )

            # Build and run graph
            graph = build_trading_graph()
            final_state = graph.invoke(state)

            # Get signals
            signals = final_state.get("signals", [])

            # Filter strong signals
            strong_signals = [
                s for s in signals
                if s.confiance > self.settings.CONFIDENCE_THRESHOLD
                and s.action in ["ACHAT_FORT", "VENTE_FORTE"]
            ]

            # Check for new signals
            new_signals = [
                s for s in strong_signals
                if self._is_new_signal(s.ticker, s.action)
            ]

            # Performance Tracking: Update open signals and check TP/SL
            if self.performance_tracker:
                market_data = final_state.get("market_data", {})
                closed_signals = self.performance_tracker.check_and_close_signals(market_data)
                if closed_signals:
                    print(f"📊 {len(closed_signals)} signal(aux) fermé(s) (TP/SL/Timeout)")
                    for sig in closed_signals:
                        print(f"   • {sig.ticker} {sig.action}: {sig.pnl_percent:+.2f}% ({sig.exit_reason})")

            if new_signals:
                print(f"🚨 {len(new_signals)} nouveau(x) signal(aux) fort(s) détecté(s)!")
                for s in new_signals:
                    print(f"   • {s.ticker}: {s.action} (confiance: {s.confiance:.0%})")

                # Update tracked signals
                self._update_signals(signals)
                self._save_state()

                # Record new signals in performance tracker
                if self.performance_tracker:
                    for s in new_signals:
                        self.performance_tracker.record_signal(
                            ticker=s.ticker,
                            action=s.action,
                            entry_price=s.prix_entree,
                            stop_loss=s.stop_loss,
                            take_profit=s.take_profit,
                            confiance=s.confiance
                        )

                # Alerts are sent automatically by the graph via discord_alerts node
                self.stats["alerts_sent"] += len(new_signals)

                # Print performance summary
                if self.performance_tracker:
                    self.performance_tracker.print_performance_summary(days=7)

                return True
            else:
                if strong_signals:
                    print(f"ℹ️ {len(strong_signals)} signal(aux) fort(s) mais déjà alerté(s)")
                else:
                    print("✅ Pas de signaux forts")

            # Update stats
            self.stats["checks_count"] += 1
            self.stats["last_check"] = datetime.now().isoformat()
            self._save_state()

            return False

        except Exception as e:
            print(f"❌ Erreur analyse: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Main monitoring loop."""
        print("=" * 60)
        print("🔔 ALERT MONITOR - Surveillance Continue")
        print("=" * 60)
        print(f"\nConfiguration:")
        print(f"  • Intervalle: {self.settings.ALERT_INTERVAL_MINUTES} minutes")
        print(f"  • Horaires: {self.settings.ALERT_HOURS_START}h-{self.settings.ALERT_HOURS_END}h")
        print(f"  • Jours: {self.settings.ALERT_DAYS_START}-{self.settings.ALERT_DAYS_END} (1=Lundi)")
        print(f"  • Mode 'Only New': {self.settings.ALERT_ONLY_NEW_SIGNALS}")
        print(f"  • Seuil confiance: {self.settings.CONFIDENCE_THRESHOLD:.0%}")
        print(f"  • Webhook Discord: {'✅ Configuré' if self.settings.DISCORD_WEBHOOK_URL else '❌ Non configuré'}")
        print()

        if not self.settings.DISCORD_WEBHOOK_URL:
            print("⚠️ ATTENTION: Aucun webhook Discord configuré!")
            print("   Les alertes ne seront pas envoyées.")
            print("   Configurez DISCORD_WEBHOOK_URL dans .env\n")

        self.running = True
        self.stats["started_at"] = datetime.now().isoformat()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print("🚀 Démarrage de la surveillance...")
        print("   (Ctrl+C pour arrêter)\n")

        while self.running:
            try:
                if self._is_monitoring_time():
                    self.run_analysis()
                else:
                    now = datetime.now()
                    next_start = now.replace(
                        hour=self.settings.ALERT_HOURS_START,
                        minute=0,
                        second=0
                    )
                    if now.hour >= self.settings.ALERT_HOURS_END:
                        next_start += timedelta(days=1)

                    print(f"⏰ [{now.strftime('%H:%M')}] Hors plage horaire. "
                          f"Prochaine analyse à {next_start.strftime('%H:%M')}")

                # Wait for next interval
                for _ in range(self.settings.ALERT_INTERVAL_MINUTES * 60):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                print(f"❌ Erreur dans la boucle: {e}")
                time.sleep(60)  # Wait 1 minute before retry

        print("\n👋 Surveillance arrêtée.")
        self._save_state()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n🛑 Signal d'arrêt reçu...")
        self.running = False

    def get_status(self) -> dict:
        """Get current monitoring status."""
        return {
            "running": self.running,
            "in_monitoring_hours": self._is_monitoring_time(),
            "stats": self.stats,
            "last_signals": self.last_signals,
            "config": {
                "interval_minutes": self.settings.ALERT_INTERVAL_MINUTES,
                "hours": f"{self.settings.ALERT_HOURS_START}-{self.settings.ALERT_HOURS_END}",
                "days": f"{self.settings.ALERT_DAYS_START}-{self.settings.ALERT_DAYS_END}",
            }
        }


def write_pid():
    """Write PID file."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        print(f"⚠️ Erreur écriture PID: {e}")


def read_pid() -> Optional[int]:
    """Read PID from file."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE, 'r') as f:
                return int(f.read().strip())
        except:
            return None
    return None


def is_running(pid: int) -> bool:
    """Check if process is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Alert Monitor - Surveillance continue des marchés",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python alert_monitor.py              # Démarrer la surveillance
  python alert_monitor.py --status     # Voir le statut
  python alert_monitor.py --test       # Tester une analyse immédiate
        """
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Afficher le statut du monitor"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Exécuter une analyse immédiate (test)"
    )

    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Mode daemon (détacher du terminal)"
    )

    parser.add_argument(
        "--performance",
        action="store_true",
        help="Afficher le rapport de performance des signaux"
    )

    args = parser.parse_args()

    if args.status:
        # Show status
        pid = read_pid()
        if pid and is_running(pid):
            print(f"✅ Monitor actif (PID: {pid})")
        else:
            print("❌ Monitor inactif")

        monitor = AlertMonitor()
        status = monitor.get_status()
        print(f"\n📊 Statistiques:")
        print(f"   Démarré: {status['stats'].get('started_at', 'N/A')}")
        print(f"   Vérifications: {status['stats'].get('checks_count', 0)}")
        print(f"   Alertes envoyées: {status['stats'].get('alerts_sent', 0)}")
        print(f"   Dernier check: {status['stats'].get('last_check', 'N/A')}")
        print(f"\n📈 Signaux suivis: {len(status['last_signals'])}")
        for ticker, action in status['last_signals'].items():
            print(f"   • {ticker}: {action}")
        return

    if args.test:
        # Run single analysis
        print("🧪 Mode TEST - Analyse unique\n")
        monitor = AlertMonitor()
        monitor.run_analysis()
        return

    if args.performance:
        # Show performance report
        print("📊 RAPPORT DE PERFORMANCE\n")
        tracker = get_performance_tracker()
        tracker.print_performance_summary(days=7)
        # Also show 30-day summary if enough data
        metrics_30 = tracker.get_performance_metrics(days=30)
        if metrics_30.total_signals > 0:
            print(f"\n📈 Performance (30 jours):")
            print(f"   • Signaux: {metrics_30.total_signals} | Win Rate: {metrics_30.win_rate:.1%}")
            print(f"   • Return moyen: {metrics_30.avg_return_percent:+.2f}%")
        return

    # Check if already running
    pid = read_pid()
    if pid and is_running(pid):
        print(f"⚠️ Monitor déjà actif (PID: {pid})")
        print("   Arrêtez-le avant de redémarrer.")
        sys.exit(1)

    # Start monitoring
    write_pid()

    if args.daemon:
        # Daemon mode - detach from terminal
        try:
            pid = os.fork()
            if pid > 0:
                print(f"🚀 Monitor démarré en arrière-plan (PID: {pid})")
                sys.exit(0)
        except OSError as e:
            print(f"❌ Erreur daemon: {e}")
            sys.exit(1)

    monitor = AlertMonitor()
    monitor.run()

    # Clean up PID file
    if PID_FILE.exists():
        PID_FILE.unlink()


if __name__ == "__main__":
    main()
