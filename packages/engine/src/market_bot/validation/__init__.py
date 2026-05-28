"""Probabilistic-signal calibration metrics.

Two complementary lenses:

* :func:`brier_score` — single scalar that combines refinement and
  reliability. Lower is better; 0.25 is the score of a random guess that
  always says 50/50. Anything below ~0.22 starts to be meaningful.

* :func:`reliability_bins` — bucketed view: are predictions of ~0.7
  actually right ~70% of the time? Useful to spot systematic over- or
  under-confidence the Brier scalar hides.
"""

from .brier import (
    BrierResult,
    ReliabilityBin,
    brier_score,
    reliability_bins,
    walk_forward_predictions,
)

__all__ = [
    "BrierResult",
    "ReliabilityBin",
    "brier_score",
    "reliability_bins",
    "walk_forward_predictions",
]
