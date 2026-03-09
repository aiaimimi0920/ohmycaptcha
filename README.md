<div align="center">

# OhMyCaptcha

**Self-hostable YesCaptcha-style captcha solver for flow2api and similar integrations**

[中文说明](README.zh-CN.md) · [Documentation](https://shenhao-stu.github.io/ohmycaptcha/) · [GitHub Pages](https://shenhao-stu.github.io/ohmycaptcha/)

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-blue.svg">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688.svg">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-Chromium-2EAD33.svg">
  <img alt="Docs" src="https://img.shields.io/badge/docs-MkDocs%20Material-526CFE.svg">
</p>

<p align="center">
  <img src="docs/assets/hero.svg" alt="OhMyCaptcha hero illustration" width="100%">
</p>

OhMyCaptcha is a self-hostable captcha solving service that exposes a **YesCaptcha-style async API** for the task types implemented in this repository. It is designed for **flow2api**, internal routing layers, and other systems that expect `createTask` / `getTaskResult` semantics.

It combines:

- **FastAPI** for the HTTP API
- **Playwright + Chromium** for reCAPTCHA v3 token generation
- **OpenAI-compatible multimodal APIs** for image captcha analysis
- **A simple in-memory async task manager** for background execution

---

## Overview

<table>
  <tr>
    <td width="52%" valign="top">

### Why this project?

Managed services such as YesCaptcha are convenient, but self-hosted workflows often need:

- deployment control
- model routing flexibility
- compatibility with local or self-hosted multimodal providers
- a transparent browser-based solving pipeline

OhMyCaptcha focuses on that space.

### What it is not

OhMyCaptcha should be described as a **self-hostable YesCaptcha-compatible service for the task types implemented here**, not as a claim of full parity with every commercial captcha-solving platform.

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

## Features

- YesCaptcha-style API surface:
  - `POST /createTask`
  - `POST /getTaskResult`
  - `POST /getBalance`
  - `GET /api/v1/health`
- Implemented reCAPTCHA v3 task types:
  - `RecaptchaV3TaskProxyless`
  - `RecaptchaV3TaskProxylessM1`
  - `RecaptchaV3TaskProxylessM1S7`
  - `RecaptchaV3TaskProxylessM1S9`
- Implemented multimodal task type:
  - `ImageToTextTask`
- OpenAI-compatible model integration for hosted or self-hosted multimodal gateways
- Render-ready Docker deployment
- GitHub Pages documentation with English and Simplified Chinese content

## Supported task types

### reCAPTCHA v3

The service currently registers the following task types at startup:

- `RecaptchaV3TaskProxyless`
- `RecaptchaV3TaskProxylessM1`
- `RecaptchaV3TaskProxylessM1S7`
- `RecaptchaV3TaskProxylessM1S9`

All four task types currently use the same browser-based solving path in this codebase.

### Image captcha recognition

- `ImageToTextTask`

`ImageToTextTask` is backed by an Argus-inspired multimodal recognition prompt. It normalizes images to a 1440×900 coordinate space and returns structured recognition output serialized into `solution.text`.

## Quick start

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 2. Configure environment variables

```bash
export CLIENT_KEY="your-client-key"
export CAPTCHA_BASE_URL="https://your-openai-compatible-endpoint/v1"
export CAPTCHA_API_KEY="your-api-key"
export CAPTCHA_MODEL="gpt-5.4"
export CAPTCHA_MULTIMODAL_MODEL="qwen3.5-2b"
export BROWSER_HEADLESS="true"
export BROWSER_TIMEOUT="30"
```

### 3. Start the service

```bash
python main.py
```

### 4. Verify health

```bash
curl http://localhost:8000/api/v1/health
```

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `CLIENT_KEY` | Client authentication key used as `clientKey` | unset |
| `CAPTCHA_BASE_URL` | OpenAI-compatible API base URL | `https://your-openai-compatible-endpoint/v1` |
| `CAPTCHA_API_KEY` | API key for the configured model backend | unset |
| `CAPTCHA_MODEL` | Strong text model name | `gpt-5.4` |
| `CAPTCHA_MULTIMODAL_MODEL` | Multimodal model name | `qwen3.5-2b` |
| `CAPTCHA_RETRIES` | Retry count for model/browser operations | `3` |
| `CAPTCHA_TIMEOUT` | Model request timeout in seconds | `30` |
| `BROWSER_HEADLESS` | Whether Chromium runs headless | `true` |
| `BROWSER_TIMEOUT` | Page load timeout in seconds | `30` |
| `SERVER_HOST` | Bind host | `0.0.0.0` |
| `SERVER_PORT` | Bind port | `8000` |

## API examples

### Create a reCAPTCHA v3 task

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

### Poll task result

```bash
curl -X POST http://localhost:8000/getTaskResult \
  -H "Content-Type: application/json" \
  -d '{
    "clientKey": "your-client-key",
    "taskId": "uuid-from-createTask"
  }'
```

### Create an image task

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

## Deployment guides

Detailed guides are available in the docs site:

- [Render deployment](https://shenhao-stu.github.io/ohmycaptcha/deployment/render/)
- [Hugging Face Spaces deployment](https://shenhao-stu.github.io/ohmycaptcha/deployment/huggingface/)

## Acceptance status

This repository has been validated locally against the public reCAPTCHA v3 detector target at:

- `https://antcpt.com/score_detector/`
- site key: `6LcR_okUAAAAAPYrPe-HK_0RULO1aZM15ENyM-Mf`

The verified result for this codebase is that the service can successfully:

- start the API service
- create a detector task
- poll until `ready`
- return a non-empty `solution.gRecaptchaResponse`

The implementation does **not** claim guaranteed score targeting or full compatibility with all commercial captcha service features.

## Limitations

- Tasks are stored **in memory** and expire after the configured TTL.
- `minScore` exists in the schema for compatibility, but the current solver does **not** enforce score targeting.
- `ImageToTextTask` output is currently returned in `solution.text` as serialized JSON, not a richer typed API object.
- Reliability depends on browser environment, target-site behavior, IP reputation, and model/provider quality.

## Repository screenshots

You can add screenshots later under `docs/assets/` and reference them here, for example:

```md
![API health page](docs/assets/health.png)
```

This keeps the public README visually strong without embedding private runtime details.

## Documentation

- English docs: `docs/`
- Chinese docs: `docs/zh/`
- Published site: `https://shenhao-stu.github.io/ohmycaptcha/`

## Agent skills

This repository also includes installable agent skills under:

- `skills/ohmycaptcha/` — operate, deploy, validate, and integrate OhMyCaptcha
- `skills/ohmycaptcha-image/` — generate public-safe README and docs visuals

They are intended for Claude Code, OpenCode, and similar agent environments that can reuse repository-local skills.

## Development

Run tests:

```bash
pytest tests/
```

Run type checks:

```bash
npx pyright
```

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=shenhao-stu/ohmycaptcha&type=Date)](https://www.star-history.com/#shenhao-stu/ohmycaptcha&Date)

## License

This repository is released under the [MIT License](LICENSE).
