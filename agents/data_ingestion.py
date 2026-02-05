"""Data ingestion tools for market data, news, and macro indicators."""

import warnings
from typing import Dict, Any, List
import yfinance as yf
import pandas as pd
import ta
from GoogleNews import GoogleNews
import requests

from config import get_settings

warnings.filterwarnings("ignore", category=RuntimeWarning)

settings = get_settings()


def fetch_market_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch market data with technical indicators for a given ticker.

    Args:
        ticker: The ticker symbol (e.g., 'GC=F' for Gold)

    Returns:
        Dictionary containing price data and technical indicators
    """
    print(f"\n   ⏳ [OUTIL] Analyse Technique Avancée pour {ticker}...")

    try:
        df = yf.Ticker(str(ticker)).history(period="1y")
        if df.empty:
            return {"error": f"Pas de données pour {ticker}."}

        current = float(df['Close'].iloc[-1])
        high = float(df['High'].iloc[-1])
        low = float(df['Low'].iloc[-1])

        # Calculate Pivot Points
        pivot = (high + low + current) / 3
        r1 = (2 * pivot) - low
        s1 = (2 * pivot) - high

        # Technical indicators
        rsi = float(ta.momentum.rsi(df['Close'], window=settings.RSI_PERIOD).iloc[-1])
        sma200 = float(ta.trend.sma_indicator(df['Close'], window=settings.SMA_PERIOD).iloc[-1])

        # Additional indicators
        sma50 = float(ta.trend.sma_indicator(df['Close'], window=50).iloc[-1])
        macd = ta.trend.MACD(df['Close'])
        macd_line = float(macd.macd().iloc[-1])
        macd_signal = float(macd.macd_signal().iloc[-1])

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['Close'])
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])

        # ATR for volatility
        atr = float(ta.volatility.average_true_range(df['High'], df['Low'], df['Close']).iloc[-1])

        return {
            "ticker": ticker,
            "current_price": current,
            "high": high,
            "low": low,
            "pivot": pivot,
            "r1": r1,
            "s1": s1,
            "rsi": rsi,
            "sma200": sma200,
            "sma50": sma50,
            "macd": macd_line,
            "macd_signal": macd_signal,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "atr": atr,
            "timestamp": pd.Timestamp.now().isoformat(),
        }
    except Exception as e:
        return {"error": f"Erreur Technique: {str(e)}"}


def fetch_news(ticker: str) -> List[Dict[str, Any]]:
    """
    Fetch news using hybrid strategy (NewsData.io + Google News).

    Args:
        ticker: The ticker symbol

    Returns:
        List of news articles with metadata
    """
    print(f"\n   🌍 [HYBRIDE] Recherche News combinée (NewsData + Google) pour '{ticker}'...")

    combined_news = []
    seen_titles = set()

    # Map ticker to search query
    ticker_to_query = {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "PL=F": "Platinum",
        "PA=F": "Palladium",
        "DX-Y.NYB": "Dollar Index",
    }
    query = ticker_to_query.get(ticker, ticker)

    # Source 1: NewsData.io API (Free tier: 200 requests/day)
    if settings.NEWS_DATA_API_KEY:
        try:
            # NewsData.io endpoint - latest news with query
            url = f"https://newsdata.io/api/1/latest"
            params = {
                "apikey": settings.NEWS_DATA_API_KEY,
                "q": query,
                "language": "en",
                "size": 10,  # Max 10 for free tier
                "category": "business",  # Focus on business/finance news
            }
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    articles = data.get("results", [])
                    print(f"       💎 [NEWSDATA] {len(articles)} articles récupérés.")

                    for item in articles:
                        title = item.get('title', '')
                        if title and title not in seen_titles:
                            news_item = {
                                "title": title,
                                "sentiment": "N/A",  # NewsData doesn't provide sentiment
                                "source": item.get('source_name', 'NewsData'),
                                "date": item.get('pubDate', '').split(' ')[0] if item.get('pubDate') else 'Recent',
                                "url": item.get('link', ''),
                                "type": "PRO",
                            }
                            combined_news.append(news_item)
                            seen_titles.add(title)
                else:
                    print(f"       ⚠️ [NEWSDATA] API Error: {data.get('message', 'Unknown error')}")
            elif response.status_code == 429:
                print(f"       ⚠️ [NEWSDATA] Rate limit exceeded (200 req/day)")
            else:
                print(f"       ⚠️ [NEWSDATA] HTTP {response.status_code}")
        except Exception as e:
            print(f"       ⚠️ [NEWSDATA] Erreur: {str(e)}")
    else:
        print(f"       ⚠️ [NEWSDATA] Clé API non configurée")

    # Source 2: Google News
    try:
        googlenews = GoogleNews(lang='en', period='1d')
        googlenews.search(query)
        results = googlenews.result()

        count_google = 0
        for r in results:
            title = r.get('title', '')
            if title not in seen_titles:
                news_item = {
                    "title": title,
                    "sentiment": "N/A",
                    "source": r.get('media', 'Web'),
                    "date": r.get('date', 'Recent'),
                    "url": r.get('link', ''),
                    "type": "WEB",
                }
                combined_news.append(news_item)
                seen_titles.add(title)
                count_google += 1
                if count_google >= 6:
                    break

        print(f"       🔎 [GOOGLE] {count_google} articles complémentaires ajoutés.")
    except Exception as e:
        print(f"       ❌ [GOOGLE] Erreur: {str(e)}")

    return combined_news


def fetch_macro_data() -> Dict[str, Any]:
    """
    Fetch macroeconomic context (VIX and US Treasury Yields).

    Returns:
        Dictionary with VIX and US 10Y Yield data
    """
    print("\n   🏦 [OUTIL] Analyse du contexte Macro-Économique (VIX & Taux)...")

    try:
        tickers = ["^VIX", "^TNX"]
        data = yf.download(tickers, period="5d", progress=False)['Close']

        vix = float(data['^VIX'].iloc[-1])
        tnx = float(data['^TNX'].iloc[-1])

        # Interpretation
        sentiment_vix = "PANIQUE (Bullish Or)" if vix > settings.VIX_FEAR_THRESHOLD else "CALME (Neutre)"
        sentiment_tnx = "TAUX ÉLEVÉS (Bearish Or)" if tnx > settings.US_YIELD_HIGH_THRESHOLD else "TAUX FAIBLES"

        return {
            "vix": vix,
            "vix_sentiment": sentiment_vix,
            "us_10y_yield": tnx,
            "yield_sentiment": sentiment_tnx,
            "timestamp": pd.Timestamp.now().isoformat(),
        }
    except Exception as e:
        return {"error": f"Erreur Macro: {str(e)}"}
