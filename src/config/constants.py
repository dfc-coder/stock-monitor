"""
Configuraciones y constantes de la aplicación.
"""

from typing import List

# ⚠️ Máximo recomendado por Yahoo para una sola subscripción: <= 100 tickers
DEFAULT_TICKERS: List[str] = [
    "AAPL", "MSFT", "GOOG", "AMZN", "NVDA",
    "META", "TSLA", "AMD", "NFLX", "INTC",
    "CRM", "ORCL", "IBM", "UBER", "SHOP",
    "BABA", "MELI", "PYPL", "SQ", "COIN",
    "BTC-USD", "ETH-USD"
]  # Puedes reemplazar por tu lista (<= 100)
