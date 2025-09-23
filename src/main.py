"""
Stock Widget Application - Main Entry Point

This is the main entry point for the Stock Widget application.
It initializes the UI and starts the real-time data updates.
"""
from utils.config import Config


def main():
    """Main entry point for the Stock Widget application."""
    # Load configuration
    config = Config.load()

    # TODO: Initialize UI components
    # TODO: Start real-time updates

    print("Stock Widget application started successfully!")
    print(f"Configuration loaded: DB={config.DB_NAME}, Max Tickers={config.MAX_TICKERS}")


if __name__ == "__main__":
    main()
