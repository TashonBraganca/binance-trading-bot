# Binance Futures Testnet Setup Guide

## Step 1: Create Testnet Account

1. Visit: https://testnet.binancefuture.com
2. Click "Register" (top-right)
3. Complete registration (email + password)
4. Verify email address

## Step 2: Generate API Credentials

1. Login to testnet
2. Click your profile icon → "API Management"
3. Click "Create API"
4. Name it: "Trading Bot"
5. Complete 2FA verification
6. **SAVE YOUR API KEY & SECRET** (secret shown once only)

## Step 3: Enable Futures Trading

1. On testnet dashboard, click "Activate" for Futures
2. You'll receive 10,000 USDT testnet balance
3. Navigate to "Futures" section to verify

## Step 4: Configure Bot

```bash
# Create .env file
cp .env.example .env

# Edit .env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_key_here
TESTNET=True
```

## Step 5: Test Connection

```bash
python src/main.py --test-connection
```

Should output:
```
✓ API connection successful
✓ Account balance: 10,000 USDT
✓ Testnet mode: ACTIVE
```

## Troubleshooting

**Error: Invalid API Key**
- Verify key copied correctly (no spaces)
- Ensure API Management shows "Enabled"

**Error: Timestamp Error**
- Your system time is off
- Run: `sudo ntpdate -s time.nist.gov` (Linux/Mac)

**Error: Insufficient Balance**
- Request more testnet funds: https://testnet.binancefuture.com/en/support