import json
import os
import time
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
from web3 import Web3
from typing import Tuple, Optional

# ------------------------------------------------------------------------------
# Logging & Environment Setup
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
load_dotenv()

# ------------------------------------------------------------------------------
# Configurable Parameters (via environment variables)
# ------------------------------------------------------------------------------
SLIPPAGE_TOLERANCE: float = float(os.getenv("SLIPPAGE_TOLERANCE", "0.98"))
GAS_MULTIPLIER: float = float(os.getenv("GAS_MULTIPLIER", "1.3"))
TRADE_SIZE_MAGIC: int = int(os.getenv("TRADE_SIZE_MAGIC", "50000000").replace(",", ""))

# ------------------------------------------------------------------------------
# Environment Variables and Web3 Setup
# ------------------------------------------------------------------------------
ARBITRUM_RPC: str = os.getenv("ARBITRUM_RPC")
PRIVATE_KEY: str = os.getenv("PRIVATE_KEY")
MY_ADDRESS: str = os.getenv("WALLET_ADDRESS")
ARBITRAGE_CONTRACT_ADDRESS: str = os.getenv("ARBITRAGE_CONTRACT_ADDRESS")  # Deployed contract

w3: Web3 = Web3(Web3.WebsocketProvider(ARBITRUM_RPC))
if w3.is_connected():
    logger.info("✅ Connected to Arbitrum Network")
else:
    logger.error("❌ Connection failed!")
    exit(1)

account = w3.eth.account.from_key(PRIVATE_KEY)
w3.eth.default_account = account.address
logger.info(f"✅ Using account: {w3.eth.default_account}")

# ------------------------------------------------------------------------------
# Contract and Token Addresses (MAGIC and USDC)
# ------------------------------------------------------------------------------
UNISWAP_V3_QUOTER: str = Web3.to_checksum_address("0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6")
UNISWAP_V3_ROUTER: str = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")
SUSHISWAP_ROUTER: str = Web3.to_checksum_address("0x1b02da8cb0d097eb8d57a175b88c7d8b47997506")

# Set the tokens:
# - MAGIC: your MAGIC token address (18 decimals)
# - USDC: common Arbitrum USDC address (6 decimals)
TOKENS: dict = {
    "MAGIC": Web3.to_checksum_address("0x539bdE0d7Dbd336b79148AA742883198BBF60342"),
    "USDC":  Web3.to_checksum_address("0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"),
    "WETH":  Web3.to_checksum_address("0x82AF49447d8a07e3bd95bd0d56f35241523fbab1")

}

# Use the MAGIC-USDC pair.
PAIR: Tuple[str, str] = ("MAGIC", "USDC")

# ------------------------------------------------------------------------------
# Global Contract Instances for Pricing
# ------------------------------------------------------------------------------
SUSHI_ABI = '''
[
  {
    "name": "getAmountsOut",
    "type": "function",
    "inputs": [
      { "type": "uint256", "name": "amountIn" },
      { "type": "address[]", "name": "path" }
    ],
    "outputs": [
      { "type": "uint256[]", "name": "amounts" }
    ],
    "stateMutability": "view"
  }
]
'''

UNISWAP_QUOTER_ABI = '''
[
  {
    "name": "quoteExactInputSingle",
    "type": "function",
    "inputs": [
      { "internalType": "address", "name": "tokenIn", "type": "address" },
      { "internalType": "address", "name": "tokenOut", "type": "address" },
      { "internalType": "uint24", "name": "fee", "type": "uint24" },
      { "internalType": "uint256", "name": "amountIn", "type": "uint256" },
      { "internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160" }
    ],
    "outputs": [
      { "internalType": "uint256", "name": "amountOut", "type": "uint256" }
    ],
    "stateMutability": "view"
  }
]
'''

sushi = w3.eth.contract(address=SUSHISWAP_ROUTER, abi=json.loads(SUSHI_ABI))
# Use the already defined variable UNISWAP_V3_QUOTER here
uni_quoter = w3.eth.contract(address=UNISWAP_V3_QUOTER, abi=json.loads(UNISWAP_QUOTER_ABI))

# ------------------------------------------------------------------------------
# ABIs for other components
# ------------------------------------------------------------------------------
TOKEN_ABI = '''[
    {"constant": true, "inputs": [{"name": "owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
     "payable": false, "stateMutability": "view", "type": "function"},
    {"constant": true, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "payable": false, "stateMutability": "view", "type": "function"},
    {"constant": false, "inputs": [{"name": "spender", "type": "address"},
     {"name": "amount", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "payable": false, "stateMutability": "nonpayable", "type": "function"}
]'''

UNISWAP_ROUTER_ABI = '''[
  {
    "inputs": [
      {
        "components": [
          {"internalType": "address", "name": "tokenIn", "type": "address"},
          {"internalType": "address", "name": "tokenOut", "type": "address"},
          {"internalType": "uint24", "name": "fee", "type": "uint24"},
          {"internalType": "address", "name": "recipient", "type": "address"},
          {"internalType": "uint256", "name": "deadline", "type": "uint256"},
          {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
          {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
          {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
        ],
        "internalType": "struct ISwapRouter.ExactInputSingleParams",
        "name": "params",
        "type": "tuple"
      }
    ],
    "name": "exactInputSingle",
    "outputs": [
      {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
    ],
    "stateMutability": "payable",
    "type": "function"
  }
]'''

SUSHISWAP_ROUTER_ABI = '''[
    {
      "inputs": [
         {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
         {"internalType": "address[]", "name": "path", "type": "address[]"}
      ],
      "name": "getAmountsOut",
      "outputs": [
         {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
      ],
      "stateMutability": "view",
      "type": "function"
    },
    {"inputs":[{"internalType":"address","name":"_factory","type":"address"},
      {"internalType":"address","name":"_WETH","type":"address"}],
     "stateMutability":"nonpayable",
     "type":"constructor"},
    {"inputs":[],"name":"WETH","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view",
     "type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},
      {"internalType":"address","name":"tokenB","type":"address"},
      {"internalType":"uint256","name":"amountADesired","type":"uint256"},
      {"internalType":"uint256","name":"amountBDesired","type":"uint256"},
      {"internalType":"uint256","name":"amountAMin","type":"uint256"},
      {"internalType":"uint256","name":"amountBMin","type":"uint256"},
      {"internalType":"address","name":"to","type":"address"},
      {"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"swapExactTokensForTokens",
     "outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"nonpayable",
     "type":"function"}
]'''

# ------------------------------------------------------------------------------
# Updated Arbitrage Contract ABI
# ------------------------------------------------------------------------------
ARBITRAGE_CONTRACT_ABI = '''[
    {
      "inputs": [
        {"internalType": "address", "name": "_magic", "type": "address"},
        {"internalType": "address", "name": "_usdc", "type": "address"},
        {"internalType": "address", "name": "_uniswapRouter", "type": "address"},
        {"internalType": "address", "name": "_sushiswapRouter", "type": "address"},
        {"internalType": "uint256", "name": "_minProfit", "type": "uint256"},
        {"internalType": "uint256", "name": "_minProfitMagic", "type": "uint256"}
      ],
      "stateMutability": "nonpayable",
      "type": "constructor"
    },
    {
      "inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}],
      "name": "executeArbitrage",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}],
      "name": "executeArbitrageReverse",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}],
      "name": "executeArbitrageWithMagic",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}],
      "name": "executeArbitrageWithMagicReverse",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "withdrawUSDC",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [],
      "name": "withdrawMAGIC",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    },
    {
      "inputs": [
         {"internalType": "address", "name": "tokenAddress", "type": "address"},
         {"internalType": "uint256", "name": "amount", "type": "uint256"}
      ],
      "name": "rescueTokens",
      "outputs": [],
      "stateMutability": "nonpayable",
      "type": "function"
    }
]'''

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def get_decimals(token_symbol: str) -> int:
    if token_symbol == "MAGIC":
        return 18
    if token_symbol == "USDC":
        return 6
    return 18

def get_trade_size(token_symbol: str) -> int:
    # For USDC-based trades, use 10 USDC (10_000_000 raw units).
    if token_symbol == "MAGIC":
        return TRADE_SIZE_MAGIC
    return 10_000_000

def get_token_balance(token_symbol: str) -> float:
    token_contract = w3.eth.contract(address=TOKENS[token_symbol], abi=json.loads(TOKEN_ABI))
    balance = token_contract.functions.balanceOf(w3.eth.default_account).call()
    return balance / (10 ** get_decimals(token_symbol))

def get_raw_balance(token_symbol: str) -> int:
    token_contract = w3.eth.contract(address=TOKENS[token_symbol], abi=json.loads(TOKEN_ABI))
    return token_contract.functions.balanceOf(w3.eth.default_account).call()

def check_balances() -> Tuple[float, float]:
    try:
        magic_contract = w3.eth.contract(address=TOKENS["MAGIC"], abi=json.loads(TOKEN_ABI))
        usdc_contract = w3.eth.contract(address=TOKENS["USDC"], abi=json.loads(TOKEN_ABI))
        magic_balance = magic_contract.functions.balanceOf(w3.eth.default_account).call()
        usdc_balance = usdc_contract.functions.balanceOf(w3.eth.default_account).call()
        magic_corrected = magic_balance / (10 ** get_decimals("MAGIC"))
        usdc_corrected = usdc_balance / (10 ** get_decimals("USDC"))
        logger.info(f"💰 Wallet MAGIC Balance: {magic_corrected} MAGIC")
        logger.info(f"💰 Wallet USDC Balance: {usdc_corrected} USDC")
        return magic_corrected, usdc_corrected
    except Exception as e:
        logger.error(f"Error checking wallet balances: {e}")
        return 0, 0

def get_nonce() -> int:
    time.sleep(0.5)
    return w3.eth.get_transaction_count(w3.eth.default_account, "pending")

def check_allowance(token_symbol: str, spender: str) -> int:
    token_contract = w3.eth.contract(address=TOKENS[token_symbol], abi=json.loads(TOKEN_ABI))
    return token_contract.functions.allowance(w3.eth.default_account, spender).call()

def approve_tokens_if_needed(token_symbol: str, spender: str, required_amount: int) -> None:
    current_allowance = check_allowance(token_symbol, spender)
    if current_allowance >= required_amount:
        logger.info(f"✅ Allowance for {token_symbol} on {spender} sufficient: {current_allowance}")
        return
    try:
        token_contract = w3.eth.contract(address=TOKENS[token_symbol], abi=json.loads(TOKEN_ABI))
        nonce = get_nonce()
        txn = token_contract.functions.approve(spender, required_amount).build_transaction({
            'from': w3.eth.default_account,
            'gas': 60000,
            'gasPrice': int(w3.eth.gas_price * GAS_MULTIPLIER),
            'nonce': nonce,
        })
        signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logger.info(f"✅ Approved {token_symbol} spending on {spender}! TX Hash: {tx_hash.hex()}")
    except Exception as e:
        logger.error(f"Error approving tokens for {spender}: {e}")

def swap_on_uniswap_pair(token_in: str, token_out: str, amount_in_wei: int) -> Optional[str]:
    try:
        token_contract = w3.eth.contract(address=TOKENS[token_in], abi=json.loads(TOKEN_ABI))
        balance = token_contract.functions.balanceOf(w3.eth.default_account).call()
        if balance < amount_in_wei:
            logger.error(f"❌ Insufficient {token_in} balance for Uniswap swap.")
            return None
        router_contract = w3.eth.contract(address=UNISWAP_V3_ROUTER, abi=json.loads(UNISWAP_ROUTER_ABI))
        expected_uniswap_price, best_fee = get_uniswap_v3_price(amount_in_wei, token_in, token_out)
        if expected_uniswap_price is None or best_fee is None:
            logger.error(f"❌ Could not retrieve Uniswap price for {token_in} -> {token_out} swap with input {amount_in_wei}")
            return None
        decimals = get_decimals(token_out)
        expected_out = int(expected_uniswap_price * (10 ** decimals))
        amount_out_min = int(expected_out * SLIPPAGE_TOLERANCE)
        logger.info(f"Uniswap {token_in}->{token_out} swap: best fee tier = {best_fee}, expected_out = {expected_out}, amountOutMinimum = {amount_out_min}")
        base_fee = w3.eth.gas_price
        max_priority_fee = w3.to_wei(2, 'gwei')
        max_fee = base_fee + max_priority_fee
        txn = router_contract.functions.exactInputSingle({
            "tokenIn": TOKENS[token_in],
            "tokenOut": TOKENS[token_out],
            "fee": best_fee,
            "recipient": MY_ADDRESS,
            "deadline": int(time.time()) + 300,
            "amountIn": amount_in_wei,
            "amountOutMinimum": amount_out_min,
            "sqrtPriceLimitX96": 0
        }).build_transaction({
            "from": MY_ADDRESS,
            "gas": 80000,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
            "nonce": get_nonce()
        })
        return sign_and_send_transaction(txn)
    except Exception as e:
        logger.error(f"Error in swap_on_uniswap_pair ({token_in} -> {token_out}, input: {amount_in_wei}): {e}")
        return None

def swap_on_sushiswap_pair(token_in: str, token_out: str, amount_in_wei: int) -> Optional[str]:
    try:
        router_contract = w3.eth.contract(address=SUSHISWAP_ROUTER, abi=json.loads(SUSHISWAP_ROUTER_ABI))
        base_fee = w3.eth.gas_price
        max_priority_fee = w3.to_wei(2, 'gwei')
        max_fee = base_fee + max_priority_fee
        txn = router_contract.functions.swapExactTokensForTokens(
            amount_in_wei,
            0,
            [TOKENS[token_in], TOKENS[token_out]],
            MY_ADDRESS,
            int(time.time()) + 300
        ).build_transaction({
            "from": MY_ADDRESS,
            "gas": 80000,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
            "nonce": get_nonce()
        })
        signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logger.info(f"✅ Transaction Sent! TX Hash: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        logger.error(f"Error in swap_on_sushiswap_pair ({token_in} -> {token_out}, input: {amount_in_wei}): {e}")
        return None

def sign_and_send_transaction(txn: dict) -> Optional[str]:
    try:
        base_fee = w3.eth.gas_price
        max_priority_fee_per_gas = w3.to_wei(1, 'gwei')
        max_fee_per_gas = base_fee + max_priority_fee_per_gas
        txn.update({
            'maxPriorityFeePerGas': max_priority_fee_per_gas,
            'maxFeePerGas': max_fee_per_gas,
            'nonce': get_nonce(),
            'gas': w3.eth.estimate_gas(txn)
        })
        signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        logger.info(f"✅ Transaction Sent! TX Hash: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        logger.error(f"Error sending transaction: {e}")
        return None

def get_uniswap_v3_price(amount_in_wei: int, token_in: str, token_out: str) -> Tuple[Optional[float], Optional[int]]:
    try:
        fee_tiers = [100, 500, 3000, 10000]
        best_amount_out = 0
        best_fee: Optional[int] = None
        decimals_out = get_decimals(token_out)
        for fee in fee_tiers:
            try:
                amount_out = uni_quoter.functions.quoteExactInputSingle(
                    TOKENS[token_in],
                    TOKENS[token_out],
                    fee,
                    amount_in_wei,
                    0
                ).call()
                human_readable = amount_out / (10 ** decimals_out)
                logger.info(f"Fee tier {fee}: Received amount_out = {amount_out} ({human_readable:.6f}) for input {amount_in_wei} of {token_in} -> {token_out}")
                if amount_out > best_amount_out:
                    best_amount_out = amount_out
                    best_fee = fee
            except Exception as e:
                logger.error(f"Error quoting fee tier {fee} for {token_in} -> {token_out} with input {amount_in_wei}: {e}")
                continue
        if best_amount_out:
            computed_price = best_amount_out / (10 ** decimals_out)
            logger.info(f"Best fee tier: {best_fee}, computed price: {computed_price:.6f} for {token_in} -> {token_out}")
            return computed_price, best_fee
        else:
            logger.error("No valid price retrieved for any fee tier.")
            return None, None
    except Exception as e:
        logger.error(f"Error in get_uniswap_v3_price ({token_in}->{token_out}, input: {amount_in_wei}): {e}")
        return None, None

def get_sushiswap_price(amount_in_wei: int, token_in: str, token_out: str) -> Optional[float]:
    try:
        router_contract = w3.eth.contract(address=SUSHISWAP_ROUTER, abi=json.loads(SUSHISWAP_ROUTER_ABI))
        amounts_out = router_contract.functions.getAmountsOut(
            amount_in_wei, [TOKENS[token_in], TOKENS[token_out]]
        ).call()
        decimals_out = get_decimals(token_out)
        return amounts_out[-1] / (10 ** decimals_out)
    except Exception as e:
        logger.error(f"Error in get_sushiswap_price ({token_in} -> {token_out}, input: {amount_in_wei}): {e}")
        return None

def estimate_total_gas_fee() -> float:
    try:
        total_gas = 80000
        current_gas_price = w3.eth.gas_price
        fee_in_wei = total_gas * current_gas_price
        fee_in_eth = float(w3.from_wei(fee_in_wei, 'ether'))
        return fee_in_eth
    except Exception as e:
        logger.error(f"Error estimating gas fee: {e}")
        return 0

# ------------------------------------------------------------------------------
# Arbitrage Simulation and Execution with Four Routes
# ------------------------------------------------------------------------------
MIN_PROFIT_THRESHOLD_USDT: float = 0.01  
MAX_TRADES_PER_DAY: int = 10
trade_count: int = 0
next_reset: datetime = datetime.now() + timedelta(days=1)

def get_weth_to_usdc_rate() -> float:
    """
    Returns the conversion rate for 1 WETH to USDC (in human-readable USDC value).
    """
    amount_in = 10**18  # 1 WETH in wei
    try:
        quote, _ = get_uniswap_v3_price(amount_in, "WETH", "USDC")
        return quote if quote is not None else 0
    except Exception as e:
        logger.error(f"Error getting WETH->USDC rate: {e}")
        return 0

def simulate_round_trip_arbitrage() -> dict:
    results = {}
    # ----- Routes starting with MAGIC (trade size for MAGIC) -----
    magic_trade = get_trade_size("MAGIC")
    initial_magic = magic_trade / (10 ** get_decimals("MAGIC"))
    
    # Route A: MAGIC→USDC via Uniswap, then USDC→MAGIC via SushiSwap.
    uni_usdc = get_uniswap_v3_price(magic_trade, "MAGIC", "USDC")
    if uni_usdc[0] is None:
        route_A_profit = None
    else:
        uni_usdc_amount = uni_usdc[0]
        usdc_amount_wei_A = int(uni_usdc_amount * (10 ** get_decimals("USDC")))
        sushi_magic_received = get_sushiswap_price(usdc_amount_wei_A, "USDC", "MAGIC")
        route_A_profit = (sushi_magic_received - initial_magic) if sushi_magic_received is not None else None

    # Route B: MAGIC→USDC via SushiSwap, then USDC→MAGIC via Uniswap.
    sushi_usdc = get_sushiswap_price(magic_trade, "MAGIC", "USDC")
    if sushi_usdc is None:
        route_B_profit = None
    else:
        usdc_amount_wei_B = int(sushi_usdc * (10 ** get_decimals("USDC")))
        uni_magic = get_uniswap_v3_price(usdc_amount_wei_B, "USDC", "MAGIC")
        route_B_profit = (uni_magic[0] - initial_magic) if uni_magic[0] is not None else None

    # ----- Routes starting with USDC (trade size for USDC) -----
    usdc_trade = get_trade_size("USDC")
    initial_usdc = usdc_trade / (10 ** get_decimals("USDC"))
    
    # Route C: USDC→MAGIC via Uniswap, then MAGIC→USDC via SushiSwap.
    uni_magic_for_usdc = get_uniswap_v3_price(usdc_trade, "USDC", "MAGIC")
    if uni_magic_for_usdc[0] is None:
        route_C_profit = None
    else:
        uni_magic_amount = uni_magic_for_usdc[0]
        magic_amount_wei = int(uni_magic_amount * (10 ** get_decimals("MAGIC")))
        sushi_usdc_received = get_sushiswap_price(magic_amount_wei, "MAGIC", "USDC")
        route_C_profit = (sushi_usdc_received - initial_usdc) if sushi_usdc_received is not None else None

    # Route D: USDC→MAGIC via SushiSwap, then MAGIC→USDC via Uniswap.
    sushi_magic_for_usdc = get_sushiswap_price(usdc_trade, "USDC", "MAGIC")
    if sushi_magic_for_usdc is None:
        route_D_profit = None
    else:
        magic_amount_wei = int(sushi_magic_for_usdc * (10 ** get_decimals("MAGIC")))
        uni_usdc_for_usdc = get_uniswap_v3_price(magic_amount_wei, "MAGIC", "USDC")
        route_D_profit = (uni_usdc_for_usdc[0] - initial_usdc) if uni_usdc_for_usdc[0] is not None else None

    # For routes A and B, convert profit (in MAGIC) to USDC.
    magic_to_usdc_rate, _ = get_uniswap_v3_price(10**18, "MAGIC", "USDC")
    if magic_to_usdc_rate is None:
        magic_to_usdc_rate = 1
    route_A_profit_usdc = route_A_profit * magic_to_usdc_rate if route_A_profit is not None else None
    route_B_profit_usdc = route_B_profit * magic_to_usdc_rate if route_B_profit is not None else None

    # Routes C and D are already in USDC terms.
    net_profit_A = route_A_profit_usdc
    net_profit_B = route_B_profit_usdc
    net_profit_C = route_C_profit
    net_profit_D = route_D_profit

    # Estimate gas fee in ETH and convert to USDC.
    gas_fee_eth = estimate_total_gas_fee()
    weth_to_usdc_rate = get_weth_to_usdc_rate()
    gas_fee_usdc = gas_fee_eth * weth_to_usdc_rate

    net_profit_A = net_profit_A - gas_fee_usdc if net_profit_A is not None else None
    net_profit_B = net_profit_B - gas_fee_usdc if net_profit_B is not None else None
    net_profit_C = net_profit_C - gas_fee_usdc if net_profit_C is not None else None
    net_profit_D = net_profit_D - gas_fee_usdc if net_profit_D is not None else None

    if net_profit_A is not None:
        logger.info(f"Route A (MAGIC→USDC via Uniswap, USDC→MAGIC via SushiSwap): Net profit = {net_profit_A:.2f} USDC")
    else:
        logger.info("Route A simulation failed.")

    if net_profit_B is not None:
        logger.info(f"Route B (MAGIC→USDC via SushiSwap, USDC→MAGIC via Uniswap): Net profit = {net_profit_B:.2f} USDC")
    else:
        logger.info("Route B simulation failed.")

    if net_profit_C is not None:
        logger.info(f"Route C (USDC→MAGIC via Uniswap, MAGIC→USDC via SushiSwap): Net profit = {net_profit_C:.2f} USDC")
    else:
        logger.info("Route C simulation failed.")

    if net_profit_D is not None:
        logger.info(f"Route D (USDC→MAGIC via SushiSwap, MAGIC→USDC via Uniswap): Net profit = {net_profit_D:.2f} USDC")
    else:
        logger.info("Route D simulation failed.")

    results["A"] = net_profit_A
    results["B"] = net_profit_B
    results["C"] = net_profit_C
    results["D"] = net_profit_D
    return results

def reset_trade_counter_if_needed() -> None:
    global trade_count, next_reset
    if datetime.now() >= next_reset:
        trade_count = 0
        next_reset = datetime.now() + timedelta(days=1)
        logger.info("Trade counter reset for new day.")

# ------------------------------------------------------------------------------
# New helper: Get contract USDC balance.
# ------------------------------------------------------------------------------
def get_contract_usdc_balance() -> float:
    try:
        usdc_contract = w3.eth.contract(address=TOKENS["USDC"], abi=json.loads(TOKEN_ABI))
        balance = usdc_contract.functions.balanceOf(ARBITRAGE_CONTRACT_ADDRESS).call()
        contract_balance = balance / (10 ** get_decimals("USDC"))
        logger.info(f"💰 Contract USDC Balance: {contract_balance} USDC")
        return contract_balance
    except Exception as e:
        logger.error(f"Error checking contract USDC balance: {e}")
        return 0

# ------------------------------------------------------------------------------
# New helper: Get contract MAGIC balance.
# ------------------------------------------------------------------------------
def get_contract_magic_balance() -> float:
    try:
        magic_contract = w3.eth.contract(address=TOKENS["MAGIC"], abi=json.loads(TOKEN_ABI))
        balance = magic_contract.functions.balanceOf(ARBITRAGE_CONTRACT_ADDRESS).call()
        contract_balance = balance / (10 ** get_decimals("MAGIC"))
        logger.info(f"💰 Contract MAGIC Balance: {contract_balance} MAGIC")
        return contract_balance
    except Exception as e:
        logger.error(f"Error checking contract MAGIC balance: {e}")
        return 0

# ------------------------------------------------------------------------------
# Modified Trade Execution: Call the Smart Contract Directly
# ------------------------------------------------------------------------------
def execute_arbitrage_trade(direction: str) -> Optional[str]:
    nonce = get_nonce()
    contract_instance = w3.eth.contract(address=ARBITRAGE_CONTRACT_ADDRESS, abi=json.loads(ARBITRAGE_CONTRACT_ABI))
    
    # Mapping based on direction:
    # Route A: MAGIC-based → executeArbitrageWithMagic
    # Route B: MAGIC-based reverse → executeArbitrageWithMagicReverse
    # Route C: USDC-based → executeArbitrageReverse
    # Route D: USDC-based → executeArbitrage
    if direction in ["A", "B"]:
        trade_size = get_trade_size("MAGIC")
        if trade_size == 0:
            logger.error("Trade size is 0 for MAGIC-based trade.")
            return None
        if direction == "A":
            logger.info("Executing Route A via smart contract: MAGIC → USDC on Uniswap V3 then USDC → MAGIC on SushiSwap.")
            txn = contract_instance.functions.executeArbitrageWithMagic(trade_size).build_transaction({
                'from': MY_ADDRESS,
                'gas': 80000,
                'gasPrice': int(w3.eth.gas_price * GAS_MULTIPLIER),
                'nonce': nonce,
            })
        else:  # direction == "B"
            logger.info("Executing Route B via smart contract: MAGIC → USDC on SushiSwap then USDC → MAGIC on Uniswap V3.")
            txn = contract_instance.functions.executeArbitrageWithMagicReverse(trade_size).build_transaction({
                'from': MY_ADDRESS,
                'gas': 80000,
                'gasPrice': int(w3.eth.gas_price * GAS_MULTIPLIER),
                'nonce': nonce,
            })
    elif direction in ["C", "D"]:
        trade_size = get_trade_size("USDC")
        if trade_size == 0:
            logger.error("Trade size is 0 for USDC-based trade.")
            return None
        if direction == "C":
            logger.info("Executing Route C via smart contract: USDC → MAGIC on Uniswap V3 then MAGIC → USDC on SushiSwap.")
            txn = contract_instance.functions.executeArbitrageReverse(trade_size).build_transaction({
                'from': MY_ADDRESS,
                'gas': 80000,
                'gasPrice': int(w3.eth.gas_price * GAS_MULTIPLIER),
                'nonce': nonce,
            })
        else:  # direction == "D"
            logger.info("Executing Route D via smart contract: USDC → MAGIC on SushiSwap then MAGIC → USDC on Uniswap V3.")
            txn = contract_instance.functions.executeArbitrage(trade_size).build_transaction({
                'from': MY_ADDRESS,
                'gas': 80000,
                'gasPrice': int(w3.eth.gas_price * GAS_MULTIPLIER),
                'nonce': nonce,
            })
    else:
        logger.error("Invalid direction specified for arbitrage trade.")
        return None

    signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    logger.info(f"✅ Arbitrage transaction sent via contract! TX Hash: {tx_hash.hex()}")
    return tx_hash.hex()

def check_and_execute_arbitrage() -> None:
    global trade_count
    reset_trade_counter_if_needed()

    route_profits = simulate_round_trip_arbitrage()
    valid_routes = {k: v for k, v in route_profits.items() if v is not None}
    if not valid_routes:
        logger.info("No valid arbitrage route simulation available.")
        return

    best_route = max(valid_routes, key=valid_routes.get)
    best_profit = valid_routes[best_route]
    logger.info(f"Best arbitrage route: {best_route} with net profit {best_profit:.2f} USDC.")

    if best_profit > 0:
        # Check the appropriate contract collateral based on the route.
        if best_route in ["A", "B"]:
            if get_contract_magic_balance() == 0:
                logger.warning("⚠️ Contract MAGIC balance is zero! Stopping arbitrage trades.")
                return
        elif best_route in ["C", "D"]:
            if get_contract_usdc_balance() == 0:
                logger.warning("⚠️ Contract USDC balance is zero! Stopping arbitrage trades.")
                return

        logger.info(f"💰 Profitable arbitrage opportunity detected (Route {best_route}). Triggering trade.")
        execute_arbitrage_trade(best_route)
        trade_count += 1
        logger.info(f"Trade executed. Trade count for today: {trade_count}")
    else:
        logger.info("⚖️ No profitable arbitrage opportunity detected based on simulation.")

# ------------------------------------------------------------------------------
# Function to print the SushiSwap MAGIC/USDC pool address
# ------------------------------------------------------------------------------
def print_sushiswap_pool_address() -> None:
    SUSHISWAP_FACTORY_ADDRESS = Web3.to_checksum_address("0xc35DADB65012eC5796536bD9864eD8773aBc74C4")
    SUSHISWAP_FACTORY_ABI = '''[
        {
            "constant": true,
            "inputs": [
                {"internalType": "address", "name": "", "type": "address"},
                {"internalType": "address", "name": "", "type": "address"}
            ],
            "name": "getPair",
            "outputs": [{"internalType": "address", "name": "", "type": "address"}],
            "payable": false,
            "stateMutability": "view",
            "type": "function"
        }
    ]'''
    factory_contract = w3.eth.contract(address=SUSHISWAP_FACTORY_ADDRESS, abi=json.loads(SUSHISWAP_FACTORY_ABI))
    pool_address = factory_contract.functions.getPair(TOKENS["MAGIC"], TOKENS["USDC"]).call()
    logger.info(f"SushiSwap MAGIC/USDC pool address: {pool_address}")

# ------------------------------------------------------------------------------
# Logging Filter for Successful Transactions
# ------------------------------------------------------------------------------
class SuccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return ("Trade executed" in msg) or ("Arbitrage transaction sent" in msg)

success_handler = logging.FileHandler('successful_transactions.log')
success_handler.setLevel(logging.INFO)
success_handler.addFilter(SuccessFilter())
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
success_handler.setFormatter(formatter)
logger.addHandler(success_handler)

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print_sushiswap_pool_address()
    while True:
        check_and_execute_arbitrage()
        time.sleep(10)
