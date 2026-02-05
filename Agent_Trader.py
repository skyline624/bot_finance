import os
import sys
import yfinance as yf
import pandas as pd
import ta
import warnings

# --- 1. GESTION DES WARNINGS (Pour nettoyer la console) ---
# On supprime le message rouge "RuntimeWarning: package renamed to ddgs"
warnings.filterwarnings("ignore", category=RuntimeWarning)

from GoogleNews import GoogleNews
import requests
from autogen import UserProxyAgent, AssistantAgent

# --- 2. CONFIGURATION DU MODÈLE (QWEN 3) ---
llm_config = {
    "config_list": [{
        "model": "kimi-k2.5:cloud", 
        "base_url": "http://localhost:11434/v1", 
        "api_key": "ollama"
    }],
    "timeout": 120,
    "temperature": 0.0 # Rigueur absolue pour les maths et le code
}

# --- 3. OUTILS AVEC FEEDBACK VISUEL ---

def get_market_news(query: str) -> str:
    """
    Récupère les news via une stratégie Hybride (API Pro + Recherche Web).
    Arguments:
        query: Le sujet de recherche (ex: 'Silver price' ou 'Gold market')
    """
    print(f"\n   🌍 [HYBRIDE] Recherche News combinée (FMP + Google) pour '{query}'...")
    
    combined_summary = ""
    seen_titles = set() # Pour éviter les doublons entre les deux sources
    
    # --- SOURCE 1 : FMP (La qualité Pro) ---
    try:
        # Note: Remplacez par VOTRE vraie clé API FMP (gratuite)
        API_KEY = "10x0AciAuFTfp56xoWkKTfrRJRaBXo3l" 
        
        # On mappe la requête textuelle vers des Tickers pour l'API
        tickers = "SI=F,GC=F" # Par défaut Argent et Or
        if "palladium" in query.lower(): tickers += ",PA=F"
        if "platinum" in query.lower(): tickers += ",PL=F"
        
        url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={tickers}&limit=3&apikey={API_KEY}"
        
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"       💎 [FMP] {len(data)} articles pro récupérés.")
            
            for item in data:
                title = item.get('title', '')
                sentiment = item.get('sentiment', 'N/A')
                site = item.get('site', 'FMP')
                date = item.get('publishedDate', '').split(' ')[0]
                
                # On ajoute au rapport
                combined_summary += f"- [PRO][{date}] {title} (Sentiment IA: {sentiment}) - Source: {site}\n"
                seen_titles.add(title) # On mémorise pour pas le remettre
    except Exception as e:
        print(f"       ⚠️ [FMP] Erreur ou Pas de clé (Passage à Google)...")

    # --- SOURCE 2 : GoogleNews (Le Filet de sécurité) ---
    try:
        googlenews = GoogleNews(lang='en', period='1d') # News fraiches (24h)
        googlenews.search(query)
        results = googlenews.result()
        
        count_google = 0
        for r in results:
            title = r.get('title', '')
            
            # Vérification anti-doublon (Si FMP l'a déjà donné, on ignore)
            if title not in seen_titles:
                date = r.get('date', 'Récent')
                media = r.get('media', 'Web')
                
                combined_summary += f"- [WEB][{date}] {title} (Source: {media})\n"
                count_google += 1
                if count_google >= 3: break # On limite à 3 news Google pour pas noyer l'IA
        
        print(f"       🔎 [GOOGLE] {count_google} articles complémentaires ajoutés.")
        
    except Exception as e:
        print(f"       ❌ [GOOGLE] Erreur: {str(e)}")

    # --- RETOUR FINAL ---
    if not combined_summary:
        return "Aucune news trouvée sur aucune source."
    
    return combined_summary

def get_macro_context() -> str:
    """Récupère VIX (Peur) et Taux US (Yields)."""
    print("\n   🏦 [OUTIL] Analyse du contexte Macro-Économique (VIX & Taux)...")
    try:
        # ^VIX = Volatility Index, ^TNX = 10-Year Treasury Yield
        tickers = ["^VIX", "^TNX"]
        data = yf.download(tickers, period="5d", progress=False)['Close']
        
        vix = data['^VIX'].iloc[-1]
        tnx = data['^TNX'].iloc[-1]
        
        # Interprétation simple pour aider l'IA
        sentiment_vix = "PANIQUE (Bullish Or)" if vix > 20 else "CALME (Neutre)"
        sentiment_tnx = "TAUX ÉLEVÉS (Bearish Or)" if tnx > 4.0 else "TAUX FAIBLES"
        
        return f"""
        CONTEXTE MACRO-ÉCONOMIQUE (Moteurs du marché):
        1. VIX (Indice de la Peur): {vix:.2f} -> {sentiment_vix}
           (Note: VIX élevé favorise les valeurs refuges comme l'Or/Argent)
           
        2. US 10Y YIELDS (Taux Obligataires): {tnx:.2f}% -> {sentiment_tnx}
           (Note: Une hausse des taux fait généralement chuter l'Or et l'Argent)
        """
    except Exception as e:
        return f"Erreur Macro: {str(e)}"

# --- MODIFIEZ LA FONCTION get_market_data POUR AJOUTER LES PIVOTS ---

def get_market_data(ticker: str) -> str:
    print(f"\n   ⏳ [OUTIL] Analyse Technique Avancée pour {ticker}...")
    try:
        df = yf.Ticker(str(ticker)).history(period="1y")
        if df.empty: return f"Erreur: Pas de données pour {ticker}."
        
        current = df['Close'].iloc[-1]
        high = df['High'].iloc[-1]
        low = df['Low'].iloc[-1]
        
        # 1. Calcul des PIVOTS POINTS (Classique)
        # Pivot (P) = (High + Low + Close) / 3
        pivot = (high + low + current) / 3
        r1 = (2 * pivot) - low  # Résistance 1
        s1 = (2 * pivot) - high # Support 1
        
        # 2. Indicateurs classiques
        rsi = ta.momentum.rsi(df['Close'], window=14).iloc[-1]
        sma200 = ta.trend.sma_indicator(df['Close'], window=200).iloc[-1]
        
        return f"""
        RAPPORT TECHNIQUE AVANCÉ ({ticker}):
        - PRIX ACTUEL: {current:.2f}
        
        [INDICATEURS]
        - RSI (14): {rsi:.2f}
        - SMA200: {sma200:.2f} (Tendance de fond)
        
        [NIVEAUX CLÉS (PIVOTS)]
        - RÉSISTANCE R1 (Objectif court terme): {r1:.2f}
        - PIVOT CENTRAL: {pivot:.2f}
        - SUPPORT S1 (Zone d'achat idéale): {s1:.2f}
        """
    except Exception as e:
        return f"Erreur Technique: {str(e)}"

# --- 4. L'AGENT ---

user_proxy = UserProxyAgent(
    name="Admin",
    human_input_mode="NEVER",
    # CORRECTION ICI : On arrête si "TERMINATE" est présent n'importe où dans le message
    is_termination_msg=lambda x: x.get("content") is not None and "TERMINATE" in x.get("content", "").upper(),
    # On limite les échanges max à 15 pour éviter une boucle infinie si ça plante
    max_consecutive_auto_reply=15,
    code_execution_config={"work_dir": "coding", "use_docker": False}
)

trader = AssistantAgent(
    name="Trader_Bot",
    llm_config=llm_config,
    system_message="""
    Tu es un Hedge Fund Manager Expert.
    
    PROTOCOLE D'ANALYSE DE PRÉCISION :
    1. Commence TOUJOURS par appeler 'get_macro_context' pour sentir le marché (VIX + Taux).
       - Si les Taux (Yields) montent -> Sois prudent sur l'Or/Argent.
       - Si le VIX explose -> Cherche des achats refuge.
       
    2. Ensuite, appelle 'get_market_data' pour chaque métal.
       - Regarde les Niveaux Pivots (S1/R1). Si le prix est proche de S1, c'est un bon achat technique.
       
    3. Enfin, valide avec 'get_market_news'.
    
    4. Ton verdict doit être nuancé : "ACHAT FORT", "ACHAT SUR REPLI (vers S1)", "NEUTRE", "VENTE".
    
    5. Finis par TERMINATE.
    """
)

user_proxy.register_for_execution(name="get_market_data")(get_market_data)
trader.register_for_llm(name="get_market_data", description="Get data")(get_market_data)

user_proxy.register_for_execution(name="get_market_news")(get_market_news)
trader.register_for_llm(name="get_market_news", description="Get news")(get_market_news)

user_proxy.register_for_execution(name="get_macro_context")(get_macro_context)
trader.register_for_llm(name="get_macro_context", description="Get VIX and US Yields context")(get_macro_context)

# --- 5. LANCEMENT ---
if __name__ == "__main__":
    print("🚀 Démarrage du Bot...")
    
    # On sauvegarde le chat pour créer le rapport à la fin
    chat = user_proxy.initiate_chat(
        trader,
        message="""
        Fais une analyse complète et comparative de ces actifs :
        1. OR (Gold - Ticker: GC=F)
        2. ARGENT (Silver - Ticker: SI=F)
        3. PLATINE (Platinum - Ticker: PL=F)
        4. PALLADIUM (Ticker: PA=F)
        5. DOLLAR INDEX (Ticker: DX-Y.NYB) pour le contexte forex.
        """,
        max_turns=40
    )
    
    # Création du fichier rapport
    try:
        last_msg = chat.chat_history[-1]['content'].replace("TERMINATE", "")
        filename = "Rapport_Trading_Final.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(last_msg)
        print(f"\n📄 Rapport sauvegardé dans : {os.path.abspath(filename)}")
    except Exception as e:
        print(f"\n⚠️ Impossible de sauvegarder le fichier, voir la console ci-dessus.\n{str(e)}")