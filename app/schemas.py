"""请求/响应数据模型与输入校验。

校验策略：用 ``AfterValidator`` 在 Pydantic 完成类型转换之后显式检查有限性
（Pydantic 默认放行 NaN / ±Infinity，且 gt/ge 等范围约束对 NaN 恒为 False、
无法拦截）；布尔值与字符串等非数字类型则由 ``float`` 类型本身拒绝。
所有不合法输入统一返回明确的 422 错误。
"""

from __future__ import annotations

import math
from numbers import Real
from typing_extensions import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic_core import PydanticCustomError


def _coerce_strict_number(value: object) -> float:
    """BeforeValidator：仅接受 int/float，拒绝 bool 与字符串等非数字类型。

    Pydantic 默认的 lax 模式会把布尔值和 "50.0" 这样的数字字符串隐式转成
    float；本服务要求输入必须是 JSON 数字，故在此显式拒绝。
    """
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PydanticCustomError(
            "not_a_number",
            "value must be a finite number",
        )
    return float(value)


def _ensure_finite(value: float) -> float:
    """AfterValidator：拒绝 NaN / ±Infinity。

    Pydantic 默认放行非有限浮点，且 gt/ge 等范围约束对 NaN 的比较恒为
    False、无法拦截，因此有限性必须独立保证。
    """
    if not math.isfinite(value):
        raise PydanticCustomError(
            "not_finite",
            "value must be a finite number",
        )
    return value


# 严格数字类型 -> 有限性 -> 数值范围
FiniteFloat = Annotated[
    float,
    BeforeValidator(_coerce_strict_number),
    AfterValidator(_ensure_finite),
]

# CIELAB 各分量的物理可达范围（反射介质）
LabL = Annotated[
    FiniteFloat,
    Field(ge=0.0, le=100.0, description="明度 L*，范围 0–100"),
]
LabAB = Annotated[
    FiniteFloat,
    Field(ge=-128.0, le=128.0, description="红-绿 a* / 黄-蓝 b* 轴，范围 ±128"),
]
# 参数加权因子：正的有限数即可（如纺织业常用 kL=2）
WeightFactor = Annotated[
    FiniteFloat,
    Field(gt=0.0, description="加权因子，须为正数"),
]


class LabColor(BaseModel):
    """一个测点的 CIELAB 三元值。"""

    model_config = ConfigDict(extra="forbid")

    L: LabL
    a: LabAB
    b: LabAB

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.L, self.a, self.b)


class WeightParams(BaseModel):
    """CIEDE2000 的参数加权因子（参考观察条件下均为 1）。"""

    model_config = ConfigDict(extra="forbid")

    kL: WeightFactor = 1.0
    kC: WeightFactor = 1.0
    kH: WeightFactor = 1.0


class DeltaERequest(BaseModel):
    """色差计算请求：同一测点的参考色与样张色。"""

    model_config = ConfigDict(extra="forbid")

    reference: LabColor = Field(description="参考色 / 标准样（签字稿）的 CIELAB 值")
    sample: LabColor = Field(description="样张 / 印品实测色的 CIELAB 值")
    kL: WeightFactor = Field(default=1.0, description="明度加权因子，默认 1")
    kC: WeightFactor = Field(default=1.0, description="彩度加权因子，默认 1")
    kH: WeightFactor = Field(default=1.0, description="色相加权因子，默认 1")


class DeltaEResponse(BaseModel):
    """色差计算结果。"""

    method: str = Field(description="计算方法，固定为 CIEDE2000")
    delta_E: float = Field(description="CIEDE2000 色差 ΔE00（完整精度）")
    delta_E_rounded: float = Field(description="ΔE00，保留两位小数")
    reference: LabColor
    sample: LabColor
    params: WeightParams
