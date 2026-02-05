"""Sentiment analysis tools for news and market data."""

from typing import Dict, Any, List
from langchain_ollama import OllamaLLM

from config import get_settings

settings = get_settings()


def analyze_sentiment(news_items: List[Dict[str, Any]], ticker: str) -> Dict[str, Any]:
    """
    Analyze sentiment of news articles using LLM.

    Args:
        news_items: List of news articles
        ticker: The ticker symbol being analyzed

    Returns:
        Dictionary with sentiment analysis results
    """
    if not news_items:
        return {
            "ticker": ticker,
            "overall_sentiment": "NEUTRE",
            "score": 0.5,
            "summary": "Aucune news disponible pour analyse.",
        }

    # Combine news titles for analysis
    news_text = "\n".join([f"- {item['title']} (Source: {item['source']})" for item in news_items[:5]])

    # Create prompt for sentiment analysis
    prompt = f"""Analyse le sentiment des news suivantes pour {ticker}:

{news_text}

Instructions:
1. Évalue le sentiment global (TRÈS POSITIF, POSITIF, NEUTRE, NÉGATIF, TRÈS NÉGATIF)
2. Attribue un score entre 0 (très négatif) et 1 (très positif)
3. Résume les points clés en 2-3 phrases

Format de réponse:
Sentiment: [sentiment]
Score: [0.XX]
Résumé: [votre analyse]"""

    try:
        llm = OllamaLLM(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL.replace("/v1", ""),
            temperature=0.0,
        )

        response = llm.invoke(prompt)

        # Parse response
        lines = response.strip().split("\n")
        sentiment = "NEUTRE"
        score = 0.5
        summary = response

        for line in lines:
            if line.lower().startswith("sentiment:"):
                sentiment = line.split(":", 1)[1].strip()
            elif line.lower().startswith("score:"):
                try:
                    score = float(line.split(":", 1)[1].strip())
                except ValueError:
                    score = 0.5
            elif line.lower().startswith("résumé:") or line.lower().startswith("resume:"):
                summary = line.split(":", 1)[1].strip()

        return {
            "ticker": ticker,
            "overall_sentiment": sentiment,
            "score": score,
            "summary": summary,
            "news_count": len(news_items),
        }

    except Exception as e:
        # Fallback: basic sentiment based on FMP sentiment if available
        fmp_sentiments = [item.get("sentiment", "Neutral") for item in news_items if item.get("type") == "PRO"]

        if fmp_sentiments:
            positive_count = sum(1 for s in fmp_sentiments if s.lower() in ["positive", "bullish"])
            negative_count = sum(1 for s in fmp_sentiments if s.lower() in ["negative", "bearish"])
            total = len(fmp_sentiments)

            if positive_count > negative_count:
                sentiment = "POSITIF"
                score = 0.6 + (positive_count / total) * 0.3
            elif negative_count > positive_count:
                sentiment = "NÉGATIF"
                score = 0.4 - (negative_count / total) * 0.3
            else:
                sentiment = "NEUTRE"
                score = 0.5
        else:
            sentiment = "NEUTRE"
            score = 0.5

        return {
            "ticker": ticker,
            "overall_sentiment": sentiment,
            "score": max(0, min(1, score)),
            "summary": f"Analyse basique basée sur {len(news_items)} articles. Erreur LLM: {str(e)}",
            "news_count": len(news_items),
        }


def analyze_market_sentiment(macro_data: Dict[str, Any]) -> str:
    """
    Analyze overall market sentiment based on macro indicators.

    Args:
        macro_data: Dictionary with VIX and yield data

    Returns:
        Market sentiment description
    """
    if "error" in macro_data:
        return "Données macro indisponibles"

    vix = macro_data.get("vix", 15)
    us_yield = macro_data.get("us_10y_yield", 3.0)

    # VIX interpretation
    if vix > 30:
        vix_sentiment = "PANIQUE EXTRÊME - Opportunité d'achat refuge"
    elif vix > 20:
        vix_sentiment = "PEUR ÉLEVÉE - Favorise les métaux précieux"
    elif vix > 15:
        vix_sentiment = "MARCHÉ NERVEUX"
    else:
        vix_sentiment = "MARCHÉ CALME - Appétit pour le risque"

    # Yield interpretation for precious metals
    if us_yield > 4.5:
        yield_impact = "TRÈS NÉGATIF pour métaux (opportunité coût élevée)"
    elif us_yield > 4.0:
        yield_impact = "NÉGATIF pour métaux"
    elif us_yield > 3.0:
        yield_impact = "NEUTRE"
    else:
        yield_impact = "POSITIF pour métaux (rendement alternatif faible)"

    return f"""
    SENTIMENT MARCHÉ:
    - VIX ({vix:.2f}): {vix_sentiment}
    - US 10Y Yield ({us_yield:.2f}%): {yield_impact}
    """
