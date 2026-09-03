# 融合版 V2 认证与运维配置

## 生产认证

1. 生成不少于 32 位的 `PLATFORM_AUTH_SECRET`，不得提交到 Git。
2. 运行 `python scripts/generate_password_hash.py` 为每个账号生成 PBKDF2-SHA256 密码哈希。
3. 将账号数组写入部署环境的 `PLATFORM_USERS_JSON`，字段为 `username`、`display_name`、`role`、`password_hash` 和 `active`。
4. 将后端 `PLATFORM_AUTH_MODE` 设置为 `token`，前端构建变量 `VITE_AUTH_REQUIRED` 设置为 `true`。
5. 只在受控运维流程中保留 `PLATFORM_BOOTSTRAP_KEY`；普通用户使用账号密码登录，不接触启动密钥。
6. 生产入口必须启用 HTTPS，并将 `PLATFORM_CORS_ORIGINS` 限定为实际前端域名。

支持的角色为系统管理员、规划与调度工程师、运行值班员、只读用户和审计用户。服务端对写操作、审计查询和系统状态实施角色校验；前端同时隐藏无权菜单并禁用无权导出，但权限最终以服务端判定为准。

## 任务与监控

- `/health`：进程与数据库存活检查。
- `/ready`：流量接入前的就绪检查。
- `/metrics`：优化任务状态指标。
- 优化任务持久化保存，支持幂等键、状态机、进度、工作进程租约、心跳、失败重试和过期任务恢复。
- 首次运行收益和压力模型耗时较长，应由独立工作进程执行，不应在多副本 Web 进程内重复计算。

## 备份与恢复

- 创建并校验备份：`python scripts/backup_platform.py`
- 只校验指定备份：`python scripts/backup_platform.py --verify <备份文件>`
- 恢复演练：`python scripts/restore_platform.py <备份文件> --target-dir <演练目录> --force`

备份格式包含数据库一致性检查、文件 SHA-256 清单和结果文件；强制恢复前自动创建回滚备份。生产 PostgreSQL 还应配置平台外部的定时全量备份、连续归档和异地副本。

## 生产启用前检查

- 禁止使用 `PLATFORM_AUTH_MODE=disabled`。
- 禁止设置明文账号密码或把密钥写入镜像。
- 验证管理员、工程师、值班员、只读和审计五类角色的最小权限。
- 执行备份恢复演练并记录恢复点目标与恢复时间目标。
- 检查数据库、工作进程、磁盘、证书、错误率、任务积压和备份新鲜度告警。
