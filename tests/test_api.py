import math

from fastapi.testclient import TestClient

from app.ciede2000 import ciede2000
from app.main import app


client = TestClient(app)

# Selected values from G. Sharma, W. Wu, E. N. Dalal,
# "The CIEDE2000 Color-Difference Formula: Implementation Notes,
# Supplementary Test Data, and Mathematical Observations", 2005.
SHARMA_CASES = [
    ((50, 2.6772, -79.7751), (50, 0.0, -82.7485), 2.0425),
    ((50, 3.1571, -77.2803), (50, 0.0, -82.7485), 2.8615),
    ((50, -1.3802, -84.2814), (50, 0.0, -82.7485), 1.0000),
    ((50.0000, 0.0, 0.0), (50.0000, -1.0, 2.0), 2.3669),
    ((50.0000, -1.0, 2.0), (50.0000, 0.0, 0.0), 2.3669),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
]


def test_ciede2000_reference_dataset() -> None:
    for reference, sample, expected in SHARMA_CASES:
        assert math.isclose(
            ciede2000(reference, sample), expected, abs_tol=0.0001
        )


def test_hue_wrap_uses_short_arc() -> None:
    # h ≈ 350° versus h ≈ 10° is a 20° hue difference, not 340°.
    near_350 = (60.0, 5.0, -0.8816)
    near_010 = (60.0, 5.0, 0.8816)
    short_arc = ciede2000(near_350, near_010)
    long_arc = ciede2000(near_350, (60.0, -5.0, 0.8816))
    assert short_arc < 2.0
    assert long_arc > short_arc

    # Reversing the color order must give the same result.
    assert math.isclose(
        ciede2000(near_350, near_010),
        ciede2000(near_010, near_350),
        abs_tol=1e-12,
    )


def test_zero_chroma_hue_boundary_rule() -> None:
    achromatic = (50.0, 0.0, 0.0)
    chromatic_1 = (50.0, 1.0, 0.0)   # h' = 0°
    chromatic_2 = (50.0, 0.0, 1.0)   # h' = 90°

    assert math.isclose(
        ciede2000(achromatic, chromatic_1),
        ciede2000(chromatic_1, achromatic),
        abs_tol=1e-12,
    )
    assert math.isclose(
        ciede2000(achromatic, chromatic_2),
        ciede2000(chromatic_2, achromatic),
        abs_tol=1e-12,
    )
    assert ciede2000(achromatic, achromatic) == 0.0


def post_payload(payload: dict[str, object]):
    return client.post("/api/v1/delta-e00", json=payload)


def test_api_returns_delta_e00() -> None:
    payload = {
        "reference": {"L": 50.0, "a": 2.6772, "b": -79.7751},
        "sample": {"L": 50.0, "a": 0.0, "b": -82.7485},
    }

    response = post_payload(payload)

    assert response.status_code == 200
    data = response.json()
    assert data["formula"] == "CIEDE2000"
    assert math.isclose(data["delta_e00"], 2.0425, abs_tol=0.0001)
    assert data["reference"] == payload["reference"]
    assert data["sample"] == payload["sample"]


def test_api_rejects_non_finite_values_with_422() -> None:
    for invalid_b in ("NaN", float("nan"), float("inf"), float("-inf")):
        response = post_payload(
            {
                "reference": {"L": 50, "a": 0, "b": invalid_b},
                "sample": {"L": 50, "a": 0, "b": 0},
            }
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "invalid_input"
        assert data["details"][0]["field"] == "reference.b"
        assert "有限数字" in data["details"][0]["message"]


def test_api_rejects_booleans_and_invalid_lightness() -> None:
    response = post_payload(
        {
            "reference": {"L": 120, "a": 0, "b": 0},
            "sample": {"L": 50, "a": True, "b": 0},
        }
    )

    assert response.status_code == 422
    fields = {detail["field"] for detail in response.json()["details"]}
    assert "reference.L" in fields
    assert "sample.a" in fields


def test_api_rejects_unknown_fields_with_422() -> None:
    response = post_payload(
        {
            "reference": {"L": 50, "a": 0, "b": 0, "x": 1},
            "sample": {"L": 50, "a": 0, "b": 0},
        }
    )

    assert response.status_code == 422
    assert "reference.x" in response.json()["details"][0]["field"]


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
