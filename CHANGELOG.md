# Changelog

## 0.2.0

- 新增领域输入、结构化校验错误和应用服务层。
- Streamlit通过`SimulationService`调用模型，不再直接编排求解器。
- 修复`restrict_investments`开关未参与容量规划的问题。
- 成功结果和导出输入摘要新增平台版本、模型版本。
- 增加全页面Streamlit烟测、输入校验和投资限制测试。
- Matplotlib固定使用无桌面服务器兼容的`Agg`后端。

## 0.1.0

- 冻结`d68e955`为项目级升级基线。
- 增加实时72小时场景和V17 S0/S4/S8黄金回归测试。
- 增加GitHub Actions编译、静态检查和自动测试质量门。
