"""Graph builder functions for constructing LangGraph workflows."""

from langgraph.graph import StateGraph, START, END

from graph.state import AgentState
from graph.nodes import (
    node_data_collection,
    node_macro_analysis,
    node_technical_analysis,
    node_sentiment_analysis,
    node_generate_signals,
    node_send_alerts,
    node_write_report,
    node_rag_retrieve,
    node_rag_generate,
)
from graph.edges import (
    route_by_mode,
    route_after_technical,
    route_after_signals,
    route_after_rag_retrieve,
)


def build_trading_graph():
    """
    Build the trading analysis graph.

    Flow:
    START -> data_collector -> macro_analyzer -> technical_analyzer (loop)
    -> sentiment_analyzer -> signal_generator -> [discord_alerts] -> report_writer -> END

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("data_collector", node_data_collection)
    workflow.add_node("macro_analyzer", node_macro_analysis)
    workflow.add_node("technical_analyzer", node_technical_analysis)
    workflow.add_node("sentiment_analyzer", node_sentiment_analysis)
    workflow.add_node("signal_generator", node_generate_signals)
    workflow.add_node("discord_alerts", node_send_alerts)
    workflow.add_node("report_writer", node_write_report)

    # Add edges
    workflow.add_edge(START, "data_collector")
    workflow.add_edge("data_collector", "macro_analyzer")
    workflow.add_edge("macro_analyzer", "technical_analyzer")

    # Conditional: iterate through all tickers
    workflow.add_conditional_edges(
        "technical_analyzer",
        route_after_technical,
        {
            "technical_analyzer": "technical_analyzer",
            "sentiment_analyzer": "sentiment_analyzer",
        }
    )

    workflow.add_edge("sentiment_analyzer", "signal_generator")

    # Conditional: send Discord alerts if strong signals
    workflow.add_conditional_edges(
        "signal_generator",
        route_after_signals,
        {
            "discord_alerts": "discord_alerts",
            "report_writer": "report_writer",
        }
    )

    workflow.add_edge("discord_alerts", "report_writer")
    workflow.add_edge("report_writer", END)

    return workflow.compile()


def build_chatbot_graph():
    """
    Build the RAG chatbot graph.

    Flow:
    START -> rag_retriever -> rag_generator -> END

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("rag_retriever", node_rag_retrieve)
    workflow.add_node("rag_generator", node_rag_generate)

    # Add edges
    workflow.add_edge(START, "rag_retriever")
    workflow.add_edge("rag_retriever", "rag_generator")
    workflow.add_edge("rag_generator", END)

    return workflow.compile()


def build_unified_graph():
    """
    Build a unified graph supporting both trading and chatbot modes.

    Flow (Trading):
    START -> [routing] -> data_collector -> ... -> report_writer -> END

    Flow (Chatbot):
    START -> [routing] -> rag_retriever -> rag_generator -> END

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(AgentState)

    # Trading nodes
    workflow.add_node("data_collector", node_data_collection)
    workflow.add_node("macro_analyzer", node_macro_analysis)
    workflow.add_node("technical_analyzer", node_technical_analysis)
    workflow.add_node("sentiment_analyzer", node_sentiment_analysis)
    workflow.add_node("signal_generator", node_generate_signals)
    workflow.add_node("discord_alerts", node_send_alerts)
    workflow.add_node("report_writer", node_write_report)

    # Chatbot nodes
    workflow.add_node("rag_retriever", node_rag_retrieve)
    workflow.add_node("rag_generator", node_rag_generate)

    # Initial routing by mode
    workflow.add_conditional_edges(
        START,
        route_by_mode,
        {
            "data_collector": "data_collector",
            "rag_retriever": "rag_retriever",
        }
    )

    # Trading flow
    workflow.add_edge("data_collector", "macro_analyzer")
    workflow.add_edge("macro_analyzer", "technical_analyzer")

    workflow.add_conditional_edges(
        "technical_analyzer",
        route_after_technical,
        {
            "technical_analyzer": "technical_analyzer",
            "sentiment_analyzer": "sentiment_analyzer",
        }
    )

    workflow.add_edge("sentiment_analyzer", "signal_generator")

    workflow.add_conditional_edges(
        "signal_generator",
        route_after_signals,
        {
            "discord_alerts": "discord_alerts",
            "report_writer": "report_writer",
        }
    )

    workflow.add_edge("discord_alerts", "report_writer")
    workflow.add_edge("report_writer", END)

    # Chatbot flow
    workflow.add_edge("rag_retriever", "rag_generator")
    workflow.add_edge("rag_generator", END)

    return workflow.compile()
