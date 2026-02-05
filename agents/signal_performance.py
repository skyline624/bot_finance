"""Signal performance tracking system.

This module tracks the performance of trading signals over time,
calculating P&L, win rates, and other metrics.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from config import get_settings

settings = get_settings()


class SignalPerformance(BaseModel):
    """Performance tracking for a single trading signal."""
    signal_id: str
    ticker: str
    action: str  # "ACHAT", "VENTE", "ACHAT_FORT", "VENTE_FORT", "NEUTRE"
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp_entry: str  # ISO format
    timestamp_exit: Optional[str] = None
    status: str = "OPEN"  # "OPEN", "CLOSED_WIN", "CLOSED_LOSS", "CLOSED_NEUTRAL"
    pnl_percent: Optional[float] = None
    holding_period_minutes: Optional[int] = None
    confiance_at_entry: float
    exit_reason: Optional[str] = None  # "TP", "SL", "TIMEOUT", "REVERSAL", "MANUAL"


class PerformanceMetrics(BaseModel):
    """Aggregated performance metrics."""
    total_signals: int = 0
    win_count: int = 0
    loss_count: int = 0
    neutral_count: int = 0
    open_count: int = 0
    win_rate: float = 0.0
    avg_return_percent: float = 0.0
    avg_holding_time_minutes: int = 0
    best_trade: Optional[Dict[str, Any]] = None
    worst_trade: Optional[Dict[str, Any]] = None
    by_action: Dict[str, Dict[str, Any]] = {}
    last_updated: Optional[str] = None


class PerformanceTracker:
    """Tracker for signal performance."""

    def __init__(self, data_file: Optional[str] = None):
        self.data_file = Path(data_file or settings.PERFORMANCE_DATA_FILE)
        self.signals: List[SignalPerformance] = []
        self._load_data()

    def _load_data(self) -> None:
        """Load existing performance data from file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.signals = [SignalPerformance(**s) for s in data.get('signals', [])]
                print(f"📂 Performance data loaded: {len(self.signals)} signals")
            except Exception as e:
                print(f"⚠️ Error loading performance data: {e}")
                self.signals = []
        else:
            self.signals = []

    def _save_data(self) -> None:
        """Save performance data to file."""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump({
                    'signals': [s.model_dump() for s in self.signals],
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving performance data: {e}")

    def record_signal(
        self,
        ticker: str,
        action: str,
        entry_price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        confiance: float
    ) -> str:
        """
        Record a new trading signal.

        Returns:
            signal_id: Unique identifier for the signal
        """
        signal_id = str(uuid.uuid4())[:8]  # Short UUID
        signal = SignalPerformance(
            signal_id=signal_id,
            ticker=ticker,
            action=action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp_entry=datetime.now().isoformat(),
            status="OPEN",
            confiance_at_entry=confiance
        )
        self.signals.append(signal)
        self._save_data()
        return signal_id

    def update_signal(self, signal_id: str, current_price: float) -> Optional[SignalPerformance]:
        """
        Update an open signal with current price.

        Returns:
            Updated signal or None if not found
        """
        for signal in self.signals:
            if signal.signal_id == signal_id and signal.status == "OPEN":
                # Calculate P&L
                if signal.action in ["ACHAT", "ACHAT_FORT"]:
                    signal.pnl_percent = ((current_price - signal.entry_price) / signal.entry_price) * 100
                elif signal.action in ["VENTE", "VENTE_FORTE"]:
                    signal.pnl_percent = ((signal.entry_price - current_price) / signal.entry_price) * 100
                else:
                    signal.pnl_percent = 0.0

                # Calculate holding time
                entry_time = datetime.fromisoformat(signal.timestamp_entry)
                current_time = datetime.now()
                signal.holding_period_minutes = int((current_time - entry_time).total_seconds() / 60)

                self._save_data()
                return signal
        return None

    def close_signal(
        self,
        signal_id: str,
        exit_price: float,
        reason: str
    ) -> Optional[SignalPerformance]:
        """
        Close a signal and calculate final P&L.

        Returns:
            Closed signal or None if not found
        """
        for signal in self.signals:
            if signal.signal_id == signal_id and signal.status == "OPEN":
                signal.exit_price = exit_price
                signal.timestamp_exit = datetime.now().isoformat()
                signal.exit_reason = reason

                # Calculate final P&L
                if signal.action in ["ACHAT", "ACHAT_FORT"]:
                    signal.pnl_percent = ((exit_price - signal.entry_price) / signal.entry_price) * 100
                elif signal.action in ["VENTE", "VENTE_FORTE"]:
                    signal.pnl_percent = ((signal.entry_price - exit_price) / signal.entry_price) * 100
                else:
                    signal.pnl_percent = 0.0

                # Determine status
                if signal.pnl_percent > 0.5:
                    signal.status = "CLOSED_WIN"
                elif signal.pnl_percent < -0.5:
                    signal.status = "CLOSED_LOSS"
                else:
                    signal.status = "CLOSED_NEUTRAL"

                # Calculate holding time
                entry_time = datetime.fromisoformat(signal.timestamp_entry)
                exit_time = datetime.fromisoformat(signal.timestamp_exit)
                signal.holding_period_minutes = int((exit_time - entry_time).total_seconds() / 60)

                self._save_data()
                return signal
        return None

    def check_and_close_signals(
        self,
        market_data: Dict[str, Any]
    ) -> List[SignalPerformance]:
        """
        Check all open signals against current market data and close if TP/SL hit.

        Returns:
            List of closed signals
        """
        closed_signals = []

        for signal in self.signals:
            if signal.status != "OPEN":
                continue

            ticker_data = market_data.get(signal.ticker, {})
            if "error" in ticker_data:
                continue

            current_price = ticker_data.get("current_price")
            if not current_price:
                continue

            # Update current P&L
            self.update_signal(signal.signal_id, current_price)

            # Check TP/SL
            should_close = False
            reason = ""

            if signal.action in ["ACHAT", "ACHAT_FORT"]:
                if signal.take_profit and current_price >= signal.take_profit:
                    should_close = True
                    reason = "TP"
                elif signal.stop_loss and current_price <= signal.stop_loss:
                    should_close = True
                    reason = "SL"
            elif signal.action in ["VENTE", "VENTE_FORTE"]:
                if signal.take_profit and current_price <= signal.take_profit:
                    should_close = True
                    reason = "TP"
                elif signal.stop_loss and current_price >= signal.stop_loss:
                    should_close = True
                    reason = "SL"

            # Check timeout
            entry_time = datetime.fromisoformat(signal.timestamp_entry)
            if datetime.now() - entry_time > timedelta(minutes=settings.SIGNAL_HOLDING_TIMEOUT_MINUTES):
                should_close = True
                reason = "TIMEOUT"

            if should_close:
                closed_signal = self.close_signal(signal.signal_id, current_price, reason)
                if closed_signal:
                    closed_signals.append(closed_signal)

        return closed_signals

    def get_open_signals(self) -> List[SignalPerformance]:
        """Get all currently open signals."""
        return [s for s in self.signals if s.status == "OPEN"]

    def get_performance_metrics(
        self,
        days: int = 7,
        ticker: Optional[str] = None
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics for a given period.

        Args:
            days: Number of days to look back
            ticker: Optional ticker filter

        Returns:
            PerformanceMetrics object
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Filter signals
        filtered_signals = [
            s for s in self.signals
            if datetime.fromisoformat(s.timestamp_entry) >= cutoff_date
            and (ticker is None or s.ticker == ticker)
        ]

        metrics = PerformanceMetrics()
        metrics.total_signals = len(filtered_signals)
        metrics.last_updated = datetime.now().isoformat()

        if metrics.total_signals == 0:
            return metrics

        # Count by status
        for signal in filtered_signals:
            if signal.status == "OPEN":
                metrics.open_count += 1
            elif signal.status == "CLOSED_WIN":
                metrics.win_count += 1
            elif signal.status == "CLOSED_LOSS":
                metrics.loss_count += 1
            else:
                metrics.neutral_count += 1

        # Calculate win rate (excluding open signals)
        closed_signals = metrics.win_count + metrics.loss_count + metrics.neutral_count
        if closed_signals > 0:
            metrics.win_rate = metrics.win_count / closed_signals

        # Calculate average return
        closed_with_pnl = [s for s in filtered_signals if s.pnl_percent is not None]
        if closed_with_pnl:
            metrics.avg_return_percent = sum(s.pnl_percent for s in closed_with_pnl) / len(closed_with_pnl)

            # Best and worst trades
            best = max(closed_with_pnl, key=lambda s: s.pnl_percent or 0)
            worst = min(closed_with_pnl, key=lambda s: s.pnl_percent or 0)
            metrics.best_trade = {
                "ticker": best.ticker,
                "action": best.action,
                "pnl_percent": best.pnl_percent,
                "exit_reason": best.exit_reason
            }
            metrics.worst_trade = {
                "ticker": worst.ticker,
                "action": worst.action,
                "pnl_percent": worst.pnl_percent,
                "exit_reason": worst.exit_reason
            }

        # Average holding time
        closed_with_time = [s for s in filtered_signals if s.holding_period_minutes is not None]
        if closed_with_time:
            metrics.avg_holding_time_minutes = int(
                sum(s.holding_period_minutes for s in closed_with_time) / len(closed_with_time)
            )

        # Metrics by action type
        by_action = {}
        for signal in filtered_signals:
            action = signal.action
            if action not in by_action:
                by_action[action] = {"count": 0, "wins": 0, "losses": 0, "avg_pnl": 0.0}
            by_action[action]["count"] += 1
            if signal.status == "CLOSED_WIN":
                by_action[action]["wins"] += 1
            elif signal.status == "CLOSED_LOSS":
                by_action[action]["losses"] += 1
            if signal.pnl_percent is not None:
                by_action[action]["avg_pnl"] += signal.pnl_percent

        # Calculate averages
        for action in by_action:
            count = by_action[action]["count"]
            if count > 0:
                by_action[action]["avg_pnl"] /= count
                closed = by_action[action]["wins"] + by_action[action]["losses"]
                if closed > 0:
                    by_action[action]["win_rate"] = by_action[action]["wins"] / closed

        metrics.by_action = by_action

        return metrics

    def print_performance_summary(self, days: int = 7) -> None:
        """Print a performance summary to console."""
        metrics = self.get_performance_metrics(days=days)

        print("\n" + "=" * 60)
        print(f"📊 PERFORMANCE TRACKER ({days} derniers jours)")
        print("=" * 60)

        print(f"\n📈 Résumé global:")
        print(f"   • Signaux: {metrics.total_signals} (Ouverts: {metrics.open_count})")
        print(f"   • Gagnants: {metrics.win_count} | Perdants: {metrics.loss_count} | Neutres: {metrics.neutral_count}")
        if metrics.win_count + metrics.loss_count > 0:
            print(f"   • Win Rate: {metrics.win_rate:.1%}")
        print(f"   • Return moyen: {metrics.avg_return_percent:+.2f}%")
        print(f"   • Temps moyen: {metrics.avg_holding_time_minutes} min")

        if metrics.best_trade:
            print(f"\n🏆 Meilleur trade:")
            print(f"   • {metrics.best_trade['ticker']} {metrics.best_trade['action']}: {metrics.best_trade['pnl_percent']:+.2f}%")
            print(f"   • Exit: {metrics.best_trade['exit_reason']}")

        if metrics.worst_trade:
            print(f"\n🔻 Pire trade:")
            print(f"   • {metrics.worst_trade['ticker']} {metrics.worst_trade['action']}: {metrics.worst_trade['pnl_percent']:+.2f}%")
            print(f"   • Exit: {metrics.worst_trade['exit_reason']}")

        if metrics.by_action:
            print(f"\n📊 Par type d'action:")
            for action, stats in metrics.by_action.items():
                win_rate = stats.get('win_rate', 0)
                print(f"   • {action}: {stats['count']} sig, Win Rate {win_rate:.0%}, Avg P&L {stats['avg_pnl']:+.2f}%")

        # Show open signals
        open_signals = self.get_open_signals()
        if open_signals:
            print(f"\n🔄 Signaux ouverts ({len(open_signals)}):")
            for sig in open_signals[:5]:  # Show max 5
                pnl_str = f"P&L: {sig.pnl_percent:+.2f}%" if sig.pnl_percent else "En attente..."
                print(f"   • {sig.ticker} {sig.action} @ {sig.entry_price:.2f} | {pnl_str}")
            if len(open_signals) > 5:
                print(f"   ... et {len(open_signals) - 5} autres")

        print("=" * 60)

    def get_signal_history(self, ticker: Optional[str] = None, limit: int = 10) -> List[SignalPerformance]:
        """Get signal history, optionally filtered by ticker."""
        signals = self.signals
        if ticker:
            signals = [s for s in signals if s.ticker == ticker]
        # Sort by entry time descending
        signals.sort(key=lambda s: s.timestamp_entry, reverse=True)
        return signals[:limit]


# Global tracker instance
_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get or create the global performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker
