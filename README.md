# 印刷打样 CIEDE2000 色差计算 API

使用 Python + FastAPI 实现的印刷打样色差服务。接口接收同一测点的参考色与样张 CIELAB（`L*`, `a*`, `b*`）三元值，按 [CIEDE2000](https://en.wikipedia.org/wiki/Color_difference#CIEDE2000) 返回色差 `ΔE00`。

实现已处理：

- 色相角跨 `0°/360°` 的环绕，计算最短色相弧；
- 参考色或样张任一彩度为零时的 CIEDE2000 色相边界规则；
- 参数权重固定为印刷/常规观察条件 `kL = kC = kH = 1`；
- 非数值、`null`、布尔值、`NaN`、`Infinity`、缺失字段、`L*` 越界等返回明确的 HTTP `422`。

## 一键启动

确保已安装 Docker 与 Docker Compose 插件，然后在项目根目录执行：

```bash
docker compose up --build -d
```

启动后访问：

- API 服务地址：<http://localhost:8000>
- 健康检查：<http://localhost:8000/health>
- Swagger 文档：<http://localhost:8000/docs>
- OpenAPI JSON：<http://localhost:8000/openapi.json>

停止服务：

```bash
docker compose down
```

## 接口

### 计算 ΔE00

```http
POST /api/v1/delta-e00
Content-Type: application/json
```

请求体：

```json
{
  "reference": {
    "L": 50.0,
    "a": 2.6772,
    "b": -79.7751
  },
  "sample": {
    "L": 50.0,
    "a": 0.0,
    "b": -82.7485
  }
}
```

字段说明：

- `reference`：参考测点，即标准色/目标色；
- `sample`：样张测点，即打样实际测量色；
- `L`：CIELAB 明度，合法范围为 `0` 到 `100`；
- `a`、`b`：CIELAB 色度坐标，必须为有限数字。

成功响应示例：

```json
{
  "delta_e00": 2.0424596801565764,
  "formula": "CIEDE2000",
  "reference": {
    "L": 50.0,
    "a": 2.6772,
    "b": -79.7751
  },
  "sample": {
    "L": 50.0,
    "a": 0.0,
    "b": -82.7485
  }
}
```

调用示例：

```bash
curl -X POST http://localhost:8000/api/v1/delta-e00 \
  -H "Content-Type: application/json" \
  -d '{
    "reference": {"L": 50.0, "a": 2.6772, "b": -79.7751},
    "sample": {"L": 50.0, "a": 0.0, "b": -82.7485}
  }'
```

### 健康检查

```bash
curl http://localhost:8000/health
```

返回：

```json
{"status":"ok"}
```

## 422 错误示例

非法输入不会被静默转换，例如将 `b` 传成字符串：

```bash
curl -i -X POST http://localhost:8000/api/v1/delta-e00 \
  -H "Content-Type: application/json" \
  -d '{
    "reference": {"L": 50, "a": 0, "b": "NaN"},
    "sample": {"L": 50, "a": 0, "b": 0}
  }'
```

响应状态码为 `422 Unprocessable Entity`：

```json
{
  "error": "invalid_input",
  "message": "请求参数非法，请提供 reference 和 sample，且各自包含有限数字 L、a、b。",
  "details": [
    {
      "field": "reference.b",
      "message": "必须是有限数字，不能使用字符串、null 或其他非数值类型",
      "type": "value_error"
    }
  ]
}
```

JSON 原生 `NaN` / `Infinity` 不是合法 JSON 值；即便客户端以非标准扩展发送，服务端也会将其作为非法 JSON 或非有限值拒绝。

## 本地开发（不使用 Docker）

要求 Python 3.11+：

```bash
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

运行测试：

```bash
pytest -q
```

测试包含 Sharma、Wu、Dalal（2005）公开 CIEDE2000 补充测试数据中的代表样例，以及零彩度边界和色相角环绕测试。

## 项目结构

```text
.
├── app/
│   ├── __init__.py
│   ├── ciede2000.py      # CIEDE2000 纯函数实现
│   └── main.py           # FastAPI 路由、模型与 422 错误处理
├── tests/
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```
