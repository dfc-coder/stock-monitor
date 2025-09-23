import os
from typing import Optional, Set
from dotenv import load_dotenv, dotenv_values


class Config:
    """
    Global configuration class.
    - `Config.load()` loads .env (from DOTENV_PATH or .env) and returns a singleton.
    - `Config()` (direct) reads ONLY current os.environ and, por defecto, IGNORA
      las variables que fueron inyectadas previamente desde .env por `Config.load()`,
      para que los tests puedan verificar valores por defecto sin interferencia.
    """

    _instance: Optional["Config"] = None
    _dotenv_keys: Set[str] = set()

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    MARKET_TIMEZONE: str
    MAX_TICKERS: int

    def __init__(self, *, ignore_dotenv_env: bool = True) -> None:
        def read(key: str, default: str) -> str:
            # Si ignore_dotenv_env=True y la clave provino del .env cargado, ignoramos su valor del entorno.
            if ignore_dotenv_env and key in Config._dotenv_keys:
                return default
            return os.getenv(key, default)

        self.DB_HOST = read("DB_HOST", "localhost")
        self.DB_PORT = int(read("DB_PORT", "5432"))
        self.DB_NAME = read("DB_NAME", "stock_widget")
        self.DB_USER = read("DB_USER", "default_user")
        self.DB_PASSWORD = read("DB_PASSWORD", "")
        self.MARKET_TIMEZONE = read("MARKET_TIMEZONE", "America/New_York")
        self.MAX_TICKERS = int(read("MAX_TICKERS", "100"))

    @classmethod
    def load(cls) -> "Config":
        """Load singleton reading .env exactly once."""
        if cls._instance is None:
            dotenv_path = os.getenv("DOTENV_PATH", ".env")
            # Guardamos las claves definidas en .env para poder distinguirlas luego.
            try:
                values = dotenv_values(dotenv_path) or {}
                cls._dotenv_keys = set(values.keys())
            except Exception:
                cls._dotenv_keys = set()
            # Carga real de .env (no pisa variables existentes por defecto)
            load_dotenv(dotenv_path)
            cls._instance = cls(ignore_dotenv_env=False)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton and known dotenv keys (useful for tests)."""
        cls._instance = None
        cls._dotenv_keys = set()
