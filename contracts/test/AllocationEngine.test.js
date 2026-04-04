const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("AllocationEngine", function () {
  let token, vault, engine;
  let owner, agent1, agent2, other;

  beforeEach(async function () {
    [owner, agent1, agent2, other] = await ethers.getSigners();

    // Deploy MockERC20
    const MockERC20 = await ethers.getContractFactory("MockERC20");
    token = await MockERC20.deploy("Mock Token", "MTK", ethers.parseEther("1000000"));

    // Deploy CapitalVault
    const CapitalVault = await ethers.getContractFactory("CapitalVault");
    vault = await CapitalVault.deploy(await token.getAddress());

    // Deploy AllocationEngine
    const AllocationEngine = await ethers.getContractFactory("AllocationEngine");
    engine = await AllocationEngine.deploy(await vault.getAddress());

    // Wire vault to recognize engine
    await vault.connect(owner).setAllocationEngine(await engine.getAddress());
  });

  describe("submitUpdate", function () {
    it("stores agent scores after submitUpdate", async function () {
      const agents = [agent1.address, agent2.address];
      const scores = [500n, 200n];
      // weights must sum to 1e18
      const weights = [ethers.parseEther("0.6"), ethers.parseEther("0.4")];

      await engine.connect(owner).submitUpdate(agents, scores, weights);

      expect(await engine.agentScores(agent1.address)).to.equal(500n);
      expect(await engine.agentScores(agent2.address)).to.equal(200n);
    });

    it("reverts when called by non-owner", async function () {
      const agents = [agent1.address];
      const scores = [100n];
      const weights = [ethers.parseEther("1")];

      await expect(
        engine.connect(other).submitUpdate(agents, scores, weights)
      ).to.be.revertedWithCustomError(engine, "OwnableUnauthorizedAccount");
    });
  });

  describe("setEta", function () {
    it("reverts when eta is 0", async function () {
      await expect(
        engine.connect(owner).setEta(0)
      ).to.be.revertedWith("eta out of range");
    });

    it("reverts when eta is 50001", async function () {
      await expect(
        engine.connect(owner).setEta(50001)
      ).to.be.revertedWith("eta out of range");
    });

    it("accepts valid eta values", async function () {
      await engine.connect(owner).setEta(50000);
      expect(await engine.eta()).to.equal(50000n);

      await engine.connect(owner).setEta(1);
      expect(await engine.eta()).to.equal(1n);
    });
  });

  describe("reputation decay", function () {
    it("computes correct reputation score on first update", async function () {
      // historical = 0, recent = 1000
      // score = (300 * 1000 + 700 * 0) / 1000 = 300
      const agents = [agent1.address];
      const scores = [1000n];
      const weights = [ethers.parseEther("1")];

      await engine.connect(owner).submitUpdate(agents, scores, weights);

      expect(await engine.reputationScores(agent1.address)).to.equal(300n);
    });

    it("applies decay formula correctly on subsequent update", async function () {
      // First update: recent=1000, historical=0 → score = 300
      const agents = [agent1.address];
      const weights = [ethers.parseEther("1")];

      await engine.connect(owner).submitUpdate(agents, [1000n], weights);
      // score after first = 300

      // Second update: recent=500, historical=300
      // score = (300 * 500 + 700 * 300) / 1000 = (150000 + 210000) / 1000 = 360
      await engine.connect(owner).submitUpdate(agents, [500n], weights);

      expect(await engine.reputationScores(agent1.address)).to.equal(360n);
    });

    it("treats negative scores as zero for reputation", async function () {
      // recent = 0 (negative clamped), historical = 0 → score = 0
      const agents = [agent1.address];
      const weights = [ethers.parseEther("1")];

      await engine.connect(owner).submitUpdate(agents, [-500n], weights);

      expect(await engine.reputationScores(agent1.address)).to.equal(0n);
    });
  });
});
