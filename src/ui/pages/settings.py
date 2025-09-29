
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

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
