# 系统架构说明

## 当前分层

```text
Streamlit UI (app.py)
        |
        v
Application Service (src/application)
        |
        +--> Input schemas and validation (src/core)
        +--> Persistence repository (src/persistence)
        |
        v
Realtime LP engine (src/storemore_engine.py)
        |
        +--> SciPy HiGHS
        +--> CSV/DataFrame results
        +--> ZIP artifacts

V17 adapter (src/model_adapter.py)
        |
        v
V17 county-region integrated energy model (src/model)
```

## 分层职责

- `app.py`：只负责用户交互、页面状态和结果展示，不定义优化规则。
- `src/application`：编排一次优化请求，将界面输入交给校验与模型层，并返回结构化成功或失败结果。
- `src/core`：定义稳定的输入结构、错误码和表格校验规则，不依赖Streamlit。
- `src/storemore_engine.py`：执行源荷生成、容量规划、滚动线性优化、指标计算和结果打包。
- `src/persistence`：管理数据库迁移，以及项目、场景、数据集、模型任务、结果和审计记录。
- `src/model_adapter.py`：适配V17 S0—S8/R0—R4综合能源模型。

## 已建立的兼容边界

- `StoreMoreInputs`从核心领域模块导出，旧代码仍可通过`src.storemore_engine.StoreMoreInputs`访问。
- 应用服务失败结果包含稳定的`error.code`、`error.message`和`error.issues`。
- 成功结果包含`platform_version`和`model_version`，导出包的`input_summary.csv`也记录版本。
- 模型重构不得绕过`tests/golden`中的黄金基线。

## 下一阶段

阶段3将在当前仓储层之上建立FastAPI和后台任务执行器。SQLite用于本地与自动测试；生产环境的PostgreSQL适配将在容器化阶段加入，不改变上层业务对象。
