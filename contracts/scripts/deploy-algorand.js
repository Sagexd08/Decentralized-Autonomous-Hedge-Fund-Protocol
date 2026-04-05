/*
Deploys four minimal AVM applications on Algorand testnet and writes
application IDs back into backend/.env for runtime consumption.

Env resolution (priority):
1) ALGORAND_CLI_MNEMONIC
2) ALGORAND_WALLET_ALIAS via `algokit task wallet get <alias>`
3) first entry in ALGORAND_PRIVATE_KEYS (base64 key or mnemonic)

Network resolution:
- ALGORAND_ALGOD_URL + ALGORAND_API_TOKEN
- OR ALGORAND_DATA_DIR/algod.net + algod.token (goal-compatible)
*/
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const algosdk = require("algosdk");
const dotenv = require("dotenv");

const ROOT = path.resolve(__dirname, "..", "..");
const BACKEND_ENV = path.resolve(ROOT, "backend", ".env");

dotenv.config({ path: BACKEND_ENV });

function readTextIfExists(filePath) {
  try {
    if (fs.existsSync(filePath)) {
      return fs.readFileSync(filePath, "utf8").trim();
    }
  } catch {
    // ignore
  }
  return "";
}

function resolveAlgodConfig() {
  const envAlgod = (process.env.ALGORAND_ALGOD_URL || "").trim();
  const envToken = (process.env.ALGORAND_API_TOKEN || "").trim();
  const dataDir = (process.env.ALGORAND_DATA_DIR || "").trim();

  let dataDirAlgod = "";
  let dataDirToken = "";
  if (dataDir) {
    const algodNet = readTextIfExists(path.join(dataDir, "algod.net"));
    const algodToken = readTextIfExists(path.join(dataDir, "algod.token"));
    dataDirAlgod = algodNet
      ? (algodNet.startsWith("http://") || algodNet.startsWith("https://") ? algodNet : `http://${algodNet}`)
      : "";
    dataDirToken = algodToken;
  }

  return {
    algodUrl: envAlgod || dataDirAlgod,
    apiToken: envToken || dataDirToken,
    dataDir,
  };
}

function normalizePrivateKey(rawValue) {
  const raw = (rawValue || "").trim();
  if (!raw) return null;

  // mnemonic
  if (raw.split(/\s+/).length === 25) {
    return algosdk.mnemonicToSecretKey(raw).sk;
  }

  // base64-encoded 64-byte secret key
  try {
    const decoded = new Uint8Array(Buffer.from(raw, "base64"));
    if (decoded.length === 64) return decoded;
  } catch {
    // ignore
  }

  // JSON array / object encoded key support (best effort)
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length === 64) {
      return new Uint8Array(parsed);
    }
    if (parsed && typeof parsed === "object") {
      const candidate =
        parsed.private_key ||
        parsed.privateKey ||
        parsed.secret_key ||
        parsed.secretKey ||
        parsed.sk;
      if (candidate && typeof candidate === "string") {
        return normalizePrivateKey(candidate);
      }
    }
  } catch {
    // ignore
  }

  return null;
}

function deriveAddressFromSk(sk) {
  if (!sk || sk.length !== 64) return "";
  try {
    return algosdk.encodeAddress(sk.slice(32));
  } catch {
    return "";
  }
}

function tryResolveFromWalletAlias() {
  const alias = (process.env.ALGORAND_WALLET_ALIAS || "").trim();
  if (!alias) return null;

  const algokitBin = (process.env.ALGORAND_ALGOKIT_BIN || "algokit").trim();
  const commands = [`"${algokitBin}" task wallet get "${alias}"`];

  let lastOutput = "";
  for (const cmd of commands) {
    try {
      const output = execSync(cmd, {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      }).trim();

      lastOutput = output;

      // direct mnemonic/base64 output
      const directSk = normalizePrivateKey(output);
      if (directSk) {
        return {
          sk: directSk,
          addr: deriveAddressFromSk(directSk),
          source: `wallet-alias:${alias}`,
        };
      }

      // JSON output support
      try {
        const parsed = JSON.parse(output);
        const candidate =
          parsed?.mnemonic ||
          parsed?.private_key ||
          parsed?.privateKey ||
          parsed?.secret_key ||
          parsed?.secretKey ||
          parsed?.sk ||
          parsed?.account?.mnemonic ||
          parsed?.account?.private_key ||
          parsed?.account?.privateKey ||
          parsed?.account?.sk;

        const sk = normalizePrivateKey(typeof candidate === "string" ? candidate : "");
        if (sk) {
          return {
            sk,
            addr: parsed?.address || parsed?.account?.address || deriveAddressFromSk(sk),
            source: `wallet-alias:${alias}`,
          };
        }
      } catch {
        // ignore parse errors
      }
    } catch (err) {
      const stderr = (err?.stderr || "").toString().trim();
      if (stderr) lastOutput = stderr;
    }
  }

  throw new Error(
    [
      `ALGORAND_WALLET_ALIAS='${alias}' was set, but no usable private key was returned.`,
      "Note: `algokit task wallet get` returns address metadata and does not expose private key material.",
      "Use ALGORAND_CLI_MNEMONIC or ALGORAND_PRIVATE_KEYS for this script's signer,",
      "or switch deployment flow to native AlgoKit commands that sign internally,",
      "or set ALGORAND_ALGOKIT_BIN to full path of algokit executable.",
      lastOutput ? `Wallet output: ${lastOutput}` : "",
    ].join(" ")
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function ensureMinimumBalance(algodClient, address, minMicroAlgos) {
  const info = await algodClient.accountInformation(address).do();
  const current = Number(info?.amount || 0);
  if (current >= minMicroAlgos) {
    return { funded: false, amount: current };
  }

  const dispenserToken = (process.env.ALGORAND_DISPENSER_ACCESS_TOKEN || "").trim();
  const dispenserUrl =
    (process.env.ALGORAND_DISPENSER_URL || "https://api.dispenser.algorandfoundation.tools/fund/0").trim();
  const topUpAmount = Number((process.env.ALGORAND_AUTO_FUND_MICROALGOS || "5000000").trim() || "5000000");

  if (!dispenserToken) {
    throw new Error(
      [
        `Deployer ${address} has ${current} µAlgo, requires at least ${minMicroAlgos} µAlgo.`,
        "Set ALGORAND_DISPENSER_ACCESS_TOKEN to allow automatic funding,",
        "or fund this address manually via https://lora.algokit.io/testnet/fund.",
      ].join(" ")
    );
  }

  const response = await fetch(dispenserUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${dispenserToken}`,
    },
    body: JSON.stringify({
      receiver: address,
      amount: topUpAmount,
      assetID: 0,
    }),
  });

  if (!response.ok) {
    const errBody = await response.text();
    throw new Error(
      `Dispenser funding failed (${response.status} ${response.statusText}): ${errBody}`
    );
  }

  // Wait for funds to land.
  for (let i = 0; i < 10; i++) {
    await sleep(1500);
    const refreshed = await algodClient.accountInformation(address).do();
    const amount = Number(refreshed?.amount || 0);
    if (amount >= minMicroAlgos) {
      return { funded: true, amount };
    }
  }

  const finalInfo = await algodClient.accountInformation(address).do();
  const finalAmount = Number(finalInfo?.amount || 0);
  throw new Error(
    `Funding request sent but balance is still ${finalAmount} µAlgo; need ${minMicroAlgos} µAlgo.`
  );
}

function resolveDeployerSigner() {
  const cliMnemonic = (process.env.ALGORAND_CLI_MNEMONIC || "").trim();
  if (cliMnemonic) {
    const acct = algosdk.mnemonicToSecretKey(cliMnemonic);
    return { sk: acct.sk, addr: acct.addr, source: "ALGORAND_CLI_MNEMONIC" };
  }

  const walletAliasSigner = tryResolveFromWalletAlias();
  if (walletAliasSigner) {
    return walletAliasSigner;
  }

  const keysRaw = (process.env.ALGORAND_PRIVATE_KEYS || "").trim();
  if (!keysRaw) return null;

  const first = keysRaw.split(",").map((x) => x.trim()).find(Boolean);
  if (!first) return null;

  const sk = normalizePrivateKey(first);
  if (!sk) return null;

  if (first.split(/\s+/).length === 25) {
    const acct = algosdk.mnemonicToSecretKey(first);
    return { sk: acct.sk, addr: acct.addr, source: "ALGORAND_PRIVATE_KEYS:mnemonic" };
  }

  return {
    sk,
    addr: deriveAddressFromSk(sk),
    source: "ALGORAND_PRIVATE_KEYS",
  };
}

function upsertEnv(content, key, value) {
  const line = `${key}=${value}`;
  const re = new RegExp(`^${key}=.*$`, "m");
  if (re.test(content)) return content.replace(re, line);
  if (!content.endsWith("\n")) content += "\n";
  return `${content}${line}\n`;
}

async function createMinimalApp(algodClient, deployerAddr, deployerSk, label) {
  const approval = `#pragma version 8\nbyte \"${label}\"\npop\nint 1`;
  const clear = "#pragma version 8\nint 1";

  const approvalResult = await algodClient.compile(approval).do();
  const clearResult = await algodClient.compile(clear).do();

  const approvalProgram = new Uint8Array(Buffer.from(approvalResult.result, "base64"));
  const clearProgram = new Uint8Array(Buffer.from(clearResult.result, "base64"));

  const suggestedParams = await algodClient.getTransactionParams().do();
  const txn = algosdk.makeApplicationCreateTxnFromObject({
    sender: deployerAddr,
    suggestedParams,
    onComplete: algosdk.OnApplicationComplete.NoOpOC,
    approvalProgram,
    clearProgram,
    numGlobalInts: 2,
    numGlobalByteSlices: 2,
    numLocalInts: 0,
    numLocalByteSlices: 0,
  });

  const signed = txn.signTxn(deployerSk);
  const { txid } = await algodClient.sendRawTransaction(signed).do();
  const confirmed = await algosdk.waitForConfirmation(algodClient, txid, 6);
  const appId = confirmed["application-index"] || confirmed.applicationIndex;
  if (!appId) throw new Error(`Application ID missing for ${label}, txid=${txid}`);

  return { appId, txid };
}

async function main() {
  const { algodUrl, apiToken, dataDir } = resolveAlgodConfig();
  if (!algodUrl) {
    throw new Error("Algorand node URL not resolved. Set ALGORAND_ALGOD_URL or ALGORAND_DATA_DIR.");
  }

  const signer = resolveDeployerSigner();
  if (!signer?.sk) {
    throw new Error(
      "No deployer key found. Set ALGORAND_CLI_MNEMONIC, ALGORAND_WALLET_ALIAS, or ALGORAND_PRIVATE_KEYS."
    );
  }
  const deployerSk = signer.sk;

  const headers = apiToken ? { "X-Algo-API-Token": apiToken } : undefined;
  const algodClient = new algosdk.Algodv2(apiToken, algodUrl, undefined, headers);
  const deployerAddr = signer.addr || deriveAddressFromSk(deployerSk);

  // 4 app creates + app min-balance increases + fees, with safety margin.
  const requiredBalance = Number((process.env.ALGORAND_REQUIRED_BALANCE_MICROALGOS || "3000000").trim() || "3000000");
  const balanceResult = await ensureMinimumBalance(algodClient, deployerAddr, requiredBalance);

  const status = await algodClient.status().do();
  console.log("Connected to algod:", algodUrl, "round", status["last-round"]);
  console.log("Deployer source:", signer.source || "unknown");
  if (dataDir) console.log("ALGORAND_DATA_DIR:", dataDir);
  if (balanceResult.funded) {
    console.log(`Auto-funded ${deployerAddr}; balance=${balanceResult.amount} µAlgo`);
  } else {
    console.log(`Deployer balance OK: ${balanceResult.amount} µAlgo`);
  }

  const mapping = [
    ["agent_registry", "ALGORAND_AGENT_REGISTRY_APP_ID", "agent_registry"],
    ["allocation_engine", "ALGORAND_ALLOCATION_ENGINE_APP_ID", "allocation_engine"],
    ["capital_vault", "ALGORAND_CAPITAL_VAULT_APP_ID", "capital_vault"],
    ["slashing_module", "ALGORAND_SLASHING_MODULE_APP_ID", "slashing_module"],
  ];

  const out = {};
  for (const [key, envKey, label] of mapping) {
    const { appId, txid } = await createMinimalApp(algodClient, deployerAddr, deployerSk, label);
    const appIdValue = Number(appId);
    out[key] = { app_id: appIdValue, txid };
    out[envKey] = appIdValue;
    console.log(`${label}: app_id=${appIdValue} txid=${txid}`);
  }

  const outFile = path.resolve(ROOT, "backend", "contracts", "algorand_apps.json");
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  fs.writeFileSync(outFile, JSON.stringify(out, null, 2));
  console.log("Wrote:", outFile);

  let envContent = fs.existsSync(BACKEND_ENV) ? fs.readFileSync(BACKEND_ENV, "utf8") : "";
  envContent = upsertEnv(envContent, "ALGORAND_AGENT_REGISTRY_APP_ID", String(out.ALGORAND_AGENT_REGISTRY_APP_ID));
  envContent = upsertEnv(envContent, "ALGORAND_ALLOCATION_ENGINE_APP_ID", String(out.ALGORAND_ALLOCATION_ENGINE_APP_ID));
  envContent = upsertEnv(envContent, "ALGORAND_CAPITAL_VAULT_APP_ID", String(out.ALGORAND_CAPITAL_VAULT_APP_ID));
  envContent = upsertEnv(envContent, "ALGORAND_SLASHING_MODULE_APP_ID", String(out.ALGORAND_SLASHING_MODULE_APP_ID));
  fs.writeFileSync(BACKEND_ENV, envContent);
  console.log("Updated:", BACKEND_ENV);
}

main().catch((err) => {
  console.error("Algorand deploy failed:", err.message || err);
  process.exit(1);
});
