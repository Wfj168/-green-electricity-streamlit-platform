# 园区低碳规划与绿电直连优化平台

这是一个基于 V17.3.9 县域/园区综合能源模型封装的 Streamlit 演示平台，可部署到 Streamlit Cloud，也可在本地运行。

## 本次增强

- 修复页面中文乱码，统一图表标签和指标卡文字。
- 新增“算法与界面对应关系”页面，整理平台嵌入算法、对应界面、输入输出和代码位置。
- 融合 StoreMore 模型说明与用户手册内容，包括 RPS、CO2、CEEP、两阶段求解思想、储能技术、氢能参数、电价上传校验和模型状态流程。
- 新增“StoreMore融合与功能自检”页面，检查数据文件、关键字段、结果图、模型代码和快速试算回退机制。
- 保留原有页面：平台概述、系统构建、调度结果图、综合指标、案例对比、绿电直连和技术路线。

## 主要算法模块

- 县域/园区综合能源线性规划与混合整数优化。
- StoreMore-inspired perfect foresight + myopic 两阶段求解思想。
- RPS 可再生能源占比约束。
- CO2 年度排放约束与碳成本核算。
- CEEP/弃电约束与新能源消纳。
- 储能 SOC、等效循环和充放电诊断。
- 氢能/P2X 耦合筛选。
- 碳管理后处理与减排贡献分解。
- 绿电直连成本筛选。
- 典型日与源荷数据生成。

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

平台内置 `data/results` 中的正式结果 CSV 和 `assets/figures` 中的 19 张论文结果图。模型用于规划优化、运行调度、碳管理路径分析和政策机制比较。它不是实际 10kV 配电网潮流模型，也不是详细氢气管网模型。
