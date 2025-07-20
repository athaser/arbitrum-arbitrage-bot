import os
from web3 import Web3

# Set your Arbitrum RPC URL via an environment variable or directly here.
ARBITRUM_RPC = os.getenv("ARBITRUM_RPC", "https://arb1.arbitrum.io/rpc")

# Create a Web3 instance using the HTTP provider.
w3 = Web3(Web3.HTTPProvider(ARBITRUM_RPC))

if not w3.is_connected():
    print("Failed to connect to the network!")
    exit(1)

# MAGIC token address (replace with the correct address if needed)
token_address = Web3.to_checksum_address("0x539bdE0d7Dbd336b79148AA742883198BBF60342")

# Minimal ERC-20 ABI with only the decimals function.
TOKEN_ABI = '''
[
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {
                "name": "",
                "type": "uint8"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
'''

# Create the token contract instance.
token_contract = w3.eth.contract(address=token_address, abi=TOKEN_ABI)

# Call the decimals function.
decimals = token_contract.functions.decimals().call()

print("Decimals of token:", decimals)
