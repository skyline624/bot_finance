"""
Main entry point for the LangGraph trading analysis bot.

Usage:
    python main.py
    python main.py --tickers GC=F,SI=F
    python main.py --mode trading
"""

import argparse
import sys
from typing import List, Optional

from config import get_settings, Settings
from graph.state import create_initial_state
from graph.builder import build_trading_graph, build_unified_graph


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Bot de Trading AI - Analyse des Métaux Précieux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s                           # Analyse par défaut (Or, Argent, Platine, Palladium)
  %(prog)s --tickers GC=F,SI=F       # Analyse uniquement Or et Argent
  %(prog)s --mode trading            # Mode explicite
  %(prog)s --verbose                 # Sortie détaillée
        """
    )

    parser.add_argument(
        "--tickers",
        type=str,
        help="Liste des tickers à analyser, séparés par des virgules (ex: GC=F,SI=F,PL=F)",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["trading", "chatbot"],
        default="trading",
        help="Mode d'exécution (défaut: trading)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Afficher des informations détaillées pendant l'exécution",
    )

    parser.add_argument(
        "--discord-webhook",
        type=str,
        help="URL du webhook Discord pour les alertes (override la config)",
    )

    return parser.parse_args()


def run_trading_analysis(tickers: List[str], verbose: bool = False) -> None:
    """
    Run the trading analysis workflow.

    Args:
        tickers: List of ticker symbols to analyze
        verbose: Whether to print detailed output
    """
    print("🚀 Démarrage du Bot Trading AI (LangGraph)")
    print(f"📊 Tickers à analyser: {', '.join(tickers)}")
    print("=" * 60)

    # Create initial state
    state = create_initial_state(tickers=tickers, chat_mode=False)

    # Build and run graph
    graph = build_trading_graph()

    try:
        # Execute the workflow
        final_state = graph.invoke(state)

        print("\n" + "=" * 60)
        print("✅ Analyse terminée!")

        # Print summary
        signals = final_state.get("signals", [])
        print(f"\n📈 Signaux générés: {len(signals)}")

        for signal in signals:
            emoji = {
                "ACHAT_FORT": "🚀",
                "ACHAT": "📈",
                "NEUTRE": "➖",
                "VENTE": "📉",
                "VENTE_FORTE": "🔻",
            }.get(signal.action, "❓")

            print(f"   {emoji} {signal.ticker}: {signal.action} (confiance: {signal.confiance:.0%})")

        # Print errors if any
        errors = final_state.get("errors", [])
        if errors:
            print(f"\n⚠️ Erreurs ({len(errors)}):")
            for error in errors:
                print(f"   • {error}")

        # Print steps executed
        if verbose:
            steps = final_state.get("steps", [])
            print(f"\n📝 Étapes exécutées ({len(steps)}):")
            for step in steps:
                print(f"   • {step}")

        print(f"\n📄 Rapport sauvegardé dans: Rapport_Trading_Final.md")

    except Exception as e:
        print(f"\n❌ Erreur lors de l'exécution: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    # Load settings
    settings = get_settings()

    # Override Discord webhook if provided
    if args.discord_webhook:
        settings.DISCORD_WEBHOOK_URL = args.discord_webhook

    # Parse tickers
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        tickers = settings.DEFAULT_TICKERS.split(',') if isinstance(settings.DEFAULT_TICKERS, str) else settings.DEFAULT_TICKERS

    # Run based on mode
    if args.mode == "trading":
        run_trading_analysis(tickers, verbose=args.verbose)
    elif args.mode == "chatbot":
        print("Mode chatbot - Utilisez cli_chatbot.py pour l'interface interactive")
        sys.exit(1)
    else:
        print(f"Mode inconnu: {args.mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
