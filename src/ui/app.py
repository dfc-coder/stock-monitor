"""
Aplicación principal de interfaz de usuario con Tkinter (multi-pantalla con Notebook).
"""

import queue
import time
from typing import Dict, List, Tuple, Optional, Set

import tkinter as tk
from tkinter import ttk, messagebox

from models import TickerQuote
from websocket import WebSocketWorker


# =========================
# Páginas (Frames)
# =========================
class QuotesPage(ttk.Frame):
    """
    Página de cotizaciones: muestra la tabla (Treeview).
    Usa los datos de app.quote_by_symbol.
    """
    def __init__(self, parent: tk.Widget, app: "RealtimeApp") -> None:
        super().__init__(parent, padding=8)
        self.app = app

        columns = ("symbol", "last", "delta", "delta_pct", "time")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=20)
        self.tree.pack(fill="both", expand=True)

        self.tree.heading("symbol", text="Símbolo")
        self.tree.heading("last", text="Último")
        self.tree.heading("delta", text="Δ")
        self.tree.heading("delta_pct", text="Δ%")
        self.tree.heading("time", text="Hora")

        self.tree.column("symbol", width=100, anchor="center")
        self.tree.column("last", width=120, anchor="e")
        self.tree.column("delta", width=100, anchor="e")
        self.tree.column("delta_pct", width=100, anchor="e")
        self.tree.column("time", width=160, anchor="center")

        # Carga filas iniciales
        self.rebuild_rows()

        # Al seleccionar un símbolo, actualizamos la página de detalle
        self.tree.bind("<<TreeviewSelect>>", self._on_select_symbol)

    def rebuild_rows(self) -> None:
        """Reconstruye la tabla a partir de app.quote_by_symbol."""
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        for sym in self.app.quote_by_symbol:
            self.tree.insert("", "end", iid=sym, values=(sym, "-", "-", "-", "-"))

    def refresh(self) -> None:
        """Refresca las celdas con los datos actuales (no agrega/elimina filas)."""
        for sym, q in self.app.quote_by_symbol.items():
            last_s = f"{q.last:.4f}" if q.last is not None else "-"
            delta_s = f"{q.delta:+.4f}" if q.delta is not None else "-"
            dpp = q.delta_pct
            delta_pct_s = f"{dpp:+.3f}%" if dpp is not None else "-"
            time_s = self.app._fmt_time(q.last_ts)
            if self.tree.exists(sym):
                self.tree.item(sym, values=(sym, last_s, delta_s, delta_pct_s, time_s))

    def _on_select_symbol(self, _: tk.Event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        sym = sel[0]
        self.app.detail_page.set_symbol(sym)


class DetailPage(ttk.Frame):
    """
    Página de detalle: muestra información del símbolo seleccionado.
    """
    def __init__(self, parent: tk.Widget, app: "RealtimeApp") -> None:
        super().__init__(parent, padding=16)
        self.app = app
        self.symbol_var = tk.StringVar(value="-")
        self.last_var = tk.StringVar(value="-")
        self.delta_var = tk.StringVar(value="-")
        self.delta_pct_var = tk.StringVar(value="-")
        self.time_var = tk.StringVar(value="-")

        grid = ttk.Frame(self)
        grid.pack(anchor="nw")

        self._row(grid, 0, "Símbolo:", self.symbol_var)
        self._row(grid, 1, "Último:", self.last_var)
        self._row(grid, 2, "Δ:", self.delta_var)
        self._row(grid, 3, "Δ%:", self.delta_pct_var)
        self._row(grid, 4, "Hora:", self.time_var)

        # Botón para saltar a la pestaña de cotizaciones
        ttk.Button(self, text="Ver tabla", command=self._go_quotes).pack(pady=(12, 0), anchor="w")

        self._selected_symbol: Optional[str] = None

    def _row(self, parent: ttk.Frame, r: int, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Label(parent, textvariable=var, font=("TkDefaultFont", 10, "bold")).grid(
            row=r, column=1, sticky="w", pady=4, padx=(8, 0)
        )

    def set_symbol(self, symbol: str) -> None:
        """Selecciona el símbolo a mostrar y realiza un refresh inmediato."""
        self._selected_symbol = symbol
        self.symbol_var.set(symbol)
        self.refresh({symbol})

        # Cambia a la pestaña de Detalle automáticamente (opcional)
        self.app.notebook.select(self)

    def refresh(self, changed_symbols: Set[str]) -> None:
        """
        Refresca si el símbolo seleccionado cambió o está en el batch actualizado.
        """
        if not self._selected_symbol:
            return
        if changed_symbols and self._selected_symbol not in changed_symbols:
            return

        q = self.app.quote_by_symbol.get(self._selected_symbol)
        if not q:
            return

        self.last_var.set(f"{q.last:.4f}" if q.last is not None else "-")
        self.delta_var.set(f"{(q.delta or 0):+.4f}" if q.delta is not None else "-")
        self.delta_pct_var.set(f"{(q.delta_pct or 0):+.3f}%" if q.delta_pct is not None else "-")
        self.time_var.set(self.app._fmt_time(q.last_ts))

    def _go_quotes(self) -> None:
        self.app.notebook.select(self.app.quotes_page)


class SettingsPage(ttk.Frame):
    """
    Página de configuración: agrega/borra símbolos y reinicia el WebSocketWorker.
    Mantiene KISS: usa Listbox + Entry.
    """
    def __init__(self, parent: tk.Widget, app: "RealtimeApp") -> None:
        super().__init__(parent, padding=8)
        self.app = app

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Símbolo:").pack(side="left")
        self.input_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.input_var, width=16)
        entry.pack(side="left", padx=6)
        ttk.Button(top, text="Agregar", command=self._add_symbol).pack(side="left")
        ttk.Button(top, text="Eliminar seleccionado", command=self._remove_selected).pack(side="left", padx=(6, 0))

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, pady=(8, 0))
        self.listbox = tk.Listbox(mid, selectmode="extended")
        self.listbox.pack(fill="both", expand=True)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Guardar y Reiniciar", command=self._save_and_restart).pack(side="right")

        self._load_current_symbols()

    def _load_current_symbols(self) -> None:
        self.listbox.delete(0, tk.END)
        for sym in sorted(self.app.quote_by_symbol.keys()):
            self.listbox.insert(tk.END, sym)

    def _add_symbol(self) -> None:
        raw = self.input_var.get().strip().upper()
        if not raw:
            return
        if raw in self.app.quote_by_symbol:
            messagebox.showinfo("Info", f"{raw} ya existe.")
            return
        if self.listbox.size() >= 100:
            messagebox.showwarning("Límite", "Máximo 100 símbolos.")
            return
        self.listbox.insert(tk.END, raw)
        self.input_var.set("")

    def _remove_selected(self) -> None:
        sel = list(self.listbox.curselection())
        if not sel:
            return
        # Eliminar de abajo hacia arriba para no desplazar índices
        for idx in reversed(sel):
            self.listbox.delete(idx)

    def _save_and_restart(self) -> None:
        symbols = [self.listbox.get(i) for i in range(self.listbox.size())]
        if not symbols:
            if not messagebox.askyesno("Confirmar", "No hay símbolos. ¿Continuar?"):
                return
        self.app.restart_worker(symbols)
        messagebox.showinfo("OK", f"Reiniciado con {len(symbols)} símbolo(s).")


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
        self.detail_page = DetailPage(self.notebook, self)
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