import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_API_SECRET: str = os.getenv("BINANCE_API_SECRET", "")
    TESTNET: bool = os.getenv("TESTNET", "True").lower() == "true"

    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file")

settings = Settings()