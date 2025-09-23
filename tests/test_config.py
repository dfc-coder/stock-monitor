import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
import pytest
from unittest.mock import patch
from utils.config import Config


class TestConfig:
    """Test suite for the Config class."""
    
    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path):
        """Create a temporary .env file for testing."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "DB_HOST=testhost\n"
            "DB_PORT=9999\n"
            "DB_NAME=testdb\n"
            "DB_USER=testuser\n"
            "DB_PASSWORD=testpass\n"
            "MARKET_TIMEZONE=Europe/London\n"
            "MAX_TICKERS=50"
        )
        os.environ["DOTENV_PATH"] = str(env_file)
        yield
        # Cleanup
        if "DOTENV_PATH" in os.environ:
            del os.environ["DOTENV_PATH"]
    
    def test_config_loading(self):
        """Test that configuration loads correctly from environment."""
        config = Config.load()
        
        assert config.DB_HOST == "testhost"
        assert config.DB_PORT == 9999
        assert config.DB_NAME == "testdb"
        assert config.DB_USER == "testuser"
        assert config.DB_PASSWORD == "testpass"
        assert config.MARKET_TIMEZONE == "Europe/London"
        assert config.MAX_TICKERS == 50
    
    def test_singleton_pattern(self):
        """Test that Config uses singleton pattern."""
        config1 = Config.load()
        config2 = Config.load()
        
        assert config1 is config2
    
    def test_default_values(self):
        """Test that default values are used when env vars are missing."""
        # Clear specific env vars
        os.environ.pop("DB_HOST", None)
        os.environ.pop("DB_PORT", None)
        
        config = Config()
        
        assert config.DB_HOST == "localhost"
        assert config.DB_PORT == 5432
        assert config.MAX_TICKERS == 100
