import tkinter as tk
from tkinter import ttk

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



