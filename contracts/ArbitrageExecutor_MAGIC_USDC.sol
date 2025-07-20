// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address recipient, uint256 amount) external returns (bool);
}

interface ISushiSwapRouter {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
}

interface IUniswapV3Router {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }
    function exactInputSingle(ExactInputSingleParams calldata params) external payable returns (uint256 amountOut);
}

contract ArbitrageExecutor {
    // Immutable variables to reduce gas and enforce constant settings after deployment.
    address public immutable owner;
    address public immutable usdc;
    address public immutable magic;
    address public immutable uniswapRouter;
    address public immutable sushiswapRouter;
    uint256 public immutable minProfit;      // Minimum profit threshold in USDC (smallest units)
    uint256 public immutable minProfitMagic; // Minimum profit threshold in MAGIC (smallest units)

    // Robust reentrancy guard.
    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status;

    modifier nonReentrant() {
        require(_status != _ENTERED, "Reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this");
        _;
    }

    constructor(
        address _usdc,
        address _magic,
        address _uniswapRouter,
        address _sushiswapRouter,
        uint256 _minProfit,
        uint256 _minProfitMagic
    ) {
        require(_usdc != address(0), "Invalid USDC address");
        require(_magic != address(0), "Invalid MAGIC address");
        require(_uniswapRouter != address(0), "Invalid Uniswap Router address");
        require(_sushiswapRouter != address(0), "Invalid SushiSwap Router address");
        require(_minProfit > 0, "minProfit must be > 0");
        require(_minProfitMagic > 0, "minProfitMagic must be > 0");

        owner = msg.sender;
        usdc = _usdc;
        magic = _magic;
        uniswapRouter = _uniswapRouter;
        sushiswapRouter = _sushiswapRouter;
        minProfit = _minProfit;
        minProfitMagic = _minProfitMagic;
        
        _status = _NOT_ENTERED;
    }

    //////////////////////////////
    // USDC-based Arbitrage
    //////////////////////////////

    // Executes arbitrage: USDC -> MAGIC on SushiSwap then MAGIC -> USDC on Uniswap V3.
    function executeArbitrage(uint256 amountIn) external onlyOwner nonReentrant {
        require(amountIn > 0, "amountIn must be > 0");

        uint256 initialUSDC = IERC20(usdc).balanceOf(address(this));
        require(initialUSDC >= amountIn, "Insufficient USDC balance");

        // Approve SushiSwap Router to spend USDC.
        require(IERC20(usdc).approve(sushiswapRouter, amountIn), "USDC approval failed");

        // Swap USDC to MAGIC on SushiSwap.
        address[] memory path = new address[](2);
        path[0] = usdc;
        path[1] = magic;
        uint[] memory amounts = ISushiSwapRouter(sushiswapRouter).swapExactTokensForTokens(
            amountIn,
            0, // Minimal output, adjust for slippage control.
            path,
            address(this),
            block.timestamp + 300
        );
        require(amounts.length > 1, "Invalid swap output");
        uint256 magicReceived = amounts[amounts.length - 1];
        require(magicReceived > 0, "No MAGIC received");

        // Approve Uniswap Router to spend MAGIC.
        require(IERC20(magic).approve(uniswapRouter, magicReceived), "MAGIC approval failed");

        // Swap MAGIC back to USDC on Uniswap V3.
        IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router.ExactInputSingleParams({
            tokenIn: magic,
            tokenOut: usdc,
            fee: 3000,
            recipient: address(this),
            deadline: block.timestamp + 300,
            amountIn: magicReceived,
            amountOutMinimum: 0, // Minimal output, adjust for slippage control.
            sqrtPriceLimitX96: 0
        });
        uint256 usdcReceived = IUniswapV3Router(uniswapRouter).exactInputSingle(params);
        require(usdcReceived > 0, "No USDC received");

        // Ensure the trade is profitable.
        require(usdcReceived >= initialUSDC + minProfit, "Arbitrage not profitable");

        // Transfer profit to owner.
        uint256 finalUSDC = IERC20(usdc).balanceOf(address(this));
        uint256 profit = finalUSDC - initialUSDC;
        require(profit >= minProfit, "Profit below threshold");
        require(IERC20(usdc).transfer(owner, profit), "Profit transfer failed");
    }

    // Executes reverse arbitrage: USDC -> MAGIC on Uniswap V3 then MAGIC -> USDC on SushiSwap.
    function executeArbitrageReverse(uint256 amountIn) external onlyOwner nonReentrant {
        require(amountIn > 0, "amountIn must be > 0");

        uint256 initialUSDC = IERC20(usdc).balanceOf(address(this));
        require(initialUSDC >= amountIn, "Insufficient USDC balance");

        // Approve Uniswap Router to spend USDC.
        require(IERC20(usdc).approve(uniswapRouter, amountIn), "USDC approval failed");

        // Swap USDC to MAGIC on Uniswap V3.
        IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router.ExactInputSingleParams({
            tokenIn: usdc,
            tokenOut: magic,
            fee: 3000,
            recipient: address(this),
            deadline: block.timestamp + 300,
            amountIn: amountIn,
            amountOutMinimum: 0, // Minimal output, adjust for slippage control.
            sqrtPriceLimitX96: 0
        });
        uint256 magicReceived = IUniswapV3Router(uniswapRouter).exactInputSingle(params);
        require(magicReceived > 0, "No MAGIC received");

        // Approve SushiSwap Router to spend MAGIC.
        require(IERC20(magic).approve(sushiswapRouter, magicReceived), "MAGIC approval failed");

        // Swap MAGIC back to USDC on SushiSwap.
        address[] memory path = new address[](2);
        path[0] = magic;
        path[1] = usdc;
        uint[] memory amounts = ISushiSwapRouter(sushiswapRouter).swapExactTokensForTokens(
            magicReceived,
            0, // Minimal output, adjust for slippage control.
            path,
            address(this),
            block.timestamp + 300
        );
        require(amounts.length > 1, "Invalid swap output");
        uint256 usdcReceived = amounts[amounts.length - 1];
        require(usdcReceived > 0, "No USDC received");

        // Ensure the trade is profitable.
        require(usdcReceived >= initialUSDC + minProfit, "Arbitrage not profitable");

        // Transfer profit to owner.
        uint256 finalUSDC = IERC20(usdc).balanceOf(address(this));
        uint256 profit = finalUSDC - initialUSDC;
        require(profit >= minProfit, "Profit below threshold");
        require(IERC20(usdc).transfer(owner, profit), "Profit transfer failed");
    }

    //////////////////////////////
    // MAGIC-based Arbitrage
    //////////////////////////////

    // Executes arbitrage starting with MAGIC:
    // Swap MAGIC -> USDC on Uniswap V3 then USDC -> MAGIC on SushiSwap.
    function executeArbitrageWithMagic(uint256 amountIn) external onlyOwner nonReentrant {
        require(amountIn > 0, "amountIn must be > 0");

        uint256 initialMAGIC = IERC20(magic).balanceOf(address(this));
        require(initialMAGIC >= amountIn, "Insufficient MAGIC balance");

        // Approve Uniswap Router to spend MAGIC.
        require(IERC20(magic).approve(uniswapRouter, amountIn), "MAGIC approval failed");

        // Swap MAGIC to USDC on Uniswap V3.
        IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router.ExactInputSingleParams({
            tokenIn: magic,
            tokenOut: usdc,
            fee: 3000,
            recipient: address(this),
            deadline: block.timestamp + 300,
            amountIn: amountIn,
            amountOutMinimum: 0, // Minimal output, adjust for slippage control.
            sqrtPriceLimitX96: 0
        });
        uint256 usdcReceived = IUniswapV3Router(uniswapRouter).exactInputSingle(params);
        require(usdcReceived > 0, "No USDC received");

        // Approve SushiSwap Router to spend USDC.
        require(IERC20(usdc).approve(sushiswapRouter, usdcReceived), "USDC approval failed");

        // Swap USDC back to MAGIC on SushiSwap.
        address[] memory path = new address[](2);
        path[0] = usdc;
        path[1] = magic;
        uint[] memory amounts = ISushiSwapRouter(sushiswapRouter).swapExactTokensForTokens(
            usdcReceived,
            0, // Minimal output, adjust for slippage control.
            path,
            address(this),
            block.timestamp + 300
        );
        require(amounts.length > 1, "Invalid swap output");
        uint256 finalMAGIC = amounts[amounts.length - 1];
        require(finalMAGIC > 0, "No MAGIC received");

        // Ensure the trade is profitable.
        require(finalMAGIC >= initialMAGIC + minProfitMagic, "Arbitrage not profitable");

        // Transfer profit (in MAGIC) to owner.
        uint256 profit = finalMAGIC - initialMAGIC;
        require(IERC20(magic).transfer(owner, profit), "Profit transfer failed");
    }

    // Executes reverse arbitrage starting with MAGIC:
    // Swap MAGIC -> USDC on SushiSwap then USDC -> MAGIC on Uniswap V3.
    function executeArbitrageWithMagicReverse(uint256 amountIn) external onlyOwner nonReentrant {
        require(amountIn > 0, "amountIn must be > 0");

        uint256 initialMAGIC = IERC20(magic).balanceOf(address(this));
        require(initialMAGIC >= amountIn, "Insufficient MAGIC balance");

        // Approve SushiSwap Router to spend MAGIC.
        require(IERC20(magic).approve(sushiswapRouter, amountIn), "MAGIC approval failed");

        // Swap MAGIC to USDC on SushiSwap.
        address[] memory path = new address[](2);
        path[0] = magic;
        path[1] = usdc;
        uint[] memory amounts = ISushiSwapRouter(sushiswapRouter).swapExactTokensForTokens(
            amountIn,
            0, // Minimal output, adjust for slippage control.
            path,
            address(this),
            block.timestamp + 300
        );
        require(amounts.length > 1, "Invalid swap output");
        uint256 usdcReceived = amounts[amounts.length - 1];
        require(usdcReceived > 0, "No USDC received");

        // Approve Uniswap Router to spend USDC.
        require(IERC20(usdc).approve(uniswapRouter, usdcReceived), "USDC approval failed");

        // Swap USDC back to MAGIC on Uniswap V3.
        IUniswapV3Router.ExactInputSingleParams memory params = IUniswapV3Router.ExactInputSingleParams({
            tokenIn: usdc,
            tokenOut: magic,
            fee: 3000,
            recipient: address(this),
            deadline: block.timestamp + 300,
            amountIn: usdcReceived,
            amountOutMinimum: 0, // Minimal output, adjust for slippage control.
            sqrtPriceLimitX96: 0
        });
        uint256 finalMAGIC = IUniswapV3Router(uniswapRouter).exactInputSingle(params);
        require(finalMAGIC > 0, "No MAGIC received");

        // Ensure the trade is profitable.
        require(finalMAGIC >= initialMAGIC + minProfitMagic, "Arbitrage not profitable");

        // Transfer profit (in MAGIC) to owner.
        uint256 profit = finalMAGIC - initialMAGIC;
        require(IERC20(magic).transfer(owner, profit), "Profit transfer failed");
    }

    //////////////////////////////
    // Withdraw and Rescue Functions
    //////////////////////////////

    // Withdraw USDC from the contract.
    function withdrawUSDC() external onlyOwner nonReentrant {
        uint256 balance = IERC20(usdc).balanceOf(address(this));
        require(balance > 0, "No USDC to withdraw");
        require(IERC20(usdc).transfer(owner, balance), "Withdraw failed");
    }

    // Withdraw MAGIC from the contract.
    function withdrawMAGIC() external onlyOwner nonReentrant {
        uint256 balance = IERC20(magic).balanceOf(address(this));
        require(balance > 0, "No MAGIC to withdraw");
        require(IERC20(magic).transfer(owner, balance), "Withdraw failed");
    }

    // Rescue function to recover any tokens mistakenly sent to this contract.
    function rescueTokens(address tokenAddress, uint256 amount) external onlyOwner nonReentrant {
        require(tokenAddress != address(0), "Invalid token address");
        require(IERC20(tokenAddress).transfer(owner, amount), "Rescue transfer failed");
    }
}
