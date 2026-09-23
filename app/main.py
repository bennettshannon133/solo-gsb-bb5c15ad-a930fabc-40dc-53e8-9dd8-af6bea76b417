"""FastAPI application for printing-proof CIEDE2000 color differences."""

from __future__ import annotations

import math
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.responses import JSONResponse

from app.ciede2000 import ciede2000

app = FastAPI(
    title="印刷打样色差计算 API",
    description="计算同一测点参考色与样张色之间的 CIEDE2000 色差 ΔE00。",
    version="1.0.0",
)


class LabInput(BaseModel):
    """A CIELAB measurement point."""

    model_config = ConfigDict(extra="forbid")

    L: float
    a: float
    b: float

    @field_validator("L", "a", "b", mode="before")
    @classmethod
    def validate_finite_number(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("必须是数字，不能使用 true/false")
        if not isinstance(value, (int, float)):
            raise ValueError("必须是有限数字，不能使用字符串、null 或其他非数值类型")
        if not math.isfinite(value):
            raise ValueError("必须是有限数字，不能为 NaN 或 Infinity")
        return value

    @field_validator("L")
    @classmethod
    def validate_lightness_range(cls, value: float) -> float:
        if not 0.0 <= value <= 100.0:
            raise ValueError("CIELAB 的 L* 必须位于 0 到 100 之间")
        return value


class ColorDifferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: LabInput = Field(description="参考测点的 CIELAB 值")
    sample: LabInput = Field(description="样张测点的 CIELAB 值")


class ColorDifferenceResponse(BaseModel):
    delta_e00: float = Field(description="CIEDE2000 色差 ΔE00")
    formula: str = "CIEDE2000"
    reference: LabInput
    sample: LabInput


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    _request: Any, exc: RequestValidationError
) -> JSONResponse:
    details: list[dict[str, str]] = []
    for error in jsonable_encoder(exc.errors()):
        field_path = ".".join(
            str(part) for part in error.get("loc", ()) if part != "body"
        )
        error_type = error.get("type", "validation_error")
        message = error.get("msg", "输入值不合法").removeprefix("Value error, ")

        if error_type == "missing":
            message = f"字段 {field_path} 为必填项"
        elif error_type == "extra_forbidden":
            message = f"不允许出现未定义字段 {field_path}"
        elif error_type == "json_invalid" or not field_path:
            message = "请求体必须是合法的 JSON 对象"

        details.append(
            {
                "field": field_path or "body",
                "message": message,
                "type": error_type,
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_input",
            "message": "请求参数非法，请提供 reference 和 sample，且各自包含有限数字 L、a、b。",
            "details": details,
        },
    )


@app.get("/health", tags=["health"], summary="健康检查")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/delta-e00",
    response_model=ColorDifferenceResponse,
    tags=["color-difference"],
    summary="计算 CIEDE2000 色差",
)
def calculate_delta_e00(
    request: ColorDifferenceRequest,
) -> ColorDifferenceResponse:
    reference = (request.reference.L, request.reference.a, request.reference.b)
    sample = (request.sample.L, request.sample.a, request.sample.b)
    delta_e00 = ciede2000(reference, sample)

    return ColorDifferenceResponse(
        delta_e00=delta_e00,
        reference=request.reference,
        sample=request.sample,
    )
