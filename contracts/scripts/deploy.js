const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

// Initial prices scaled by 1e8
const INITIAL_PRICES = {
  WBTC: "3000000000000",   // 30,000 USD
  WETH: "200000000000",    // 2,000 USD
  USDC: "100000000",       // 1 USD
  LINK: "1500000000",      // 15 USD
  UNI:  "800000000",       // 8 USD
};

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // 1. Deploy MockERC20 x4 (WBTC, USDC, LINK, UNI)
  const MockERC20 = await hre.ethers.getContractFactory("MockERC20");

  const wbtc = await MockERC20.deploy("Wrapped Bitcoin", "WBTC", 8);
  await wbtc.waitForDeployment();
  console.log("WBTC deployed to:", await wbtc.getAddress());

  const usdc = await MockERC20.deploy("USD Coin", "USDC", 6);
  await usdc.waitForDeployment();
  console.log("USDC deployed to:", await usdc.getAddress());

  const link = await MockERC20.deploy("Chainlink", "LINK", 18);
  await link.waitForDeployment();
  console.log("LINK deployed to:", await link.getAddress());

  const uni = await MockERC20.deploy("Uniswap", "UNI", 18);
  await uni.waitForDeployment();
  console.log("UNI deployed to:", await uni.getAddress());

  // 2. Deploy MockPriceFeed
  // We include WETH as a 5th token (no ERC20 needed, just price tracking)
  // For simplicity, use a placeholder address for WETH price tracking
  const wethPlaceholder = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"; // mainnet WETH

  const tokenAddresses = [
    await wbtc.getAddress(),
    wethPlaceholder,
    await usdc.getAddress(),
    await link.getAddress(),
    await uni.getAddress(),
  ];
  const initialPrices = [
    INITIAL_PRICES.WBTC,
    INITIAL_PRICES.WETH,
    INITIAL_PRICES.USDC,
    INITIAL_PRICES.LINK,
    INITIAL_PRICES.UNI,
  ];

  const MockPriceFeed = await hre.ethers.getContractFactory("MockPriceFeed");
  const priceFeed = await MockPriceFeed.deploy(tokenAddresses, initialPrices);
  await priceFeed.waitForDeployment();
  console.log("MockPriceFeed deployed to:", await priceFeed.getAddress());

  // 3. Deploy MockUniswapRouter
  const MockUniswapRouter = await hre.ethers.getContractFactory("MockUniswapRouter");
  const router = await MockUniswapRouter.deploy(await priceFeed.getAddress());
  await router.waitForDeployment();
  console.log("MockUniswapRouter deployed to:", await router.getAddress());

  // 4. Deploy MockAavePool
  const MockAavePool = await hre.ethers.getContractFactory("MockAavePool");
  const aavePool = await MockAavePool.deploy();
  await aavePool.waitForDeployment();
  console.log("MockAavePool deployed to:", await aavePool.getAddress());

  // 5. Deploy MockStakeToken
  const MockStakeToken = await hre.ethers.getContractFactory("MockStakeToken");
  const stakeToken = await MockStakeToken.deploy();
  await stakeToken.waitForDeployment();
  console.log("MockStakeToken deployed to:", await stakeToken.getAddress());

  // 6. Deploy AgentRegistry
  const AgentRegistry = await hre.ethers.getContractFactory("AgentRegistry");
  const registry = await AgentRegistry.deploy(await stakeToken.getAddress());
  await registry.waitForDeployment();
  console.log("AgentRegistry deployed to:", await registry.getAddress());

  // 7. Deploy CapitalVault
  const CapitalVault = await hre.ethers.getContractFactory("CapitalVault");
  const vault = await CapitalVault.deploy();
  await vault.waitForDeployment();
  console.log("CapitalVault deployed to:", await vault.getAddress());

  // 8. Deploy AllocationEngine
  const AllocationEngine = await hre.ethers.getContractFactory("AllocationEngine");
  const engine = await AllocationEngine.deploy(await vault.getAddress());
  await engine.waitForDeployment();
  console.log("AllocationEngine deployed to:", await engine.getAddress());

  // 9. Deploy SlashingModule
  const SlashingModule = await hre.ethers.getContractFactory("SlashingModule");
  const slashing = await SlashingModule.deploy(
    await vault.getAddress(),
    await registry.getAddress()
  );
  await slashing.waitForDeployment();
  console.log("SlashingModule deployed to:", await slashing.getAddress());

  // 10. Wire contracts
  await vault.setAllocationEngine(await engine.getAddress());
  await vault.setSlashingModule(await slashing.getAddress());
  await vault.setTradingContracts(
    await router.getAddress(),
    await aavePool.getAddress(),
    await priceFeed.getAddress()
  );
  console.log("Vault wired to AllocationEngine, SlashingModule, and trading contracts");

  // 11. Register Hardhat accounts as agents in CapitalVault so they can trade
  const hardhatAccounts = [
    "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    "0x90F79bf6EB2c4f870365E785982E1f101E93b906",
    "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
  ];
  for (const acct of hardhatAccounts) {
    await vault.registerAgent(acct);
  }
  console.log("Registered 5 Hardhat accounts as agents in CapitalVault");

  // 12. Transfer MockERC20 ownership to MockUniswapRouter and MockAavePool so they can mint
  // Router gets ownership of WBTC, USDC, LINK, UNI
  await wbtc.transferOwnership(await router.getAddress());
  await usdc.transferOwnership(await router.getAddress());
  await link.transferOwnership(await router.getAddress());
  await uni.transferOwnership(await router.getAddress());
  console.log("MockERC20 ownership transferred to MockUniswapRouter");

  // Note: MockAavePool uses mint via borrow — for borrow to work, router must be owner.
  // In a real setup you'd use a multi-owner pattern; for simulation, router owns all tokens.

  console.log("\n--- Deployment Summary ---");
  console.log("WBTC:             ", await wbtc.getAddress());
  console.log("USDC:             ", await usdc.getAddress());
  console.log("LINK:             ", await link.getAddress());
  console.log("UNI:              ", await uni.getAddress());
  console.log("MockPriceFeed:    ", await priceFeed.getAddress());
  console.log("MockUniswapRouter:", await router.getAddress());
  console.log("MockAavePool:     ", await aavePool.getAddress());
  console.log("MockStakeToken:   ", await stakeToken.getAddress());
  console.log("AgentRegistry:    ", await registry.getAddress());
  console.log("CapitalVault:     ", await vault.getAddress());
  console.log("AllocationEngine: ", await engine.getAddress());
  console.log("SlashingModule:   ", await slashing.getAddress());

  // 12. Write extended config.json for the frontend
  const configDir = path.resolve(__dirname, "../../frontend/src/contracts");
  fs.mkdirSync(configDir, { recursive: true });

  const config = {
    CapitalVault:      hre.ethers.getAddress(await vault.getAddress()),
    AllocationEngine:  hre.ethers.getAddress(await engine.getAddress()),
    AgentRegistry:     hre.ethers.getAddress(await registry.getAddress()),
    SlashingModule:    hre.ethers.getAddress(await slashing.getAddress()),
    MockUniswapRouter: hre.ethers.getAddress(await router.getAddress()),
    MockAavePool:      hre.ethers.getAddress(await aavePool.getAddress()),
    MockPriceFeed:     hre.ethers.getAddress(await priceFeed.getAddress()),
    WBTC:              hre.ethers.getAddress(await wbtc.getAddress()),
    USDC:              hre.ethers.getAddress(await usdc.getAddress()),
    LINK:              hre.ethers.getAddress(await link.getAddress()),
    UNI:               hre.ethers.getAddress(await uni.getAddress()),
  };

  const configPath = path.join(configDir, "config.json");
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log("\nWrote contract config to:", configPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
