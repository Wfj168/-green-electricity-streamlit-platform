from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from src.application.model_service import list_model_specs
from src.persistence import PlatformRepository
from src.security import AuthService, Principal
from src.version import PLATFORM_VERSION


ROLE_DEFINITIONS = [
    {"role": "admin", "name": "系统管理员", "permissions": "全部配置、任务、数据与审计权限"},
    {"role": "engineer", "name": "规划与调度工程师", "permissions": "模型运行、数据维护、报告导出"},
    {"role": "operator", "name": "运行值班员", "permissions": "运行查看、指令操作、告警处置"},
    {"role": "viewer", "name": "只读用户", "permissions": "授权园区与业务数据只读"},
    {"role": "auditor", "name": "审计用户", "permissions": "审计日志与报告只读"},
]


class SystemStatusService:
    """汇总可公开给已认证用户的系统运行状态，不返回密码或连接密钥。"""

    def __init__(self, repository: PlatformRepository, auth: AuthService) -> None:
        self.repository = repository
        self.auth = auth

    def snapshot(self, principal: Principal) -> dict[str, Any]:
        database_path = self.repository.database.path
        jobs = self.repository.list_jobs()
        visible_jobs = jobs if principal.role == "admin" else [item for item in jobs if item["created_by"] == principal.user_id]
        audits = self.repository.list_audit_logs(limit=50)
        visible_audits = audits if principal.role in {"admin", "auditor"} else [item for item in audits if item["actor_id"] == principal.user_id]
        backup_dir = Path(os.getenv("PLATFORM_BACKUP_DIR", "var/backups"))
        backup_files = sorted(backup_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True) if backup_dir.exists() else []
        last_backup = backup_files[0] if backup_files else None
        status_counts = self.repository.job_status_counts()
        postgres_configured = bool(os.getenv("V2_DATABASE_URL", "").strip())
        database_size = database_path.stat().st_size if database_path.exists() else 0
        now = datetime.now(timezone.utc).isoformat()

        return {
            "meta": {
                "dataStatus": "系统实时状态",
                "sourceReference": "应用进程、任务数据库与部署环境",
                "modelVersion": "本页不使用计算模型",
                "parameterVersion": "不适用",
                "currency": "CNY",
                "asOf": now,
            },
            "currentUser": {"userId": principal.user_id, "role": principal.role},
            "auth": {
                "mode": self.auth.mode,
                "modeName": "令牌认证" if self.auth.mode == "token" else "公开演示/本地开发",
                "tokenTtlSeconds": self.auth.token_ttl_seconds,
                "configuredAccountCount": len(self.auth.accounts),
            },
            "accounts": self.auth.safe_accounts() if principal.role == "admin" else [
                item for item in self.auth.safe_accounts() if item["username"] == principal.user_id
            ],
            "roles": ROLE_DEFINITIONS,
            "organizations": [
                {"organization": "项目实施组织（待配置）", "park": "零碳农业示范园区", "parkStatus": "演示基准", "dataDomain": "能源、农业任务、碳与绿电"}
            ],
            "models": list_model_specs(),
            "interfaces": [
                {"name": "健康检查", "path": "/health", "method": "读取", "status": "在线"},
                {"name": "就绪检查", "path": "/ready", "method": "读取", "status": "在线"},
                {"name": "运行指标", "path": "/metrics", "method": "读取", "status": "在线"},
                {"name": "融合版总览", "path": "/api/v2/overview", "method": "读取", "status": "在线"},
                {"name": "融合版策略", "path": "/api/v2/strategies", "method": "读取", "status": "在线"},
                {"name": "绿电收益", "path": "/api/v2/green-direct-benefits", "method": "读取", "status": "在线"},
                {"name": "优化任务", "path": "/api/v1/jobs", "method": "读写", "status": "在线"},
            ],
            "alertRules": [
                {"rule": "母线平衡误差", "threshold": "大于0.0000001兆瓦", "severity": "严重", "status": "启用"},
                {"rule": "数据超过采集周期未更新", "threshold": "连续2个采集周期", "severity": "警告", "status": "待接入测点"},
                {"rule": "优化任务租约过期", "threshold": "超过任务租约时间", "severity": "严重", "status": "启用"},
                {"rule": "生产任务能量不闭合", "threshold": "误差大于0.0000001兆瓦时", "severity": "严重", "status": "启用"},
            ],
            "units": [
                {"quantity": "有功功率", "unit": "兆瓦", "symbol": "MW"},
                {"quantity": "电量", "unit": "兆瓦时", "symbol": "MWh"},
                {"quantity": "金额", "unit": "人民币元", "symbol": "CNY"},
                {"quantity": "碳排放", "unit": "吨二氧化碳当量", "symbol": "tCO₂e"},
                {"quantity": "比例", "unit": "百分比", "symbol": "%"},
            ],
            "jobStatusCounts": status_counts,
            "jobs": visible_jobs[:30],
            "auditEvents": visible_audits,
            "components": [
                {"component": "应用接口", "status": "在线", "detail": f"平台版本 {PLATFORM_VERSION}"},
                {"component": "现有任务数据库", "status": "在线", "detail": f"SQLite，{database_size / 1024:.1f} KiB"},
                {"component": "融合版项目数据库", "status": "已配置" if postgres_configured else "待部署配置", "detail": "PostgreSQL连接信息已提供" if postgres_configured else "已交付表结构，尚未设置V2_DATABASE_URL"},
                {"component": "任务执行器", "status": "可用", "detail": f"工作进程 {os.getenv('PLATFORM_WORKER_ID', 'worker-1')}，租约 {os.getenv('PLATFORM_JOB_LEASE_SECONDS', '3600')} 秒"},
                {"component": "备份与恢复", "status": "已有备份" if last_backup else "尚未执行", "detail": last_backup.name if last_backup else "使用scripts/backup_platform.py创建校验备份"},
            ],
            "backup": {
                "format": "平台备份格式v2",
                "backupCount": len(backup_files),
                "lastBackup": last_backup.name if last_backup else None,
                "lastBackupAt": datetime.fromtimestamp(last_backup.stat().st_mtime, timezone.utc).isoformat() if last_backup else None,
                "verification": "每个归档包含SHA-256校验清单与SQLite完整性检查",
                "restoreProtection": "默认拒绝覆盖；强制恢复前自动建立回滚备份",
            },
        }
