
# Binance Futures Testnet Setup Guide

This guide will walk you through setting up a Binance Futures Testnet account and configuring the bot to connect to it.

## Step 1: Create a Testnet Account

1.  **Go to the Testnet Website:** Open your web browser and navigate to [https://testnet.binancefuture.com](https://testnet.binancefuture.com).
2.  **Register:** Click on "Register" and create a new account. This account is separate from your real Binance account and uses test funds only.
3.  **Verify Your Email:** Complete the registration process by verifying your email address.

## Step 2: Get Testnet Funds

Once logged in, your account should be automatically credited with testnet assets (like USDT, BTC, ETH). If you need more, look for a "Faucet" or "Add Assets" button on the testnet interface to get more free test funds.

## Step 3: Generate API Credentials

1.  **Navigate to API Management:** While logged into the testnet site, find your user profile icon and click on "API Management".
2.  **Create a New API Key:**
    *   Give your API key a label, for example, `trading-bot`.
    *   Click "Create API".
    *   Complete any security verification required (2FA, email).
3.  **Save Your Keys:**
    *   Binance will now display your **API Key** and **Secret Key**.
    *   **IMPORTANT:** The Secret Key is shown only once. Copy both keys and save them somewhere secure immediately. You will need them in the next step.
4.  **Check Restrictions:** For this bot, ensure that "Enable Futures" is checked. For security, you can leave "Enable Withdrawals" unchecked.

## Step 4: Configure The Bot

1.  **Clone the Repository:** If you haven't already, clone the bot's source code to your local machine.
    ```bash
    git clone https://github.com/your-repo/binance-trading-bot.git
    cd binance-trading-bot
    ```

2.  **Create the Environment File:** In the root directory of the project, you will find a file named `.env.example`. Make a copy of this file and name it `.env`.
    ```bash
    # On Windows
    copy .env.example .env

    # On macOS / Linux
    cp .env.example .env
    ```

3.  **Edit the `.env` File:** Open the new `.env` file in a text editor. You will see the following content:
    ```
    BINANCE_API_KEY="YOUR_API_KEY"
    BINANCE_API_SECRET="YOUR_API_SECRET"

    # Set to True for testnet, False for mainnet
    TESTNET=True
    ```
    *   Replace `YOUR_API_KEY` with the API Key you saved from Binance.
    *   Replace `YOUR_API_SECRET` with the Secret Key you saved.
    *   Ensure `TESTNET` is set to `True`.

## Step 5: Install Dependencies and Run

1.  **Install Python packages:** Make sure you have Python 3.9 or newer installed. Then, run the following command in the project's root directory:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the bot:**
    ```bash
    python src/main.py
    ```

If everything is configured correctly, you should see the bot's main menu appear in your terminal, showing a connection to the TESTNET account.

## Troubleshooting

*   **Error: Invalid API Key:**
    *   Double-check that the API Key and Secret in your `.env` file are copied exactly, with no extra spaces or characters.
    *   Ensure the API key is not restricted by IP address on the Binance website (unless you have configured a static IP).

*   **Error: Timestamp for this request is outside of the recvWindow:**
    *   This means your computer's system clock is out of sync with Binance's servers. You need to synchronize it. On most operating systems, you can do this through your Date & Time settings by enabling automatic time synchronization with an internet time server.

*   **Error: Insufficient Balance:**
    *   Make sure you have sufficient testnet funds in your Futures wallet on the Binance Testnet website.
