# 园区低碳规划与绿电直连优化平台

这是一个基于 V17.3.9 县域/园区综合能源模型封装的 Streamlit 演示平台，可部署到 Streamlit Cloud，也可在本地运行。

## 功能

- 平台概述与论文结果图展示
- 园区设备、降碳技术、低碳机制和源荷预测数据配置
- 调度结果图：电、热、气、氢、碳多维图表
- 调度综合指标：经济效益、环境效益、绿电和绿氢指标
- 常见案例对比
- 绿电直连补充方式成本测算
- 低分辨率快速试算，云端资源不足时回退到正式结果

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud 部署

1. 将本项目推送到 GitHub。
2. 在 Streamlit Cloud 中选择该仓库。
3. Main file path 填写 `app.py`。
4. Python 版本使用 `runtime.txt` 中的 `python-3.11`。

## 数据与模型说明

平台内置 `data/results` 中的正式结果 CSV 和 `assets/figures` 中的 19 张论文结果图。

模型是县域/园区综合能源系统线性规划与调度模型，用于规划优化、运行调度、碳管理路径分析和政策机制比较。它不是真实 10kV 配电网潮流模型，也不是详细氢气管网模型。
