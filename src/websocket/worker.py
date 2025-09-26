"""
Worker para manejar la conexión WebSocket con yfinance.
"""

import threading
import queue
import time
from typing import List, Optional, Callable

import yfinance as yf

from utils.parsing import parse_ws_message


class WebSocketWorker:
    """
    Corre el WebSocket de yfinance en un hilo aparte y empuja updates a una Queue thread-safe.
    Maneja reconexiones con backoff exponencial simple.
    """

    def __init__(
        self,
        tickers: List[str],
        on_message_queue: queue.Queue,
        log: Callable[[str], None],
    ) -> None:
        """
        Inicializa el WebSocket worker.

        Args:
            tickers: Lista de símbolos a monitorear
            on_message_queue: Queue para enviar mensajes de actualización
            log: Función de logging
        """
        self.tickers = sorted(set([t.strip().upper() for t in tickers if t.strip()]))[:100]
        self.q = on_message_queue
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._log = log

    def start(self) -> None:
        """
        Inicia el worker en un hilo separado.
        """
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_loop, name="WS-Worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Detiene el worker.
        """
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        """
        Espera a que el hilo termine.

        Args:
            timeout: Tiempo máximo de espera en segundos
        """
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run_loop(self) -> None:
        """
        Loop principal del WebSocket con manejo de reconexiones.
        """
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self._log(f"Conectando WebSocket… ({len(self.tickers)} tickers)")
                with yf.WebSocket() as ws:
                    ws.subscribe(self.tickers)
                    # yfinance WS síncrono: registra callback y bloquea en listen()
                    ws.listen(self._on_raw_message)
            except Exception as e:
                self._log(f"WS error: {e!r}. Reintentando en {backoff:.1f}s…")
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
            else:
                backoff = 1.0  # si terminó sin excepción, resetea backoff
            # Pequeña pausa para ceder CPU si se desconectó limpiamente
            time.sleep(0.2)

    def _on_raw_message(self, msg) -> None:
        """
        Callback para procesar mensajes del WebSocket.

        Args:
            msg: Mensaje recibido del WebSocket
        """
        if self._stop.is_set():
            return
        updates = parse_ws_message(msg)
        if not updates:
            return
        # Encola en batch para minimizar contención
        self.q.put(updates)
