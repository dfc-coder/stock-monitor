import asyncio
from src.ui.widget import StockWidget
from src.data.updater import RealTimeUpdater
from src.utils.config import Config


def main():
    """Main entry point for the Stock Widget application."""
    config = Config.load()
    
    # Initialize UI components
    widget = StockWidget(config)
    
    # Start real-time updates
    updater = RealTimeUpdater(config)
    asyncio.run(updater.start(widget.update_display))


if __name__ == "__main__":
    main()
