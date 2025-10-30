import os
from dotenv import load_dotenv
from binance import AsyncClient
import asyncio

load_dotenv()

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
testnet = os.getenv("TESTNET", "True").lower() in ("true", "1", "t")

async def check_api():
    print(f"Using API Key: {api_key[:5]}...{api_key[-5:]}")
    print(f"Using Testnet: {testnet}")
    try:
        client = await AsyncClient.create(api_key, api_secret, testnet=testnet)
        account_info = await client.futures_account_balance()
        print("API connection successful!")
        print("Account Balance:")
        for balance in account_info:
            if float(balance['balance']) > 0:
                print(f"  {balance['asset']}: {balance['balance']}")
        await client.close_connection()
    except Exception as e:
        print(f"API connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_api())
