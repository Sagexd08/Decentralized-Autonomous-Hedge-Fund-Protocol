import os
import io
import pickle
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import confusion_matrix, mean_squared_error, mean_absolute_error

from core.supabase import download_storage_file, upload_storage_file
from ml.hybrid_model import CNNLSTMModel
from ml.regime_classifier import RegimeClassifier, rolling_volatility
from ml.monte_carlo import gbm_paths, var_cvar

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

WINDOW_SIZE   = 50
BATCH_SIZE    = 64
EPOCHS        = 30
LR            = 1e-3
ONLINE_STEPS  = 200
PATIENCE      = 5
MODEL_PATH    = Path("backend/ml/model.pkl")
DEVICE        = torch.device("cpu")
DECISION_LABELS = ("SELL", "HOLD", "BUY")

def load_bitcoin_data() -> pd.DataFrame:
    """
    Download Bitcoin historical OHLCV data from Kaggle via kagglehub.
    Falls back gracefully if the dataset is unavailable.
    """
    log.info("Fetching Bitcoin dataset from Kaggle…")
    try:
        import kagglehub
        from kagglehub import KaggleDatasetAdapter

        hf_dataset = kagglehub.load_dataset(
            KaggleDatasetAdapter.HUGGING_FACE,
            "mczielinski/bitcoin-historical-data",
            "bitstampUSD_1-min_data_2012-01-01_to_2021-03-31.csv",
        )
        df = hf_dataset.to_pandas() if hasattr(hf_dataset, "to_pandas") else hf_dataset["train"].to_pandas()
        log.info("Loaded %d rows from Kaggle.", len(df))
    except Exception as exc:
        log.warning("Kaggle load failed (%s) — generating synthetic OHLCV data.", exc)
        df = _synthetic_ohlcv(5000)

    return df

def _synthetic_ohlcv(n: int = 5000) -> pd.DataFrame:
    """Fallback: generate synthetic OHLCV that mimics Bitcoin dynamics."""
    np.random.seed(42)
    price = 30_000.0
    prices = [price]
    for _ in range(n - 1):
        price *= np.exp(np.random.normal(0, 0.02))
        prices.append(price)
    prices = np.array(prices)
    df = pd.DataFrame({
        "Timestamp": pd.date_range("2017-01-01", periods=n, freq="h"),
        "Open":   prices * (1 + np.random.uniform(-0.005, 0.005, n)),
        "High":   prices * (1 + np.random.uniform(0.001, 0.015, n)),
        "Low":    prices * (1 - np.random.uniform(0.001, 0.015, n)),
        "Close":  prices,
        "Volume": np.random.uniform(1e7, 5e8, n),
    })
    return df

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a rich feature matrix from raw OHLCV data.
    Returns a DataFrame with NaNs dropped.
    """

    df.columns = [c.strip().capitalize() for c in df.columns]
    required = {"Open", "High", "Low", "Close", "Volume"}

    rename_map = {"Weightedprice": "Close", "Closeprice": "Close"}
    df.rename(columns=rename_map, inplace=True)

    if not required.issubset(df.columns):

        price_col = next((c for c in df.columns if "close" in c.lower() or "price" in c.lower()), None)
        if price_col:
            df["Close"] = df[price_col]
        else:
            raise ValueError(f"Cannot find OHLCV columns. Got: {df.columns.tolist()}")

    df = df[list(required)].copy().astype(float)
    df.sort_index(inplace=True)
    df.dropna(inplace=True)

    c = df["Close"]

    df["return_1"]   = c.pct_change(1)
    df["return_5"]   = c.pct_change(5)
    df["log_return"] = np.log(c / c.shift(1))
    df["price_diff"] = c.diff(1)

    for w in (10, 20):
        df[f"roll_mean_{w}"]  = c.rolling(w).mean()
        df[f"roll_std_{w}"]   = c.rolling(w).std()
        df[f"roll_vol_{w}"]   = df["log_return"].rolling(w).std()

    df["momentum_10"] = c - c.shift(10)
    df["momentum_20"] = c - c.shift(20)

    df["hl_spread"]   = (df["High"] - df["Low"]) / df["Close"]
    df["body_ratio"]  = (df["Close"] - df["Open"]).abs() / (df["High"] - df["Low"] + 1e-8)

    df["vol_norm"]    = df["Volume"] / df["Volume"].rolling(20).mean()

    df["target"] = df["log_return"].shift(-1)

    df.dropna(inplace=True)
    log.info("Feature matrix shape: %s", df.shape)
    return df

FEATURE_COLS = [
    "Open", "High", "Low", "Close", "Volume",
    "return_1", "return_5", "log_return", "price_diff",
    "roll_mean_10", "roll_std_10", "roll_vol_10",
    "roll_mean_20", "roll_std_20", "roll_vol_20",
    "momentum_10", "momentum_20",
    "hl_spread", "body_ratio", "vol_norm",
]

class OHLCVDataset(Dataset):
    """Sliding-window dataset: X = (window, features), y = scalar."""

    def __init__(self, X: np.ndarray, y: np.ndarray, window: int = WINDOW_SIZE):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32)
        self.window = window

    def __len__(self):
        return len(self.X) - self.window

    def __getitem__(self, idx):
        return self.X[idx : idx + self.window], self.y[idx + self.window]

def train_batch(
    model: CNNLSTMModel,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = EPOCHS,
    lr: float = LR,
    patience: int = PATIENCE,
) -> list[float]:
    """
    Standard mini-batch training with early stopping.
    Returns list of per-epoch validation losses.
    """
    optimizer  = torch.optim.Adam(model.parameters(), lr=lr)
    criterion  = nn.MSELoss()
    scheduler  = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    val_losses = []
    best_val   = float("inf")
    no_improve = 0

    for epoch in range(1, epochs + 1):

        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            pred  = model(xb)
            loss  = criterion(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(train_loader.dataset)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                pred = model(xb)
                val_loss += criterion(pred, yb).item() * len(xb)
        val_loss /= len(val_loader.dataset)
        val_losses.append(val_loss)

        scheduler.step(val_loss)
        log.info("Epoch %3d/%d | train_loss=%.6f | val_loss=%.6f", epoch, epochs, train_loss, val_loss)

        if val_loss < best_val - 1e-6:
            best_val   = val_loss
            no_improve = 0
            torch.save(model.state_dict(), "/tmp/_best_cnn_lstm.pt")
        else:
            no_improve += 1
            if no_improve >= patience:
                log.info("Early stopping triggered at epoch %d.", epoch)
                break

    model.load_state_dict(torch.load("/tmp/_best_cnn_lstm.pt", map_location=DEVICE))
    return val_losses

def online_train(
    model: CNNLSTMModel,
    X_online: np.ndarray,
    y_online: np.ndarray,
    window: int = WINDOW_SIZE,
    lr: float = 1e-4,
    steps: int = ONLINE_STEPS,
) -> list[float]:
    """
    Active regression: process one sample at a time, update weights immediately.
    Simulates a streaming environment where ground truth arrives after each tick.

    Args:
        X_online : feature array for the online phase
        y_online : target array
        steps    : number of online updates to perform
    Returns:
        list of per-step losses
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
    losses    = []
    n         = len(X_online) - window

    log.info("Starting online learning for %d steps…", min(steps, n))
    model.train()

    for i in range(min(steps, n)):
        x_seq = torch.tensor(
            X_online[i : i + window][np.newaxis],
            dtype=torch.float32,
        ).to(DEVICE)
        y_true = torch.tensor([y_online[i + window]], dtype=torch.float32).to(DEVICE)

        optimizer.zero_grad()
        pred = model(x_seq)
        loss = criterion(pred, y_true)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        losses.append(loss.item())
        if (i + 1) % 50 == 0:
            log.info("  Online step %4d | loss=%.6f", i + 1, loss.item())

    return losses

def evaluate(model: CNNLSTMModel, loader: DataLoader) -> dict:
    """Return regression metrics plus direction-level confusion matrix."""
    model.eval()
    preds, truths = [], []
    with torch.no_grad():
        for xb, yb in loader:
            preds.extend(model(xb.to(DEVICE)).cpu().numpy())
            truths.extend(yb.numpy())
    preds  = np.array(preds)
    truths = np.array(truths)
    mse  = mean_squared_error(truths, preds)
    mae  = mean_absolute_error(truths, preds)
    rmse = np.sqrt(mse)
    pred_actions = [decision(float(pred)) for pred in preds]
    true_actions = [decision(float(truth)) for truth in truths]
    matrix = confusion_matrix(true_actions, pred_actions, labels=list(DECISION_LABELS))
    direction_accuracy = float((np.array(true_actions) == np.array(pred_actions)).mean())

    log.info(
        "Evaluation → MSE=%.6f | MAE=%.6f | RMSE=%.6f | DirectionAcc=%.2f%%",
        mse,
        mae,
        rmse,
        direction_accuracy * 100,
    )
    log.info("Confusion matrix labels: %s", list(DECISION_LABELS))
    for label, row in zip(DECISION_LABELS, matrix.tolist()):
        log.info("  actual=%-4s -> %s", label, row)

    return {
        "mse": float(mse),
        "mae": float(mae),
        "rmse": float(rmse),
        "direction_accuracy": direction_accuracy,
        "confusion_matrix": {
            "labels": list(DECISION_LABELS),
            "values": matrix.tolist(),
        },
    }

def save_model(model: CNNLSTMModel, scaler: StandardScaler, path: Path = MODEL_PATH):
    """Pickle both model weights and scaler into a single file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_state": model.state_dict(),
        "model_config": {
            "input_size":   model.fc[0].in_features,
            "window_size":  WINDOW_SIZE,
            "cnn_channels": [16, 32],
            "lstm_hidden":  64,
            "lstm_layers":  2,
        },
        "scaler": scaler,
    }
    with open(path, "wb") as f:
        pickle.dump(payload, f)
    log.info("Model saved to %s (%.1f KB)", path, path.stat().st_size / 1024)

def load_model(path: Path = MODEL_PATH) -> tuple[CNNLSTMModel, StandardScaler]:
    """Restore model and scaler from a .pkl file."""
    with open(path, "rb") as f:
        payload = pickle.load(f)
    cfg   = payload["model_config"]
    model = CNNLSTMModel(
        input_size   = len(FEATURE_COLS),
        window_size  = cfg["window_size"],
        cnn_channels = cfg["cnn_channels"],
        lstm_hidden  = cfg["lstm_hidden"],
        lstm_layers  = cfg["lstm_layers"],
    ).to(DEVICE)
    model.load_state_dict(payload["model_state"])
    model.eval()
    log.info("Model loaded from %s", path)
    return model, payload["scaler"]

def upload_to_supabase(path: Path = MODEL_PATH):
    """Upload model.pkl to Supabase storage bucket 'models'."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        log.warning("Supabase credentials not found — skipping upload.")
        return

    try:
        bucket = "models"
        remote = "model.pkl"
        upload_storage_file(path, bucket, remote)
        log.info("Model uploaded to Supabase storage: %s/%s", bucket, remote)
    except Exception as exc:
        log.error("Supabase upload failed: %s", exc)

def download_from_supabase(dest: Path = MODEL_PATH):
    """Download model.pkl from Supabase and load it."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        log.warning("Supabase credentials not found — cannot download.")
        return None, None

    try:
        download_storage_file("models", "model.pkl", dest)
        log.info("Model downloaded from Supabase to %s", dest)
        return load_model(dest)
    except Exception as exc:
        log.error("Supabase download failed: %s", exc)
        return None, None

def predict(features: np.ndarray, model: CNNLSTMModel, scaler: StandardScaler) -> float:
    """
    Real-time inference.

    Args:
        features : np.ndarray of shape (window_size, n_features)
                   Raw (unscaled) feature values.
        model    : trained CNNLSTMModel
        scaler   : fitted StandardScaler

    Returns:
        Predicted log-return as a Python float.
        Decision rule:
            > +0.001 → BUY
            < -0.001 → SELL
            else     → HOLD
    """
    model.eval()
    x_scaled = scaler.transform(features)
    x_tensor = torch.tensor(x_scaled[np.newaxis], dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        pred = model(x_tensor).item()
    return pred

def decision(pred_return: float) -> str:
    if pred_return > 0.001:
        return "BUY"
    elif pred_return < -0.001:
        return "SELL"
    return "HOLD"

def main():

    os.environ["KAGGLE_USERNAME"] = "sagexd08"
    os.environ["KAGGLE_KEY"]      = "9226c40ecf21a9e3a13306024efde683"

    env_path = Path(__file__).parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

    df_raw = load_bitcoin_data()

    df = engineer_features(df_raw)

    split  = int(len(df) * 0.8)
    df_tr  = df.iloc[:split]
    df_te  = df.iloc[split:]

    online_start = int(len(df_tr) * 0.9)
    df_online    = df_tr.iloc[online_start:]
    df_tr        = df_tr.iloc[:online_start]

    log.info("Train: %d | Online: %d | Test: %d", len(df_tr), len(df_online), len(df_te))

    scaler    = StandardScaler()
    X_tr_raw  = df_tr[FEATURE_COLS].values
    y_tr      = df_tr["target"].values
    X_tr      = scaler.fit_transform(X_tr_raw)

    X_val_raw = df_te[FEATURE_COLS].values
    y_val     = df_te["target"].values
    X_val     = scaler.transform(X_val_raw)

    X_on      = scaler.transform(df_online[FEATURE_COLS].values)
    y_on      = df_online["target"].values

    train_ds  = OHLCVDataset(X_tr, y_tr)
    val_ds    = OHLCVDataset(X_val, y_val)
    train_dl  = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  drop_last=True)
    val_dl    = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False)

    model = CNNLSTMModel(
        input_size   = len(FEATURE_COLS),
        window_size  = WINDOW_SIZE,
        cnn_channels = [16, 32],
        lstm_hidden  = 64,
        lstm_layers  = 2,
        dropout      = 0.2,
    ).to(DEVICE)

    total_params = sum(p.numel() for p in model.parameters())
    log.info("Model parameters: %d", total_params)

    log.info("═" * 60)
    log.info("PHASE 1: Batch Training")
    log.info("═" * 60)
    train_batch(model, train_dl, val_dl, epochs=EPOCHS, patience=PATIENCE)

    log.info("── Post-batch evaluation ──")
    metrics_batch = evaluate(model, val_dl)

    log.info("═" * 60)
    log.info("PHASE 2: Online / Active Regression")
    log.info("═" * 60)
    online_losses = online_train(model, X_on, y_on, steps=ONLINE_STEPS)
    log.info("Mean online loss: %.6f", float(np.mean(online_losses)))

    log.info("── Post-online evaluation ──")
    metrics_online = evaluate(model, val_dl)

    save_model(model, scaler, MODEL_PATH)

    upload_to_supabase(MODEL_PATH)

    log.info("═" * 60)
    log.info("PHASE 3: Market Regime Analysis")
    log.info("═" * 60)
    test_returns = df_te["log_return"].values
    regime_clf = RegimeClassifier(n_states=3)
    regime_clf.fit(test_returns)
    regimes, confidences = regime_clf.predict(test_returns[-100:])
    vol = rolling_volatility(test_returns, window=30)
    unique, counts = np.unique(regimes, return_counts=True)
    for state, cnt in zip(unique, counts):
        log.info("  Regime %-10s: %d bars (%.1f%%)", state, cnt, 100 * cnt / len(regimes))
    log.info("  Annualised vol (last 30 bars): %.4f", vol[-1])

    log.info("═" * 60)
    log.info("PHASE 4: Monte Carlo Risk Assessment")
    log.info("═" * 60)
    last_close = float(df_te["Close"].iloc[-1])
    mu_est     = float(test_returns.mean() * 252)
    sig_est    = float(test_returns.std() * np.sqrt(252))
    mc_paths   = gbm_paths(S0=last_close, mu=mu_est, sigma=sig_est, T=30, n_paths=2000)
    risk       = var_cvar(mc_paths, confidence=0.95)
    log.info("  30-day Monte Carlo (2000 paths, 95%% confidence):")
    log.info("    VaR            : %+.4f", risk["var"])
    log.info("    CVaR (ES)      : %+.4f", risk["cvar"])
    log.info("    Expected return: %+.4f", risk["expected_return"])
    log.info("    Prob(profit)   : %.2f%%", risk["prob_profit"] * 100)

    sample_window = X_val[:WINDOW_SIZE]

    model.eval()
    x_t  = torch.tensor(sample_window[np.newaxis], dtype=torch.float32)
    pred = model(x_t).item()
    log.info("Demo prediction: %.6f  →  %s", pred, decision(pred))

    log.info("═" * 60)
    log.info("Pipeline complete.")
    log.info("  Batch  → MSE=%.6f | MAE=%.6f", metrics_batch["mse"], metrics_batch["mae"])
    log.info("  Online → MSE=%.6f | MAE=%.6f", metrics_online["mse"], metrics_online["mae"])
    log.info("  Regime (last bar): %s (conf=%.2f)", regimes[-1], confidences[-1])
    log.info("  30d VaR=%.4f | CVaR=%.4f", risk["var"], risk["cvar"])
    log.info("  Model saved: %s", MODEL_PATH)
    log.info("═" * 60)

if __name__ == "__main__":
    main()
