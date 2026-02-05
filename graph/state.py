"""State definitions for the LangGraph workflow."""

from typing import Annotated, Sequence, TypedDict, List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph.message import add_messages


class SignalTrading(BaseModel):
    """Structured trading signal model."""
    ticker: str
    action: str  # "ACHAT", "VENTE", "NEUTRE", "ACHAT_FORT", "VENTE_FORT"
    prix_entree: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confiance: float  # 0-1
    raisonnement: str = ""


class AgentState(TypedDict):
    """
    Shared state for the LangGraph workflow.

    This state is passed between all nodes in the graph and maintains
    the context throughout the analysis pipeline.
    """
    # Messages (conversation history)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Data collected
    market_data: Dict[str, Any]  # {ticker: {prix, rsi, sma, pivots...}}
    news_data: Dict[str, List[Dict[str, Any]]]  # {ticker: [articles]}
    macro_data: Dict[str, Any]  # VIX, Taux US, etc.

    # Analyses
    technical_analysis: Dict[str, str]  # {ticker: analysis_text}
    sentiment_analysis: Dict[str, Dict[str, Any]]  # {ticker: sentiment_dict}

    # Generated signals
    signals: List[SignalTrading]

    # RAG context
    retrieved_documents: List[str]
    rag_response: Optional[str]

    # Configuration and control
    tickers: List[str]
    current_ticker_index: int  # For iterating over tickers
    chat_mode: bool  # True = RAG chatbot mode, False = trading analysis mode
    question_utilisateur: Optional[str]  # For chatbot mode

    # Metadata
    errors: List[str]
    steps: List[str]  # Traceability of executed steps
    start_time: Optional[str]
    end_time: Optional[str]


def create_initial_state(
    tickers: Optional[List[str]] = None,
    chat_mode: bool = False,
    question: Optional[str] = None,
) -> AgentState:
    """
    Create an initial state for the workflow.

    Args:
        tickers: List of tickers to analyze (ignored in chat mode)
        chat_mode: Whether to run in chatbot mode
        question: User question for chatbot mode

    Returns:
        Initial AgentState
    """
    from config import get_settings
    settings = get_settings()

    return AgentState(
        messages=[],
        market_data={},
        news_data={},
        macro_data={},
        technical_analysis={},
        sentiment_analysis={},
        signals=[],
        retrieved_documents=[],
        rag_response=None,
        tickers=tickers or (settings.DEFAULT_TICKERS.split(',') if isinstance(settings.DEFAULT_TICKERS, str) else settings.DEFAULT_TICKERS),
        current_ticker_index=0,
        chat_mode=chat_mode,
        question_utilisateur=question,
        errors=[],
        steps=[],
        start_time=datetime.now().isoformat(),
        end_time=None,
    )
