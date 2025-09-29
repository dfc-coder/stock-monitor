"""
Aplicación principal de interfaz de usuario con Tkinter (multi-pantalla con Notebook).
"""

import queue
import time
from typing import Dict, List, Tuple, Optional, Set

import tkinter as tk
from tkinter import ttk

from models import TickerQuote
from websocket import WebSocketWorker
from .pages import QuotesPage, TicketDetailPage, SettingsPage

# =========================
# App principal (Notebook)
# =========================
class RealtimeApp:
    """
    Aplicación principal que muestra cotizaciones en tiempo real usando Tkinter.
    """

    def __init__(self, root: tk.Tk, tickers: List[str]) -> None:
        self.root = root
        self.root.title("Live Prices (Yahoo WebSocket)")
        self.root.geometry("820x560")

        # Datos
        self.quote_by_symbol: Dict[str, TickerQuote] = {}
        for t in sorted(set([t.strip().upper() for t in tickers if t.strip()]))[:100]:
            self.quote_by_symbol[t] = TickerQuote(symbol=t)

        # Infra WS
        self.ws_queue: "queue.Queue[List[Tuple[str, Optional[float], Optional[float]]]]" = queue.Queue()
        self.ws_worker = WebSocketWorker(
            tickers=list(self.quote_by_symbol.keys()),
            on_message_queue=self.ws_queue,
            log=self._log,
        )

        # UI
        self._build_ui()
        self._bind_events()

        # Arranca WS
        self.ws_worker.start()

        # Loop de refresco de GUI (no bloqueante)
        self._schedule_gui_update()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=8)
        root_frame.pack(fill="both", expand=True)

        # Barra superior (status + salir)
        top = ttk.Frame(root_frame)
        top.pack(side="top", fill="x")
        self.status_var = tk.StringVar(value="Conectando…")
        ttk.Label(top, textvariable=self.status_var).pack(side="left")
        ttk.Button(top, text="Salir", command=self._on_exit).pack(side="right")

        # Notebook con 3 pestañas
        self.notebook = ttk.Notebook(root_frame)
        self.notebook.pack(fill="both", expand=True, pady=(8, 0))

        self.quotes_page = QuotesPage(self.notebook, self)
        self.detail_page = TicketDetailPage(self.notebook, self)
        self.settings_page = SettingsPage(self.notebook, self)

        self.notebook.add(self.quotes_page, text="Cotizaciones")
        self.notebook.add(self.detail_page, text="Detalle")
        self.notebook.add(self.settings_page, text="Configuración")

    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

    # ---------- Loop GUI ----------
    def _schedule_gui_update(self) -> None:
        self.root.after(150, self._drain_ws_updates)

    def _drain_ws_updates(self) -> None:
        batch: List[Tuple[str, Optional[float], Optional[float]]] = []
        changed: Set[str] = set()
        try:
            while True:
                updates = self.ws_queue.get_nowait()
                batch.extend(updates)
        except queue.Empty:
            pass

        for sym, price, ts in batch:
            quote = self.quote_by_symbol.get(sym)
            if quote is None:
                # Si llega un símbolo inesperado, lo ignoramos (KISS)
                continue
            before = quote.last
            quote.update(price, ts)
            if quote.last != before:
                changed.add(sym)

        # Refrescar pantallas afectadas
        self.quotes_page.refresh()
        self.detail_page.refresh(changed)

        # Mensaje de estado y reprogramación
        self.status_var.set(f"Recibiendo datos… {time.strftime('%H:%M:%S')}")
        self._schedule_gui_update()

    # ---------- Helpers ----------
    def _fmt_time(self, ts: Optional[float]) -> str:
        if not ts:
            return "-"
        if ts > 1e12:  # ms -> s
            ts = ts / 1000.0
        try:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            return "-"

    def _log(self, msg: str) -> None:
        self.status_var.set(msg)
        print(msg, flush=True)

    # ---------- Gestión de WS ----------
    def restart_worker(self, new_symbols: List[str]) -> None:
        """
        Reinicia el WebSocket con una nueva lista de símbolos (<=100).
        Resetea el store y reconstruye la tabla.
        """
        # 1) Parar actual
        try:
            self.ws_worker.stop()
            self.ws_worker.join(timeout=2.0)
        except Exception as e:
            print(f"Error al parar WS: {e!r}", flush=True)

        # 2) Actualizar store
        normalized = sorted(set([s.strip().upper() for s in new_symbols if s.strip()]))[:100]
        self.quote_by_symbol = {s: TickerQuote(symbol=s) for s in normalized}

        # 3) Reconstruir tabla y páginas que dependan de lista
        self.quotes_page.rebuild_rows()
        self.detail_page.set_symbol(normalized[0] if normalized else "-")

        # 4) Crear y arrancar nuevo worker
        self.ws_queue = queue.Queue()
        self.ws_worker = WebSocketWorker(
            tickers=normalized,
            on_message_queue=self.ws_queue,
            log=self._log,
        )
        self.ws_worker.start()

    # ---------- Salida limpia ----------
    def _on_exit(self) -> None:
        try:
            self.ws_worker.stop()
            self.ws_worker.join(timeout=2.0)
        except Exception as e:
            print(f"Error al cerrar WS: {e!r}", flush=True)
        finally:
            self.root.destroy()