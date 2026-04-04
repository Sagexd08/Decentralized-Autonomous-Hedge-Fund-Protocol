const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CapitalVault", function () {
  let vault, token;
  let owner, investor, allocationEngine, other;

  beforeEach(async function () {
    [owner, investor, allocationEngine, other] = await ethers.getSigners();

    // Deploy mock ERC20
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    token = await MockERC20.deploy("Mock Token", "MTK", ethers.parseEther("1000000"));

    // Deploy CapitalVault
    const CapitalVault = await ethers.getContractFactory("CapitalVault");
    vault = await CapitalVault.deploy(await token.getAddress());

    // Set allocation engine
    await vault.connect(owner).setAllocationEngine(allocationEngine.address);

    // Fund investor and approve vault
    await token.transfer(investor.address, ethers.parseEther("10000"));
    await token.connect(investor).approve(await vault.getAddress(), ethers.MaxUint256);
  });

  describe("deposit", function () {
    it("increases poolTVL on deposit", async function () {
      const amount = ethers.parseEther("100");
      const poolId = 1; // Balanced

      const tvlBefore = await vault.poolTVL(poolId);
      await vault.connect(investor).deposit(poolId, amount);
      const tvlAfter = await vault.poolTVL(poolId);

      expect(tvlAfter - tvlBefore).to.equal(amount);
    });
  });

  describe("withdraw", function () {
    it("decreases poolTVL on withdraw", async function () {
      const amount = ethers.parseEther("100");
      const poolId = 0; // Conservative

      await vault.connect(investor).deposit(poolId, amount);
      const tvlAfterDeposit = await vault.poolTVL(poolId);

      await vault.connect(investor).withdraw(poolId, amount);
      const tvlAfterWithdraw = await vault.poolTVL(poolId);

      expect(tvlAfterDeposit - tvlAfterWithdraw).to.equal(amount);
    });
  });

  describe("updateWeights", function () {
    it("reverts if caller is not allocationEngine", async function () {
      const agents = [other.address];
      const weights = [ethers.parseEther("1")]; // 1e18

      await expect(
        vault.connect(other).updateWeights(agents, weights)
      ).to.be.revertedWith("Only allocation engine");
    });

    it("reverts if weights do not sum to 1e18", async function () {
      const agents = [other.address];
      const weights = [ethers.parseEther("0.5")]; // 0.5e18, not 1e18

      await expect(
        vault.connect(allocationEngine).updateWeights(agents, weights)
      ).to.be.revertedWith("Weights must sum to 1e18");
    });
  });
});
