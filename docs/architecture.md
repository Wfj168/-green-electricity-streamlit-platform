# 系统架构说明

## 当前分层

```text
Streamlit UI (app.py)
        |
        v
Application Service (src/application)
        |
        +--> UnifiedModelService + model catalog
        |           |
        |           +--> realtime_dispatch
        |           +--> integrated_planning
        |
        +--> Input schemas and validation (src/core)
        +--> Persistence repository (src/persistence)
                    |
          +---------+---------+
          |                   |
          v                   v
Realtime LP engine       V17 adapter/model
(src/storemore_engine)   (src/model_adapter + src/model)
          |                   |
          +---------+---------+
                    |
                    v
       Unified result summary + ZIP artifact

FastAPI (api.py)
        |
        +--> Persistence repository
        +--> Database job queue
                    |
                    v
              Worker (worker.py)
                    |
                    +--> UnifiedModelService
                    +--> Local artifact store
```

## 分层职责

- `app.py`：只负责用户交互、页面状态和结果展示，不定义优化规则。
- `src/application`：维护模型目录，按`model_kind`路由快速调度或V17综合能源规划，并返回统一成功/失败结果、元数据、摘要、指标和成果包。
- `src/application/scenario_comparison_service.py`：逐一调用统一模型服务生成S0—S8真实对比、减排成本和包含各场景原始ZIP的对比成果包。
- `src/application/carbon_analysis_service.py`：从逐时购电和燃气消耗重建运营期碳台账，对账排放来源、基准、目标、减排和平均减排成本。
- `src/application/model_audit_service.py`：检查人民币价格与造价、典型日权重、能量平衡、成本、排放、可靠性、利用率和容量边界。
- `src/application/green_direct_service.py`：统一快速调度绿电缺口成本计算和V17绿电直连指标读取，页面不再承载成本公式。
- `src/core`：定义稳定的输入结构、错误码和表格校验规则，不依赖Streamlit。
- `src/core/integrated_config.py`：定义V17页面配置结构、跨字段依赖校验、版本化载荷和SHA-256参数指纹。
- `src/core/timeseries_contract.py`：定义15分钟必填列、单位、时间间隔和逐行数据质量问题结构。
- `src/application/forecast_service.py`：执行季节朴素与近期均值基准评估，记录训练/验证区间并生成版本化日前96点预测。
- `src/application/intraday_service.py`：生成继承预测版本和最新电、热储能状态的15分钟日内滚动请求。
- `src/storemore_engine.py`：执行源荷生成、容量规划、滚动线性优化、指标计算和结果打包。
- `src/persistence`：管理数据库迁移，以及项目、场景、数据集、模型任务、结果和审计记录。
- `src/model_adapter.py`：适配V17 S0—S8/R0—R4综合能源模型。
- `src/presentation.py`：把V17原始技术、指标、单位和表格映射为中文交付口径，同时保留原始工程数据。
- `src/api`：提供模型目录、项目、场景、任务和结果接口；API不直接执行耗时求解。
- `src/jobs`：领取数据库任务，通过统一模型服务执行并原子写入成果包。
- `src/observability`：输出API与Worker单行JSON日志，并关联请求、任务和错误标识。
- `src/operations`：创建、校验和恢复数据库与成果备份，覆盖恢复前自动生成回滚包。

## 已建立的兼容边界

- `StoreMoreInputs`从核心领域模块导出，旧代码仍可通过`src.storemore_engine.StoreMoreInputs`访问。
- 应用服务失败结果包含稳定的`error.code`、`error.message`和`error.issues`。
- 成功结果包含`platform_version`和`model_version`，导出包的`input_summary.csv`也记录版本。
- 任务请求使用`realtime_dispatch`或`integrated_planning`模型类型；旧任务未带类型时继续按快速调度执行。
- 两类后台任务都持久化统一`summary`、`metrics`和ZIP成果包，包内包含`execution.json`执行清单。
- 前台模型模式只改变导航和页面数据源，不修改求解器；V17页面提交版本化综合规划结构，快速调度继续使用`StoreMoreInputs`。
- V17业务导航为“平台概览、参数配置与运行、运行分析、场景与决策”；“项目中心”仅在后台地址有效时出现。架构文档不是业务页面，成果下载位于分析和场景页面。
- 非S0碳约束场景先以相同分辨率和随机种子计算S0，再按相对比例及碳配额形成年度上限。
- 模型重构不得绕过`tests/golden`中的黄金基线。

## 当前生产工程边界

当前API与Worker使用SQLite/WAL数据库队列，已经实现原子领取、项目级幂等键、Worker租约、心跳、超时恢复、最大重试和结果所有权保护，适合单服务器受控试点与项目交付。API提供就绪探针、任务状态指标、请求编号和管理员审计；备份恢复提供SHA-256与SQLite完整性校验。

跨主机高可用仍需后续接入PostgreSQL、Redis或专业任务队列、S3兼容对象存储、企业SSO和集中监控。适配时应保持现有应用服务、仓储和成果存储接口不变。
