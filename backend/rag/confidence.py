"""Confidence normalization and bucket policy.

The thresholds are versioned so a later fit against reviewed evaluation data
can replace this policy without changing the API contract.
"""
from typing import Literal

ConfidenceBucket = Literal["low", "medium", "high"]
CALIBRATION_VERSION = "baseline-2026-09-21"


def calibrated_score(raw_score: float) -> float:
    return max(0.0, min(1.0, float(raw_score)))


def bucket_for(score: float) -> ConfidenceBucket:
    calibrated = calibrated_score(score)
    if calibrated >= 0.75:
        return "high"
    if calibrated >= 0.50:
        return "medium"
    return "low"
