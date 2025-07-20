# 🤖 Arbitrum Arbitrage Bot

This project contains a real-time arbitrage bot designed for a specific trading pair: **MAGIC/USDC** on the Arbitrum network.  
It identifies profitable price differences between Uniswap V3 and SushiSwap and executes atomic swaps via a custom smart contract.

While the current version is tailored for the MAGIC/USDC pair, the same logic can be reused to support additional trading pairs by:
- Adjusting token addresses and decimals
- Deploying new smart contracts per pair (if preferred)
- Reusing or duplicating the existing bot logic with minor modifications

---

## 🔧 Features

- ✅ Built for **Arbitrum One**
- 🔄 Scans **4 arbitrage routes**:
  - MAGIC → USDC (Uniswap) → MAGIC (SushiSwap)
  - MAGIC → USDC (SushiSwap) → MAGIC (Uniswap)
  - USDC → MAGIC (Uniswap) → USDC (SushiSwap)
  - USDC → MAGIC (SushiSwap) → USDC (Uniswap)
- 🤝 Uses deployed **smart contract** for atomic arbitrage
- 💰 Dynamic gas + slippage-aware execution
- 🔗 Web3 connection via **Alchemy RPC + MetaMask wallet**
- 🧪 Simulates all routes and logs only profitable trades

---

## 📁 Project Structure

```
.
├── bot/
│   ├── arbitrage_bot.py         # Main logic (4-route arbitrage loop)
│   ├── get_decimals.py          # Token decimal checker (MAGIC, USDC)
│   └── withdraw.py              # Rescue logic for incorrect token addresses
├── contracts/
│   └── ArbitrageExecutor.sol    # Smart contract for executing swaps
├── .env.example                 # Template for secrets (.env is ignored)
├── .gitignore
├── LICENSE                      # MIT license
├── requirements.txt             # Python dependencies
└── README.md
```

---

## ⚙️ Requirements

- Python 3.8+
- An [Alchemy](https://www.alchemy.com/) WebSocket endpoint for Arbitrum
- MetaMask wallet (private key & address)

---

## 🚀 Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create your `.env` file**
   ```bash
   cp .env.example .env
   ```

3. **Fill in your `.env` with values from MetaMask + Alchemy**
   - `PRIVATE_KEY` and `WALLET_ADDRESS` from MetaMask
   - `ARBITRUM_RPC` from Alchemy dashboard
   - `ARBITRAGE_CONTRACT_ADDRESS` after deploying contract (see below)

4. **Run the bot**
   ```bash
   python bot/arbitrage_bot.py
   ```

---

## 🛠 Smart Contract Deployment

This repo uses a custom `ArbitrageExecutor.sol` smart contract.

> 🧠 The contract is designed for deployment using **MetaMask + Remix**.

### Deployment steps:

1. Open [Remix](https://remix.ethereum.org/)
2. Paste in the code from `contracts/ArbitrageExecutor.sol`
3. Compile the contract
4. Use the **Deploy & Run** tab:
   - Set environment to **Injected Web3**
   - Connect to **MetaMask on Arbitrum**
   - Enter constructor params (MAGIC, USDC, routers, min profit)
   - Click **Deploy**

Copy the contract address into your `.env` file:
```env
ARBITRAGE_CONTRACT_ADDRESS=0xYourContractAddress
```

---

## 🧯 Recovering Funds (optional)

If you accidentally send USDC to the wrong token address in the contract:
- Use `withdraw.py` to detect token balances by contract address
- Ensure your smart contract includes a `rescueTokens()` function (already included)

---

## 🛡 Security Notes

- Never commit your `.env` file
- Use a MetaMask wallet with limited funds for testing
- Confirm deployed contract addresses before running the bot

---

## 💡 Contribute / Reality Check

---

## 💡 Contribute / Reality Check

> “Arbitrage sounds easy — until you factor in gas fees, slippage, and MEV bots.”

This bot was originally built to test real-world arbitrage using the **MAGIC/USDC** pair on Arbitrum.  
Among all tested combinations, **MAGIC/USDC was the most promising** in terms of volatility and route spreads — but even then, **profitable opportunities were extremely rare** once gas and slippage were factored in.

The following pairs were also tested with the same logic:
- MAGIC/ETH – high slippage, low liquidity
- SPELL/WETH – very low volume
- USDC/WBTC – stable, but rare deviation
- USDC/WETH – frequent trades, but MEV bots dominate
- USDCE/WETH – similar to USDC, used for edge testing
- USDT/WETH – good volume, but tightly correlated pricing


If you're a Web3 dev, quant, or someone who’s battled this problem before:
- 💬 Reach out or fork the project
- 🧠 Share strategies (MEV, Flashbots, multi-pair logic)
- 🔥 Help make this bot smarter, faster, and maybe... actually profitable

Let’s go broke trying together — or rich, who knows. 🚀


## 📚 Resources

Useful links to help you run, deploy, or inspect this bot on the Arbitrum network:

### Infrastructure
- 🔌 **Alchemy (Arbitrum RPC provider):** https://www.alchemy.com/
- 🦊 **MetaMask (Wallet):** https://metamask.io/
- 🔍 **Arbiscan (Arbitrum block explorer):** https://arbiscan.io/
- 🧱 **Remix (Smart contract IDE):** https://remix.ethereum.org/

### Contracts & Token Tools
- 📜 **Uniswap V3 Docs:** https://docs.uniswap.org/
- 🍣 **SushiSwap Docs:** https://docs.sushi.com/
- 🧮 **Web3.py Docs:** https://web3py.readthedocs.io/

### Deployment Networks
- 🌉 **Arbitrum One Bridge:** https://bridge.arbitrum.io/
- 📈 **Arbitrum Status Monitor:** https://status.arbitrum.io/

---


## 📜 License

This project is licensed under the MIT License — see [`LICENSE`](./LICENSE).

---

## 📬 Contact

This project is maintained anonymously.  
Feel free to fork and adapt — contributions welcome!