"""Real forward-pass tests for the CNN-LSTM hybrid model."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
import pytest
from ml.hybrid_model import CNNLSTMModel

BATCH = 8
WINDOW = 50
FEATURES = 10


@pytest.fixture(scope="module")
def model():
    m = CNNLSTMModel(input_size=FEATURES, window_size=WINDOW)
    m.eval()
    return m


@pytest.fixture(scope="module")
def sample_input():
    torch.manual_seed(42)
    return torch.randn(BATCH, WINDOW, FEATURES)


def test_output_shape(model, sample_input):
    """Forward pass must return a 1-D tensor of length == batch size."""
    with torch.no_grad():
        out = model(sample_input)
    assert out.shape == (BATCH,), f"Expected ({BATCH},), got {out.shape}"


def test_output_is_finite(model, sample_input):
    """No NaN or Inf values in predictions."""
    with torch.no_grad():
        out = model(sample_input)
    assert torch.isfinite(out).all(), f"Non-finite values: {out}"


def test_output_is_scalar_regression(model, sample_input):
    """Outputs should be unbounded real numbers (regression, not probabilities)."""
    with torch.no_grad():
        out = model(sample_input)
    # Not clamped to [0,1] — regression target
    assert out.dtype in (torch.float32, torch.float64)


def test_different_inputs_give_different_outputs(model):
    """Two different inputs must not produce identical outputs (model is not degenerate)."""
    torch.manual_seed(0)
    x1 = torch.randn(BATCH, WINDOW, FEATURES)
    x2 = torch.randn(BATCH, WINDOW, FEATURES)
    with torch.no_grad():
        o1 = model(x1)
        o2 = model(x2)
    assert not torch.allclose(o1, o2), "Model produces identical output for different inputs"


def test_batch_size_one(model):
    """Model must handle batch size of 1 (single inference)."""
    x = torch.randn(1, WINDOW, FEATURES)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (1,)
    assert torch.isfinite(out).all()


def test_gradient_flows_during_training():
    """Gradients must propagate to all parameters during a training step."""
    train_model = CNNLSTMModel(input_size=FEATURES, window_size=WINDOW)
    train_model.train()
    x = torch.randn(BATCH, WINDOW, FEATURES)
    target = torch.randn(BATCH)

    optimizer = torch.optim.Adam(train_model.parameters(), lr=1e-3)
    optimizer.zero_grad()
    out = train_model(x)
    loss = torch.nn.functional.mse_loss(out, target)
    loss.backward()

    for name, param in train_model.named_parameters():
        assert param.grad is not None, f"No gradient for {name}"
        assert torch.isfinite(param.grad).all(), f"Non-finite gradient for {name}"

    optimizer.step()
    assert loss.item() > 0


def test_deterministic_inference(model, sample_input):
    """Same input must give same output across multiple calls (eval mode)."""
    with torch.no_grad():
        o1 = model(sample_input)
        o2 = model(sample_input)
    assert torch.allclose(o1, o2), "Non-deterministic inference in eval mode"


def test_prediction_range_reasonable(model):
    """Predictions on normalised OHLCV-like inputs stay within a reasonable range."""
    # Simulate normalised return-like features (mean~0, std~1)
    torch.manual_seed(7)
    x = torch.randn(100, WINDOW, FEATURES)
    with torch.no_grad():
        out = model(x)
    # Untrained model — outputs should not explode
    assert out.abs().max().item() < 1e4, f"Predictions exploded: max={out.abs().max().item()}"
