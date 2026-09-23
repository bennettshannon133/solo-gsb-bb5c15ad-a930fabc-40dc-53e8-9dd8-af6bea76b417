"""CIEDE2000 color-difference calculation.

The implementation follows the CIE 142-2003 technical report and the
corrected notation from Sharma, Wu, and Dalal (2005).
"""

from __future__ import annotations

import math
from typing import Final, Sequence

LABComponent = float
LABValue = Sequence[LABComponent]

_PI: Final = math.pi
_RAD: Final = math.pi / 180.0


def _hue_angle(a: float, b: float) -> float:
    """Return a hue angle in degrees in the half-open interval [0, 360)."""
    angle = math.atan2(b, a) / _RAD
    if angle < 0.0:
        angle += 360.0
    return angle


def _seventh_power_ratio(value: float) -> float:
    """Return C**7 / (C**7 + 25**7) without overflowing for large C."""
    if value == 0.0:
        return 0.0
    scaled_denominator = 25.0 / value
    return 1.0 / (1.0 + scaled_denominator**7)


def ciede2000(reference: LABValue, sample: LABValue) -> float:
    """Calculate ΔE00 for two CIELAB values.

    Args:
        reference: ``(L*, a*, b*)`` of the reference measurement point.
        sample: ``(L*, a*, b*)`` of the proof/sample measurement point.

    Returns:
        The CIEDE2000 color difference, using k_L=k_C=k_H=1.
    """
    l1, a1, b1 = (float(value) for value in reference)
    l2, a2, b2 = (float(value) for value in sample)

    # Step 1: calculate CIELAB chroma, the G term, and a'/C'/h'.
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    mean_c = (c1 + c2) / 2.0
    g = 0.5 * (1.0 - math.sqrt(_seventh_power_ratio(mean_c)))

    a1_prime = (1.0 + g) * a1
    a2_prime = (1.0 + g) * a2

    c1_prime = math.hypot(a1_prime, b1)
    c2_prime = math.hypot(a2_prime, b2)

    # A zero chroma has no meaningful hue. The CIEDE2000 boundary rule
    # defines its hue angle as zero so that the mean-hue rule below works
    # when either color is achromatic.
    h1_prime = _hue_angle(a1_prime, b1) if c1_prime != 0.0 else 0.0
    h2_prime = _hue_angle(a2_prime, b2) if c2_prime != 0.0 else 0.0

    # Step 2: calculate deltas.
    delta_l = l2 - l1
    delta_c = c2_prime - c1_prime

    if c1_prime == 0.0 or c2_prime == 0.0:
        delta_h = 0.0
        delta_h_capital = 0.0
    else:
        delta_h = h2_prime - h1_prime
        if delta_h > 180.0:
            delta_h -= 360.0
        elif delta_h < -180.0:
            delta_h += 360.0

        # exp((ln C1 + ln C2) / 2) avoids overflow of C1 * C2.
        chroma_geometric_mean = math.exp(
            0.5 * (math.log(c1_prime) + math.log(c2_prime))
        )
        delta_h_capital = (
            2.0
            * chroma_geometric_mean
            * math.sin(delta_h * _PI / 360.0)
        )

    # Step 3: calculate CIEDE2000 mean values.
    mean_l = (l1 + l2) / 2.0
    mean_c_prime = (c1_prime + c2_prime) / 2.0

    if c1_prime == 0.0 or c2_prime == 0.0:
        # With the achromatic hue represented by zero, the sum is simply
        # the chromatic color's hue (and zero when both are achromatic).
        mean_h_prime = h1_prime + h2_prime
    else:
        hue_sum = h1_prime + h2_prime
        if abs(h1_prime - h2_prime) > 180.0:
            if hue_sum < 360.0:
                hue_sum += 360.0
            else:
                hue_sum -= 360.0
        mean_h_prime = hue_sum / 2.0

    t = (
        1.0
        - 0.17 * math.cos((mean_h_prime - 30.0) * _RAD)
        + 0.24 * math.cos((2.0 * mean_h_prime) * _RAD)
        + 0.32 * math.cos((3.0 * mean_h_prime + 6.0) * _RAD)
        - 0.20 * math.cos((4.0 * mean_h_prime - 63.0) * _RAD)
    )

    delta_theta = 30.0 * math.exp(
        -(((mean_h_prime - 275.0) / 25.0) ** 2)
    )
    r_c = 2.0 * math.sqrt(_seventh_power_ratio(mean_c_prime))

    s_l = 1.0 + (
        0.015 * (mean_l - 50.0) ** 2
        / math.sqrt(20.0 + (mean_l - 50.0) ** 2)
    )
    s_c = 1.0 + 0.045 * mean_c_prime
    s_h = 1.0 + 0.015 * mean_c_prime * t
    r_t = -math.sin(2.0 * delta_theta * _RAD) * r_c

    # Reference viewing condition parametric weights.
    k_l = k_c = k_h = 1.0

    lightness_term = delta_l / (k_l * s_l)
    chroma_term = delta_c / (k_c * s_c)
    hue_term = delta_h_capital / (k_h * s_h)

    return math.sqrt(
        math.fsum(
            (
                lightness_term**2,
                chroma_term**2,
                hue_term**2,
                r_t * chroma_term * hue_term,
            )
        )
    )
