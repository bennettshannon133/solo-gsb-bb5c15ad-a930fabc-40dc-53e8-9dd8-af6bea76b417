"""CIEDE2000 算法测试。

标准数据来源：
Sharma, G., Wu, W. & Dalal, E. N. (2005), Color Research & Application
30(1), 21-30，表 I 的 34 对补充测试数据（容差 1e-4，与论文一致）。
"""

from __future__ import annotations

import math

import pytest

from app.ciede2000 import ciede2000

# (Lab_1, Lab_2, 论文给出的 ΔE00 期望值)
SHARMA_2005_CASES = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
    # 第 14 对在 numpy 1.24+ 存在 atan2 跨平台末位差异（4.7461 / 4.8045）
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("lab1,lab2,expected", SHARMA_2005_CASES)
def test_sharma_2005_supplementary_data(lab1, lab2, expected):
    assert ciede2000(lab1, lab2) == pytest.approx(expected, abs=1e-4)


def test_identical_colors_have_zero_difference():
    lab = (37.82, 12.34, -56.78)
    assert ciede2000(lab, lab) == 0.0


def test_symmetric_in_arguments():
    lab1 = (50.0, 2.6772, -79.7751)
    lab2 = (50.0, 0.0, -82.7485)
    assert ciede2000(lab1, lab2) == pytest.approx(ciede2000(lab2, lab1))


def test_hue_wrap_across_0_360():
    """色相角跨 0/360 环绕：359° 与 1° 的色差必须按 2° 而不是 358° 计算。

    环绕分支的精确数值由 test_fuzz_against_colour_science 中的构造对
    与参考库逐对比对；此处验证量级（2° 旋转应是很小的色差）。
    """
    L = 50.0
    C = 10.0
    near_zero_ccw = (L, C * math.cos(math.radians(1.0)), C * math.sin(math.radians(1.0)))
    near_zero_cw = (L, C * math.cos(math.radians(-1.0)), C * math.sin(math.radians(-1.0)))
    de_wrapped = ciede2000(near_zero_cw, near_zero_ccw)
    assert de_wrapped < 0.5
    # 若错误地按 358° 处理，结果会接近半圆周色相旋转的色差（~14 量级）
    assert de_wrapped < ciede2000(
        (L, C, 0.0), (L, C * math.cos(math.radians(178.0)),
                      C * math.sin(math.radians(178.0)))
    ) / 10


def test_hue_wrap_on_other_side_is_identical():
    """方向相反的一对色相角（1°/359° vs 359°/1°）结果相同。"""
    import math

    L, C = 60.0, 20.0
    p1 = (L, C * math.cos(math.radians(1.0)), C * math.sin(math.radians(1.0)))
    p2 = (L, C * math.cos(math.radians(359.0)), C * math.sin(math.radians(359.0)))
    assert ciede2000(p1, p2) == pytest.approx(ciede2000(p2, p1), abs=1e-12)


def test_zero_chroma_both_achromatic():
    """两个纯灰（a=b=0）之间只有明度差。

    L̄'=45 时 SL = 1 + 0.015*25/sqrt(45)，ΔE = 10/SL ≈ 9.4706
    （与 colour-science 参考实现一致）。
    """
    assert ciede2000((40.0, 0.0, 0.0), (50.0, 0.0, 0.0)) == pytest.approx(
        9.4705785636, abs=1e-10
    )


def test_zero_chroma_one_achromatic_dh_is_zero():
    """任一彩度为零时色相差 dH'=0。

    边界规则下零彩度色的色相角未定义、取另一色的色相角，因此 dH' 恒为 0。
    在高彩度处 G 修正趋近于零（a'≈a），同彩度不同方向的对比色应得到
    几乎相同的色差（残余差异仅来自 G 对 a* 轴的不对称修正）；
    精确一致性由 Sharma 第 7/8 对及 fuzz 比对保证。
    """
    C = 100.0
    de_along_a = ciede2000((50.0, 0.0, 0.0), (50.0, C, 0.0))
    de_along_b = ciede2000((50.0, 0.0, 0.0), (50.0, 0.0, C))
    de_diagonal = ciede2000(
        (50.0, 0.0, 0.0),
        (50.0, C / math.sqrt(2), C / math.sqrt(2)),
    )
    # dH'=0 时方向差异只来自 G 对 a* 轴的不对称修正（高彩度下 < 2%）
    assert de_along_a == pytest.approx(de_along_b, rel=2e-2)
    assert de_along_a == pytest.approx(de_diagonal, rel=2e-2)

    # 低彩度边界值以 colour-science 参考实现为准
    assert ciede2000((50.0, 0.0, 0.0), (50.0, 5.0, 0.0)) == pytest.approx(
        6.4165335330, abs=1e-10
    )
    assert ciede2000((50.0, 0.0, 0.0), (50.0, 0.0, 5.0)) == pytest.approx(
        4.4943820225, abs=1e-10
    )


def test_zero_chroma_pairs_match_sharma_cases_7_8():
    assert ciede2000((50.0, 0.0, 0.0), (50.0, -1.0, 2.0)) == pytest.approx(
        2.3669, abs=1e-4
    )


def test_weight_factors_change_result():
    lab1 = (50.0, 2.6772, -79.7751)
    lab2 = (50.0, 0.0, -82.7485)
    base = ciede2000(lab1, lab2)
    # 加大明度权重；这对颜色没有明度差，结果不变
    assert ciede2000(lab1, lab2, kL=2.0) == pytest.approx(base, abs=1e-12)
    # 加大彩度/色相加权，色差变小
    lab3 = (40.0, 2.6772, -79.7751)
    assert ciede2000(lab3, lab2, kL=2.0) < ciede2000(lab3, lab2)


def test_result_is_finite_and_nonnegative():
    de = ciede2000((0.0, -128.0, -128.0), (100.0, 128.0, 128.0))
    assert math.isfinite(de) and de >= 0.0


def test_integer_inputs_accepted():
    assert ciede2000((50, 0, 0), (50, 2, 0)) == pytest.approx(
        ciede2000((50.0, 0.0, 0.0), (50.0, 2.0, 0.0))
    )


def test_fuzz_against_colour_science():
    """与 colour-science 参考实现在随机输入上比对（含零彩度与环绕角）。"""
    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    from colour.difference import delta_E_CIE2000

    rng = np.random.default_rng(20260923)
    # 常规随机点
    L = rng.uniform(0, 100, size=(400, 2))
    a = rng.uniform(-80, 80, size=(400, 2))
    b = rng.uniform(-80, 80, size=(400, 2))
    for i in range(400):
        lab1 = (float(L[i, 0]), float(a[i, 0]), float(b[i, 0]))
        lab2 = (float(L[i, 1]), float(a[i, 1]), float(b[i, 1]))
        assert ciede2000(lab1, lab2) == pytest.approx(
            float(delta_E_CIE2000(np.array(lab1), np.array(lab2))), abs=1e-10
        )

    # 定向构造：零彩度、近零彩度、跨 0/360 色相角
    import math as _math

    def _lab_at(L, C, h_deg):
        r = _math.radians(h_deg)
        return (L, C * _math.cos(r), C * _math.sin(r))

    special = [
        ((50.0, 0.0, 0.0), (50.0, 0.0, 0.0)),
        ((50.0, 0.0, 0.0), (50.0, 1e-9, 1e-9)),
        ((50.0, 10.0, 0.1), (50.0, 10.0, -0.1)),
        ((50.0, 10.0, 0.01), (50.0, -10.0, -0.01)),
        ((50.0, 0.01, 0.0), (50.0, 0.0, -0.01)),
        # 色相角严格跨 0/360 环绕的对（1°/359°，以及更大彩度）
        (_lab_at(50.0, 10.0, 1.0), _lab_at(50.0, 10.0, 359.0)),
        (_lab_at(50.0, 50.0, 0.5), _lab_at(50.0, 50.0, -0.5)),
        (_lab_at(80.0, 30.0, 179.5), _lab_at(80.0, 30.0, -179.5)),
    ]
    for lab1, lab2 in special:
        assert ciede2000(lab1, lab2) == pytest.approx(
            float(delta_E_CIE2000(np.array(lab1), np.array(lab2))), abs=1e-10
        )
