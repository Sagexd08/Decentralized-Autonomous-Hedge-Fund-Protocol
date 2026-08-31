"""
How long to train, and on how much at a time — Phase 13.

Both torch models were written full-batch: one forward and backward pass over
the entire training set per epoch, three hundred times. On the 600-sample
synthetic tape that is fast and perfectly reasonable.

On real market data it stops being either. A cost that is O(epochs x samples)
with epochs fixed means the price of training grows with every day of history
ingested, and it grows fastest for the transformer, whose attention is
quadratic in sequence length. Moving from two days of one-minute bars to five
took a single transformer fit from about ninety seconds to roughly forty
minutes — and there is one fit per agent, because model identity is per agent
(invariant 3). Eight agents at forty minutes is not a system anybody will run.

So training is budgeted in **gradient updates**, not epochs, and each update
sees a mini-batch rather than the whole set:

  * the cost of a fit is bounded and independent of how much history exists,
    so ingesting more data never makes the protocol unusable;
  * more data means more distinct batches rather than more expensive steps,
    which is the direction that actually helps;
  * and mini-batch gradients are noisier, which for a model this small is a
    regulariser rather than a problem.

The budget is deliberately the same for both models. They are compared against
each other and against the baseline in the Phase 4 evaluation, and a comparison
where one model was given three times the compute is a comparison of budgets.
"""

from __future__ import annotations

# Total gradient updates per fit. Chosen so a transformer fit stays near the
# ninety seconds it took on the old synthetic tape, which is what keeps a cold
# container inside the section 27 boot budget.
UPDATE_BUDGET = 900

# Samples per update. Large enough that a batch's gradient is not dominated by
# a handful of outlier bars, small enough that a step is cheap.
BATCH_SIZE = 256

# Fewer samples than this and mini-batching buys nothing; the whole set is one
# batch and the run is the full-batch schedule it always was.
MIN_BATCHED_SAMPLES = 512

# What a small, full-batch run gets. Deliberately the schedule these models
# were validated on before the budget existed, and deliberately *not* the
# budget: spending 900 full-batch passes on a couple of hundred samples does
# not bound any cost worth bounding, it just overfits.
#
# It measurably does. At 900 passes over 200 samples the transformer drove its
# training residuals to near zero, and since the spread head is fitted against
# |residual| the model came to report an error bar 64x smaller than the scale
# of its own targets — which, because confidence is expected_return / spread,
# would have made every prediction it produced look near-certain.
FULL_BATCH_EPOCHS = 300


def plan(n_samples: int) -> tuple[int, int, int]:
    """
    (batch_size, steps_per_epoch, epochs) for a dataset of `n_samples`.

    `epochs` is derived so that `steps_per_epoch * epochs` lands on the update
    budget, which is what makes the wall-clock cost flat as history grows.
    Always at least one epoch: a dataset smaller than one batch still gets
    trained on, it simply gets the full-batch schedule.
    """
    n = max(1, int(n_samples))
    if n < MIN_BATCHED_SAMPLES:
        return n, 1, FULL_BATCH_EPOCHS

    batch = min(BATCH_SIZE, n)
    steps = max(1, n // batch)
    epochs = max(1, round(UPDATE_BUDGET / steps))
    return batch, steps, epochs


def total_updates(n_samples: int) -> int:
    """What `plan` actually spends. Within rounding of the budget."""
    _batch, steps, epochs = plan(n_samples)
    return steps * epochs
