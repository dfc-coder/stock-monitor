from __future__ import annotations

import tkinter as tk

from config import DEFAULT_TICKERS
from ui import RealtimeApp


# =========================
# Entry point
# =========================
def main() -> None:
    root = tk.Tk()
    RealtimeApp(root, tickers=DEFAULT_TICKERS)
    root.mainloop()


if __name__ == "__main__":
    main()
