# ui/pages/settings.py
from __future__ import annotations

import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import PRIMARY, SUCCESS, SECONDARY, DANGER, INFO
from tkinter import messagebox
from typing import Dict, List, Tuple


class SettingsPage(tb.Frame):
    """
    UI mínima:
    - Una fila por símbolo: Checkbutton (follow 0/1) + botón Eliminar.
    - Agregar no toca la DB; 'Guardar y Reiniciar' persiste TODO en lote.
    """

    def __init__(self, parent: tk.Widget, app: "RealtimeApp") -> None:
        super().__init__(parent, padding=12)
        self.app = app
        self._vars: Dict[str, tk.BooleanVar] = {}  # símbolo -> var
        self._rows: Dict[str, tb.Frame] = {}  # símbolo -> fila
        self._initial_syms: set[str] = set()  # snapshot para detectar eliminados

        # --- Top: entrada + agregar ---
        top = tb.Frame(self)
        top.pack(fill="x")
        tb.Label(top, text="Símbolo:", bootstyle=INFO).pack(side="left")
        self.input_var = tk.StringVar()
        ent = tb.Entry(top, textvariable=self.input_var, width=18)
        ent.pack(side="left", padx=6)
        ent.bind("<Return>", lambda _e: self._add_symbol())
        tb.Button(
            top, text="Agregar", command=self._add_symbol, bootstyle=SUCCESS
        ).pack(side="left")
        ent.focus_set()

        # --- Área scrollable para filas ---
        mid = tb.Frame(self)
        mid.pack(fill="both", expand=True, pady=(10, 0))
        self.canvas = tk.Canvas(mid, highlightthickness=0)
        vsb = tb.Scrollbar(mid, orient="vertical", command=self.canvas.yview)
        self.inner = tb.Frame(self.canvas)
        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Bottom: guardar ---
        bottom = tb.Frame(self)
        bottom.pack(fill="x", pady=(10, 0))
        tb.Button(
            bottom,
            text="Guardar y Reiniciar",
            command=self._save_and_restart,
            bootstyle=PRIMARY,
        ).pack(side="right")

        self._load_from_repo()

    # --------- carga inicial ---------
    def _load_from_repo(self) -> None:
        for sym in list(self._rows):
            self._remove_row(sym)  # limpia UI
        rows: List[Tuple[str, int]] = self.app.repo.list_all()  # [(symbol, follow)]
        self._initial_syms = {s for s, _ in rows}
        for sym, f in sorted(rows):
            self._add_row(sym, bool(f))

    # --------- construcción de fila ---------
    def _add_row(self, sym: str, checked: bool) -> None:
        if sym in self._rows:
            return

        row = tb.Frame(self.inner, padding=(4, 2))
        row.pack(fill="x", padx=4, pady=2)

        var = tk.BooleanVar(value=checked)
        self._vars[sym] = var
        self._rows[sym] = row

        # Checkbutton con espacio entre checkbox y texto
        chk = tb.Checkbutton(
            row,
            text=sym,
            variable=var,
            bootstyle=(SUCCESS if checked else SECONDARY),
        )
        chk.pack(side="left")  # espacio a la derecha

        def on_toggle(*_):
            chk.config(bootstyle=(SUCCESS if var.get() else SECONDARY))

        var.trace_add("write", on_toggle)

        # Botón con margen para separarlo visualmente
        tb.Button(
            row,
            text="Eliminar",
            bootstyle=DANGER,
            command=lambda s=sym: self._remove_row(s),
        ).pack(
            side="right", padx=(200, 0)
        )  # espacio a la izquierda

    def _remove_row(self, sym: str) -> None:
        f = self._rows.pop(sym, None)
        if f:
            f.destroy()
        self._vars.pop(sym, None)

    # --------- acciones ---------
    def _add_symbol(self) -> None:
        sym = self.input_var.get().strip().upper()
        if not sym:
            return
        if sym in self._rows:
            self.input_var.set("")
            return
        self._add_row(sym, True)  # seguido por defecto
        self.input_var.set("")

    # --------- persistencia (solo al guardar) ---------
    def _save_and_restart(self) -> None:
        all_syms = list(self._rows.keys())
        if not all_syms and not messagebox.askyesno(
            "Confirmar", "No hay símbolos. ¿Continuar?"
        ):
            return

        follow_syms = [s for s, v in self._vars.items() if v.get()]
        nofollow_syms = [s for s in all_syms if s not in follow_syms]
        removed = list(self._initial_syms - set(all_syms))

        # Idempotente y en lote
        self.app.repo.upsert_many(all_syms)
        self.app.repo.set_follow_many(follow_syms, 1)
        self.app.repo.set_follow_many(nofollow_syms, 0)
        if removed:
            self.app.repo.remove_many(removed)

        self.app.restart_worker(follow_syms)
        self._initial_syms = set(all_syms)  # nuevo snapshot
        messagebox.showinfo(
            "OK", f"Seguidos: {len(follow_syms)} – Eliminados: {len(removed)}"
        )
