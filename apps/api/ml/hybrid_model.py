"""CNN + LSTM Hybrid Model for Financial Time-Series Prediction."""

import torch
import torch.nn as nn

class CNNLSTMModel(nn.Module):
    """
    Hybrid CNN-LSTM regression model.

    Input shape : (batch, window_size, input_size)
    Output shape: (batch,)  — scalar next-return prediction
    """

    def __init__(
        self,
        input_size: int = 10,
        window_size: int = 50,
        cnn_channels: list = (16, 32),
        lstm_hidden: int = 64,
        lstm_layers: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()

        cnn_layers = []
        in_ch = input_size
        for out_ch in cnn_channels:
            cnn_layers += [
                nn.Conv1d(in_channels=in_ch, out_channels=out_ch, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.BatchNorm1d(out_ch),
            ]
            in_ch = out_ch
        self.cnn = nn.Sequential(*cnn_layers)

        self.lstm = nn.LSTM(
            input_size=in_ch,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
        )

        self.fc = nn.Sequential(
            nn.Linear(lstm_hidden, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.permute(0, 2, 1)
        x = self.cnn(x)
        x = x.permute(0, 2, 1)
        _, (h_n, _) = self.lstm(x)
        x = h_n[-1]
        return self.fc(x).squeeze(-1)
