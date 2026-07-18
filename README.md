# 园区低碳规划与绿电直连优化平台

当前版本：`0.6.0`（正在`upgrade/v0.7.0-productization`分支进行项目化升级）

这是一个可部署到 Streamlit Cloud 的园区综合能源系统优化平台。平台不是静态结果展示页，而是围绕“参数输入、滚动优化、实时图表、指标校核、绿电直连决策、结果导出”形成闭环。

## 功能

- 设备容量、储能参数、燃料价格、投资成本、源荷时序和约束参数可编辑。
- 支持上传 CSV 时序数据；未上传时自动生成可复现的负荷、风光出力和电价曲线。
- 调用线性规划模型进行 48 小时滚动调度，每次保存前 24 小时结果，并保持储能 SOC 连续。
- 实时生成电力平衡、储能 SOC、购售电响应、供需校核、滚动目标函数和关键指标图。
- 支持 RPS 绿电占比约束、CO2 排放约束、CEEP 弃电率约束。
- 基于当前调度结果折算年绿电缺口，比较园区内新增绿电、虚拟电厂聚合绿电、绿电基地直连三类方案成本。
- 可导出本次计算的输入、时序、调度、投资、指标、滚动日志和图表结果包。
- 后台任务支持`realtime_dispatch`快速滚动调度和`integrated_planning` V17综合能源规划两类模型，并统一保存版本、指标和ZIP成果包。
- 前台侧栏支持双模型模式切换；V17配置覆盖设备、储能、柔性负荷、碳约束、绿电直连和P2X/绿氢，并为每次配置生成参数指纹。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

本地启动API和单次任务Worker：

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
python worker.py --once
```

设置`PLATFORM_API_URL`后，Streamlit中的“项目与任务”页面会启用项目创建、场景版本、后台任务和历史结果功能。未配置时平台自动保留原有单用户实时计算模式。

启动前可先执行`python scripts/deployment_preflight.py --profile all`检查运行环境、地址、认证配置和数据目录。生产部署使用`--require-api --check-api`进行严格检查。

单机Docker试点部署、令牌认证、备份和恢复见[部署说明](deploy/README.md)。

## 开发验证

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

当前基线、黄金场景和已知工程缺口见[项目级升级基线报告](docs/baseline_report.md)。所有模型重构必须先通过默认72小时实时场景和V17 S0/S4/S8回归测试。

模型层、应用服务层和Streamlit界面的职责划分见[系统架构说明](docs/architecture.md)。

## Streamlit Cloud 部署

1. 将项目推送到 GitHub。
2. 在 Streamlit Cloud 新建应用并选择该仓库。
3. Branch 选择 `main`。
4. Main file path 填写 `app.py`。
5. Python 版本使用 `runtime.txt` 中的 `python-3.11`。

Community Cloud默认只部署前台，未配置独立API时“项目与任务”会显示“单机演示模式”，其余实时计算与结果页面仍然可用。完整前后台部署、Secrets配置和部署前检查见[部署说明](deploy/README.md)。

## 模型边界

当前版本定位为园区综合能源系统线性规划与调度决策平台，可用于方案筛选、低碳指标评估和绿电直连成本测算。它不替代真实配电网潮流、继电保护、接入审查或详细工程设计。
