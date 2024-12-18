const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-toolbox/network-helpers");

describe("FlashLoanArbitrage", function () {
    async function deployArbitrageFixture() {
        const [owner, otherAccount] = await ethers.getSigners();

        // Deploy Mock Tokens
        const MockWETH = await ethers.getContractFactory("MockWETH");
        const weth = await MockWETH.deploy();

        const MockERC20 = await ethers.getContractFactory("MockERC20");
        const usdc = await MockERC20.deploy("USDC", "USDC", 6);
        const dai = await MockERC20.deploy("DAI", "DAI", 18);

        // Deploy Uniswap Factory and Router
        const UniswapV2Factory = await ethers.getContractFactory("UniswapV2Factory");
        const factory = await UniswapV2Factory.deploy(owner.address);

        const UniswapV2Router02 = await ethers.getContractFactory("UniswapV2Router02");
        const router = await UniswapV2Router02.deploy(
            await factory.getAddress(),
            await weth.getAddress()
        );

        // Deploy Aave Mock Pool
        const IPoolAddressesProvider = await ethers.getContractFactory("IPoolAddressesProvider");
        const aaveProvider = await IPoolAddressesProvider.deploy("Aave Test Market");
        
        const MockAavePool = await ethers.getContractFactory("MockAavePool");
        const aavePool = await MockAavePool.deploy();
        await aaveProvider.setPoolImpl(await aavePool.getAddress());

        // Deploy FlashLoanArbitrage
        const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
        const arbitrage = await FlashLoanArbitrage.deploy(
            await aaveProvider.getAddress(),
            await router.getAddress(),
            await weth.getAddress()
        );

        // Setup initial balances
        await weth.deposit({ value: ethers.parseEther("1000") });
        await usdc.mint(ethers.parseUnits("2000000", 6));
        await dai.mint(ethers.parseEther("2200000"));

        // Fund Aave pool with more WETH for flash loans
        await weth.transfer(await aavePool.getAddress(), ethers.parseEther("500"));

        // Setup liquidity pools with significant price discrepancy
        await weth.approve(await router.getAddress(), ethers.MaxUint256);
        await usdc.approve(await router.getAddress(), ethers.MaxUint256);
        await dai.approve(await router.getAddress(), ethers.MaxUint256);

        // Add liquidity WETH/USDC with price 2000 USDC per ETH
        await router.addLiquidity(
            await weth.getAddress(),
            await usdc.getAddress(),
            ethers.parseEther("100"),
            ethers.parseUnits("200000", 6),
            0,
            0,
            owner.address,
            Math.floor(Date.now() / 1000) + 3600
        );

        // Add liquidity WETH/DAI with price 2500 DAI per ETH (25% higher price creates opportunity)
        await router.addLiquidity(
            await weth.getAddress(),
            await dai.getAddress(),
            ethers.parseEther("100"),
            ethers.parseEther("250000"),
            0,
            0,
            owner.address,
            Math.floor(Date.now() / 1000) + 3600
        );

        // Transfer some initial WETH to the arbitrage contract for fees
        await weth.transfer(await arbitrage.getAddress(), ethers.parseEther("1"));

        // Pre-approve WETH for the router from arbitrage contract
        await arbitrage.withdrawToken(await weth.getAddress(), ethers.parseEther("1"));
        await weth.connect(owner).approve(await router.getAddress(), ethers.MaxUint256);
        await weth.connect(owner).transfer(await arbitrage.getAddress(), ethers.parseEther("1"));

        return {
            weth,
            usdc,
            dai,
            factory,
            router,
            aaveProvider,
            aavePool,
            arbitrage,
            owner,
            otherAccount
        };
    }

    describe("Arbitrage", function () {
        it("Should execute a profitable flash loan arbitrage", async function () {
            const { weth, usdc, dai, arbitrage, aavePool, owner } = await loadFixture(deployArbitrageFixture);

            // Get initial balances
            const initialBalance = await weth.balanceOf(owner.address);
            
            // Execute flash loan arbitrage
            const flashLoanAmount = ethers.parseEther("10");
            await arbitrage.initiateFlashLoan(
                await weth.getAddress(),
                flashLoanAmount
            );

            // Check profit
            const finalBalance = await weth.balanceOf(owner.address);
            expect(finalBalance).to.be.gt(initialBalance);
        });
    });
});
