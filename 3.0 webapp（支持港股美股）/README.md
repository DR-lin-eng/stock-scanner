# Web 股票分析系统（SSE 流式版）

基于 `Flask + AkShare + 多模型 LLM` 的股票分析 Web 应用，支持：

- A 股 / 港股 / 美股代码识别
- 单股与批量分析
- SSE（Server-Sent Events）实时推送分析进度和 AI 输出
- 可选 Web 密码鉴权
- OpenAI / Claude / 智谱 / SiliconFlow（OpenAI 兼容）多模型接入

核心文件：

- `flask_web_server.py`：Web 服务、SSE 推送、接口层
- `web_stock_analyzer.py`：行情/基本面/新闻分析与 AI 总结引擎
- `config - 示例.json`：配置示例

## 1. 快速开始（本地运行）

### 1.1 环境要求

- Python 3.10+（推荐 3.11）
- 能访问 AkShare 数据源
- 如需 AI 深度分析，需要至少配置一个模型 API Key

### 1.2 安装依赖

```bash
pip install -r requirements.txt
```

### 1.3 准备配置文件

方式一（推荐）：

```bash
cp "config - 示例.json" config.json
```

方式二：

- 直接启动程序，系统会自动生成默认 `config.json`

然后编辑 `config.json`，至少配置：

- `api_keys`：填入你要使用的 API Key（例如 `openai`）
- `ai.model_preference`：主模型提供方（如 `openai` / `siliconflow`）
- `ai.models`：模型名称
- `ai.api_base_urls`：如有中转地址可在此配置

如果只想先验证流程，也可以不填 API Key，系统会降级为规则分析（无 LLM 深度文本）。

### 1.4 启动服务

```bash
python flask_web_server.py
```

启动后访问：

- `http://localhost:5000`

默认监听：

- `0.0.0.0:5000`

### 1.5 桌面 GUI 启动（桌面用户推荐）

```bash
python desktop_gui_launcher.py
```

Windows 用户也可以直接双击：

- `启动桌面GUI.bat`

桌面启动器提供：

- 启动/停止 Web 服务
- 显示实时运行日志
- 一键打开分析页面
- 内置「配置中心」：在 GUI 内直接配置 API Key、模型偏好、Web 密码鉴权与 JSON 全量配置

### 1.6 打包为 EXE（Windows）

先安装打包工具：

```bash
pip install pyinstaller
```

执行项目内脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

打包完成后运行：

- `dist\StockAnalyzerDesktop\StockAnalyzerDesktop.exe`

说明：

- EXE 版会在程序目录下读写 `config.json`
- 可直接在 GUI 的「配置中心」里修改配置（无需手改文件）

## 2. Docker 部署

### 2.1 构建并启动

```bash
docker compose up -d --build
```

默认映射：

- `5000:5000`

`docker-compose.yaml` 已挂载：

- `./config.json -> /app/config.json`
- `./logs -> /app/logs`

### 2.2 可选 Nginx 反向代理

```bash
docker compose --profile with-nginx up -d --build
```

## 3. 股票代码输入规则

系统会自动识别市场并规范化：

- A 股：`600519` / `sh600519` / `600519.SH`
- 港股：`00700` / `700` / `00700.HK` / `HK00700`
- 美股：`AAPL` / `MSFT` / `105.MSFT`（AkShare 特殊格式也支持）

## 4. API 概览

### 4.1 健康与系统信息

- `GET /api/status`：健康检查
- `GET /api/system_info`：系统信息（包含已配置 API、SSE 状态等）

### 4.2 流式分析接口（推荐）

- `GET /api/sse?client_id=<你的客户端ID>`：建立 SSE 通道
- `POST /api/analyze_stream`：启动单股流式分析
- `POST /api/batch_analyze_stream`：启动批量流式分析（最多 10 只）

单股流式请求示例：

```json
{
  "stock_code": "600519",
  "client_id": "demo-client-001",
  "enable_streaming": true,
  "position_cost": 1520.5
}
```

批量流式请求示例：

```json
{
  "stock_codes": ["600519", "000001", "00700.HK", "AAPL"],
  "client_id": "demo-client-001"
}
```

### 4.3 兼容非流式接口

- `POST /api/analyze`：单股分析（同步返回完整结果）
- `POST /api/batch_analyze`：批量分析（最多 10 只）
- `GET /api/task_status/<stock_code>`：查看任务状态

## 5. SSE 事件类型

SSE 消息通过 `data:` 推送 JSON，常见事件：

- `connected`：连接建立
- `heartbeat`：心跳
- `log`：日志文本
- `progress`：进度更新
- `scores_update`：阶段/最终评分
- `partial_result`：中间结果
- `ai_stream`：AI 增量文本
- `final_result`：最终单股结果
- `batch_result`：批量结果
- `analysis_complete`：分析结束
- `analysis_error`：分析错误

## 6. 关键配置说明（config.json）

### 6.1 `api_keys`

- `openai` / `anthropic` / `zhipu` / `siliconflow`

### 6.2 `ai`

- `model_preference`：默认模型提供方
- `models`：每个提供方对应模型名
- `max_tokens` / `temperature`：生成参数
- `api_base_urls`：兼容 OpenAI 协议时可配置自定义地址
- `json_mode`：新闻 JSON 模式分析（可选）

### 6.3 `analysis_weights`

- `technical` / `fundamental` / `sentiment`
- 建议总和为 `1.0`

### 6.4 `analysis_params`

- `max_news_count`：新闻条数上限
- `technical_period_days`：技术分析窗口
- `financial_indicators_count`：财务指标数量

### 6.5 `web_auth`

- `enabled: true` 启用登录鉴权
- `password`：访问密码（必填）
- `session_timeout`：会话超时秒数

## 7. 常见问题

### 7.1 提示“分析器未初始化”

通常原因：

- 依赖未安装完整
- `config.json` 格式错误
- AkShare/网络环境异常

可先检查：

```bash
pip install -r requirements.txt
```

并查看启动日志中的具体异常栈。

### 7.2 流式接口返回“缺少客户端ID”

- 先建立 `/api/sse?client_id=xxx`
- 再在 `POST /api/analyze_stream` 或 `POST /api/batch_analyze_stream` 中传同一个 `client_id`

### 7.3 返回 429 “正在分析中”

- 同一股票同一时间只允许一个在途分析任务
- 等待当前任务结束后再提交

### 7.4 开启了 `web_auth.enabled=true` 但无法登录

- 确认 `web_auth.password` 非空
- 确认客户端 Cookie/Session 未被禁用

## 8. 开发说明

- 当前 Web 前端内嵌在 `flask_web_server.py` 的模板字符串中（非独立前端工程）
- 线程池默认 `max_workers=4`
- 服务运行参数：`threaded=True`，端口 `5000`

---

如果你要二次开发，建议先从以下路径阅读：

- `flask_web_server.py`（接口与推送流程）
- `web_stock_analyzer.py`（行情抓取、评分与 AI 调用）
