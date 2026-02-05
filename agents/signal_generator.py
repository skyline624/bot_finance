"""Trading signal generation based on technical and sentiment analysis."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from enum import Enum

from config import get_settings
from .technical_analysis import get_technical_signals

settings = get_settings()


class ActionSignal(str, Enum):
    """Trading action signals."""
    ACHAT_FORT = "ACHAT_FORT"
    ACHAT = "ACHAT"
    NEUTRE = "NEUTRE"
    VENTE = "VENTE"
    VENTE_FORTE = "VENTE_FORTE"


class SignalTrading(BaseModel):
    """Structured trading signal."""
    ticker: str
    action: str
    prix_entree: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    confiance: float
    raisonnement: str


def generate_trading_signals(
    ticker: str,
    market_data: Dict[str, Any],
    sentiment_analysis: Dict[str, Any],
    macro_data: Dict[str, Any],
) -> SignalTrading:
    """
    Generate trading signals based on technical and sentiment analysis.

    Args:
        ticker: The ticker symbol
        market_data: Market data with technical indicators
        sentiment_analysis: Sentiment analysis results
        macro_data: Macroeconomic data

    Returns:
        Trading signal with entry, stop loss, and take profit levels
    """
    if "error" in market_data:
        return SignalTrading(
            ticker=ticker,
            action=ActionSignal.NEUTRE,
            prix_entree=0,
            stop_loss=None,
            take_profit=None,
            confiance=0.0,
            raisonnement=f"Erreur données: {market_data['error']}",
        )

    current_price = market_data.get("current_price", 0)
    s1 = market_data.get("s1", current_price * 0.98)
    r1 = market_data.get("r1", current_price * 1.02)
    atr = market_data.get("atr", current_price * 0.01)

    # Get technical signals
    tech_signals = get_technical_signals(market_data)

    # Get sentiment score
    sentiment_score = sentiment_analysis.get("score", 0.5)
    sentiment_label = sentiment_analysis.get("overall_sentiment", "NEUTRE")

    # Get macro context
    vix = macro_data.get("vix", 15)
    us_yield = macro_data.get("us_10y_yield", 3.0)

    # Calculate signal scores
    bullish_points = 0
    bearish_points = 0
    reasons = []

    # Technical analysis
    if tech_signals.get("rsi_bullish"):
        bullish_points += 2
        reasons.append("RSI en survente")
    elif tech_signals.get("rsi_bearish"):
        bearish_points += 2
        reasons.append("RSI en surachat")

    if tech_signals.get("trend_bullish"):
        bullish_points += 1
        reasons.append("Prix au-dessus SMA200 (trend haussier)")
    else:
        bearish_points += 1
        reasons.append("Prix sous SMA200 (trend baissier)")

    if tech_signals.get("golden_cross"):
        bullish_points += 1
        reasons.append("Golden Cross SMA50/200")
    else:
        bearish_points += 1
        reasons.append("Death Cross SMA50/200")

    if tech_signals.get("macd_bullish"):
        bullish_points += 1
        reasons.append("MACD haussier")
    else:
        bearish_points += 1
        reasons.append("MACD baissier")

    if tech_signals.get("near_support"):
        bullish_points += 2
        distance = tech_signals.get("near_support_distance", 0)
        reasons.append(f"Proche support S1 ({distance:.2f}%)")

    # Sentiment analysis
    if sentiment_score > 0.7:
        bullish_points += 1
        reasons.append(f"Sentiment positif ({sentiment_label})")
    elif sentiment_score < 0.3:
        bearish_points += 1
        reasons.append(f"Sentiment négatif ({sentiment_label})")

    # Macro context (VIX helps precious metals)
    if vix > settings.VIX_FEAR_THRESHOLD:
        bullish_points += 1
        reasons.append(f"VIX élevé ({vix:.2f}) favorise les valeurs refuges")

    # Yields hurt precious metals
    if us_yield > settings.US_YIELD_HIGH_THRESHOLD:
        bearish_points += 1.5
        reasons.append(f"Taux US élevés ({us_yield:.2f}%) défavorables")
    elif us_yield < 3.0:
        bullish_points += 0.5
        reasons.append(f"Taux US bas ({us_yield:.2f}%) favorables")

    # Calculate confidence and action
    total_points = bullish_points + bearish_points
    if total_points == 0:
        confidence = 0.5
    else:
        confidence = bullish_points / total_points

    # Determine action
    if bullish_points >= 5 and confidence > 0.7:
        action = ActionSignal.ACHAT_FORT
        entry = current_price
        stop_loss = s1 - (atr * 0.5)
        take_profit = r1
    elif bullish_points >= 3 and confidence > 0.6:
        action = ActionSignal.ACHAT
        entry = current_price
        stop_loss = s1
        take_profit = r1
    elif bearish_points >= 5 and confidence < 0.3:
        action = ActionSignal.VENTE_FORTE
        entry = current_price
        stop_loss = r1 + (atr * 0.5)
        take_profit = s1
    elif bearish_points >= 3 and confidence < 0.4:
        action = ActionSignal.VENTE
        entry = current_price
        stop_loss = r1
        take_profit = s1
    else:
        action = ActionSignal.NEUTRE
        entry = current_price
        stop_loss = None
        take_profit = None

    # Build reasoning
    reasoning = f"""
    Points Bullish: {bullish_points}, Points Bearish: {bearish_points}
    Score Confiance: {confidence:.2%}

    Facteurs clés:
    {chr(10).join(f"  • {r}" for r in reasons)}

    Contexte:
    - Sentiment news: {sentiment_label} (score: {sentiment_score:.2f})
    - VIX: {vix:.2f} ({macro_data.get('vix_sentiment', 'N/A')})
    - US Yield: {us_yield:.2f}% ({macro_data.get('yield_sentiment', 'N/A')})
    """

    return SignalTrading(
        ticker=ticker,
        action=action,
        prix_entree=round(entry, 2),
        stop_loss=round(stop_loss, 2) if stop_loss else None,
        take_profit=round(take_profit, 2) if take_profit else None,
        confiance=round(confidence, 2),
        raisonnement=reasoning,
    )


def generate_all_signals(
    market_data_dict: Dict[str, Dict[str, Any]],
    sentiment_dict: Dict[str, Dict[str, Any]],
    macro_data: Dict[str, Any],
) -> List[SignalTrading]:
    """
    Generate signals for all tickers.

    Args:
        market_data_dict: Dictionary of market data by ticker
        sentiment_dict: Dictionary of sentiment analysis by ticker
        macro_data: Shared macroeconomic data

    Returns:
        List of trading signals
    """
    signals = []

    for ticker, market_data in market_data_dict.items():
        sentiment = sentiment_dict.get(ticker, {"score": 0.5, "overall_sentiment": "NEUTRE"})
        signal = generate_trading_signals(ticker, market_data, sentiment, macro_data)
        signals.append(signal)

    return signals
