from __future__ import annotations

import tkinter as tk
from pathlib import Path
from ui import RealtimeApp
from db.tickers import TickerRepository


def main() -> None:
    root = tk.Tk()

    # ruta siempre relativa a la carpeta "src"
    db_path = Path(__file__).resolve().parent / "data" / "tickers.db"

    repo = TickerRepository(db_path)

    RealtimeApp(root, repo)
    root.mainloop()


if __name__ == "__main__":
    main()
