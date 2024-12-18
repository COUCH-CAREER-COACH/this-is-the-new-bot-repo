const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Enhanced FlashLoanArbitrage", function () {
    async function deployArbitrageFixture() {
        const [owner, user1] = await ethers.getSigners();

        // Deploy mock tokens
        const TokenA = await ethers.getContractFactory("MockERC20");
        const tokenA = await TokenA.deploy("Token A", "TKA", 18);
        await tokenA.waitForDeployment();

        const WETH = await ethers.getContractFactory("MockWETH");
        const weth = await WETH.deploy();
        await weth.waitForDeployment();

        // Deploy mock Uniswap contracts
        const UniswapV2Factory = await ethers.getContractFactory("UniswapV2Factory");
        const uniswapFactory = await UniswapV2Factory.deploy(owner.address);
        await uniswapFactory.waitForDeployment();

        const MockUniswapV2Router02 = await ethers.getContractFactory("MockUniswapV2Router02");
        const uniswapRouter = await MockUniswapV2Router02.deploy(
            await uniswapFactory.getAddress(),
            await weth.getAddress()
        );
        await uniswapRouter.waitForDeployment();

        // Deploy mock Aave contracts
        const MockPoolAddressesProvider = await ethers.getContractFactory("MockPoolAddressesProvider");
        const poolAddressesProvider = await MockPoolAddressesProvider.deploy();
        await poolAddressesProvider.waitForDeployment();

        const MockAavePool = await ethers.getContractFactory("MockAavePool");
        const aavePool = await MockAavePool.deploy(await poolAddressesProvider.getAddress());
        await aavePool.waitForDeployment();

        // Set pool implementation in provider
        await poolAddressesProvider.setPoolImpl(await aavePool.getAddress());

        // Deploy FlashLoanArbitrage contract
        const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
        const flashLoanArbitrage = await FlashLoanArbitrage.deploy(
            await poolAddressesProvider.getAddress(),
            await uniswapRouter.getAddress(),
            await weth.getAddress(),
            ethers.parseEther("1000"), // Max flash loan amount
            100 // 1% minimum profit in basis points
        );
        await flashLoanArbitrage.waitForDeployment();

        // Setup initial state
        const initialBalance = ethers.parseEther("10000");
        await tokenA.mint(await aavePool.getAddress(), initialBalance);
        await tokenA.mint(await uniswapRouter.getAddress(), initialBalance);
        await weth.mint(await uniswapRouter.getAddress(), initialBalance);

        // Set initial exchange rates
        await uniswapRouter.setPrice(
            await tokenA.getAddress(),
            await weth.getAddress(),
            ethers.parseEther("1.0")
        );
        await uniswapRouter.setPrice(
            await weth.getAddress(),
            await tokenA.getAddress(),
            ethers.parseEther("1.0")
        );

        return {
            flashLoanArbitrage,
            tokenA,
            weth,
            aavePool,
            uniswapRouter,
            poolAddressesProvider,
            owner,
            user1,
            initialBalance
        };
    }

    async function setExchangeRates(uniswapRouter, tokenA, weth, intermediateToken, rates) {
        // Set rates for tokenA <-> WETH
        await uniswapRouter.setPrice(await tokenA.getAddress(), await weth.getAddress(), rates.tokenAToWeth);
        await uniswapRouter.setPrice(await weth.getAddress(), await tokenA.getAddress(), rates.wethToTokenA);

        // Set rates for tokenA <-> intermediateToken
        await uniswapRouter.setPrice(await tokenA.getAddress(), await intermediateToken.getAddress(), rates.tokenAToIntermediate);
        await uniswapRouter.setPrice(await intermediateToken.getAddress(), await tokenA.getAddress(), rates.intermediateToTokenA);

        // Set rates for WETH <-> intermediateToken
        await uniswapRouter.setPrice(await weth.getAddress(), await intermediateToken.getAddress(), rates.wethToIntermediate);
        await uniswapRouter.setPrice(await intermediateToken.getAddress(), await weth.getAddress(), rates.intermediateToWeth);
    }

    describe("Initialization", function () {
        it("Should initialize with correct values", async function () {
            const { flashLoanArbitrage, weth, uniswapRouter, poolAddressesProvider } = await loadFixture(deployArbitrageFixture);
            
            expect(await flashLoanArbitrage.WETH()).to.equal(await weth.getAddress());
            expect(await flashLoanArbitrage.uniswapRouter()).to.equal(await uniswapRouter.getAddress());
            expect(await flashLoanArbitrage.provider()).to.equal(await poolAddressesProvider.getAddress());
            expect(await flashLoanArbitrage.maxPriceDeviation()).to.equal(500); // 5% default
            expect(await flashLoanArbitrage.maxSlippage()).to.equal(100); // 1% default
        });
    });

    describe("Configuration Functions", function () {
        it("Should set max flash loan amount", async function () {
            const { flashLoanArbitrage, owner } = await loadFixture(deployArbitrageFixture);
            const newAmount = ethers.parseEther("2000");
            
            await flashLoanArbitrage.connect(owner).setMaxFlashLoanAmount(newAmount);
            expect(await flashLoanArbitrage.maxFlashLoanAmount()).to.equal(newAmount);
        });

        it("Should revert when setting invalid max flash loan amount", async function () {
            const { flashLoanArbitrage } = await loadFixture(deployArbitrageFixture);
            await expect(flashLoanArbitrage.setMaxFlashLoanAmount(0))
                .to.be.revertedWithCustomError(flashLoanArbitrage, "InvalidAmount");
        });

        it("Should set max price deviation", async function () {
            const { flashLoanArbitrage, owner } = await loadFixture(deployArbitrageFixture);
            const newDeviation = 300; // 3%
            
            await flashLoanArbitrage.connect(owner).setMaxPriceDeviation(newDeviation);
            expect(await flashLoanArbitrage.maxPriceDeviation()).to.equal(newDeviation);
        });

        it("Should set max slippage", async function () {
            const { flashLoanArbitrage, owner } = await loadFixture(deployArbitrageFixture);
            const newSlippage = 50; // 0.5%
            
            await flashLoanArbitrage.connect(owner).setMaxSlippage(newSlippage);
            expect(await flashLoanArbitrage.maxSlippage()).to.equal(newSlippage);
        });
    });

    describe("Price Deviation Protection", function () {
        it("Should detect and revert on excessive price deviation", async function () {
            const { flashLoanArbitrage, tokenA, owner, uniswapRouter, weth } = await loadFixture(deployArbitrageFixture);
            
            // Set intermediate token
            await flashLoanArbitrage.connect(owner).setIntermediateToken(await tokenA.getAddress());
            
            // Set initial exchange rates (1:1 for all pairs)
            await setExchangeRates(uniswapRouter, tokenA, weth, tokenA, {
                tokenAToWeth: ethers.parseEther("1.0"),
                wethToTokenA: ethers.parseEther("1.0"),
                tokenAToIntermediate: ethers.parseEther("1.0"),
                intermediateToTokenA: ethers.parseEther("1.0"),
                wethToIntermediate: ethers.parseEther("1.0"),
                intermediateToWeth: ethers.parseEther("1.0")
            });
            
            // Mint tokens for flash loan
            await tokenA.mint(await flashLoanArbitrage.getAddress(), ethers.parseEther("1000"));
            
            // First trade to set initial price
            await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("100"));
            
            // Simulate price change by updating mock prices (100% price increase)
            await setExchangeRates(uniswapRouter, tokenA, weth, tokenA, {
                tokenAToWeth: ethers.parseEther("2.0"),
                wethToTokenA: ethers.parseEther("0.5"),
                tokenAToIntermediate: ethers.parseEther("2.0"),
                intermediateToTokenA: ethers.parseEther("0.5"),
                wethToIntermediate: ethers.parseEther("1.0"),
                intermediateToWeth: ethers.parseEther("1.0")
            });
            
            // Should revert on next trade
            await expect(flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("100")))
                .to.be.revertedWithCustomError(flashLoanArbitrage, "PriceDeviation");
        });
    });

    describe("Trade Statistics", function () {
        it("Should track trade statistics correctly", async function () {
            const { flashLoanArbitrage, tokenA, owner, uniswapRouter, weth } = await loadFixture(deployArbitrageFixture);
            
            // Set intermediate token
            await flashLoanArbitrage.connect(owner).setIntermediateToken(await tokenA.getAddress());
            
            // Set exchange rates for profitable trades
            await setExchangeRates(uniswapRouter, tokenA, weth, tokenA, {
                tokenAToWeth: ethers.parseEther("1.2"),
                wethToTokenA: ethers.parseEther("0.8"),
                tokenAToIntermediate: ethers.parseEther("1.2"),
                intermediateToTokenA: ethers.parseEther("0.8"),
                wethToIntermediate: ethers.parseEther("1.0"),
                intermediateToWeth: ethers.parseEther("1.0")
            });
            
            // Mint tokens for flash loan
            await tokenA.mint(await flashLoanArbitrage.getAddress(), ethers.parseEther("1000"));
            
            // Execute some trades
            await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("100"));
            await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("200"));
            
            const stats = await flashLoanArbitrage.getTradeStatistics();
            expect(stats.totalTrades).to.be.gt(0);
            expect(stats.successRate).to.be.gt(0);
            expect(stats.avgGasUsed).to.be.gt(0);
        });
    });

    describe("Emergency Functions", function () {
        it("Should execute emergency withdrawal", async function () {
            const { flashLoanArbitrage, tokenA, owner } = await loadFixture(deployArbitrageFixture);
            
            // Send some tokens to the contract
            const amount = ethers.parseEther("100");
            await tokenA.mint(await flashLoanArbitrage.getAddress(), amount);
            
            // Execute emergency withdrawal
            await expect(flashLoanArbitrage.connect(owner).emergencyWithdraw(
                await tokenA.getAddress(),
                await owner.getAddress(),
                "Emergency test"
            )).to.emit(flashLoanArbitrage, "EmergencyWithdraw");
            
            // Verify balance
            expect(await tokenA.balanceOf(await owner.getAddress())).to.equal(amount);
        });

        it("Should revert emergency withdrawal for non-owner", async function () {
            const { flashLoanArbitrage, tokenA, user1 } = await loadFixture(deployArbitrageFixture);
            
            await expect(flashLoanArbitrage.connect(user1).emergencyWithdraw(
                await tokenA.getAddress(),
                await user1.getAddress(),
                "Unauthorized"
            )).to.be.revertedWith("Ownable: caller is not the owner");
        });
    });

    describe("Flash Loan Execution", function () {
        it("Should execute flash loan with profit", async function () {
            const { flashLoanArbitrage, tokenA, owner, uniswapRouter, weth } = await loadFixture(deployArbitrageFixture);
            
            // Set intermediate token
            await flashLoanArbitrage.connect(owner).setIntermediateToken(await tokenA.getAddress());
            
            // Set exchange rates for profitable arbitrage
            await setExchangeRates(uniswapRouter, tokenA, weth, tokenA, {
                tokenAToWeth: ethers.parseEther("1.2"),
                wethToTokenA: ethers.parseEther("0.8"),
                tokenAToIntermediate: ethers.parseEther("1.2"),
                intermediateToTokenA: ethers.parseEther("0.8"),
                wethToIntermediate: ethers.parseEther("1.0"),
                intermediateToWeth: ethers.parseEther("1.0")
            });
            
            // Mint tokens for flash loan
            await tokenA.mint(await flashLoanArbitrage.getAddress(), ethers.parseEther("1000"));
            
            // Execute flash loan
            await expect(flashLoanArbitrage.initiateFlashLoan(
                await tokenA.getAddress(),
                ethers.parseEther("100")
            )).to.emit(flashLoanArbitrage, "FlashLoanCompleted");
        });

        it("Should revert on insufficient profit", async function () {
            const { flashLoanArbitrage, tokenA, owner, uniswapRouter, weth } = await loadFixture(deployArbitrageFixture);
            
            // Set intermediate token
            await flashLoanArbitrage.connect(owner).setIntermediateToken(await tokenA.getAddress());
            
            // Set exchange rates for unprofitable arbitrage
            await setExchangeRates(uniswapRouter, tokenA, weth, tokenA, {
                tokenAToWeth: ethers.parseEther("1.01"),
                wethToTokenA: ethers.parseEther("0.99"),
                tokenAToIntermediate: ethers.parseEther("1.01"),
                intermediateToTokenA: ethers.parseEther("0.99"),
                wethToIntermediate: ethers.parseEther("1.0"),
                intermediateToWeth: ethers.parseEther("1.0")
            });
            
            // Mint tokens for flash loan
            await tokenA.mint(await flashLoanArbitrage.getAddress(), ethers.parseEther("1000"));
            
            // Should revert due to insufficient profit
            await expect(flashLoanArbitrage.initiateFlashLoan(
                await tokenA.getAddress(),
                ethers.parseEther("100")
            )).to.be.revertedWithCustomError(flashLoanArbitrage, "InsufficientProfit");
        });
    });
});
