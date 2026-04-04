const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");

describe("AgentRegistry", function () {
  let token, registry;
  let owner, user, agentAddr, other;

  const MIN_STAKE = ethers.parseEther("10000");
  const SIMULATION_PERIOD = 7 * 24 * 60 * 60;

  beforeEach(async function () {
    [owner, user, agentAddr, other] = await ethers.getSigners();

    const MockERC20 = await ethers.getContractFactory("MockERC20");
    token = await MockERC20.deploy("Stake Token", "STK", ethers.parseEther("1000000"));

    const AgentRegistry = await ethers.getContractFactory("AgentRegistry");
    registry = await AgentRegistry.deploy(await token.getAddress());

    await token.transfer(user.address, ethers.parseEther("100000"));
    await token.connect(user).approve(await registry.getAddress(), ethers.parseEther("100000"));
  });

  describe("registerAgent", function () {
    it("reverts if stake < MIN_STAKE", async function () {
      const belowMin = MIN_STAKE - 1n;
      await expect(
        registry.connect(user).registerAgent(
          agentAddr.address,
          ethers.keccak256(ethers.toUtf8Bytes("strategy")),
          1,
          belowMin
        )
      ).to.be.revertedWith("Insufficient stake");
    });

    it("succeeds with exactly MIN_STAKE", async function () {
      await expect(
        registry.connect(user).registerAgent(
          agentAddr.address,
          ethers.keccak256(ethers.toUtf8Bytes("strategy")),
          1,
          MIN_STAKE
        )
      ).to.emit(registry, "AgentRegistered");

      const agent = await registry.agents(agentAddr.address);
      expect(agent.stakedAmount).to.equal(MIN_STAKE);
    });
  });

  describe("activateAgent", function () {
    beforeEach(async function () {
      await registry.connect(user).registerAgent(
        agentAddr.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy")),
        0,
        MIN_STAKE
      );
    });

    it("reverts before simulation period ends", async function () {
      await expect(
        registry.connect(owner).activateAgent(agentAddr.address)
      ).to.be.revertedWith("Simulation not complete");
    });

    it("succeeds after simulation period ends", async function () {
      await time.increase(SIMULATION_PERIOD + 1);
      await expect(
        registry.connect(owner).activateAgent(agentAddr.address)
      ).to.emit(registry, "AgentActivated");

      const agent = await registry.agents(agentAddr.address);
      expect(agent.status).to.equal(2);
    });
  });

  describe("slashAgent", function () {
    beforeEach(async function () {
      await registry.connect(user).registerAgent(
        agentAddr.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy")),
        1,
        MIN_STAKE
      );
      await time.increase(SIMULATION_PERIOD + 1);
      await registry.connect(owner).activateAgent(agentAddr.address);
    });

    it("reduces stakedAmount by correct proportion", async function () {
      const slashBps = 500;
      const expectedSlash = (MIN_STAKE * BigInt(slashBps)) / 10000n;
      const expectedRemaining = MIN_STAKE - expectedSlash;

      await registry.connect(owner).slashAgent(agentAddr.address, slashBps);

      const agent = await registry.agents(agentAddr.address);
      expect(agent.stakedAmount).to.equal(expectedRemaining);
    });

    it("emits AgentSlashed with correct amount", async function () {
      const slashBps = 1000;
      const expectedSlash = (MIN_STAKE * BigInt(slashBps)) / 10000n;

      await expect(
        registry.connect(owner).slashAgent(agentAddr.address, slashBps)
      ).to.emit(registry, "AgentSlashed").withArgs(agentAddr.address, expectedSlash);
    });
  });

  describe("getActiveAgents", function () {
    let agent2;

    beforeEach(async function () {
      [, , agentAddr, agent2] = await ethers.getSigners();

      await token.transfer(other.address, ethers.parseEther("100000"));
      await token.connect(other).approve(await registry.getAddress(), ethers.parseEther("100000"));

      await registry.connect(user).registerAgent(
        agentAddr.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy1")),
        0,
        MIN_STAKE
      );
      await registry.connect(other).registerAgent(
        agent2.address,
        ethers.keccak256(ethers.toUtf8Bytes("strategy2")),
        1,
        MIN_STAKE
      );
    });

    it("returns only active agents", async function () {

      await time.increase(SIMULATION_PERIOD + 1);
      await registry.connect(owner).activateAgent(agentAddr.address);

      const active = await registry.getActiveAgents();
      expect(active.length).to.equal(1);
      expect(active[0]).to.equal(agentAddr.address);
    });

    it("returns empty array when no agents are active", async function () {
      const active = await registry.getActiveAgents();
      expect(active.length).to.equal(0);
    });

    it("returns all agents when all are active", async function () {
      await time.increase(SIMULATION_PERIOD + 1);
      await registry.connect(owner).activateAgent(agentAddr.address);
      await registry.connect(owner).activateAgent(agent2.address);

      const active = await registry.getActiveAgents();
      expect(active.length).to.equal(2);
      expect(active).to.include(agentAddr.address);
      expect(active).to.include(agent2.address);
    });
  });
});
