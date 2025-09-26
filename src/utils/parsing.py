"""
Utilidades para parsing de mensajes y manejo seguro de datos.
"""

from typing import Dict, List, Any, Tuple, Optional


def safe_get(d: Dict[str, Any], *keys: str, default=None):
    """
    Obtiene un valor de un diccionario anidado de forma segura.

    Args:
        d: Diccionario del que obtener el valor
        *keys: Claves para navegar en el diccionario
        default: Valor por defecto si no se encuentra

    Returns:
        Valor encontrado o default
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def parse_ws_message(msg: Any) -> List[Tuple[str, Optional[float], Optional[float]]]:
    """
    Normaliza el mensaje del WebSocket de yfinance a una lista de tuplas.

    Args:
        msg: Mensaje del WebSocket (puede ser dict o list)

    Returns:
        Lista de tuplas: [(symbol, price, ts_epoch), ...]
        Devuelve lista porque Yahoo puede enviar múltiples updates en un solo payload.
        Es defensivo: si faltan campos, ignora esos updates.
    """
    out: List[Tuple[str, Optional[float], Optional[float]]] = []

    # Casos observados:
    # 1) dict con 'id' (símbolo) y 'price'
    # 2) dict con 'data': [ { 'id': 'AAPL', 'price': 123.45, 'time': 1699999999 }, ... ]
    # 3) ya una lista de dicts anteriores
    if isinstance(msg, dict):
        if "data" in msg and isinstance(msg["data"], list):
            for item in msg["data"]:
                sym = safe_get(item, "id")
                price = safe_get(item, "price")
                ts = safe_get(item, "time")
                if isinstance(sym, str):
                    out.append((sym.upper(), _to_float(price), _to_float(ts)))
        else:
            sym = safe_get(msg, "id")
            price = safe_get(msg, "price")
            ts = safe_get(msg, "time")
            if isinstance(sym, str):
                out.append((sym.upper(), _to_float(price), _to_float(ts)))
    elif isinstance(msg, list):
        for item in msg:
            if not isinstance(item, dict):
                continue
            sym = safe_get(item, "id")
            price = safe_get(item, "price")
            ts = safe_get(item, "time")
            if isinstance(sym, str):
                out.append((sym.upper(), _to_float(price), _to_float(ts)))

    return out


def _to_float(x: Any) -> Optional[float]:
    """
    Convierte un valor a float de forma segura.

    Args:
        x: Valor a convertir

    Returns:
        Float convertido o None si hay error
    """
    try:
        return float(x)
    except Exception:
        return None
