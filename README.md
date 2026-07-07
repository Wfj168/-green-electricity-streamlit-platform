# 园区低碳规划与绿电直连优化平台

这是一个面向园区综合能源系统的 Streamlit 工程项目。平台同时提供正式模型结果展示和在线仿真优化能力，可部署到 Streamlit Cloud。

## 功能

- 园区多能流规划与运行结果展示。
- 设备参数、低碳机制、源荷预测和调度流程配置。
- StoreMore 风格仿真优化：RPS、CO2、CEEP 约束，容量规划，48 小时滚动调度。
- CSV 输入数据上传与模板下载。
- 发电技术、储能技术、年化投资成本和燃料成本可编辑。
- 调度结果图、综合指标、案例对比和绿电直连成本测算。
- 仿真结果 ZIP 下载，包含输入数据、调度结果、投资结果、关键指标、滚动日志和 PNG 图。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 部署

1. 将项目推送到 GitHub。
2. 在 Streamlit Cloud 中选择该仓库。
3. Branch 选择 `main`。
4. Main file path 填写 `app.py`。
5. Python 版本使用 `runtime.txt` 中的 `python-3.11`。

## 数据与模型说明

平台内置 `data/results` 中的正式结果 CSV 和 `assets/figures` 中的结果图。模型用于规划优化、运行调度、碳管理路径分析和绿电直连方案比较。它不是实际 10kV 配电网潮流模型，也不是详细氢气管网模型。
