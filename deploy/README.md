# 单节点交付部署

本部署形态由UI、API、Worker和持久化数据卷组成，适合演示、受控内网试点和单节点项目交付。SQLite使用WAL模式；后台任务使用原子领取、Worker租约、心跳、超时恢复和幂等键避免重复提交。

该形态不是跨主机高可用集群。需要多节点容灾时，应将持久化接口替换为PostgreSQL、Redis队列和对象存储，并接入企业SSO与集中监控；当前版本没有把这些外部组件标记为已实现。

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
4. 访问`http://服务器地址:8501`。
5. 检查`http://服务器地址:8000/health`和`http://服务器地址:8000/ready`均返回正常状态。
6. 将`http://服务器地址:8000/metrics`接入Prometheus兼容采集器，或限制为仅运维网段访问。

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

创建备份会使用SQLite在线备份接口，并为数据库与成果文件生成SHA-256校验清单：

```bash
python scripts/backup_platform.py
python scripts/backup_platform.py --verify var/backups/platform-backup-YYYYMMDDTHHMMSSZ.zip
```

恢复必须进入维护窗口并停止API与Worker：

```bash
python scripts/restore_platform.py var/backups/platform-backup-YYYYMMDDTHHMMSSZ.zip --verify-only
python scripts/restore_platform.py var/backups/platform-backup-YYYYMMDDTHHMMSSZ.zip --force
```

`--force`覆盖现有数据库前会自动在`var/backups/pre-restore`生成回滚备份。恢复完成后重新启动服务，依次检查`/ready`、项目列表、任务历史和一个已完成成果文件。至少每季度执行一次隔离目录恢复演练，不能只检查备份文件是否存在。

## 任务可靠性与审计

- `PLATFORM_WORKER_ID`在同一环境内必须唯一。
- `PLATFORM_JOB_LEASE_SECONDS`应长于正常任务心跳间隔；默认3600秒，Worker每不超过30秒续租一次。
- 客户端重试创建任务时应复用同一个`idempotency_key`，避免网络重试生成重复任务。
- 超时任务会在未达到`max_attempts`时重新排队，达到上限后以`WORKER_LEASE_EXPIRED`失败并等待人工检查。
- 管理员可通过`GET /api/v1/audit`查看项目、场景和任务审计记录；普通角色不能读取全局审计日志。
- API与Worker输出单行JSON日志。发布后应按`event`、`request_id`、`job_id`和`error_code`建立检索与告警规则。

## 发布与回滚检查

1. 备份当前数据库与成果目录并完成校验。
2. 记录当前镜像标签和Git提交号。
3. 运行部署前检查与完整自动测试。
4. 构建新镜像，启动API后先检查`/ready`，再启动Worker和UI。
5. 提交一次小型测试任务，确认只执行一次、成果可下载、审计记录存在。
6. 若失败，停止服务，恢复旧镜像；仅当数据库变更不可向后兼容时使用发布前备份回滚数据。
