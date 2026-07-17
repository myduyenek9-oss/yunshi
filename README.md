# 运势提醒 App

个人八字运势提醒服务：每天按北京时间自动生成当日/当月/当年运势并推送到钉钉，同时提供一个 Token 保护的网页问答入口。

## 功能

- FastAPI 后端与内置轻量网页 `/fortune?token=...`
- APScheduler 每日定时任务，默认 `Asia/Shanghai` 08:00
- `lunar-python` 计算八字、流年、流月、流日与基础关系
- OpenAI 现场生成运势与问答内容
- 钉钉群自定义机器人 Markdown 推送，支持 Secret 加签
- Docker Compose 独立部署，不影响已有应用

## 本地运行

```bash
cp .env.example .env
# 编辑 .env：填写 WEB_ACCESS_TOKEN、出生信息、OPENAI_API_KEY、钉钉 Webhook/Secret
# 如果只是本地测试，可先设置 MOCK_AI=true
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8088
```

访问：

- 健康检查：`http://127.0.0.1:8088/health`
- 网页问答：`http://127.0.0.1:8088/fortune?token=你的WEB_ACCESS_TOKEN`

## Docker Compose 部署

```bash
cp .env.example .env
nano .env

docker compose up -d --build
docker compose logs -f fortune-reminder
```

手动触发钉钉推送：

```bash
curl -X POST http://127.0.0.1:8088/api/push-now \
  -H "Authorization: Bearer 你的WEB_ACCESS_TOKEN"
```

只生成预览、不推送钉钉：

```bash
curl -X POST http://127.0.0.1:8088/api/generate-preview \
  -H "Authorization: Bearer 你的WEB_ACCESS_TOKEN"
```

## 阿里云/Nginx 建议

如果服务器已有 Nginx，可新增子域名或路径反向代理到 `127.0.0.1:8088`。Compose 默认通过 `APP_BIND_HOST=127.0.0.1` 只监听本机；没有 Nginx 时临时改为 `0.0.0.0` 并开放安全组 TCP 8088。完整阿里云部署步骤见 [`DEPLOYMENT.md`](DEPLOYMENT.md)。例如：

```nginx
location /fortune {
    proxy_pass http://127.0.0.1:8088/fortune;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api/ {
    proxy_pass http://127.0.0.1:8088/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

请在阿里云安全组中只开放需要的端口。若通过 Nginx 暴露 HTTPS，一般无需直接开放 `8088` 给公网。

## 环境变量

见 `.env.example`。注意：

- `.env` 包含出生信息、OpenAI Key、钉钉 Secret，不要提交到 Git。
- `BIRTH_CALENDAR` 支持 `solar` 或 `lunar`。
- `BIRTH_TIME` 用于计算时柱；如果时辰不准，生成结果也会提示准确性限制。
- `OPENAI_MODEL` 可随时切换。
- `MOCK_AI=true` 只用于本地测试，不会调用 OpenAI。

## API

### GET `/health`

返回服务状态、当前时间和 scheduler 状态。

### GET `/fortune?token=xxx`

返回 Token 保护的问答页面。

### POST `/api/ask`

```http
Authorization: Bearer <WEB_ACCESS_TOKEN>
Content-Type: application/json
```

```json
{"question":"我今天适合谈合作吗？"}
```

### POST `/api/push-now`

手动生成并推送钉钉消息。

### POST `/api/generate-preview`

生成并保存最近一次运势，但不推送钉钉，用于部署前检查 OpenAI 与八字计算是否正常。

## 测试

```bash
pytest
```

## 免责声明

本项目生成内容仅供个人参考，不作为医疗、投资、法律等专业决策依据。

