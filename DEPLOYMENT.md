# 阿里云 Ubuntu 部署指南

本文用于把 `fortune-reminder` 独立部署到阿里云 Ubuntu 26.04 64 位服务器，不修改或覆盖服务器上已有的英语学习 App。

## 0. 部署架构与端口原则

推荐架构：

```text
浏览器 -> Nginx/HTTPS -> 127.0.0.1:8088 -> Docker 容器 fortune-reminder
```

本项目 Compose 默认只绑定到 `127.0.0.1:8088`，因此不会直接暴露到公网。若暂时没有域名和 Nginx，可以在服务器 `.env` 中把 `APP_BIND_HOST` 改成 `0.0.0.0`，并临时开放安全组 TCP 8088；测试完成后应恢复为 `127.0.0.1`。

先不要执行任何删除旧容器、删除旧目录或修改英语学习 App 的命令。

## 1. 准备信息

请提前准备：

- 阿里云服务器公网 IP、SSH 用户和 SSH 端口；
- 一个代码仓库地址，或准备使用 SCP 上传项目压缩包；
- OpenAI 官方 API 或中转站的 API Key、模型名和 Base URL；
- 钉钉群自定义机器人 Webhook 和 Secret；
- 真实出生日期、出生时间、出生地点、性别；
- 如果使用 Nginx，准备一个解析到服务器公网 IP 的域名，例如 `fortune.example.com`。

不要把 `.env`、真实 API Key、钉钉 Webhook/Secret、`data/` 上传到公开仓库。

## 2. 本地上传代码

### 方式 A：Git（推荐）

在本地项目目录执行：

```bash
git init
git add .
git commit -m "initial fortune reminder app"
git branch -M main
git remote add origin <你的私有仓库地址>
git push -u origin main
```

如果仓库已经存在，只需要：

```bash
git add .
git commit -m "update fortune reminder"
git push
```

### 方式 B：压缩包/SCP

只上传项目源码文件，不要上传本地 `.env` 和 `data/`。服务器目标目录建议为：

```text
/opt/fortune-reminder
```

## 3. SSH 登录服务器并检查现有 App

Windows PowerShell：

```powershell
ssh root@<服务器公网IP>
```

如果不是 root 用户，将下面命令前的权限按需加 `sudo`。

登录后检查已有服务和端口：

```bash
ss -ltnp
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}'
```

确认英语学习 App 的目录、容器名和端口。不要使用相同的宿主机端口。如果 8088 已被占用，可以把本项目 `.env` 的 `APP_PORT` 改成 8090 或其他未占用端口；Nginx 只需要反代到这个新端口。

## 4. 安装 Docker Engine 和 Compose

先确认系统：

```bash
. /etc/os-release
echo "$PRETTY_NAME"
uname -m
```

Ubuntu 26.04 amd64 使用 Docker 官方 apt 仓库安装：

```bash
apt update
apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

docker --version
docker compose version
docker run --rm hello-world
```

使用新版 `docker compose` 命令，不要混用旧版 `docker-compose`。如果 apt 提示仓库暂时没有对应版本，先确认服务器架构和系统代号；不要随意安装来源不明的 Docker 包。

## 5. 放置项目

### 从 Git 仓库拉取

```bash
mkdir -p /opt/fortune-reminder
cd /opt/fortune-reminder
git clone <你的私有仓库地址> .
```

### 从本地压缩包上传后

解压到 `/opt/fortune-reminder`，确保下面文件在目录根部：

```bash
cd /opt/fortune-reminder
ls -la
# 应看到 Dockerfile、docker-compose.yml、.env.example、app/ 等
```

## 6. 创建服务器专用 `.env`

```bash
cd /opt/fortune-reminder
cp .env.example .env
chmod 600 .env
nano .env
```

至少填写以下内容（示例值必须替换）：

```env
APP_TIMEZONE=Asia/Shanghai
APP_PORT=8088
APP_BIND_HOST=127.0.0.1
WEB_ACCESS_TOKEN=请换成随机长Token

MOCK_AI=false
OPENAI_API_KEY=你的中转站API_KEY
OPENAI_MODEL=中转站实际支持的模型
OPENAI_BASE_URL=https://你的中转站域名/v1

DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=你的token
DINGTALK_SECRET=SEC你的secret

BIRTH_CALENDAR=solar
BIRTH_DATE=YYYY-MM-DD
BIRTH_TIME=HH:mm
BIRTH_PLACE=城市名
BIRTH_GENDER=male

DAILY_PUSH_CRON=0 8 * * *
DATA_DIR=data
```

生成随机 Web Token：

```bash
openssl rand -hex 32
```

中转站注意事项：

- `OPENAI_BASE_URL` 填兼容 OpenAI API 的根地址，常见格式是 `https://域名/v1`；不要重复写 `/v1/v1`；
- `OPENAI_MODEL` 必须使用中转站实际支持的模型名称；
- `OPENAI_API_KEY` 只写 Key 本身，不要写 `Bearer ` 前缀；
- 如果中转站要求特殊路径或模型名，以中转站文档为准；
- `MOCK_AI=false` 才会真正请求 AI；只测试页面时可以临时改成 `true`。

权限加固：

```bash
chmod 600 /opt/fortune-reminder/.env
mkdir -p /opt/fortune-reminder/data
chmod 700 /opt/fortune-reminder/data
```

## 7. 启动与健康检查

```bash
cd /opt/fortune-reminder
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 fortune-reminder
curl http://127.0.0.1:8088/health
```

健康检查预期包含：

```json
{"status":"ok","timezone":"Asia/Shanghai","scheduler_running":true}
```

如果使用了其他端口，请把命令中的 `8088` 替换为实际 `APP_PORT`。

## 8. 功能测试

### 页面

有 Nginx 时访问：

```text
https://fortune.example.com/fortune?token=你的WEB_ACCESS_TOKEN
```

没有 Nginx、仅临时直连时：

```text
http://<服务器公网IP>:8088/fortune?token=你的WEB_ACCESS_TOKEN
```

### 错误 Token 应返回 401

```bash
curl -i "http://127.0.0.1:8088/fortune?token=错误Token"
```

### 测试问答

```bash
curl -X POST http://127.0.0.1:8088/api/ask \
  -H "Authorization: Bearer 你的WEB_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"我今天适合推进重要合作吗？"}'
```

### 只生成预览，不发送钉钉

```bash
curl -X POST http://127.0.0.1:8088/api/generate-preview \
  -H "Authorization: Bearer 你的WEB_ACCESS_TOKEN"
```

### 手动发送一次钉钉

确认配置无误后再执行，因为会真实发送群消息：

```bash
curl -X POST http://127.0.0.1:8088/api/push-now \
  -H "Authorization: Bearer 你的WEB_ACCESS_TOKEN"
```

排查日志：

```bash
docker compose logs -f fortune-reminder
```

## 9. Nginx + HTTPS（推荐）

如果服务器已有 Nginx，先查看配置，不能覆盖英语学习 App：

```bash
ls -la /etc/nginx/sites-enabled
nginx -T
```

推荐用独立子域名 `fortune.example.com`。新增一个站点配置，例如：

```nginx
server {
    listen 80;
    server_name fortune.example.com;

    location / {
        proxy_pass http://127.0.0.1:8088;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

然后：

```bash
ln -s /etc/nginx/sites-available/fortune-reminder /etc/nginx/sites-enabled/fortune-reminder
nginx -t
systemctl reload nginx
apt install -y certbot python3-certbot-nginx
certbot --nginx -d fortune.example.com
```

证书申请前，确保域名 DNS 已指向服务器公网 IP，且阿里云安全组放行 TCP 80/443。

如果只能挂在已有域名的 `/fortune` 路径下，需要同时正确代理页面、`/api/` 和相关资源；独立子域名更不容易与英语学习 App 的路径冲突。

## 10. 阿里云安全组

推荐长期只开放：

- TCP 22（最好限制为自己的固定 IP）；
- TCP 80；
- TCP 443。

若没有 Nginx，才临时放行 TCP 8088，验证完成后关闭。Docker 暴露端口可能绕过部分 UFW 规则，生产环境应优先使用 `APP_BIND_HOST=127.0.0.1` + Nginx，并在阿里云安全组控制公网入口。

## 11. 更新、重启、备份

更新代码：

```bash
cd /opt/fortune-reminder
git pull
docker compose up -d --build
docker compose logs --tail=100 fortune-reminder
```

重启和状态：

```bash
docker compose restart
docker compose ps
docker compose logs -f fortune-reminder
```

备份最近运势数据和配置（配置文件不要上传到公开位置）：

```bash
tar -czf /root/fortune-reminder-backup-$(date +%F).tar.gz .env data
chmod 600 /root/fortune-reminder-backup-*.tar.gz
```

## 12. 常见错误

### 401 invalid_api_key

检查 `OPENAI_API_KEY` 是否是中转站的 Key、是否误加了 `Bearer`、`OPENAI_BASE_URL` 是否正确、模型是否为中转站支持的模型。修改 `.env` 后需要重建/重启容器：

```bash
docker compose up -d --build
```

### Your request was blocked

通常是中转站的风控、模型权限、内容策略或请求格式被拦截。查看完整容器日志，先用 `/api/generate-preview` 测试，并确认模型和 Base URL 与中转站文档一致；不要在前端暴露 Key。

### 页面显示旧的最近运势

最近一次运势来自服务器挂载的 `data/` 目录，不是前端固定内容。不要把本地 `data/` 上传到服务器；首次部署后先执行 `generate-preview` 生成属于当前 `.env` 八字的新数据。

## 13. 部署完成验收清单

- [ ] 英语学习 App 容器和端口未改变；
- [ ] `docker compose ps` 显示 `fortune-reminder` running/healthy；
- [ ] `/health` 返回 `status=ok`；
- [ ] 错误 Token 为 401；
- [ ] 正确 Token 可以打开页面；
- [ ] `/api/ask` 能正常回答；
- [ ] `/api/generate-preview` 生成了当前用户的新运势；
- [ ] `/api/push-now` 收到钉钉消息；
- [ ] 北京时间 08:00 自动任务已启动；
- [ ] 生产环境关闭公网 8088，仅开放 22/80/443；
- [ ] `.env` 权限为 600，真实密钥没有进入 Git。
