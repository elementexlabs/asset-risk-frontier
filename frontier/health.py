"""Selected CNAIM v2.1 equations, independently implemented from publication.

Sections 6.1.1 and 6.1.4-7, equations 3-9, table 5.
This kernel takes calibrated factors as inputs. It is not the complete CNAIM.
No fleet score is permitted without observed age and an applicable calibration.
"""

import math


def health_score(
    age: float | None,
    normal_life: float,
    location_factor: float,
    duty_factor: float,
    condition_factor: float = 1.0,
    reliability_factor: float = 1.0,
    cap: float = 10.0,
    collar: float = 0.5,
    reliability_collar: float = 0.5,
) -> float | None:
    if age is None:
        return None
    values = (
        age,
        normal_life,
        location_factor,
        duty_factor,
        condition_factor,
        reliability_factor,
        cap,
        collar,
        reliability_collar,
    )
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Health inputs must be finite")
    if age < 0 or min(values[1:6]) <= 0:
        raise ValueError("Age must be nonnegative and life/factors positive")
    if not all(0.5 <= v <= 10 for v in (cap, collar, reliability_collar)):
        raise ValueError("Caps and collars must lie in the current-health range")
    expected_life = normal_life / (location_factor * duty_factor)
    # Cap the exponent before evaluating to avoid overflow at extreme ages.
    initial = 0.5 * math.exp(min(math.log(11), math.log(11) * age / expected_life))
    current = min(initial * condition_factor * reliability_factor, cap, 10.0)
    return min(10.0, max(current, collar, reliability_collar))


def failure_rate(score: float, k: float, c: float = 1.087) -> float:
    """EQ. 3 annual functional failure rate, not a transported fleet probability."""
    if not all(math.isfinite(v) for v in (score, k, c)) or k <= 0 or c <= 0:
        raise ValueError("Invalid curve inputs")
    if not 0.5 <= score <= 15:
        raise ValueError("Score outside published range")
    x = c * max(4.0, score)
    return k * (1 + x + x**2 / 2 + x**3 / 6)


def band(score: float) -> int:
    if not math.isfinite(score) or not 0.5 <= score <= 15:
        raise ValueError("Score outside published range")
    return 1 + sum(score >= threshold for threshold in (3, 5.5, 6.5, 8))
