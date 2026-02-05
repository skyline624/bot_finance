"""Edge routing functions for conditional graph flow."""

from config import get_settings
from graph.state import AgentState

settings = get_settings()


def route_by_mode(state: AgentState) -> str:
    """
    Route to trading mode or chatbot mode based on state.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    if state.get("chat_mode", False):
        return "rag_retriever"
    return "data_collector"


def route_after_technical(state: AgentState) -> str:
    """
    Route after technical analysis - iterate through all tickers.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    tickers = state.get("tickers", [])
    current_index = state.get("current_ticker_index", 0)

    # If all tickers analyzed, move to sentiment analysis
    if current_index >= len(tickers):
        return "sentiment_analyzer"

    # Continue with next ticker
    return "technical_analyzer"


def route_after_signals(state: AgentState) -> str:
    """
    Route after signal generation - send Discord alerts if strong signals exist.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    signals = state.get("signals", [])

    # Check for strong signals
    has_strong_signals = any(
        s.confiance > settings.CONFIDENCE_THRESHOLD and s.action in ["ACHAT_FORT", "VENTE_FORTE"]
        for s in signals
    )

    if has_strong_signals and settings.DISCORD_WEBHOOK_URL:
        return "discord_alerts"

    return "report_writer"


def route_after_rag_retrieve(state: AgentState) -> str:
    """
    Route after RAG retrieval.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # Always go to generator, it handles empty documents
    return "rag_generator"


def route_error_handler(state: AgentState) -> str:
    """
    Route to handle errors - decide whether to continue or terminate.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    errors = state.get("errors", [])
    critical_errors = [e for e in errors if "data_collection" in e or "macro" in e]

    if len(critical_errors) > 2:
        # Too many critical errors, terminate
        return "report_writer"

    # Continue with available data
    return "macro_analyzer"
