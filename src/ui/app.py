"""
Aplicación principal de interfaz de usuario con Tkinter (multi-pantalla con Notebook).
"""

import queue
import time
import tkinter as tk

# ... imports iguales ...
from tkinter import ttk
from typing import Dict, List, Tuple, Optional, Set

from models import TickerQuote
from websocket import WebSocketWorker
from .pages import QuotesPage, TicketDetailPage, SettingsPage
from db.tickers import TickerRepository


class RealtimeApp:
    def __init__(self, root: tk.Tk, repo: TickerRepository) -> None:
        self.root = root
        self.repo = repo
        self.root.title("Live Prices (Yahoo WebSocket)")
        self.root.geometry("820x560")
        self.quote_by_symbol: Dict[str, TickerQuote] = {}

        # ---------- UI base (siempre) ----------
        

        # ---------- Datos ----------
        symbols = self.repo.list(limit=100)
        if not symbols:
            # Estado vacío: mostrar aviso en UI y llevar al usuario a Configuración
            self.quote_by_symbol = {}
            self._build_ui()
            self._bind_events()
            self._show_empty_state()
            return  # ⬅ early return: no inicia WS ni loop

        # Store con símbolos (ya normalizados)
        self.quote_by_symbol: Dict[str, TickerQuote] = {s: TickerQuote(symbol=s) for s in symbols}
        self._build_ui()
        self._bind_events()
        
        # ---------- Infra WS ----------
        self.ws_queue: "queue.Queue[List[Tuple[str, Optional[float], Optional[float]]]]" = queue.Queue()
        self.ws_worker = WebSocketWorker(
            tickers=list(self.quote_by_symbol.keys()),
            on_message_queue=self.ws_queue,
            log=self._log,
        )
        self.ws_worker.start()

        # Loop de refresco de GUI (no bloqueante)
        self._schedule_gui_update()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        # estilo para banner de alerta
        style = ttk.Style(self.root)
        style.configure("Warn.TLabel", foreground="#b45309")  # ámbar oscuro
        style.configure("Warn.TFrame", background="#FFF7ED")

        root_frame = ttk.Frame(self.root, padding=8)
        root_frame.pack(fill="both", expand=True)

        top = ttk.Frame(root_frame)
        top.pack(side="top", fill="x")
        self.status_var = tk.StringVar(value="Conectando…")
        ttk.Label(top, textvariable=self.status_var).pack(side="left")
        ttk.Button(top, text="Salir", command=self._on_exit).pack(side="right")

        self.notebook = ttk.Notebook(root_frame)
        self.notebook.pack(fill="both", expand=True, pady=(8, 0))

        self.quotes_page = QuotesPage(self.notebook, self)
        self.detail_page = TicketDetailPage(self.notebook, self)
        self.settings_page = SettingsPage(self.notebook, self)

        self.notebook.add(self.quotes_page, text="Cotizaciones")
        self.notebook.add(self.detail_page, text="Detalle")
        self.notebook.add(self.settings_page, text="Configuración")

    def _show_empty_state(self) -> None:
        """Muestra aviso cuando no hay símbolos en DB y enfoca Configuración."""
        self.status_var.set("No hay símbolos. Configurá los que querés seguir.")
        self.notebook.select(self.settings_page)

        # Banner simple al tope de la pestaña Configuración
        banner = ttk.Frame(self.settings_page, style="Warn.TFrame", padding=8)
        banner.pack(side="top", fill="x", pady=(0, 8))
        ttk.Label(
            banner,
            text="No hay símbolos configurados.\nAgregá al menos uno en esta pestaña y guardá los cambios.",
            style="Warn.TLabel",
            justify="left",
            wraplength=600,
        ).pack(anchor="w")

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
                continue
            before = quote.last
            quote.update(price, ts)
            if quote.last != before:
                changed.add(sym)

        self.quotes_page.refresh()
        self.detail_page.refresh(changed)

        self.status_var.set(f"Recibiendo datos… {time.strftime('%H:%M:%S')}")
        self._schedule_gui_update()

    # ---------- Helpers ----------
    def _fmt_time(self, ts: Optional[float]) -> str:
        if not ts:
            return "-"
        if ts > 1e12:
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
        if not new_symbols:
            # Si quedó vacío, parar WS y mostrar estado vacío
            try:
                self.ws_worker.stop()
                self.ws_worker.join(timeout=2.0)
            except Exception:
                pass
            self._show_empty_state()
            return

        try:
            self.ws_worker.stop()
            self.ws_worker.join(timeout=2.0)
        except Exception:
            pass

        unique = list(dict.fromkeys(new_symbols))[:100]
        self.quote_by_symbol = {s: TickerQuote(symbol=s) for s in unique}

        self.quotes_page.rebuild_rows()
        self.detail_page.set_symbol(unique[0])

        self.ws_queue = queue.Queue()
        self.ws_worker = WebSocketWorker(
            tickers=unique,
            on_message_queue=self.ws_queue,
            log=self._log,
        )
        self.ws_worker.start()

    # ---------- Salida limpia ----------
    def _on_exit(self) -> None:
        try:
            self.ws_worker.stop()
            self.ws_worker.join(timeout=2.0)
        except Exception:
            pass
        finally:
            self.root.destroy()
