# 印刷打样色差计算 API

基于 **Python + FastAPI** 的 CIELAB 色差服务：输入同一测点的参考（标准样）与样张
CIELAB 三元值，按 **CIEDE2000** 公式返回色差 **ΔE₀₀**（GB/T 38723 / ISO 15076 所用方法）。

## 一键启动（Docker Compose）

```bash
docker compose up -d --build
```

启动后访问：

| 地址 | 说明 |
| --- | --- |
| <http://localhost:8000/docs> | Swagger UI（可在线试发请求） |
| <http://localhost:8000/redoc> | ReDoc 接口文档 |
| <http://localhost:8000/health> | 健康检查 |
| `POST http://localhost:8000/api/v1/delta-e/ciede2000` | 色差计算接口 |

停止：`docker compose down`；端口修改：`docker compose up -d --build -e PORT=9000`
或直接编辑 `.env` / compose 文件中的 `8000:8000` 映射。

## 调用示例

```bash
curl -s -X POST http://localhost:8000/api/v1/delta-e/ciede2000 \
  -H "Content-Type: application/json" \
  -d '{
        "reference": {"L": 50.0, "a":   2.6772, "b": -79.7751},
        "sample":    {"L": 50.0, "a":   0.0000, "b": -82.7485}
      }'
```

响应：

```json
{
  "method": "CIEDE2000",
  "delta_E": 2.04245968,
  "delta_E_rounded": 2.04,
  "reference": {"L": 50.0, "a": 2.6772, "b": -79.7751},
  "sample": {"L": 50.0, "a": 0.0, "b": -82.7485},
  "params": {"kL": 1.0, "kC": 1.0, "kH": 1.0}
}
```

字段含义：

- `reference`：参考色 / 标准样（签字稿、印前数字稿）的 CIELAB 值；
- `sample`：样张 / 印品实测色的 CIELAB 值；
- `L` ∈ [0, 100]，`a`、`b` ∈ [-128, 128]（CIELAB 反射介质可达范围）；
- 可选参数 `kL` / `kC` / `kH`：明度、彩度、色相的参数加权因子，默认均为 1
  （参考观察条件）。纺织等行业可取 `kL=2`。

## 算法边界规则的处理

实现严格遵循 Sharma, Wu & Dalal (2005), *Color Research & Application* 30(1)
的 CIEDE2000 参考实现，重点处理了两类边界：

1. **色相角环绕（0°/360° 跨界）**：平均色相角按带符号的原始色相角差判定，
   当 `|h1' − h2'| > 180°` 时给均值加/减 360°，再取模回到 [0°, 360°)；
   色相差 `Δh'` 同样按 ±360° 环绕修正。因此 359° 与 1° 的色差为 2°，
   而不是 358°。
2. **任一输入彩度为零**：零彩度色的色相角无定义。计算色相差 `Δh'` 时，
   只要 **任一个** 彩度为零则取 `Δh' = 0`；计算平均色相角时，只要
   **任一个** 彩度为零则取 `h̄' = h1' + h2'`（即直接采用非零色的色相角）；
   两个彩度都为零时 `h̄' = 0`。

## 非法输入与 422

以下情况一律返回 **HTTP 422 Unprocessable Entity**，并在响应体中给出
出错字段与原因（不接受 Pydantic 默认放行的 `NaN` / `Infinity`）：

- 缺字段、类型不是数字（字符串、布尔、对象、数组、`null`）；
- 数值为 `NaN`、`+Infinity`、`-Infinity` 等非有限值；
- `L`、`a`、`b` 超出允许范围；
- `kL`、`kC`、`kH` 不是正数或非有限。

错误体示例：

```json
{
  "detail": [
    {
      "type": "not_finite",
      "loc": ["body", "reference", "b"],
      "msg": "value must be a finite number",
      "input": "NaN"
    }
  ]
}
```

## 本地开发（不使用 Docker）

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 运行测试

```bash
pip install -r requirements-dev.txt
pytest -q
```

测试包含：Sharma et al. (2005) 34 对标准数据、零彩度边界、色相角环绕、
加权因子、422 校验，以及与 `colour-science` 参考库的随机模糊比对。

## 项目结构

```
.
├── app/
│   ├── __init__.py
│   ├── ciede2000.py      # CIEDE2000 纯标准库实现
│   ├── schemas.py        # 请求/响应模型与有限性校验
│   └── main.py           # FastAPI 应用与路由
├── tests/
│   ├── test_ciede2000.py
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```
