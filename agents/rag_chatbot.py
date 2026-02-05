"""RAG chatbot with vector store integration for market context."""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from agents.data_ingestion import fetch_market_data, fetch_news

settings = get_settings()

# Mapping des noms communs vers les tickers
TICKER_MAPPING = {
    # Français
    "or": "GC=F",
    "argent": "SI=F",
    "platine": "PL=F",
    "palladium": "PA=F",
    "dollar": "DX-Y.NYB",
    "indice dollar": "DX-Y.NYB",
    # Anglais
    "gold": "GC=F",
    "silver": "SI=F",
    "platinum": "PL=F",
    "palladium": "PA=F",
    "dxy": "DX-Y.NYB",
    "dollar index": "DX-Y.NYB",
    # Tickers directs
    "gc=f": "GC=F",
    "si=f": "SI=F",
    "pl=f": "PL=F",
    "pa=f": "PA=F",
    "dx-y.nyb": "DX-Y.NYB",
}


def detect_ticker(question: str) -> Optional[str]:
    """
    Detect ticker from question using keyword mapping.

    Args:
        question: User question

    Returns:
        Ticker symbol if found, None otherwise
    """
    question_lower = question.lower()

    # Check for exact ticker matches first
    for keyword, ticker in TICKER_MAPPING.items():
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, question_lower):
            return ticker

    # Check for ticker patterns like GC=F, SI=F, etc.
    ticker_pattern = r'\b(GC=F|SI=F|PL=F|PA=F|DX-Y\.NYB)\b'
    match = re.search(ticker_pattern, question_upper := question.upper())
    if match:
        return match.group(1)

    return None


def fetch_fresh_market_data(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch real-time market data and news for a specific ticker.
    Enriches the RAG vector store with fresh data.

    Args:
        ticker: The ticker symbol (e.g., 'GC=F')

    Returns:
        Dictionary with fresh market data or None if error
    """
    print(f"   🔄 Fetch temps réel pour {ticker}...")

    try:
        # Fetch real-time market data
        market_data = fetch_market_data(ticker)

        if "error" in market_data:
            print(f"   ⚠️ Erreur fetch marché: {market_data['error']}")
            return None

        # Fetch fresh news
        news_data = fetch_news(ticker)

        # Create fresh data document
        fresh_content = f"""
        DONNÉES TEMPS RÉEL pour {ticker} (récupérées à {market_data['timestamp']}):
        Prix actuel: {market_data['current_price']:.2f}
        RSI: {market_data['rsi']:.2f}
        SMA200: {market_data['sma200']:.2f}
        SMA50: {market_data['sma50']:.2f}
        MACD: {market_data['macd']:.4f}
        Signal MACD: {market_data['macd_signal']:.4f}
        Support S1: {market_data['s1']:.2f}
        Résistance R1: {market_data['r1']:.2f}
        Bollinger Upper: {market_data['bb_upper']:.2f}
        Bollinger Lower: {market_data['bb_lower']:.2f}
        ATR: {market_data['atr']:.2f}

        News fraîches ({len(news_data)} articles):
        """

        for news in news_data[:3]:  # Top 3 news
            fresh_content += f"\n- [{news.get('source', 'Unknown')}] {news.get('title', 'N/A')}"

        # Create document for RAG
        fresh_doc = Document(
            page_content=fresh_content,
            metadata={
                "type": "fresh_data",
                "ticker": ticker,
                "timestamp": market_data['timestamp'],
                "is_fresh": True,
                "price": market_data['current_price'],
                "rsi": market_data['rsi'],
            }
        )

        # Add to vector store
        try:
            vectorstore = initialize_vectorstore([fresh_doc])
            print(f"   ✅ Données fraîches stockées dans RAG")
        except Exception as e:
            print(f"   ⚠️ Erreur stockage RAG: {e}")

        return {
            "ticker": ticker,
            "timestamp": market_data['timestamp'],
            "price": market_data['current_price'],
            "rsi": market_data['rsi'],
            "sma200": market_data['sma200'],
            "sma50": market_data['sma50'],
            "macd": market_data['macd'],
            "macd_signal": market_data['macd_signal'],
            "s1": market_data['s1'],
            "r1": market_data['r1'],
            "news_count": len(news_data),
            "news": news_data[:3],
            "fresh": True,
        }

    except Exception as e:
        print(f"   ❌ Erreur fetch temps réel: {e}")
        return None


def retrieve_documents_hybrid(vectorstore: Chroma, question: str, k: int = 5) -> List[Document]:
    """
    Retrieve documents using hybrid approach:
    1. If ticker detected in question, filter by metadata first
    2. Then apply semantic search on filtered results
    3. If no ticker, use pure semantic search

    Args:
        vectorstore: Chroma vector store instance
        question: User question
        k: Number of documents to retrieve

    Returns:
        List of relevant documents
    """
    ticker = detect_ticker(question)

    if ticker:
        # Ticker detected: filter by metadata first
        print(f"   🔍 Ticker détecté: {ticker}")

        # Get all documents for this ticker using metadata filter
        results = vectorstore.get(where={"ticker": ticker})

        if results and results["ids"]:
            # Reconstruct documents from results
            documents = []
            for i, doc_id in enumerate(results["ids"]):
                if i < len(results["documents"]):
                    doc = Document(
                        page_content=results["documents"][i],
                        metadata=results["metadatas"][i] if i < len(results["metadatas"]) else {}
                    )
                    documents.append(doc)

            # Limit to k documents
            documents = documents[:k]
            print(f"   ✅ {len(documents)} documents trouvés pour {ticker}")
            return documents
        else:
            print(f"   ⚠️ Aucun document pour {ticker}, recherche sémantique...")

    # Fallback: semantic search
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    return retriever.invoke(question)


def get_embeddings():
    """Get Ollama embeddings model."""
    base_url = settings.OLLAMA_BASE_URL.replace("/v1", "")
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=base_url,
    )


def initialize_vectorstore(documents: Optional[List[Document]] = None) -> Chroma:
    """
    Initialize or load the Chroma vector store.

    Args:
        documents: Optional list of documents to add initially

    Returns:
        Chroma vector store instance
    """
    embeddings = get_embeddings()

    if documents:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        splits = text_splitter.split_documents(documents)

        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
    else:
        vectorstore = Chroma(
            embedding_function=embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )

    return vectorstore


def get_existing_news_titles(vectorstore: Chroma, ticker: str) -> set:
    """
    Get existing news titles for a ticker to avoid duplicates.

    Args:
        vectorstore: Chroma vector store instance
        ticker: Ticker symbol

    Returns:
        Set of existing news titles
    """
    try:
        # Get all documents for this ticker (will filter by type manually)
        results = vectorstore.get(where={"ticker": ticker})
        if results and results["documents"]:
            titles = set()
            for i, doc in enumerate(results["documents"]):
                # Only process news documents
                metadata = results["metadatas"][i] if i < len(results["metadatas"]) else {}
                if metadata.get("type") != "news":
                    continue

                # Extract title from document content (format: "News pour X:\nTitre: ...")
                lines = doc.split('\n')
                for line in lines:
                    if line.strip().startswith("Titre:"):
                        title = line.replace("Titre:", "").strip()
                        titles.add(title)
                        break
            return titles
    except Exception as e:
        print(f"   ⚠️ Erreur récupération titres existants: {e}")
    return set()


def add_market_context_to_vectorstore(
    market_data: Dict[str, Any],
    news_data: Dict[str, List[Dict[str, Any]]],
    signals: List[Any],
) -> None:
    """
    Add current market context to the vector store for RAG retrieval.
    Skips duplicate news articles based on title.

    Args:
        market_data: Dictionary of market data by ticker
        news_data: Dictionary of news by ticker
        signals: List of trading signals
    """
    documents = []
    skipped_duplicates = 0

    # Add market data documents
    for ticker, data in market_data.items():
        if "error" not in data:
            content = f"""
            Données marché pour {ticker} au {data.get('timestamp', datetime.now().isoformat())}:
            Prix: {data.get('current_price', 'N/A')}
            RSI: {data.get('rsi', 'N/A')}
            SMA200: {data.get('sma200', 'N/A')}
            Support S1: {data.get('s1', 'N/A')}
            Résistance R1: {data.get('r1', 'N/A')}
            """
            documents.append(Document(
                page_content=content,
                metadata={"type": "market_data", "ticker": ticker, "timestamp": datetime.now().isoformat()}
            ))

    # Add news documents with deduplication
    vectorstore_temp = initialize_vectorstore()  # Get existing store to check duplicates
    for ticker, news_list in news_data.items():
        # Get existing titles for this ticker
        existing_titles = get_existing_news_titles(vectorstore_temp, ticker)

        for news in news_list:
            title = news.get('title', 'N/A')

            # Skip if duplicate
            if title in existing_titles:
                skipped_duplicates += 1
                continue

            content = f"""
            News pour {ticker}:
            Titre: {title}
            Source: {news.get('source', 'N/A')}
            Date: {news.get('date', 'N/A')}
            Sentiment: {news.get('sentiment', 'N/A')}
            """
            documents.append(Document(
                page_content=content,
                metadata={"type": "news", "ticker": ticker, "source": news.get('source', 'unknown'), "title": title}
            ))
            existing_titles.add(title)  # Add to set to avoid duplicates within same batch

    # Add signal documents
    for signal in signals:
        content = f"""
        Signal trading pour {signal.ticker}:
        Action: {signal.action}
        Prix entrée: {signal.prix_entree}
        Confiance: {signal.confiance}
        Raisonnement: {signal.raisonnement[:500]}
        """
        documents.append(Document(
            page_content=content,
            metadata={"type": "signal", "ticker": signal.ticker, "action": signal.action}
        ))

    # Add to vector store
    if documents:
        try:
            vectorstore = initialize_vectorstore(documents)
            msg = f"   ✅ [RAG] {len(documents)} documents ajoutés au vector store"
            if skipped_duplicates > 0:
                msg += f" ({skipped_duplicates} doublons ignorés)"
            print(msg)
        except Exception as e:
            print(f"   ⚠️ [RAG] Erreur ajout documents: {str(e)}")


def chat_with_rag(
    question: str,
    market_context: Optional[Dict[str, Any]] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Generate a response using RAG with market context.

    Args:
        question: User question
        market_context: Optional current market data context
        chat_history: Optional chat history for conversational memory

    Returns:
        Generated response
    """
    try:
        # Initialize vector store
        vectorstore = initialize_vectorstore()

        # Check if we should fetch real-time data
        ticker = detect_ticker(question)
        fresh_data_section = ""

        if ticker:
            # Fetch real-time data for the detected ticker
            fresh_data = fetch_fresh_market_data(ticker)
            if fresh_data:
                # Add fresh data to context
                fresh_data_section = f"""
🔄 DONNÉES TEMPS RÉEL ({ticker} - récupérées à {fresh_data['timestamp']}):
💰 Prix actuel: {fresh_data['price']:.2f}
📊 RSI: {fresh_data['rsi']:.2f}
📈 SMA200: {fresh_data['sma200']:.2f}
📉 SMA50: {fresh_data['sma50']:.2f}
🔀 MACD: {fresh_data['macd']:.4f}
🎯 Support S1: {fresh_data['s1']:.2f} | Résistance R1: {fresh_data['r1']:.2f}
📰 News fraîches ({fresh_data['news_count']} articles)
"""
                print(f"   ✅ Données temps réel ajoutées au contexte")

        # Retrieve relevant documents using hybrid approach
        retrieved_docs = retrieve_documents_hybrid(vectorstore, question, k=settings.TOP_K_RETRIEVAL)

        # Build context from retrieved documents
        context_parts = []
        for doc in retrieved_docs:
            context_parts.append(f"[{doc.metadata.get('type', 'unknown')}] {doc.page_content}")

        context = "\n\n".join(context_parts)

        # Prepend fresh data if available
        if fresh_data_section:
            context = fresh_data_section + "\n\n📚 CONTEXTE HISTORIQUE (RAG):\n" + context

        # Add current market context if available
        if market_context:
            current_context = "\n\nCONTEXTE ACTUEL:\n"
            if "macro_data" in market_context:
                macro = market_context["macro_data"]
                current_context += f"VIX: {macro.get('vix', 'N/A')}\n"
                current_context += f"US 10Y Yield: {macro.get('us_10y_yield', 'N/A')}%\n"

            if "signals" in market_context:
                current_context += "\nSignaux actifs:\n"
                for signal in market_context["signals"]:
                    current_context += f"- {signal.ticker}: {signal.action} (confiance: {signal.confiance})\n"

            context += current_context

        # Build prompt (~60K tokens context)
        history_text = ""
        if chat_history:
            # Take last 150 messages for large context window
            for msg in chat_history[-150:]:  # Last 150 messages (~30K tokens)
                role = "Utilisateur" if msg["role"] == "user" else "Assistant"
                content = msg['content']
                # Truncate very long messages to prevent overflow
                if len(content) > 2000:
                    content = content[:2000] + "... [truncated]"
                history_text += f"{role}: {content}\n"

        prompt = f"""Tu es un assistant expert en trading de métaux précieux (Or, Argent, Platine, Palladium).

CONTEXTE RÉCUPÉRÉ:
{context}

{history_text}

Question actuelle: {question}

Instructions:
1. Réponds en français de façon concise et professionnelle
2. Base ta réponse sur le contexte fourni
3. Si tu ne trouves pas l'information dans le contexte, dis-le clairement
4. N'invente pas de données de marché
5. Pour les recommandations de trading, rappelle toujours que ce sont des suggestions informatives et pas des conseils financiers

Réponse:"""

        # Generate response
        llm = OllamaLLM(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL.replace("/v1", ""),
            temperature=0.3,
        )

        response = llm.invoke(prompt)
        return response

    except Exception as e:
        return f"Désolé, une erreur s'est produite lors de la génération de la réponse: {str(e)}"


def add_documents_to_vectorstore(documents: List[Document]) -> bool:
    """
    Add custom documents to the vector store.

    Args:
        documents: List of documents to add

    Returns:
        True if successful
    """
    try:
        vectorstore = initialize_vectorstore(documents)
        return True
    except Exception as e:
        print(f"Erreur ajout documents: {str(e)}")
        return False


def clear_vectorstore() -> bool:
    """
    Clear all documents from the vector store.

    Returns:
        True if successful
    """
    try:
        embeddings = get_embeddings()
        vectorstore = Chroma(
            embedding_function=embeddings,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
        vectorstore.delete_collection()
        return True
    except Exception as e:
        print(f"Erreur nettoyage vector store: {str(e)}")
        return False
