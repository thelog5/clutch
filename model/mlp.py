"""Small PyTorch MLP: 2 hidden layers of 32, sigmoid output, binary cross-entropy.

Training needs torch. Inference doesn't: ``export`` writes the weights and the
input scaler to an ``.npz`` file that ``model.predict`` runs with numpy, so
the deployed API stays light.
"""

from __future__ import annotations

import logging
import time

import numpy as np

log = logging.getLogger(__name__)

HIDDEN = 32


def build(n_features: int):
    import torch.nn as nn

    return nn.Sequential(
        nn.Linear(n_features, HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, 1),  # sigmoid lives in the loss (BCEWithLogits) for stability
    )


def train(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    epochs: int = 30,
    batch_size: int = 4096,
    lr: float = 2e-3,
    patience: int = 4,
    seed: int = 0,
) -> dict:
    """Train with early stopping on validation log loss. Returns exported params."""
    import torch

    torch.manual_seed(seed)
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0) + 1e-6

    def prep(x):
        return torch.from_numpy(((x - mean) / std).astype(np.float32))

    xt, yt = prep(x_train), torch.from_numpy(y_train.astype(np.float32)).unsqueeze(1)
    xv, yv = prep(x_val), torch.from_numpy(y_val.astype(np.float32)).unsqueeze(1)

    net = build(x_train.shape[1])
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=1)
    loss_fn = torch.nn.BCEWithLogitsLoss()

    best_loss, best_state, bad_epochs = float("inf"), None, 0
    gen = torch.Generator().manual_seed(seed)
    for epoch in range(1, epochs + 1):
        started = time.time()
        net.train()
        order = torch.randperm(len(xt), generator=gen)
        for i in range(0, len(xt), batch_size):
            idx = order[i : i + batch_size]
            opt.zero_grad()
            loss = loss_fn(net(xt[idx]), yt[idx])
            loss.backward()
            opt.step()

        net.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(net(xv), yv))
        sched.step(val_loss)
        log.info("mlp epoch %d val logloss %.5f (%.1fs)", epoch, val_loss, time.time() - started)
        if val_loss < best_loss - 1e-5:
            best_loss, bad_epochs = val_loss, 0
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                log.info("mlp early stop at epoch %d", epoch)
                break

    net.load_state_dict(best_state)
    return export(net, mean, std) | {"best_val_logloss": best_loss}


def export(net, mean: np.ndarray, std: np.ndarray) -> dict:
    layers = [m for m in net if hasattr(m, "weight")]
    params = {"mean": mean.astype(np.float32), "std": std.astype(np.float32)}
    for i, layer in enumerate(layers):
        params[f"w{i}"] = layer.weight.detach().numpy().T.copy()
        params[f"b{i}"] = layer.bias.detach().numpy().copy()
    return params


def forward_numpy(params: dict, x: np.ndarray) -> np.ndarray:
    """Probability of a home win, numpy only (matches the torch net)."""
    h = (np.asarray(x, dtype=np.float32) - params["mean"]) / params["std"]
    n_layers = sum(1 for k in params if k.startswith("w"))
    for i in range(n_layers):
        h = h @ params[f"w{i}"] + params[f"b{i}"]
        if i < n_layers - 1:
            h = np.maximum(h, 0.0)
    return 1.0 / (1.0 + np.exp(-np.clip(h[:, 0], -40.0, 40.0)))
