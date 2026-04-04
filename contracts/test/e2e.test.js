const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CapitalVault E2E — depositETH with EIP-712 delegation", function () {
  let vault;
  let investor;
  let agent;

  const POOL_BALANCED = 1;
  const MAX_DRAWDOWN_BPS = 1500n; // 15%
  const MAX_ALLOCATION_WEI = ethers.parseEther("5");
  const DEPOSIT_AMOUNT = ethers.parseEther("1");

  beforeEach(async function () {
    [, investor, agent] = await ethers.getSigners();

    const CapitalVault = await ethers.getContractFactory("CapitalVault");
    vault = await CapitalVault.deploy();
    await vault.waitForDeployment();
  });

  async function buildSignature(signer, pool, agentAddr, amount, maxDrawdownBps, maxAllocationWei) {
    const network = await ethers.provider.getNetwork();
    const chainId = network.chainId;
    const vaultAddress = await vault.getAddress();

    const domain = {
      name: "DACAP",
      version: "1",
      chainId: chainId,
      verifyingContract: vaultAddress,
    };

    const types = {
      DelegationParams: [
        { name: "pool",             type: "uint8"   },
        { name: "agent",            type: "address" },
        { name: "amount",           type: "uint256" },
        { name: "maxDrawdownBps",   type: "uint256" },
        { name: "maxAllocationWei", type: "uint256" },
        { name: "investor",         type: "address" },
      ],
    };

    const value = {
      pool:             pool,
      agent:            agentAddr,
      amount:           amount,
      maxDrawdownBps:   maxDrawdownBps,
      maxAllocationWei: maxAllocationWei,
      investor:         signer.address,
    };

    // ethers v6: signer.signTypedData(domain, types, value)
    return signer.signTypedData(domain, types, value);
  }

  it("emits DelegationDeposited with correct args", async function () {
    const sig = await buildSignature(
      investor,
      POOL_BALANCED,
      agent.address,
      DEPOSIT_AMOUNT,
      MAX_DRAWDOWN_BPS,
      MAX_ALLOCATION_WEI
    );

    await expect(
      vault.connect(investor).depositETH(
        POOL_BALANCED,
        agent.address,
        MAX_DRAWDOWN_BPS,
        MAX_ALLOCATION_WEI,
        sig,
        { value: DEPOSIT_AMOUNT }
      )
    )
      .to.emit(vault, "DelegationDeposited")
      .withArgs(
        investor.address,
        agent.address,
        POOL_BALANCED,
        DEPOSIT_AMOUNT,
        MAX_DRAWDOWN_BPS,
        MAX_ALLOCATION_WEI
      );
  });

  it("updates investorBalances and poolTVL correctly", async function () {
    const sig = await buildSignature(
      investor,
      POOL_BALANCED,
      agent.address,
      DEPOSIT_AMOUNT,
      MAX_DRAWDOWN_BPS,
      MAX_ALLOCATION_WEI
    );

    const tvlBefore = await vault.poolTVL(POOL_BALANCED);
    const balBefore = await vault.investorBalances(investor.address, POOL_BALANCED);

    await vault.connect(investor).depositETH(
      POOL_BALANCED,
      agent.address,
      MAX_DRAWDOWN_BPS,
      MAX_ALLOCATION_WEI,
      sig,
      { value: DEPOSIT_AMOUNT }
    );

    const tvlAfter = await vault.poolTVL(POOL_BALANCED);
    const balAfter = await vault.investorBalances(investor.address, POOL_BALANCED);

    expect(tvlAfter - tvlBefore).to.equal(DEPOSIT_AMOUNT);
    expect(balAfter - balBefore).to.equal(DEPOSIT_AMOUNT);
  });

  it("getDelegation returns correct DelegationParams after deposit", async function () {
    const sig = await buildSignature(
      investor,
      POOL_BALANCED,
      agent.address,
      DEPOSIT_AMOUNT,
      MAX_DRAWDOWN_BPS,
      MAX_ALLOCATION_WEI
    );

    await vault.connect(investor).depositETH(
      POOL_BALANCED,
      agent.address,
      MAX_DRAWDOWN_BPS,
      MAX_ALLOCATION_WEI,
      sig,
      { value: DEPOSIT_AMOUNT }
    );

    const delegation = await vault.getDelegation(investor.address, agent.address);
    expect(delegation.agent).to.equal(agent.address);
    expect(delegation.maxDrawdownBps).to.equal(MAX_DRAWDOWN_BPS);
    expect(delegation.maxAllocationWei).to.equal(MAX_ALLOCATION_WEI);
  });
});
