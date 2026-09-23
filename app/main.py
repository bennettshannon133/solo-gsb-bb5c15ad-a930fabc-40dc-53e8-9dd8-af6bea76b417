"""FastAPI 应用：印刷打样 CIEDE2000 色差计算。"""

from __future__ import annotations

import math

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .ciede2000 import ciede2000
from .schemas import DeltaERequest, DeltaEResponse, WeightParams

app = FastAPI(
    title="印刷打样色差计算 API",
    description=(
        "输入同一测点的参考（标准样）与样张 CIELAB 三元值，"
        "按 CIEDE2000 返回色差 ΔE00。"
    ),
    version="1.0.0",
)


def _sanitize_json(value: object) -> object:
    """递归把 NaN / ±Infinity 替换为字符串，保证响应体是合法 JSON。"""
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, dict):
        return {k: _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """非法输入统一返回 422。

    默认处理器会把原始输入（可能是 NaN / Infinity）直接放进错误体回显，
    导致 JSON 序列化抛 ValueError 并退化为 500；这里先清洗非有限值，
    保证 422 响应体本身始终是合法 JSON。
    """
    return JSONResponse(
        status_code=422,
        content={"detail": _sanitize_json(exc.errors())},
    )


@app.get("/health", tags=["系统"], summary="健康检查")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/delta-e/ciede2000",
    response_model=DeltaEResponse,
    tags=["色差"],
    summary="计算 CIEDE2000 色差 ΔE00",
)
def delta_e_ciede2000(req: DeltaERequest) -> DeltaEResponse:
    dE = ciede2000(
        req.reference.as_tuple(),
        req.sample.as_tuple(),
        kL=req.kL,
        kC=req.kC,
        kH=req.kH,
    )
    return DeltaEResponse(
        method="CIEDE2000",
        delta_E=dE,
        delta_E_rounded=round(dE, 2),
        reference=req.reference,
        sample=req.sample,
        params=WeightParams(kL=req.kL, kC=req.kC, kH=req.kH),
    )
