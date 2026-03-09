<div align="center">

# OhMyCaptcha

**面向 flow2api 与类似集成场景的可自托管 YesCaptcha 风格验证码服务**

[English README](README.md) · [在线文档](https://shenhao-stu.github.io/ohmycaptcha/) · [GitHub Pages](https://shenhao-stu.github.io/ohmycaptcha/)

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688.svg">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-Chromium-2EAD33.svg">
  <img alt="Docs" src="https://img.shields.io/badge/docs-MkDocs%20Material-526CFE.svg">
</p>

<p align="center">
  <img src="docs/assets/hero.svg" alt="OhMyCaptcha Hero 图" width="100%">
</p>

OhMyCaptcha 是一个可自托管的验证码解决服务，为本仓库已经实现的任务类型提供 **YesCaptcha 风格异步 API**。它面向 **flow2api**、内部路由层以及其他依赖 `createTask` / `getTaskResult` 语义的系统。

它主要由以下部分组成：

- **FastAPI**：提供 HTTP API
- **Playwright + Chromium**：生成 reCAPTCHA v3 token
- **OpenAI-compatible 多模态接口**：分析图片验证码
- **内存型异步任务管理器**：负责后台执行

---

## 项目概览

<table>
  <tr>
    <td width="52%" valign="top">

### 为什么做这个项目？

YesCaptcha 等托管服务很方便，但很多自托管场景还需要：

- 更可控的部署方式
- 更灵活的模型路由
- 兼容本地或自托管多模态提供方
- 更透明的浏览器求解流程

OhMyCaptcha 主要聚焦在这个方向。

### 它不是什么？

OhMyCaptcha 更准确的描述是：**针对本仓库已实现任务类型的、自托管 YesCaptcha-compatible 服务**，而不是对所有商业打码平台功能的完整对标。

</td>
<td width="48%" valign="top">

```text
Client / flow2api
        │
        ▼
  POST /createTask
        │
        ▼
 In-memory TaskManager
        │
   ┌────┴────┐
   ▼         ▼
Playwright   OpenAI-compatible
reCAPTCHA    multimodal model
solver       backend
   │         │
   └────┬────┘
        ▼
 POST /getTaskResult
```

</td>
  </tr>
</table>

---

## 功能特性

- YesCaptcha 风格 API：
  - `POST /createTask`
  - `POST /getTaskResult`
  - `POST /getBalance`
  - `GET /api/v1/health`
- 已实现的 reCAPTCHA v3 任务类型：
  - `RecaptchaV3TaskProxyless`
  - `RecaptchaV3TaskProxylessM1`
  - `RecaptchaV3TaskProxylessM1S7`
  - `RecaptchaV3TaskProxylessM1S9`
- 已实现的多模态任务类型：
  - `ImageToTextTask`
- 支持对接托管或自托管的 OpenAI-compatible 多模态网关
- 提供 Render-ready Docker 部署文件
- 提供中英文 GitHub Pages 文档站

## 支持的任务类型

### reCAPTCHA v3

服务启动时会注册以下任务类型：

- `RecaptchaV3TaskProxyless`
- `RecaptchaV3TaskProxylessM1`
- `RecaptchaV3TaskProxylessM1S7`
- `RecaptchaV3TaskProxylessM1S9`

当前这四种任务类型在本仓库中共用同一套浏览器求解路径。

### 图片验证码识别

- `ImageToTextTask`

`ImageToTextTask` 采用受 Argus 启发的多模态识别提示词设计，会先将图片归一化到 1440×900 坐标空间，再把结构化识别结果序列化到 `solution.text` 中返回。

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 2. 配置环境变量

```bash
export CLIENT_KEY="your-client-key"
export CAPTCHA_BASE_URL="https://your-openai-compatible-endpoint/v1"
export CAPTCHA_API_KEY="your-api-key"
export CAPTCHA_MODEL="gpt-5.4"
export CAPTCHA_MULTIMODAL_MODEL="qwen3.5-2b"
export BROWSER_HEADLESS="true"
export BROWSER_TIMEOUT="30"
```

### 3. 启动服务

```bash
python main.py
```

### 4. 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

## 配置项

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `CLIENT_KEY` | 客户端认证密钥，对应 `clientKey` | 未设置 |
| `CAPTCHA_BASE_URL` | OpenAI-compatible API 基地址 | `https://your-openai-compatible-endpoint/v1` |
| `CAPTCHA_API_KEY` | 模型接口密钥 | 未设置 |
| `CAPTCHA_MODEL` | 强文本模型名称 | `gpt-5.4` |
| `CAPTCHA_MULTIMODAL_MODEL` | 多模态模型名称 | `qwen3.5-2b` |
| `CAPTCHA_RETRIES` | 模型或浏览器失败重试次数 | `3` |
| `CAPTCHA_TIMEOUT` | 模型请求超时（秒） | `30` |
| `BROWSER_HEADLESS` | Chromium 是否无头运行 | `true` |
| `BROWSER_TIMEOUT` | 页面加载超时（秒） | `30` |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `8000` |

## API 示例

### 创建 reCAPTCHA v3 任务

```bash
curl -X POST http://localhost:8000/createTask \
  -H "Content-Type: application/json" \
  -d '{
    "clientKey": "your-client-key",
    "task": {
      "type": "RecaptchaV3TaskProxyless",
      "websiteURL": "https://antcpt.com/score_detector/",
      "websiteKey": "6LcR_okUAAAAAPYrPe-HK_0RULO1aZM15ENyM-Mf",
      "pageAction": "homepage"
    }
  }'
```

### 轮询任务结果

```bash
curl -X POST http://localhost:8000/getTaskResult \
  -H "Content-Type: application/json" \
  -d '{
    "clientKey": "your-client-key",
    "taskId": "uuid-from-createTask"
  }'
```

### 创建图片验证码任务

```bash
curl -X POST http://localhost:8000/createTask \
  -H "Content-Type: application/json" \
  -d '{
    "clientKey": "your-client-key",
    "task": {
      "type": "ImageToTextTask",
      "body": "<base64-encoded-image>"
    }
  }'
```

## 部署指南

详细部署文档见文档站：

- [Render 部署](https://shenhao-stu.github.io/ohmycaptcha/zh/deployment/render/)
- [Hugging Face Spaces 部署](https://shenhao-stu.github.io/ohmycaptcha/zh/deployment/huggingface/)

## 验收状态

本仓库已经在本地环境下，针对以下公开 reCAPTCHA v3 检测目标完成了验收：

- `https://antcpt.com/score_detector/`
- site key：`6LcR_okUAAAAAPYrPe-HK_0RULO1aZM15ENyM-Mf`

当前已验证的结果是：

- 服务可以正常启动
- 可以成功创建 detector 任务
- 可以轮询到 `ready`
- 可以返回非空的 `solution.gRecaptchaResponse`

本实现**不宣称**可以保证特定 score，也**不宣称**与商业打码平台所有功能完全一致。

## 限制说明

- 任务状态保存在**内存中**，并会在 TTL 到期后清理。
- `minScore` 为兼容性字段，当前 solver **不会**依据它做分数控制。
- `ImageToTextTask` 目前把结构化结果序列化后放在 `solution.text` 中返回，而不是更强类型化的 API 对象。
- 实际稳定性取决于浏览器环境、目标站行为、IP 信誉以及模型/供应商质量。

## 仓库截图建议

后续你可以把截图放到 `docs/assets/` 下，再在 README 中引用，例如：

```md
![API 健康检查](docs/assets/health.png)
```

这样可以保持公开 README 的美观，同时避免泄露任何运行时隐私信息。

## 文档

- 英文文档：`docs/`
- 中文文档：`docs/zh/`
- 在线文档：`https://shenhao-stu.github.io/ohmycaptcha/`

## Agent Skills

仓库还包含可安装的 agent skills：

- `skills/ohmycaptcha/` — 用于部署、验证、集成和运维 OhMyCaptcha
- `skills/ohmycaptcha-image/` — 用于生成 README 与文档所需的公开安全图片

适用于 Claude Code、OpenCode 以及类似可以复用仓库内 skill 的 agent 环境。

## 开发

运行测试：

```bash
pytest tests/
```

运行类型检查：

```bash
npx pyright
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=shenhao-stu/ohmycaptcha&type=Date)](https://www.star-history.com/#shenhao-stu/ohmycaptcha&Date)

## License

本仓库采用 [MIT License](LICENSE)。
