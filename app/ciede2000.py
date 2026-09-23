"""CIEDE2000 色差公式（纯标准库实现）。

实现步骤严格对应：

    Sharma, G., Wu, W. & Dalal, E. N. (2005).
    "The CIEDE2000 color-difference formula: Implementation notes,
    supplementary test data, and mathematical observations."
    Color Research & Application, 30(1), 21-30.
    doi:10.1002/col.20070

公式形式：

    dE00 = sqrt( (dL'/kL*SL)^2 + (dC'/kC*SC)^2 + (dH'/kH*SH)^2
                 + R_T * (dC'/(kC*SC)) * (dH'/(kH*SH)) )

调用方负责输入校验；本模块只接受有限的 ``int``/``float``。
"""

from __future__ import annotations

import math
from typing import Tuple

__all__ = ["ciede2000"]

_DEG2RAD = math.pi / 180.0


def _hue_angle_deg(b: float, a: float) -> float:
    """返回 (a, b) 对应的色相角，取值范围 [0, 360)。

    注意 atan2 的参数顺序：CIELAB 中色相角 h = atan2(b*, a*)。
    C* = 0（a、b 同时为 0）时色相角无定义，由调用方按边界规则处理。
    """
    return math.degrees(math.atan2(b, a)) % 360.0


def ciede2000(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    kL: float = 1.0,
    kC: float = 1.0,
    kH: float = 1.0,
) -> float:
    """计算两个 CIELAB 颜色之间的 CIEDE2000 色差 ΔE₀₀。

    参数
    ----
    lab1, lab2:
        参考色与样张色的 ``(L*, a*, b*)`` 三元组。
    kL, kC, kH:
        明度、彩度、色相的参数加权因子（参考观察条件下均为 1.0）。

    返回
    ----
    float
        非负的 ΔE₀₀ 值。
    """
    L1, a1, b1 = (float(v) for v in lab1)  # type: ignore[call-overload]
    L2, a2, b2 = (float(v) for v in lab2)  # type: ignore[call-overload]
    kL, kC, kH = float(kL), float(kC), float(kH)  # type: ignore[assignment]

    # ---- 步骤 1：计算 C'i、h'i ----------------------------------------
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    C_bar = (C1 + C2) / 2.0
    C_bar_7 = C_bar**7
    G = 0.5 * (1.0 - math.sqrt(C_bar_7 / (C_bar_7 + 25.0**7)))

    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2

    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)

    # 零彩度（a' 与 b 同时为 0）时色相角无定义；按 Sharma 参考实现先记为 0，
    # 后续步骤 4/5 再依边界规则处理。
    h1p = _hue_angle_deg(b1, a1p) if (a1p != 0.0 or b1 != 0.0) else 0.0
    h2p = _hue_angle_deg(b2, a2p) if (a2p != 0.0 or b2 != 0.0) else 0.0

    # ---- 步骤 2：计算 dL'、dC'、dH' -----------------------------------
    dLp = L2 - L1
    dCp = C2p - C1p

    # 色相角差：任一彩度为零 -> dH' = 0；否则环绕到 (-180, 180]。
    if C1p == 0.0 or C2p == 0.0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180.0:
            dhp -= 360.0
        elif dhp < -180.0:
            dhp += 360.0

    # 保留正负号：dH' = 2 * sqrt(C1'C2') * sin(dh'/2)
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(dhp / 2.0 * _DEG2RAD)

    # ---- 步骤 4：计算平均明度、平均彩度、平均色相角 -------------------
    L_bar_p = (L1 + L2) / 2.0
    C_bar_p = (C1p + C2p) / 2.0

    # 平均色相角：任一彩度为零 -> h̄' = h1' + h2'（零值色相角为 0，
    # 即直接采用非零色的色相角；两个彩度都为零时结果为 0）。
    if C1p == 0.0 or C2p == 0.0:
        h_bar_p = h1p + h2p
    else:
        h_sum = h1p + h2p
        if abs(h1p - h2p) > 180.0:
            # 跨过 0/360 环绕：均值朝环绕方向修正
            h_bar_p = (h_sum + 360.0) / 2.0 if h_sum < 360.0 else (h_sum - 360.0) / 2.0
        else:
            h_bar_p = h_sum / 2.0
        h_bar_p %= 360.0

    # ---- 步骤 5：加权函数 SL、SC、SH 与旋转项 RT ----------------------
    T = (
        1.0
        - 0.17 * math.cos((h_bar_p - 30.0) * _DEG2RAD)
        + 0.24 * math.cos((2.0 * h_bar_p) * _DEG2RAD)
        + 0.32 * math.cos((3.0 * h_bar_p + 6.0) * _DEG2RAD)
        - 0.20 * math.cos((4.0 * h_bar_p - 63.0) * _DEG2RAD)
    )

    d_theta = 30.0 * math.exp(-(((h_bar_p - 275.0) / 25.0) ** 2))
    C_bar_p_7 = C_bar_p**7
    R_C = 2.0 * math.sqrt(C_bar_p_7 / (C_bar_p_7 + 25.0**7))
    S_L = 1.0 + (0.015 * (L_bar_p - 50.0) ** 2) / math.sqrt(
        20.0 + (L_bar_p - 50.0) ** 2
    )
    S_C = 1.0 + 0.045 * C_bar_p
    S_H = 1.0 + 0.015 * C_bar_p * T
    R_T = -math.sin(2.0 * d_theta * _DEG2RAD) * R_C

    # ---- 步骤 6：总色差 ------------------------------------------------
    term_L = dLp / (kL * S_L)
    term_C = dCp / (kC * S_C)
    term_H = dHp / (kH * S_H)
    dE = math.sqrt(term_L**2 + term_C**2 + term_H**2 + R_T * term_C * term_H)

    # 数值误差可能在同色输入时产生极小的负值
    return max(dE, 0.0)
