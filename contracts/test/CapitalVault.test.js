const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CapitalVault", function () {
  let vault, token;
  let owner, investor, allocationEngine, other;

  beforeEach(async function () {
    [owner, investor, allocationEngine, other] = await ethers.getSigners();

    const MockERC20 = await ethers.getContractFactory("MockERC20");
    token = await MockERC20.deploy("Mock Token", "MTK", ethers.parseEther("1000000"));

    const CapitalVault = await ethers.getContractFactory("CapitalVault");
    vault = await CapitalVault.deploy(await token.getAddress());

    await vault.connect(owner).setAllocationEngine(allocationEngine.address);

    await token.transfer(investor.address, ethers.parseEther("10000"));
    await token.connect(investor).approve(await vault.getAddress(), ethers.MaxUint256);
  });

  describe("deposit", function () {
    it("increases poolTVL on deposit", async function () {
      const amount = ethers.parseEther("100");
      const poolId = 1;

      const tvlBefore = await vault.poolTVL(poolId);
      await vault.connect(investor).deposit(poolId, amount);
      const tvlAfter = await vault.poolTVL(poolId);

      expect(tvlAfter - tvlBefore).to.equal(amount);
    });
  });

  describe("withdraw", function () {
    it("decreases poolTVL on withdraw", async function () {
      const amount = ethers.parseEther("100");
      const poolId = 0;

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
      const weights = [ethers.parseEther("1")];

      await expect(
        vault.connect(other).updateWeights(agents, weights)
      ).to.be.revertedWith("Only allocation engine");
    });

    it("reverts if weights do not sum to 1e18", async function () {
      const agents = [other.address];
      const weights = [ethers.parseEther("0.5")];

      await expect(
        vault.connect(allocationEngine).updateWeights(agents, weights)
      ).to.be.revertedWith("Weights must sum to 1e18");
    });
  });
});
