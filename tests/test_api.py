"""FastAPI 接口测试：正常路径、加权因子与 422 校验。"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_basic_delta_e_matches_sharma_first_pair():
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        json={
            "reference": {"L": 50.0, "a": 2.6772, "b": -79.7751},
            "sample": {"L": 50.0, "a": 0.0, "b": -82.7485},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "CIEDE2000"
    assert body["delta_E"] == pytest.approx(2.0425, abs=1e-4)
    assert body["delta_E_rounded"] == 2.04
    assert body["params"] == {"kL": 1.0, "kC": 1.0, "kH": 1.0}
    assert body["reference"] == {"L": 50.0, "a": 2.6772, "b": -79.7751}


def test_integer_components_accepted():
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        json={
            "reference": {"L": 50, "a": 0, "b": 0},
            "sample": {"L": 50, "a": 2, "b": 0},
        },
    )
    assert r.status_code == 200, r.text


def test_identical_inputs_return_zero():
    payload = {"reference": {"L": 42.5, "a": -10.0, "b": 33.3},
               "sample": {"L": 42.5, "a": -10.0, "b": 33.3}}
    r = client.post("/api/v1/delta-e/ciede2000", json=payload)
    assert r.status_code == 200
    assert r.json()["delta_E"] == 0.0


def test_hue_wrap_endpoint():
    c = 10.0
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        json={
            "reference": {"L": 50.0, "a": c * math.cos(math.radians(359.0)),
                          "b": c * math.sin(math.radians(359.0))},
            "sample": {"L": 50.0, "a": c * math.cos(math.radians(1.0)),
                       "b": c * math.sin(math.radians(1.0))},
        },
    )
    assert r.status_code == 200
    assert r.json()["delta_E"] < 0.5


def test_zero_chroma_endpoint():
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        json={
            "reference": {"L": 50.0, "a": 0.0, "b": 0.0},
            "sample": {"L": 50.0, "a": -1.0, "b": 2.0},
        },
    )
    assert r.status_code == 200
    assert r.json()["delta_E"] == pytest.approx(2.3669, abs=1e-4)


def test_custom_weight_factors_echoed_and_applied():
    base = {
        "reference": {"L": 40.0, "a": 2.6772, "b": -79.7751},
        "sample": {"L": 50.0, "a": 0.0, "b": -82.7485},
    }
    r1 = client.post("/api/v1/delta-e/ciede2000", json={**base, "kL": 2.0})
    r2 = client.post("/api/v1/delta-e/ciede2000", json=base)
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["params"]["kL"] == 2.0
    assert r1.json()["delta_E"] < r2.json()["delta_E"]


# ------------------------------- 422 用例 ---------------------------------

def _post(ref, sample, **extra):
    return client.post(
        "/api/v1/delta-e/ciede2000",
        json={"reference": ref, "sample": sample, **extra},
    )


VALID = {"L": 50.0, "a": 0.0, "b": 0.0}


def test_422_when_field_missing():
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        json={"reference": {"L": 50.0, "a": 0.0}, "sample": VALID},
    )
    assert r.status_code == 422
    locs = [tuple(e["loc"]) for e in r.json()["detail"]]
    assert ("body", "reference", "b") in locs


def test_422_when_whole_color_missing():
    r = client.post("/api/v1/delta-e/ciede2000", json={"sample": VALID})
    assert r.status_code == 422
    assert ("body", "reference") in [tuple(e["loc"]) for e in r.json()["detail"]]


@pytest.mark.parametrize(
    "bad",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        "1e999",  # Python json 解析为 Infinity
        True,
        False,
        "50.0",
        None,
        [1, 2, 3],
        {"x": 1},
    ],
)
def test_422_for_non_finite_or_non_numeric_component(bad):
    # 非有限数与非数字类型统一通过原始 JSON 请求体发送
    # （NaN/Infinity 是非标准 JSON，但 Python json 可解析，
    # 必须在模型层拒绝；其余是普通 JSON 值）
    import json

    raw_value = json.dumps(bad, allow_nan=True)
    body = (
        f'{{"reference": {{"L": 50.0, "a": 0.0, "b": {raw_value}}},'
        f' "sample": {{"L": 50.0, "a": 0.0, "b": 0.0}}}}'
    )
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        content=body.encode(),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"][0]
    assert detail["loc"][-1] == "b"
    assert detail["type"] in {"not_finite", "not_a_number"}
    assert "finite number" in detail["msg"]


def test_422_for_nan_inf_via_pydantic_layer():
    """直接验证模型层拒绝 NaN / ±Infinity（对应真实客户端发送的非标准 JSON）。"""
    from pydantic import ValidationError

    from app.schemas import DeltaERequest

    for raw in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError) as exc:
            DeltaERequest(
                reference={"L": 50.0, "a": 0.0, "b": raw},
                sample={"L": 50.0, "a": 0.0, "b": 0.0},
            )
        err = exc.value.errors()[0]
        assert err["loc"][-1] == "b"
        assert err["type"] == "not_finite"


@pytest.mark.parametrize(
    "field,value",
    [("L", -0.0001), ("L", 100.0001), ("a", -128.0001), ("a", 128.0001),
     ("b", -200.0), ("b", 200.0)],
)
def test_422_for_out_of_range_component(field, value):
    r = _post({**VALID, field: value}, VALID)
    assert r.status_code == 422
    detail = r.json()["detail"][0]
    assert detail["loc"][-1] == field
    assert detail["type"].startswith("greater_than") or detail["type"].startswith(
        "less_than"
    )


def test_422_for_boundary_values_accepted():
    """范围端点本身合法。"""
    r = _post({"L": 0.0, "a": -128.0, "b": -128.0},
              {"L": 100.0, "a": 128.0, "b": 128.0})
    assert r.status_code == 200


@pytest.mark.parametrize("factor", ["kL", "kC", "kH"])
@pytest.mark.parametrize("bad", [0.0, -1.0, True, "x"])
def test_422_for_bad_weight_factors(factor, bad):
    r = _post(VALID, VALID, **{factor: bad})
    assert r.status_code == 422
    detail = r.json()["detail"][0]
    assert detail["loc"][-1] == factor


def test_422_for_non_finite_weight_factors():
    """加权因子为 NaN/Infinity（经原始 JSON 字面量发送）时返回 422。"""
    for token in ("NaN", "Infinity", "-Infinity"):
        r = client.post(
            "/api/v1/delta-e/ciede2000",
            content=(
                f'{{"reference": {{"L": 50.0, "a": 0.0, "b": 0.0}},'
                f' "sample": {{"L": 50.0, "a": 0.0, "b": 0.0}},'
                f' "kL": {token}}}'
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"][-1] == "kL"


def test_422_for_unknown_fields():
    r = _post({**VALID, "extra": 1.0}, VALID)
    assert r.status_code == 422
    assert r.json()["detail"][0]["type"] == "extra_forbidden"


def test_422_for_malformed_json():
    r = client.post(
        "/api/v1/delta-e/ciede2000",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422
