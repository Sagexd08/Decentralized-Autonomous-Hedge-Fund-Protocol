const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("SlashingModule", function () {
  let token, vault, registry, slashing;
  let owner, agentAddr, other;

  const MIN_STAKE = ethers.parseEther("10000");
  const SIMULATION_PERIOD = 7 * 24 * 60 * 60;

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

    await vault.connect(owner).setSlashingModule(await slashing.getAddress());

    await registry.connect(owner).transferOwnership(await slashing.getAddress());
  }

  beforeEach(deployStack);

  describe("reportPerformance - DrawdownReported event", function () {
    it("emits DrawdownReported when drawdown > 0 (below slash threshold)", async function () {

      await slashing.connect(owner).setThreshold(5000);

      await slashing.connect(owner).reportPerformance(agentAddr.address, 1_000_000);

      await expect(
        slashing.connect(owner).reportPerformance(agentAddr.address, 900_000)
      )
        .to.emit(slashing, "DrawdownReported")
        .withArgs(agentAddr.address, 1000);
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

      await tok.connect(owner).approve(await reg.getAddress(), MIN_STAKE);
      await reg.connect(owner).registerAgent(
        agentAddr.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy")),
        1,
        MIN_STAKE
      );
      await time.increase(SIMULATION_PERIOD + 1);
      await reg.connect(owner).activateAgent(agentAddr.address);

      await reg.connect(owner).transferOwnership(await slash.getAddress());

      await slash.connect(owner).reportPerformance(agentAddr.address, 1_000_000);

      await slash.connect(owner).reportPerformance(agentAddr.address, 700_000);

      const history = await slash.getSlashHistory(agentAddr.address);
      expect(history.length).to.equal(1);
      expect(history[0].drawdownBps).to.equal(3000);

      expect(history[0].slashedBps).to.equal(1000);
    });
  });
});
