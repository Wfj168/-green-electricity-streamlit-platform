# 单机试点部署

## 部署前检查

每次发布或修改环境变量后，先执行：

```bash
python scripts/deployment_preflight.py --profile all
```

生产环境还应要求后台地址存在并实际验证健康状态：

```bash
python scripts/deployment_preflight.py --profile all --require-api --check-api
```

只有全部`FAIL`项清零后才进入启动步骤。`WARN`表示允许继续，但需要确认当前确实是演示或受控内网环境。

## 开发/内网试运行

1. 复制`.env.example`为`.env`。
2. 保持`PLATFORM_AUTH_MODE=disabled`，仅限本机或受控内网。
3. 执行`docker compose up -d --build`。
4. 访问`http://服务器地址:8501`，API健康检查为`http://服务器地址:8000/health`。

## Streamlit Community Cloud演示

Community Cloud只启动`app.py`，因此默认是单机演示模式：实时计算、图表、指标和导出可用，项目版本、后台任务和历史结果暂不启用。这是正确的降级状态，不应把`127.0.0.1:8000`配置为云端后台地址。

如果已有独立部署且可通过HTTPS访问的API，可在应用Secrets中配置根级键：

```toml
PLATFORM_API_URL = "https://api.example.com"
PLATFORM_USER_ID = "demo-user"
PLATFORM_ACCESS_TOKEN = "replace-with-short-lived-token"
PLATFORM_AUTH_MODE = "token"
```

不得把签名密钥、启动密钥或长期令牌提交到Git仓库。

## 令牌认证模式

1. 生成长度不少于32字符的`PLATFORM_AUTH_SECRET`和不少于16字符的`PLATFORM_BOOTSTRAP_KEY`。
2. 使用`compose.production.yaml`启动。
3. 调用`POST /api/v1/auth/token`换取管理员、工程师或只读用户令牌。
4. 将前端试点账户的短期令牌写入`PLATFORM_ACCESS_TOKEN`后重启UI。

令牌模式适合受控试点，不替代企业SSO、身份生命周期、MFA或集中权限平台。正式客户交付前应接入客户现有身份系统。

## 备份与恢复

容器停止或进入维护窗口后执行：

```bash
python scripts/backup_platform.py
python scripts/restore_platform.py var/backups/platform-backup-YYYYMMDDTHHMMSSZ.zip --force
```

恢复前必须停止API和Worker，并保留当前数据目录的额外副本。
