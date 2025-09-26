"""
Modelos de datos para la aplicación de monitoreo de acciones.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TickerQuote:
    """
    Representa una cotización de un ticker con información de precios y timestamps.
    """
    symbol: str
    last: Optional[float] = None
    prev: Optional[float] = None
    last_ts: Optional[float] = None  # epoch seconds

    def update(self, price: Optional[float], ts: Optional[float]) -> None:
        """
        Actualiza el precio y timestamp de la cotización.

        Args:
            price: Nuevo precio
            ts: Timestamp en segundos epoch
        """
        if price is None:
            return
        if self.last is not None:
            self.prev = self.last
        self.last = price
        if ts is not None:
            self.last_ts = ts

    @property
    def delta(self) -> Optional[float]:
        """
        Calcula la diferencia entre el precio actual y el anterior.

        Returns:
            Diferencia de precios o None si no hay datos suficientes
        """
        if self.last is None or self.prev is None:
            return None
        return self.last - self.prev

    @property
    def delta_pct(self) -> Optional[float]:
        """
        Calcula el porcentaje de cambio entre el precio actual y el anterior.

        Returns:
            Porcentaje de cambio o None si no hay datos suficientes
        """
        if self.last is None or self.prev is None or self.prev == 0:
            return None
        return (self.last - self.prev) / self.prev * 100.0
