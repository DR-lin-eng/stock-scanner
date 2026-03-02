# config - 示例.json 填写指南（config-readme）

本文专门说明如何填写 `config - 示例.json`（复制后通常命名为 `config.json`）。

适用场景：

- 首次配置项目，不清楚哪些字段必须填
- 想快速切换 `OpenAI / Claude / 智谱 / SiliconFlow`
- 想开启 Web 登录密码或调整分析参数

## 1. 最快可用配置（先跑起来）

步骤：

1. 复制示例文件为 `config.json`
2. 至少填写一个 API Key（如 `api_keys.openai`）
3. 确认 `ai.model_preference` 与你填写的 Key 对应
4. 启动服务

示例（只用 OpenAI）：

```json
{
  "api_keys": {
    "openai": "sk-your-real-key",
    "anthropic": "",
    "zhipu": "",
    "siliconflow": ""
  },
  "ai": {
    "model_preference": "openai",
    "models": {
      "openai": "gpt-4.1-nano"
    },
    "api_base_urls": {
      "openai": "https://api.openai.com/v1"
    },
    "max_tokens": 4000,
    "temperature": 0.7
  }
}
```

说明：

- 其余字段不填会走默认值（程序会自动补齐或按内置默认运行）
- 不填任何 Key 也能运行，但会降级为规则分析（无 LLM 深度文本）

## 2. 顶层字段逐项说明

当前示例文件主要包含以下顶层键：

- `api_keys`
- `ai`
- `analysis_weights`
- `cache`
- `streaming`
- `analysis_params`
- `web_auth`
- `logging`
- `data_sources`
- `ui`
- `_metadata`

### 2.1 `api_keys`

用途：存放各模型平台密钥。

建议：

- 只填你要用的平台，其他保持空字符串即可
- 不要把真实密钥提交到 Git 仓库

字段：

- `openai`: OpenAI Key
- `anthropic`: Claude Key
- `zhipu`: 智谱 Key
- `siliconflow`: SiliconFlow Key

### 2.2 `ai`

用途：模型选择、模型名、生成参数和 API 地址。

关键字段：

- `model_preference`: 当前主提供方，必须与已填 Key 对应
- `models`: 各提供方的模型名映射
- `api_base_urls`: 各提供方 API Base URL
- `max_tokens`: 输出 token 上限，建议 `1500~4000`
- `temperature`: 随机性，建议 `0.2~0.8`
- `json_mode`: 新闻 JSON 模式配置

注意：

- 如果使用中转网关，通常改 `api_base_urls.<provider>`
- `json_mode.enabled=true` 时，建议 `temperature` 用较低值（如 `0.1~0.3`）

### 2.3 `analysis_weights`

用途：综合评分中各维度权重。

字段：

- `technical`: 技术面权重
- `fundamental`: 基本面权重
- `sentiment`: 情绪面权重

建议：

- 三者总和保持 `1.0`
- 常用组合：
1. 均衡：`0.4 / 0.4 / 0.2`
2. 偏交易：`0.6 / 0.2 / 0.2`
3. 偏基本面：`0.2 / 0.6 / 0.2`

### 2.4 `cache`

用途：各类数据缓存时间，减少重复请求。

字段建议：

- `price_hours`: 价格缓存小时，常用 `1`
- `fundamental_hours`: 基本面缓存小时，常用 `6`
- `news_hours`: 新闻缓存小时，常用 `1~4`
- `invalid_symbol_minutes`: 无效代码缓存分钟，常用 `30`
- `akshare_endpoint_cooldown_seconds`: 数据端点冷却秒，常用 `60~120`

### 2.5 `streaming`

用途：前端流式输出行为。

字段：

- `enabled`: 是否启用流式
- `show_thinking`: 是否展示思考过程（一般建议 `false`）
- `delay`: 流式输出间隔，常用 `0.03~0.1`

### 2.6 `analysis_params`

用途：分析数据量与窗口大小。

常用字段：

- `max_news_count`: 抓取新闻上限，常用 `50~150`
- `technical_period_days`: 技术分析周期，常用 `180~365`
- `financial_indicators_count`: 财务指标数量，常用 `20~35`
- `main_prompt_news_max_items`: 主提示词新闻条目上限
- `main_prompt_news_max_chars`: 主提示词新闻字符上限

### 2.7 `web_auth`

用途：Web 页面密码保护。

字段：

- `enabled`: 是否启用
- `password`: 登录密码（启用后必填）
- `session_timeout`: 会话超时秒数（如 `3600`）

安全建议：

- 对外网访问务必开启
- 密码不要使用示例值 `your_password_here`

### 2.8 `logging`

用途：日志等级与日志文件名。

字段：

- `level`: 建议 `INFO`；排障可改 `DEBUG`
- `file`: 日志文件名

### 2.9 `data_sources`

用途：数据源与备用策略（当前以 AkShare 为主）。

字段：

- `akshare_token`: 如你使用的渠道需要可填写
- `backup_sources`: 备用数据源列表

### 2.10 `ui`

用途：界面偏好（主题、语言、窗口尺寸等）。

说明：

- 多数情况下保留默认即可

### 2.11 `_metadata`

用途：配置版本与说明信息。

说明：

- 仅用于备注，通常不影响业务逻辑

## 3. 常见配置模板

### 3.1 模板 A：OpenAI 官方直连

```json
{
  "api_keys": {
    "openai": "sk-your-real-key"
  },
  "ai": {
    "model_preference": "openai",
    "models": {
      "openai": "gpt-4.1-mini"
    },
    "api_base_urls": {
      "openai": "https://api.openai.com/v1"
    },
    "max_tokens": 3000,
    "temperature": 0.6
  }
}
```

### 3.2 模板 B：SiliconFlow

```json
{
  "api_keys": {
    "siliconflow": "sk-your-real-key"
  },
  "ai": {
    "model_preference": "siliconflow",
    "models": {
      "siliconflow": "Qwen/Qwen2.5-7B-Instruct"
    },
    "api_base_urls": {
      "siliconflow": "https://api.siliconflow.cn/v1"
    },
    "max_tokens": 3000,
    "temperature": 0.6
  }
}
```

### 3.3 模板 C：仅规则分析（无 LLM）

```json
{
  "api_keys": {
    "openai": "",
    "anthropic": "",
    "zhipu": "",
    "siliconflow": ""
  },
  "ai": {
    "model_preference": "openai"
  }
}
```

说明：

- 可跑通分析流程，但 AI 深度解读会降级

## 4. 桌面 GUI 用户怎么配

如果你使用桌面启动器（`desktop_gui_launcher.py` 或 `StockAnalyzerDesktop.exe`）：

1. 打开「配置中心」页签
2. 在“快速配置”填入常用项（Key、主模型、Web 鉴权）
3. 点击“应用快速配置到 JSON”
4. 点击“保存配置”
5. 回到“运行日志”页签启动服务

你也可以直接在配置中心的 JSON 编辑区全量修改并保存。

## 5. 常见错误与排查

### 5.1 `JSON 解析失败`

排查：

- 检查是否多了逗号或少了引号
- 用桌面 GUI 的“验证 JSON / 格式化 JSON”

### 5.2 已填 Key 但仍显示未配置

排查：

- 确认 `api_keys.<provider>` 不是空字符串
- 确认 `ai.model_preference` 与该 provider 一致
- 保存后重启服务

### 5.3 启用了 `web_auth.enabled=true` 但无法登录

排查：

- 确认 `web_auth.password` 非空
- 清理浏览器 Cookie 后重试
- 检查 `session_timeout` 是否过短

### 5.4 使用中转 API 报 401/404

排查：

- 检查 `ai.api_base_urls.<provider>` 是否带 `/v1`
- 确认模型名与中转平台实际支持一致
- 用同一 Key 在平台控制台验证可用性

## 6. 安全建议（务必看）

- 不要把真实 API Key 发给他人或提交到公开仓库
- 对公网部署强烈建议开启 `web_auth`
- 建议将配置文件加入 `.gitignore`（如果你使用 Git）

---

如果你希望，我可以再补一份：

- 面向“只用 OpenAI”的极简 `config.json` 模板
- 面向“公司代理网关”的中转版模板
- 面向“高频批量分析”的性能优先模板
