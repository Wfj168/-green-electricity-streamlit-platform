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
- `src/application/green_direct_service.py`：统一快速调度绿电缺口成本计算和V17绿电直连指标读取，页面不再承载成本公式。
- `src/core`：定义稳定的输入结构、错误码和表格校验规则，不依赖Streamlit。
- `src/core/integrated_config.py`：定义V17页面配置结构、跨字段依赖校验、版本化载荷和SHA-256参数指纹。
- `src/core/timeseries_contract.py`：定义15分钟必填列、单位、时间间隔和逐行数据质量问题结构。
- `src/application/forecast_service.py`：执行季节朴素与近期均值基准评估，记录训练/验证区间并生成版本化日前96点预测。
- `src/application/intraday_service.py`：生成继承预测版本和最新电/热储能SOC的15分钟日内滚动请求。
- `src/storemore_engine.py`：执行源荷生成、容量规划、滚动线性优化、指标计算和结果打包。
- `src/persistence`：管理数据库迁移，以及项目、场景、数据集、模型任务、结果和审计记录。
- `src/model_adapter.py`：适配V17 S0—S8/R0—R4综合能源模型。
- `src/api`：提供模型目录、项目、场景、任务和结果接口；API不直接执行耗时求解。
- `src/jobs`：领取数据库任务，通过统一模型服务执行并原子写入成果包。

## 已建立的兼容边界

- `StoreMoreInputs`从核心领域模块导出，旧代码仍可通过`src.storemore_engine.StoreMoreInputs`访问。
- 应用服务失败结果包含稳定的`error.code`、`error.message`和`error.issues`。
- 成功结果包含`platform_version`和`model_version`，导出包的`input_summary.csv`也记录版本。
- 任务请求使用`realtime_dispatch`或`integrated_planning`模型类型；旧任务未带类型时继续按快速调度执行。
- 两类后台任务都持久化统一`summary`、`metrics`和ZIP成果包，包内包含`execution.json`执行清单。
- 前台模型模式只改变导航和页面数据源，不修改求解器；V17页面提交`integrated-planning-v1`结构，快速调度继续使用`StoreMoreInputs`。
- 模型重构不得绕过`tests/golden`中的黄金基线。

## 下一阶段

当前API与Worker使用数据库队列，适合本地开发、自动测试和单机试运行。容器化阶段将增加PostgreSQL和Redis适配、Worker并发控制与任务租约，保持API数据结构不变。
