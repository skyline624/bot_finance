"""Node functions for the LangGraph workflow."""

from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage

from config import get_settings
from graph.state import AgentState
from agents import (
    fetch_market_data,
    fetch_news,
    fetch_macro_data,
    analyze_technicals,
    analyze_sentiment,
    generate_trading_signals,
    send_discord_alert,
    send_summary_to_discord,
    add_market_context_to_vectorstore,
    chat_with_rag,
)

settings = get_settings()


def node_data_collection(state: AgentState) -> AgentState:
    """
    Collect market data and news for all tickers.

    Args:
        state: Current workflow state

    Returns:
        Updated state with collected data
    """
    print("\n📊 [NODE] Collecte des données marché et news...")

    tickers = state["tickers"]
    market_data = {}
    news_data = {}
    errors = list(state.get("errors", []))
    steps = list(state.get("steps", []))
    steps.append(f"data_collection: {len(tickers)} tickers")

    for ticker in tickers:
        # Fetch market data
        data = fetch_market_data(ticker)
        if "error" in data:
            errors.append(f"{ticker}: {data['error']}")
        market_data[ticker] = data

        # Fetch news
        news = fetch_news(ticker)
        news_data[ticker] = news

    return {
        **state,
        "market_data": market_data,
        "news_data": news_data,
        "errors": errors,
        "steps": steps,
    }


def node_macro_analysis(state: AgentState) -> AgentState:
    """
    Fetch and analyze macroeconomic data (VIX, US Yields).

    Args:
        state: Current workflow state

    Returns:
        Updated state with macro data
    """
    print("\n📈 [NODE] Analyse du contexte macro-économique...")

    macro_data = fetch_macro_data()
    steps = list(state.get("steps", []))
    steps.append("macro_analysis")

    if "error" in macro_data:
        errors = list(state.get("errors", []))
        errors.append(f"Macro: {macro_data['error']}")
        return {**state, "macro_data": {}, "errors": errors, "steps": steps}

    return {
        **state,
        "macro_data": macro_data,
        "steps": steps,
    }


def node_technical_analysis(state: AgentState) -> AgentState:
    """
    Perform technical analysis for the current ticker.

    Args:
        state: Current workflow state

    Returns:
        Updated state with technical analysis
    """
    tickers = state["tickers"]
    current_index = state.get("current_ticker_index", 0)
    market_data = state.get("market_data", {})
    technical_analysis = dict(state.get("technical_analysis", {}))
    steps = list(state.get("steps", []))

    if current_index >= len(tickers):
        return state

    ticker = tickers[current_index]
    print(f"\n🔍 [NODE] Analyse technique pour {ticker}...")

    data = market_data.get(ticker, {})
    analysis = analyze_technicals(data)
    technical_analysis[ticker] = analysis

    steps.append(f"technical_analysis: {ticker}")

    return {
        **state,
        "technical_analysis": technical_analysis,
        "current_ticker_index": current_index + 1,
        "steps": steps,
    }


def node_sentiment_analysis(state: AgentState) -> AgentState:
    """
    Analyze sentiment for all tickers based on news.

    Args:
        state: Current workflow state

    Returns:
        Updated state with sentiment analysis
    """
    print("\n💭 [NODE] Analyse du sentiment des news...")

    news_data = state.get("news_data", {})
    sentiment_analysis = {}
    steps = list(state.get("steps", []))
    steps.append("sentiment_analysis")

    for ticker, news_list in news_data.items():
        sentiment = analyze_sentiment(news_list, ticker)
        sentiment_analysis[ticker] = sentiment

    return {
        **state,
        "sentiment_analysis": sentiment_analysis,
        "steps": steps,
    }


def node_generate_signals(state: AgentState) -> AgentState:
    """
    Generate trading signals for all tickers.

    Args:
        state: Current workflow state

    Returns:
        Updated state with trading signals
    """
    print("\n🎯 [NODE] Génération des signaux trading...")

    market_data = state.get("market_data", {})
    sentiment_analysis = state.get("sentiment_analysis", {})
    macro_data = state.get("macro_data", {})
    steps = list(state.get("steps", []))
    steps.append("generate_signals")

    signals = []
    for ticker in state["tickers"]:
        market = market_data.get(ticker, {})
        sentiment = sentiment_analysis.get(ticker, {"score": 0.5, "overall_sentiment": "NEUTRE"})

        signal = generate_trading_signals(ticker, market, sentiment, macro_data)
        signals.append(signal)

        print(f"   • {ticker}: {signal.action} (confiance: {signal.confiance:.0%})")

    return {
        **state,
        "signals": signals,
        "steps": steps,
    }


def node_send_alerts(state: AgentState) -> AgentState:
    """
    Send Discord alerts for strong signals.

    Args:
        state: Current workflow state

    Returns:
        Updated state
    """
    print("\n🔔 [NODE] Envoi des alertes Discord...")

    signals = state.get("signals", [])
    steps = list(state.get("steps", []))
    errors = list(state.get("errors", []))

    # Filter strong signals
    strong_signals = [s for s in signals if s.confiance > settings.CONFIDENCE_THRESHOLD]

    if not strong_signals:
        print("   ℹ️ Pas de signaux forts à alerter")
        steps.append("send_alerts: no_strong_signals")
        return {**state, "steps": steps}

    # Send alerts
    if settings.DISCORD_WEBHOOK_URL:
        import asyncio
        from agents.discord_alerts import send_multiple_alerts, send_summary_to_discord

        try:
            # Send individual alerts
            asyncio.run(send_multiple_alerts(strong_signals))
            # Send summary
            asyncio.run(send_summary_to_discord(signals))
            steps.append(f"send_alerts: {len(strong_signals)} sent")
        except Exception as e:
            errors.append(f"Discord: {str(e)}")
            steps.append("send_alerts: error")
    else:
        print("   ⚠️ Webhook Discord non configuré")
        steps.append("send_alerts: not_configured")

    return {
        **state,
        "errors": errors,
        "steps": steps,
    }


def node_write_report(state: AgentState) -> AgentState:
    """
    Write the final trading report to file.

    Args:
        state: Current workflow state

    Returns:
        Updated state with report written
    """
    print("\n📝 [NODE] Sauvegarde du rapport...")

    signals = state.get("signals", [])
    macro_data = state.get("macro_data", {})
    technical_analysis = state.get("technical_analysis", {})
    sentiment_analysis = state.get("sentiment_analysis", {})
    steps = list(state.get("steps", []))
    errors = list(state.get("errors", []))

    # Build report content
    report_lines = [
        "# 📊 Rapport Trading - Métaux Précieux",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 📈 Contexte Macro-Économique",
        "",
    ]

    if macro_data and "error" not in macro_data:
        report_lines.extend([
            f"- **VIX (Indice de Peur):** {macro_data.get('vix', 'N/A')} - {macro_data.get('vix_sentiment', 'N/A')}",
            f"- **US 10Y Yield:** {macro_data.get('us_10y_yield', 'N/A')}% - {macro_data.get('yield_sentiment', 'N/A')}",
            "",
        ])
    else:
        report_lines.append("*Données macro indisponibles*\n")

    report_lines.extend([
        "## 🎯 Signaux Trading",
        "",
    ])

    for signal in signals:
        report_lines.extend([
            f"### {signal.ticker}",
            "",
            f"**Action:** {signal.action}",
            f"**Prix d'entrée:** {signal.prix_entree:.2f}",
            f"**Confiance:** {signal.confiance:.0%}",
        ])

        if signal.stop_loss:
            report_lines.append(f"**Stop Loss:** {signal.stop_loss:.2f}")
        if signal.take_profit:
            report_lines.append(f"**Take Profit:** {signal.take_profit:.2f}")

        report_lines.extend([
            "",
            "**Raisonnement:**",
            signal.raisonnement,
            "",
        ])

    report_lines.extend([
        "## 📉 Analyses Techniques",
        "",
    ])

    for ticker, analysis in technical_analysis.items():
        report_lines.extend([
            f"### {ticker}",
            "",
            "```",
            analysis,
            "```",
            "",
        ])

    report_lines.extend([
        "## 💭 Analyse Sentiment",
        "",
    ])

    for ticker, sentiment in sentiment_analysis.items():
        report_lines.extend([
            f"### {ticker}",
            "",
            f"- **Sentiment:** {sentiment.get('overall_sentiment', 'N/A')}",
            f"- **Score:** {sentiment.get('score', 0):.2f}",
            f"- **Articles analysés:** {sentiment.get('news_count', 0)}",
            f"- **Résumé:** {sentiment.get('summary', 'N/A')[:200]}...",
            "",
        ])

    # Write report
    filename = "Rapport_Trading_Final.md"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"   ✅ Rapport sauvegardé: {filename}")
        steps.append("write_report: success")
    except Exception as e:
        errors.append(f"Report: {str(e)}")
        steps.append("write_report: error")

    # Also add to RAG vector store for future queries
    try:
        news_data = state.get("news_data", {})
        add_market_context_to_vectorstore(
            state.get("market_data", {}),
            news_data,
            signals,
        )
        steps.append("add_to_rag: success")
    except Exception as e:
        errors.append(f"RAG: {str(e)}")

    return {
        **state,
        "steps": steps,
        "errors": errors,
        "end_time": datetime.now().isoformat(),
    }


def node_rag_retrieve(state: AgentState) -> AgentState:
    """
    Retrieve relevant documents for RAG chatbot.

    Args:
        state: Current workflow state

    Returns:
        Updated state with retrieved documents
    """
    print("\n🔍 [NODE] Récupération documents RAG...")

    question = state.get("question_utilisateur")
    if not question:
        return {**state, "retrieved_documents": []}

    from agents.rag_chatbot import initialize_vectorstore

    try:
        vectorstore = initialize_vectorstore()
        retriever = vectorstore.as_retriever(search_kwargs={"k": settings.TOP_K_RETRIEVAL})
        docs = retriever.invoke(question)

        documents = [doc.page_content for doc in docs]
        print(f"   ✅ {len(documents)} documents récupérés")

        return {
            **state,
            "retrieved_documents": documents,
        }
    except Exception as e:
        print(f"   ⚠️ Erreur RAG: {str(e)}")
        return {**state, "retrieved_documents": []}


def node_rag_generate(state: AgentState) -> AgentState:
    """
    Generate RAG response for chatbot.

    Args:
        state: Current workflow state

    Returns:
        Updated state with generated response
    """
    print("\n🤖 [NODE] Génération réponse RAG...")

    question = state.get("question_utilisateur", "")
    retrieved_docs = state.get("retrieved_documents", [])
    messages = list(state.get("messages", []))

    # Build context
    context = "\n\n".join(retrieved_docs) if retrieved_docs else "Aucun document pertinent trouvé."

    # Build chat history
    chat_history = []
    for msg in messages[-10:]:  # Last 10 messages
        if hasattr(msg, 'type') and hasattr(msg, 'content'):
            role = "user" if msg.type == "human" else "assistant"
            chat_history.append({"role": role, "content": msg.content})

    # Generate response
    response = chat_with_rag(
        question=question,
        market_context=None,  # Could add current market data here
        chat_history=chat_history,
    )

    print(f"   ✅ Réponse générée ({len(response)} caractères)")

    # Add to messages
    messages.append(HumanMessage(content=question))
    messages.append(AIMessage(content=response))

    return {
        **state,
        "rag_response": response,
        "messages": messages,
    }
