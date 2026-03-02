# 🚀 AI增强股票分析系统 (Enhanced AI Stock Analysis System)

## 📋 项目简介

这是一个比较专业的AI增强 A股股票分析系统，集成了**25项财务指标分析**、**综合新闻情绪分析**、**技术指标计算**和**AI深度解读**。系统支持多种AI模型（OpenAI GPT、Claude、智谱AI），提供桌面GUI和Web两种界面，具备实时流式推送功能。
暂时只支持中国股票，港美股正在优化还未发布，港美股新闻信息等获取受限缓慢优化中。

### 近期刚刚开学。事情比较多有点摆。可能有些问题修复受限（在逆向学校查寝系统中）
## 💰 请我喝奶茶

如果这个项目对您有帮助，欢迎支持：
🔗 [https://juanzen.linzefeng.top/](https://juanzen.linzefeng.top/)
## demo网站小日志
#### ~~最近家里云openwrt不堪重负的逝去了，择日恢复demo站点。(大家不要学我all in one，那么就会变成all in boom）~~
#### 更换cdn到国内节点
#### 已经恢复demo站点，使用deepseek-ai/DeepSeek-R1-0528-Qwen3-8B模型分析。版本为2.6webapp（3.1出现大量bug，回退）。
#### 现在最新版本是3.0，版本目前已经可以投入生产，支持了港美股，在win端支持了快速部署。支持了新闻压缩。
## 近期开发日志
- docker编译支持一键部署 x86及arm 64
- 港美股支持
- 其他慢慢想和学习一些策略。
## ✨ 核心特性

### 🎯 多维度分析
- **25项核心财务指标**：盈利能力、偿债能力、营运能力、发展能力、市场表现
- **技术面分析**：移动平均线、RSI、MACD、布林带、成交量分析
- **市场情绪分析**：新闻、公告、研报情绪挖掘，支持100+条新闻分析
- **AI智能解读**：多模型深度分析，提供专业投资建议

### 🤖 AI能力支持
- **多模型兼容**：OpenAI GPT-4、Claude-3、智谱AI ChatGLM
- **智能切换**：主备API自动切换，确保服务可用性
- **流式推理**：实时AI分析过程展示，支持Server-Sent Events
- **高级规则**：AI不可用时自动降级到高级规则分析

### 🌐 多端支持
- **桌面版GUI**：基于PyQt6的现代化界面，支持实时日志和进度显示
- **Web版本**：Flask + SSE，支持多用户并发，实时流式推送
- **批量分析**：支持多股票并发分析，线程池优化
- **Docker部署**：容器化部署，支持一键启动

### 🔐 企业级特性
- **密码鉴权**：Web版支持密码保护和会话管理
- **高并发**：线程池 + 异步处理 + 任务队列优化
- **缓存机制**：智能数据缓存，减少API调用
- **错误处理**：完善的异常处理和重试机制

## 🏗️ 系统架构

```
📦 AI股票分析系统
├── 🖥️ 桌面版 (2.0 win app/)
│   ├── gui2.py                    # 现代化GUI界面
│   ├── stock_analyzer.py          # 核心分析引擎
│   ├── 配置文件编辑器.py            # 可视化配置管理
│   └── config.json                # 系统配置文件
├── 🌐 Web版 (2.6 webapp/)
│   ├── flask_web_server.py        # Flask服务器(SSE支持)
│   ├── web_stock_analyzer.py      # Web优化分析器
│   ├── Dockerfile                 # Docker容器配置
│   └── docker-compose.yaml        # 容器编排配置
└── 📚 文档
    └── README.md                   # 项目文档
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/DR-lin-eng/stock-scanner.git
cd stock-analysis-system

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置系统

创建 `config.json` 文件（参考 `config - 示例.json`）：

```json
{
    "api_keys": {
        "openai": "sk-your-openai-key",
        "anthropic": "sk-ant-your-claude-key",
        "zhipu": "your-zhipu-key"
    },
    "ai": {
        "model_preference": "openai",
        "models": {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307"
        }
    },
    "web_auth": {
        "enabled": true,
        "password": "your_password",
        "session_timeout": 3600
    }
}
```

### 3. 运行系统

#### 🖥️ 桌面版GUI
```bash
cd "2.0 win app"
python gui2.py
```

#### 🌐 Web版本
```bash
cd "2.6 webapp（流式传输测试版）"
python flask_web_server.py
# 访问 http://localhost:5000
```

#### 🐳 Docker部署
```bash
cd "2.6 webapp（流式传输测试版）"
docker-compose up -d
```

## 📊 功能详解

### 财务指标分析（25项）

| 类别 | 指标 | 说明 |
|------|------|------|
| 盈利能力 | 净利润率、净资产收益率、总资产收益率 | 评估公司盈利水平 |
| 偿债能力 | 流动比率、资产负债率、利息保障倍数 | 评估财务风险 |
| 营运能力 | 总资产周转率、存货周转率 | 评估运营效率 |
| 发展能力 | 营收增长率、净利润增长率 | 评估成长性 |
| 市场表现 | 市盈率、市净率、PEG比率 | 评估估值水平 |

### 技术指标体系
- **趋势指标**：多周期移动平均线、MACD金叉死叉
- **震荡指标**：RSI超买超卖、布林带位置
- **成交量**：量价配合分析、成交量比率
- **综合评分**：多指标权重计算，0-100分评级

### AI分析能力
- **智能解读**：基于25项指标的专业分析
- **投资策略**：明确的买卖建议和操作策略
- **风险评估**：潜在风险和机会识别
- **行业对比**：同行业估值和财务对比

## 🔧 API接口文档

### Web版API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 系统状态检查 |
| `/api/sse` | GET | SSE流式接口 |
| `/api/analyze_stream` | POST | 单股票流式分析 |
| `/api/batch_analyze_stream` | POST | 批量流式分析 |
| `/api/system_info` | GET | 系统信息 |

### SSE事件类型
- `connected`: 连接确认
- `log`: 日志消息  
- `progress`: 进度更新
- `scores_update`: 评分更新
- `final_result`: 最终结果
- `ai_stream`: AI流式内容

## 🎨 界面展示

### 桌面版GUI
- 现代化Material Design风格
- 实时日志和进度显示
- 动态评分卡片和数据指标
- 支持单股票和批量分析

### Web版界面  
- 响应式设计，支持移动端
- SSE实时流式推送
- 动态结果更新
- 密码鉴权保护

## ⚙️ 配置选项

### 核心配置
```json
{
    "analysis_weights": {
        "technical": 0.4,    // 技术面权重
        "fundamental": 0.4,  // 基本面权重  
        "sentiment": 0.2     // 情绪面权重
    },
    "analysis_params": {
        "max_news_count": 100,           // 最大新闻数量
        "technical_period_days": 365,    // 技术分析周期
        "financial_indicators_count": 25  // 财务指标数量
    },
    "cache": {
        "price_hours": 1,      // 价格数据缓存时间
        "fundamental_hours": 6, // 基本面缓存时间
        "news_hours": 2        // 新闻数据缓存时间
    }
}
```

## 🔍 使用示例

### 单股票分析
```python
from stock_analyzer import EnhancedStockAnalyzer

# 初始化分析器
analyzer = EnhancedStockAnalyzer()

# 分析股票
report = analyzer.analyze_stock('000001')

print(f"股票名称: {report['stock_name']}")
print(f"综合得分: {report['scores']['comprehensive']:.1f}")
print(f"投资建议: {report['recommendation']}")
```

### Web API调用
```bash
# 单股票分析
curl -X POST http://localhost:5000/api/analyze_stream \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "000001", "client_id": "test_client"}'

# 批量分析
curl -X POST http://localhost:5000/api/batch_analyze_stream \
  -H "Content-Type: application/json" \
  -d '{"stock_codes": ["000001", "000002"], "client_id": "test_client"}'
```

## 📈 性能优化

### 高并发特性
- **线程池**：支持4个工作线程并发处理
- **异步分析**：非阻塞任务处理
- **连接复用**：SSE连接池管理
- **智能缓存**：多级缓存减少API调用

### 数据优化
- **NaN值清理**：确保JSON序列化兼容
- **批量处理**：并发获取多股票数据
- **增量更新**：支持部分结果推送

## 🛡️ 安全特性

### Web端安全
- **密码鉴权**：支持自定义密码保护
- **会话管理**：可配置会话超时时间
- **CSRF防护**：跨站请求伪造防护
- **输入验证**：严格的参数校验

### 数据安全
- **API密钥保护**：本地加密存储
- **错误处理**：不泄露敏感信息
- **访问控制**：基于会话的权限控制

## 🔧 故障排除

### 常见问题

1. **数据获取失败**
   ```bash
   # 检查网络连接
   ping quote.eastmoney.com
   
   # 检查akshare版本
   pip install --upgrade akshare
   ```

2. **AI分析失败**
   ```bash
   # 检查API密钥配置
   python -c "import json; print(json.load(open('config.json'))['api_keys'])"
   
   # 测试API连接
   curl -H "Authorization: Bearer YOUR_API_KEY" https://api.openai.com/v1/models
   ```

3. **Web版访问问题**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep :5000
   
   # 查看服务日志
   python flask_web_server.py
   ```

## 📦 部署指南

### 开发环境
```bash
# 安装开发依赖
pip install -r requirements.txt

# 启动开发服务器
python flask_web_server.py
```

### 生产环境
```bash
# 使用Gunicorn部署
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 flask_web_server:app

# 或使用Docker
docker-compose up -d
```

### 反向代理参考(Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/sse {
        proxy_pass http://localhost:5000;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
```

## 📊 版本历史

### v3.0 (2024-12) - AI增强版
- ✨ 集成多AI模型支持
- 🌊 新增SSE流式推送
- 🔐 增加Web端密码鉴权
- 🚀 高并发性能优化

### v2.0 (2024-11) - 增强版  
- 📊 新增25项财务指标分析
- 📰 增加综合新闻情绪分析
- 🎨 现代化GUI界面
- ⚙️ 可视化配置管理器

### v1.0 (2024-10) - 基础版
- 📈 基础技术指标分析
- 🖥️ 简单GUI界面
- 📋 单股票分析功能

## 🤝 贡献指南

欢迎提交Issues和Pull Requests！

### 开发流程
1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

Copyright (c) 2024 [linzefeng]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## ⚠️ 免责声明

**本系统仅用于学习和研究目的，所有分析结果仅供参考，不构成投资建议。投资有风险，入市需谨慎。**



## 💖 特别鸣谢
[Pollinations AI](https://auth.pollinations.ai/) 为提供llm生成服务
![NodeSupport](https://github.com/user-attachments/assets/843f88fc-ecf7-4993-93c4-f82a29078e28)

[yxvm](https://yxvm.com/) | [NodeSupport](https://github.com/NodeSeekDev/NodeSupport) 赞助了本项目

## 👨‍💻 作者

Created by [linzefeng]

---

<div align="center">

**如果这个项目对您有帮助，请给个 ⭐ Star 支持一下！**

[📧 Issue反馈](../../issues) | [🚀 功能建议](../../discussions) | [📖 更多文档](../../wiki) | ![Docker Image](https://ghcr-badge.deta.dev/dr-lin-eng/stock-scanner/stock-webapp/latest_tag?trim=major\&label=最新版本)


</div>
