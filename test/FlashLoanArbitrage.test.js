const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("FlashLoanArbitrage", function () {
  async function deployArbitrageFixture() {
    const [owner, user1] = await ethers.getSigners();

    // Deploy mock tokens
    const TokenA = await ethers.getContractFactory("MockERC20");
    const tokenA = await TokenA.deploy("Token A", "TKA", 18);

    const WETH = await ethers.getContractFactory("MockWETH");
    const weth = await WETH.deploy();

    // Deploy mock Aave contracts
    const MockPoolAddressesProvider = await ethers.getContractFactory("MockPoolAddressesProvider");
    const poolAddressesProvider = await MockPoolAddressesProvider.deploy();

    const MockAavePool = await ethers.getContractFactory("MockAavePool");
    const aavePool = await MockAavePool.deploy(await poolAddressesProvider.getAddress());

    // Set pool implementation in provider
    await poolAddressesProvider.setPoolImpl(await aavePool.getAddress());

    // Deploy mock Uniswap router
    const MockUniswapV2Router02 = await ethers.getContractFactory("MockUniswapV2Router02");
    const uniswapRouter = await MockUniswapV2Router02.deploy();

    // Deploy FlashLoanArbitrage contract
    const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
    const flashLoanArbitrage = await FlashLoanArbitrage.deploy(
      await poolAddressesProvider.getAddress(),
      await uniswapRouter.getAddress(),
      await weth.getAddress(),
      ethers.parseEther("1000"), // Max flash loan amount
      100 // 1% minimum profit
    );

    // Setup initial state
    const initialBalance = ethers.parseEther("10000"); // Increased initial balance
    await tokenA.mint(await aavePool.getAddress(), initialBalance);
    await tokenA.mint(await uniswapRouter.getAddress(), initialBalance);
    await weth.mint(await uniswapRouter.getAddress(), initialBalance);

    // Set profitable exchange rates (1 TokenA = 1.1 WETH, 1 WETH = 1.2 TokenA)
    await uniswapRouter.setPrice(
      await tokenA.getAddress(),
      await weth.getAddress(),
      ethers.parseEther("1.1")
    );
    await uniswapRouter.setPrice(
      await weth.getAddress(),
      await tokenA.getAddress(),
      ethers.parseEther("1.2")
    );

    // Set intermediate token
    await flashLoanArbitrage.setIntermediateToken(await weth.getAddress());

    return {
      tokenA,
      weth,
      poolAddressesProvider,
      aavePool,
      uniswapRouter,
      flashLoanArbitrage,
      owner,
      user1
    };
  }

  describe("Safety Features", function () {
    it("Should pause and unpause the contract", async function () {
      const { flashLoanArbitrage, tokenA, owner, user1 } = await loadFixture(
        deployArbitrageFixture
      );

      // Set intermediate token
      await flashLoanArbitrage.setIntermediateToken(await tokenA.getAddress());

      // Check initial state
      expect(await flashLoanArbitrage.paused()).to.equal(false);

      // Pause contract
      await expect(flashLoanArbitrage.pause())
        .to.emit(flashLoanArbitrage, "Paused")
        .withArgs(await owner.getAddress());

      // Verify paused state
      expect(await flashLoanArbitrage.paused()).to.equal(true);

      // Try to execute flash loan while paused (should fail)
      await expect(
        flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("1"))
      ).to.be.revertedWith("Pausable: paused");

      // Unpause contract
      await expect(flashLoanArbitrage.unpause())
        .to.emit(flashLoanArbitrage, "Unpaused")
        .withArgs(await owner.getAddress());

      // Verify unpaused state
      expect(await flashLoanArbitrage.paused()).to.equal(false);
    });

    it("Should enforce maximum flash loan amount", async function () {
      const { flashLoanArbitrage, tokenA, aavePool } = await loadFixture(
        deployArbitrageFixture
      );

      await flashLoanArbitrage.setIntermediateToken(await tokenA.getAddress());

      // Set maximum flash loan amount
      const maxAmount = ethers.parseEther("100");
      await flashLoanArbitrage.setMaxFlashLoanAmount(maxAmount);

      // Mint enough tokens to the pool
      await tokenA.mint(await aavePool.getAddress(), ethers.parseEther("1000"));  

      // Check maximum amount

      // Try to borrow more than the maximum (should fail)
      await expect(
        flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), maxAmount + 1n)
      ).to.be.revertedWith("Amount exceeds maximum");
    });

    it("Should allow emergency withdrawal", async function () {
      const { flashLoanArbitrage, tokenA, owner } = await loadFixture(
        deployArbitrageFixture
      );

      // Send some tokens to the contract
      const amount = ethers.parseEther("100");
      await tokenA.mint(await flashLoanArbitrage.getAddress(), amount);

      // Check initial balance
      expect(await tokenA.balanceOf(await flashLoanArbitrage.getAddress())).to.equal(amount);
      expect(await tokenA.balanceOf(await owner.getAddress())).to.equal(0);

      // Emergency withdraw
      await expect(
        flashLoanArbitrage.emergencyWithdraw(
          await tokenA.getAddress(),
          await owner.getAddress()
        )
      )
        .to.emit(flashLoanArbitrage, "EmergencyWithdraw")
        .withArgs(
          await tokenA.getAddress(),
          await owner.getAddress(),
          amount
        );

      // Check final balances
      expect(await tokenA.balanceOf(await flashLoanArbitrage.getAddress())).to.equal(0);
      expect(await tokenA.balanceOf(await owner.getAddress())).to.equal(amount);
    });

    it("Should enforce minimum profit requirement", async function () {
      const { flashLoanArbitrage, tokenA } = await loadFixture(
        deployArbitrageFixture
      );

      await flashLoanArbitrage.setIntermediateToken(await tokenA.getAddress());

      // Set minimum profit percentage
      const minProfit = 100; // 1%
      await flashLoanArbitrage.setMinProfitBps(minProfit);

      // Verify minimum profit
      expect(await flashLoanArbitrage.minProfitBps()).to.equal(minProfit);
    });
  });

  describe("Flash Loan", function () {
    it("Should execute flash loan successfully", async function () {
      const { flashLoanArbitrage, tokenA } = await loadFixture(deployArbitrageFixture);
      const loanAmount = ethers.parseEther("100");
      await expect(flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), loanAmount))
        .to.not.be.reverted;
    });

    it("Should execute flash loan successfully and emit correct events", async function () {
      const { flashLoanArbitrage, tokenA } = await loadFixture(deployArbitrageFixture);
      const loanAmount = ethers.parseEther("100");
      await expect(flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), loanAmount))
        .to.emit(flashLoanArbitrage, "FlashLoanInitiated")
        .withArgs(await tokenA.getAddress(), loanAmount);
    });

    it("Should revert if called by non-owner", async function () {
      const { flashLoanArbitrage, tokenA, user1 } = await loadFixture(deployArbitrageFixture);
      await expect(
        flashLoanArbitrage.connect(user1).initiateFlashLoan(await tokenA.getAddress(), ethers.parseEther("1"))
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should execute profitable flash loan arbitrage", async function () {
      const { flashLoanArbitrage, tokenA, weth, aavePool } = await loadFixture(deployArbitrageFixture);
      const loanAmount = ethers.parseEther("100");

      // Get initial balances
      const initialBalance = await tokenA.balanceOf(await flashLoanArbitrage.getAddress());

      // Execute flash loan
      const tx = await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), loanAmount);
      await tx.wait();

      // Verify profit
      const finalBalance = await tokenA.balanceOf(await flashLoanArbitrage.getAddress());
      expect(finalBalance).to.be.gt(initialBalance);

      // Calculate minimum expected profit (1% of loan amount)
      const minProfitBps = await flashLoanArbitrage.minProfitBps();
      const minProfit = (loanAmount * minProfitBps) / 10000n;
      expect(finalBalance - initialBalance).to.be.gte(minProfit);
    });
  });

  describe("Gas Optimizations", function () {
    it("Should approve tokens only once", async function () {
      const { flashLoanArbitrage, tokenA } = await loadFixture(deployArbitrageFixture);

      // Execute two flash loans with the same token
      const loanAmount = ethers.parseEther("100");
      await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), loanAmount);
      await flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), loanAmount);
    });

    it("Should pre-approve intermediate token when setting it", async function () {
      const { flashLoanArbitrage, tokenA, uniswapRouter } = await loadFixture(deployArbitrageFixture);
      
      // Deploy a new token that hasn't been approved yet
      const TokenB = await ethers.getContractFactory("MockERC20");
      const tokenB = await TokenB.deploy("Token B", "TKB", 18);
      
      // Set the new token as intermediate token
      await flashLoanArbitrage.setIntermediateToken(await tokenB.getAddress());
      
      // Check that the new token is approved
      const allowance = await tokenB.allowance(
        await flashLoanArbitrage.getAddress(),
        await uniswapRouter.getAddress()
      );
      expect(allowance).to.equal(ethers.MaxUint256);
    });

    it("Should revert with zero amount", async function () {
      const { flashLoanArbitrage, tokenA } = await loadFixture(
        deployArbitrageFixture
      );

      await flashLoanArbitrage.setIntermediateToken(await tokenA.getAddress());

      await expect(flashLoanArbitrage.initiateFlashLoan(await tokenA.getAddress(), 0))
        .to.be.revertedWith("Amount must be greater than 0");
    });

    it("Should revert with zero address token", async function () {
      const { flashLoanArbitrage } = await loadFixture(deployArbitrageFixture);

      await expect(
        flashLoanArbitrage.setIntermediateToken(ethers.ZeroAddress)
      ).to.be.revertedWith("Invalid token address");
    });
  });
});
