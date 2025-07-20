import json
import os
import logging
from web3 import Web3
from dotenv import load_dotenv

# ------------------------------------------------------------------------------
# Logging & Environment Setup
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)
load_dotenv()

# ------------------------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------------------------
ARBITRUM_RPC = os.getenv("ARBITRUM_RPC")
ARBITRAGE_CONTRACT_ADDRESS = os.getenv("ARBITRAGE_CONTRACT_ADDRESS")
# USDC address that was set in your contract constructor (the "correct" USDC)
CORRECT_USDC_ADDRESS = os.getenv("CORRECT_USDC_ADDRESS")  # e.g. 0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8
# USDC address to which you mistakenly sent tokens
WRONG_USDC_ADDRESS = os.getenv("WRONG_USDC_ADDRESS")      # e.g. 0xaf88d065e77c8cC2239327C5EDb3A432268e5831

if not ARBITRUM_RPC or not ARBITRAGE_CONTRACT_ADDRESS or not CORRECT_USDC_ADDRESS or not WRONG_USDC_ADDRESS:
    logger.error("Missing one or more required environment variables: ARBITRUM_RPC, ARBITRAGE_CONTRACT_ADDRESS, CORRECT_USDC_ADDRESS, WRONG_USDC_ADDRESS")
    exit(1)

# ------------------------------------------------------------------------------
# Web3 Setup
# ------------------------------------------------------------------------------
w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))
if w3.is_connected():
    logger.info("✅ Connected to Arbitrum Network")
else:
    logger.error("❌ Connection to Arbitrum Network failed!")
    exit(1)

# ------------------------------------------------------------------------------
# Standard ERC-20 ABI (for balanceOf)
# ------------------------------------------------------------------------------
TOKEN_ABI = json.loads(r'''[
    {
      "constant": true,
      "inputs": [{"name": "account", "type": "address"}],
      "name": "balanceOf",
      "outputs": [{"name": "", "type": "uint256"}],
      "type": "function"
    }
]''')

# ------------------------------------------------------------------------------
# Convert Addresses to Checksum Format
# ------------------------------------------------------------------------------
contract_address = Web3.to_checksum_address(ARBITRAGE_CONTRACT_ADDRESS)
correct_usdc = Web3.to_checksum_address(CORRECT_USDC_ADDRESS)
wrong_usdc = Web3.to_checksum_address(WRONG_USDC_ADDRESS)

# ------------------------------------------------------------------------------
# Create Token Contract Instances
# ------------------------------------------------------------------------------
correct_usdc_contract = w3.eth.contract(address=correct_usdc, abi=TOKEN_ABI)
wrong_usdc_contract = w3.eth.contract(address=wrong_usdc, abi=TOKEN_ABI)

# ------------------------------------------------------------------------------
# Check the Balances
# ------------------------------------------------------------------------------
balance_correct = correct_usdc_contract.functions.balanceOf(contract_address).call()
balance_wrong = wrong_usdc_contract.functions.balanceOf(contract_address).call()

logger.info(f"Contract Balance for Correct USDC ({correct_usdc}): {balance_correct} (in token smallest units)")
logger.info(f"Contract Balance for Mistaken USDC ({wrong_usdc}): {balance_wrong} (in token smallest units)")

# ------------------------------------------------------------------------------
# Analysis & Next Steps
# ------------------------------------------------------------------------------
logger.info("------------------------------------------------------------------")
logger.info("Analysis:")
logger.info("Your contract’s withdraw function (withdrawUSDC) only transfers tokens from the USDC")
logger.info("address hardcoded at deployment (the correct USDC).")
logger.info("Since you sent tokens to a different USDC contract address (the mistaken address),")
logger.info("these tokens are not accessible via the withdraw function.")
logger.info("")
logger.info("Without a generic rescue function (e.g., rescueERC20) in your contract,")
logger.info("the tokens sent to the wrong address are locked in the contract and cannot be recovered.")
logger.info("------------------------------------------------------------------")
