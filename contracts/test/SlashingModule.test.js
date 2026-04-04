const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("SlashingModule", function () {
  let token, vault, registry, slashing;
  let owner, agentAddr, other;

  const MIN_STAKE = ethers.parseEther("10000");
  const SIMULATION_PERIOD = 7 * 24 * 60 * 60; // 7 days

  async function deployStack() {
    [owner, agentAddr, other] = await ethers.getSigners();

    const MockERC20 = await ethers.getContractFactory("MockERC20");
    token = await MockERC20.deploy("Stake Token", "STK", ethers.parseEther("1000000"));

    const CapitalVault = await ethers.getContractFactory("CapitalVault");
    vault = await CapitalVault.deploy(await token.getAddress());

    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    registry = await AgentRegistry.deploy(await token.getAddress());

    const SlashingModule = await ethers.getContractFactory("SlashingModule");
    slashing = await SlashingModule.deploy(
      await vault.getAddress(),
      await registry.getAddress()
    );

    // Wire vault to recognize slashing module
    await vault.connect(owner).setSlashingModule(await slashing.getAddress());

    // Transfer AgentRegistry ownership to SlashingModule so it can call slashAgent
    await registry.connect(owner).transferOwnership(await slashing.getAddress());
  }

  beforeEach(deployStack);

  describe("reportPerformance - DrawdownReported event", function () {
    it("emits DrawdownReported when drawdown > 0 (below slash threshold)", async function () {
      // Set a very high threshold so slash is not triggered, only event emitted
      await slashing.connect(owner).setThreshold(5000); // 50%

      // First call establishes peak at 1_000_000
      await slashing.connect(owner).reportPerformance(agentAddr.address, 1_000_000);

      // Second call: value drops to 900_000 → drawdown = 10% (1000 bps), below 50% threshold
      await expect(
        slashing.connect(owner).reportPerformance(agentAddr.address, 900_000)
      )
        .to.emit(slashing, "DrawdownReported")
        .withArgs(agentAddr.address, 1000); // 10% = 1000 bps
    });
  });

  describe("setThreshold", function () {
    it("reverts when threshold is below 500", async function () {
      await expect(
        slashing.connect(owner).setThreshold(400)
      ).to.be.revertedWith("Out of range");
    });

    it("reverts when threshold is above 5000", async function () {
      await expect(
        slashing.connect(owner).setThreshold(5001)
      ).to.be.revertedWith("Out of range");
    });

    it("accepts boundary values 500 and 5000", async function () {
      await expect(slashing.connect(owner).setThreshold(500))
        .to.emit(slashing, "ThresholdUpdated")
        .withArgs(500);

      await expect(slashing.connect(owner).setThreshold(5000))
        .to.emit(slashing, "ThresholdUpdated")
        .withArgs(5000);
    });
  });

  describe("slash history", function () {
    it("records slash history after drawdown exceeds threshold", async function () {
      // Deploy a fresh stack: activate agent BEFORE transferring registry ownership to slashing
      [owner, agentAddr, other] = await ethers.getSigners();

      const MockERC20 = await ethers.getContractFactory("MockERC20");
      const tok = await MockERC20.deploy("Stake Token", "STK", ethers.parseEther("1000000"));

      const CapitalVault = await ethers.getContractFactory("CapitalVault");
      const vlt = await CapitalVault.deploy(await tok.getAddress());

      const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
      const reg = await AgentRegistry.deploy(await tok.getAddress());

      const SlashingModule = await ethers.getContractFactory("SlashingModule");
      const slash = await SlashingModule.deploy(
        await vlt.getAddress(),
        await reg.getAddress()
      );

      await vlt.connect(owner).setSlashingModule(await slash.getAddress());

      // Register and activate agent BEFORE transferring registry ownership
      await tok.connect(owner).approve(await reg.getAddress(), MIN_STAKE);
      await reg.connect(owner).registerAgent(
        agentAddr.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy")),
        1,
        MIN_STAKE
      );
      await time.increase(SIMULATION_PERIOD + 1);
      await reg.connect(owner).activateAgent(agentAddr.address);

      // Now transfer registry ownership to slashing module
      await reg.connect(owner).transferOwnership(await slash.getAddress());

      // Establish peak value
      await slash.connect(owner).reportPerformance(agentAddr.address, 1_000_000);

      // Report a value that causes >20% drawdown (default threshold = 2000 bps)
      // Drop to 700_000 → drawdown = 30% = 3000 bps > 2000 threshold → slash triggered
      await slash.connect(owner).reportPerformance(agentAddr.address, 700_000);

      const history = await slash.getSlashHistory(agentAddr.address);
      expect(history.length).to.equal(1);
      expect(history[0].drawdownBps).to.equal(3000); // 30%
      // slashBps = min(3000 - 2000, 5000) = 1000
      expect(history[0].slashedBps).to.equal(1000);
    });
  });
});
