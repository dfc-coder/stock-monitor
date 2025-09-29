import tkinter as tk
from tkinter import ttk
from typing import Set, Optional

class TicketDetailPage(ttk.Frame):
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
