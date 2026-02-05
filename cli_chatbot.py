#!/usr/bin/env python3
"""
Interactive CLI Chatbot for the trading bot with RAG capabilities.

Usage:
    python cli_chatbot.py
    python cli_chatbot.py --interactive

The chatbot can answer questions about:
- Market data and prices
- Technical analysis
- Trading signals
- News sentiment
- General precious metals trading questions
"""

import argparse
import sys
from typing import Optional

from config import get_settings
from graph.state import create_initial_state
from graph.builder import build_chatbot_graph


def print_banner():
    """Print the chatbot banner."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 Bot Trading AI - Assistant Conversationnel RAG          ║
║                                                                ║
║  Posez vos questions sur l'or, l'argent, le platine,           ║
║  le palladium et les analyses de marché.                       ║
║                                                                ║
║  Commandes disponibles:                                        ║
║    /help     - Afficher l'aide                                 ║
║    /context  - Voir le contexte actuel du marché               ║
║    /clear    - Effacer l'historique de conversation            ║
║    /quit     - Quitter le chatbot                              ║
╚═══════════════════════════════════════════════════════════════╝
""")


def print_help():
    """Print help information."""
    print("""
📖 Aide - Assistant Trading AI

COMMANDES:
  /help      - Afficher cette aide
  /context   - Afficher les données marché actuelles (nécessite analyse préalable)
  /clear     - Effacer l'historique de conversation
  /quit      - Quitter le chatbot

EXEMPLES DE QUESTIONS:
  • "Quel est le prix actuel de l'or?"
  • "Analyse technique de l'argent"
  • "Quel est le sentiment du marché sur le platine?"
  • "Devrais-je acheter du palladium maintenant?"
  • "Expliquer les signaux trading d'aujourd'hui"
  • "Quels sont les supports et résistances de l'or?"

CONSEILS:
  - Soyez spécifique dans vos questions
  - Le chatbot utilise les données d'analyse les plus récentes
  - Les réponses sont générées par un LLM local (Ollama)
""")


def run_interactive_chat():
    """Run the interactive chat session."""
    settings = get_settings()

    print_banner()

    # Initialize chat history
    chat_history = []

    # Build the chatbot graph
    graph = build_chatbot_graph()

    while True:
        try:
            # Get user input
            user_input = input("\n👤 Vous: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ["/quit", "/exit", "quit", "exit", "q"]:
                print("\n👋 Au revoir!")
                break

            if user_input.lower() == "/help":
                print_help()
                continue

            if user_input.lower() == "/clear":
                chat_history = []
                print("\n🗑️ Historique effacé.")
                continue

            if user_input.lower() == "/context":
                print("\n📊 Pour voir le contexte marché, exécutez d'abord: python main.py")
                continue

            # Process the question through the RAG graph
            print("\n🤖 Assistant: ", end="", flush=True)

            try:
                # Create state for this question
                state = create_initial_state(
                    chat_mode=True,
                    question=user_input,
                )

                # Add previous messages to state
                from langchain_core.messages import HumanMessage, AIMessage
                messages = []
                for msg in chat_history:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
                state["messages"] = messages

                # Run the graph
                final_state = graph.invoke(state)

                # Get the response
                response = final_state.get("rag_response", "Désolé, je n'ai pas pu générer de réponse.")

                print(response)

                # Update chat history
                chat_history.append({"role": "user", "content": user_input})
                chat_history.append({"role": "assistant", "content": response})

                # Limit history size (~60K tokens max)
                if len(chat_history) > 300:
                    chat_history = chat_history[-300:]

            except Exception as e:
                print(f"\n❌ Erreur: {str(e)}")
                print("Veuillez réessayer ou utiliser /quit pour quitter.")

        except KeyboardInterrupt:
            print("\n\n👋 Au revoir!")
            break
        except EOFError:
            break


def run_single_question(question: str) -> str:
    """
    Run a single question through the chatbot.

    Args:
        question: The user's question

    Returns:
        The chatbot's response
    """
    graph = build_chatbot_graph()

    state = create_initial_state(
        chat_mode=True,
        question=question,
    )

    final_state = graph.invoke(state)
    return final_state.get("rag_response", "Pas de réponse générée.")


def main():
    """Main entry point for CLI chatbot."""
    parser = argparse.ArgumentParser(
        description="Chatbot RAG pour le Bot Trading AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s                           # Mode interactif
  %(prog)s -q "Prix de l'or"         # Question unique
        """
    )

    parser.add_argument(
        "-q", "--question",
        type=str,
        help="Question unique à poser au chatbot",
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Mode interactif (conversation continue)",
    )

    args = parser.parse_args()

    if args.question:
        # Single question mode
        response = run_single_question(args.question)
        print(response)
    else:
        # Interactive mode (default)
        run_interactive_chat()


if __name__ == "__main__":
    main()
