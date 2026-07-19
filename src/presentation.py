from __future__ import annotations

from typing import Any

import pandas as pd


UNIT_LABELS = {
    "CNY/year": "元/年",
    "million CNY/year": "百万元/年",
    "tCO2/day": "吨二氧化碳/日",
    "tCO2/year": "吨二氧化碳/年",
    "tCO2/MWh": "吨二氧化碳/兆瓦时",
    "MWh/year": "兆瓦时/年",
    "cycles/year": "次/年",
    "h/year": "小时/年",
    "MW/step": "兆瓦/时段",
    "index": "序号",
}


TECHNOLOGY_LABELS = {
    "PV": "光伏",
    "WT": "风电",
    "CHP": "燃气热电联产",
    "Heat pump": "热泵",
    "Electric chiller": "电制冷机",
    "Gas boiler": "燃气锅炉",
    "Battery energy": "电池储能容量",
    "Battery power": "电池充放功率",
    "Thermal storage energy": "蓄热容量",
    "Thermal storage power": "蓄热充放功率",
    "Electrolyzer": "电解槽",
}


COST_ITEM_LABELS = {
    "Annualized capital cost": "年化建设投资",
    "Fixed O&M cost": "固定运维成本",
    "Grid purchase cost": "电网购电成本",
    "Grid sale revenue": "上网售电收入",
    "Grid export wheeling cost": "外送过网成本",
    "Grid export capacity cost": "外送容量成本",
    "Gas purchase cost": "天然气采购成本",
    "Carbon external cost": "碳排放成本",
    "Demand response cost": "需求响应成本",
    "Renewable curtailment cost": "新能源弃电成本",
    "Unserved-energy cost": "未供能惩罚成本",
    "Storage degradation cost": "储能衰减成本",
    "P2X variable O&M cost": "电转其他能源可变运维成本",
    "Grid demand charge": "电网需量费用",
    "Grid fluctuation cost": "电网波动成本",
    "Device smoothing cost": "设备平滑运行成本",
    "Variable operating annual cost": "年度可变运行成本",
    "Private total annual cost": "项目年度总成本",
    "Social total annual cost": "社会年度总成本",
    "Objective annual cost": "优化目标年度成本",
}


CARBON_ITEM_LABELS = {
    "Daily average CO2 emissions": "日均二氧化碳排放",
    "Annual CO2 emissions": "年度二氧化碳排放",
    "CO2 cap": "二氧化碳排放上限",
    "CO2 cap slack": "二氧化碳排放剩余额度",
}


METRIC_LABELS = {
    "Annualized capital cost": "年化建设投资",
    "Fixed O&M cost": "固定运维成本",
    "Variable operating annual cost": "年度可变运行成本",
    "Private total annual cost": "项目年度总成本",
    "Carbon external cost": "碳排放成本",
    "Social total annual cost": "社会年度总成本",
    "Annual CO2 emissions": "年度二氧化碳排放",
    "Annual renewable available": "年度新能源可发电量",
    "Annual renewable used": "年度新能源利用量",
    "Renewable utilization rate (including export)": "新能源综合利用率（含外送）",
    "Renewable curtailment rate": "新能源弃电率",
    "Annual renewable curtailment": "年度新能源弃电量",
    "Annual renewable local absorption": "年度新能源本地消纳量",
    "Annual renewable export": "年度新能源外送量",
    "Renewable local consumption rate": "新能源本地消费率",
    "Renewable local absorption rate": "新能源本地消纳率",
    "Renewable export rate": "新能源外送率",
    "Renewable local share of electric-service demand": "电力服务需求本地绿电占比",
    "Grid import share of electric-service demand": "电力服务需求外购电占比",
    "Annual unmet load": "年度未满足综合负荷",
    "Annual electric unmet load": "年度未满足电负荷",
    "Annual heat unmet load": "年度未满足热负荷",
    "Annual cooling unmet load": "年度未满足冷负荷",
    "Electric service rate": "电力服务保障率",
    "Heat service rate": "供热服务保障率",
    "Cooling service rate": "供冷服务保障率",
    "Total multi-energy service rate": "多能综合服务保障率",
    "Unserved energy ratio": "未供能比例",
    "Expected shortage duration": "预计供能不足时长",
    "Annual grid import": "年度电网购电量",
    "Annual grid export": "年度上网电量",
    "Peak grid import": "最大购电功率",
    "Peak grid export": "最大上网功率",
    "Grid peak-valley difference": "电网交互峰谷差",
    "Grid weighted standard deviation": "电网交互波动标准差",
    "Maximum grid ramp": "电网交互最大爬坡",
    "Annual battery throughput": "电池年度吞吐量",
    "Battery equivalent cycles": "电池等效循环次数",
    "Annual thermal-storage throughput": "蓄热年度吞吐量",
    "Thermal-storage equivalent cycles": "蓄热等效循环次数",
    "Annual flexible-load shifting": "年度柔性负荷转移量",
    "Annual interruptible load": "年度可中断负荷量",
    "Battery simultaneous overlap": "电池同时充放电量",
    "Thermal-storage simultaneous overlap": "蓄热同时充放量",
    "Grid import-export overlap": "同时购售电量",
    "Flexible-load in-out overlap": "柔性负荷同时转入转出量",
    "Annual low-altitude economy electric load": "低空经济年度用电量",
    "Annual low-altitude critical electric load": "低空经济年度关键用电量",
    "Peak low-altitude economy electric load": "低空经济最大用电功率",
    "Peak low-altitude critical electric load": "低空经济关键负荷峰值",
    "Low-altitude economy share of electric load": "低空经济用电占比",
    "Battery autonomy for critical low-altitude load": "电池保障低空关键负荷时长",
    "Annual industrial-park electric load": "工业园区年度用电量",
    "Annual industrial-park process heat load": "工业园区年度工艺热负荷",
    "Peak industrial-park electric load": "工业园区最大用电功率",
    "Industrial-park share of electric load": "工业园区用电占比",
    "Industrial-park local renewable coverage": "工业园区本地绿电覆盖率",
    "System carbon intensity per electric-service demand": "单位电力服务碳排放强度",
    "System carbon intensity per multi-energy demand": "单位综合能源服务碳排放强度",
    "Carbon allowance gap": "碳配额缺口",
    "Green-direct target electricity": "绿电直连目标电量",
    "Park-internal green-direct cost": "园区内绿电直连年度成本",
    "VPP aggregated green-direct cost": "虚拟电厂聚合绿电年度成本",
    "Remote green-base direct cost": "远端绿电基地直连年度成本",
    "Best green-direct mode index": "最优绿电直连方案序号",
    "Best green-direct annual cost": "最优绿电直连年度成本",
    "Green-direct saving vs worst option": "最优方案相对最高成本方案节省率",
    "Endogenous P2X electricity consumption": "电转其他能源年度用电量",
    "Endogenous H2 heat supply": "绿氢年度供热量",
    "Endogenous green hydrogen production": "年度绿氢产量",
    "Endogenous P2X heat substitution share": "绿氢替代工艺热比例",
    "Endogenous P2X CO2 avoidance": "电转其他能源年度减排量",
    "Electrolyzer capacity": "电解槽规划容量",
    "Electrolyzer full-load hours": "电解槽年利用小时数",
    "P2X candidate green electricity": "可用于电转其他能源的绿电量",
    "Green hydrogen production potential": "绿氢生产潜力",
    "Industrial process heat substitution by H2": "绿氢替代工业工艺热量",
    "CO2 reduction potential from P2X": "电转其他能源减排潜力",
    "Post-P2X residual CO2": "实施电转其他能源后的剩余碳排放",
    "Carbon allowance gap after P2X": "实施电转其他能源后的碳配额缺口",
    "P2X screening annual cost": "电转其他能源筛选年度成本",
}


DIAGNOSTIC_LABELS = {
    "Maximum electric balance error": "最大电力平衡误差",
    "Maximum heat balance error": "最大热力平衡误差",
    "Maximum cooling balance error": "最大冷量平衡误差",
    "Number of capacity upper bounds >=95%": "容量达到上限95%以上的设备数",
    "Strict storage exclusivity enabled": "是否启用储能严格充放互斥",
    "MILP used": "是否使用混合整数规划",
    "Carbon cap binding": "碳排放上限是否起约束作用",
    "Annual export share of renewable available [%]": "新能源可发电量年度外送占比",
    "Storage rule-constrained mode": "是否使用储能规则约束模式",
    "Grid import-export overlap [MWh/year]": "年度同时购售电量",
    "Flexible-load in-out overlap [MWh/year]": "年度柔性负荷同时转入转出量",
    "Renewable export attribution enforced": "是否强制新能源外送归因",
    "Unmet load hard-fixed to zero": "是否强制未满足负荷为零",
    "Annual EENS limit enabled": "是否启用年度缺供能上限",
    "Critical-load protection enabled": "是否启用关键负荷保障",
    "Minimum local renewable share target [%]": "本地绿电最低占比目标",
    "Minimum renewable utilization target [%]": "新能源最低利用率目标",
    "Maximum grid-import share target [%]": "外购电最高占比目标",
    "Low-altitude local renewable share target [%]": "低空经济本地绿电占比目标",
    "Remote low-altitude microgrid screening enabled": "是否启用偏远低空微网筛选",
    "Low-altitude autonomy target [h]": "低空关键负荷自治时长目标",
    "Industrial-park green-electricity target [%]": "工业园区绿电占比目标",
    "Carbon allowance [tCO2/year]": "年度碳配额",
    "Green-direct target share [%]": "绿电直连目标占比",
    "Best green-direct mode index": "最优绿电直连方案序号",
    "Endogenous P2X enabled": "是否启用电转其他能源",
    "P2X heat substitution target [%]": "绿氢替代工艺热目标",
    "Max electrolyzer capacity [MW]": "电解槽容量上限",
    "Electrolyzer capacity [MW]": "电解槽规划容量",
}


DISPATCH_COLUMN_LABELS = {
    "day_id": "典型日编号",
    "day_name": "典型日名称",
    "day_type": "典型日类型",
    "day_weight": "典型日权重/天",
    "hour": "时刻/小时",
    "electric_load": "电负荷/兆瓦",
    "heat_load": "热负荷/兆瓦",
    "cooling_load": "冷负荷/兆瓦",
    "electric_load_adjusted": "需求响应后电负荷/兆瓦",
    "P_grid_buy": "电网购电功率/兆瓦",
    "P_grid_sell": "上网售电功率/兆瓦",
    "P_grid_net": "电网净交换功率/兆瓦",
    "P_PV": "光伏出力/兆瓦",
    "P_WT": "风电出力/兆瓦",
    "P_CHP": "热电联产发电功率/兆瓦",
    "H_CHP": "热电联产供热功率/兆瓦",
    "G_CHP": "热电联产耗气功率/兆瓦",
    "P_HP": "热泵耗电功率/兆瓦",
    "H_HP": "热泵供热功率/兆瓦",
    "P_EC": "电制冷耗电功率/兆瓦",
    "C_EC_out": "电制冷供冷功率/兆瓦",
    "G_GB": "燃气锅炉耗气功率/兆瓦",
    "H_GB": "燃气锅炉供热功率/兆瓦",
    "P_ELZ": "电解槽耗电功率/兆瓦",
    "H_H2": "绿氢供热功率/兆瓦",
    "P_BAT_ch": "电池充电功率/兆瓦",
    "P_BAT_dis": "电池放电功率/兆瓦",
    "SOC_BAT": "电池储能量/兆瓦时",
    "H_TS_ch": "蓄热充热功率/兆瓦",
    "H_TS_dis": "蓄热放热功率/兆瓦",
    "SOC_TS": "蓄热储能量/兆瓦时",
    "P_shift_in": "柔性负荷转入/兆瓦",
    "P_shift_out": "柔性负荷转出/兆瓦",
    "P_interrupt": "可中断负荷/兆瓦",
    "P_unmet_e": "未满足电负荷/兆瓦",
    "H_unmet": "未满足热负荷/兆瓦",
    "C_unmet": "未满足冷负荷/兆瓦",
    "renewable_available": "新能源可发功率/兆瓦",
    "renewable_used": "新能源利用功率/兆瓦",
    "renewable_curtailment": "新能源弃电功率/兆瓦",
    "co2_emission": "时段二氧化碳排放/吨",
    "co2_emission_annual": "加权年度二氧化碳排放/吨",
    "electric_balance_error": "电力平衡误差/兆瓦",
    "heat_balance_error": "热力平衡误差/兆瓦",
    "cooling_balance_error": "冷量平衡误差/兆瓦",
}


def _translated_unit(value: Any) -> Any:
    return UNIT_LABELS.get(str(value), value)


def _cost_to_wan_cny(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    if {"Value", "Unit"}.issubset(output.columns):
        cny_rows = output["Unit"].eq("CNY/year")
        output.loc[cny_rows, "Value"] = pd.to_numeric(output.loc[cny_rows, "Value"], errors="coerce") / 10_000.0
        output.loc[cny_rows, "Unit"] = "万元/年"
        million_rows = output["Unit"].eq("million CNY/year")
        output.loc[million_rows, "Value"] = (
            pd.to_numeric(output.loc[million_rows, "Value"], errors="coerce") * 100.0
        )
        output.loc[million_rows, "Unit"] = "万元/年"
    return output


def localize_v17_table(table_name: str, table: pd.DataFrame) -> pd.DataFrame:
    """Return a user-facing Chinese copy without changing the model's internal contract."""
    if not isinstance(table, pd.DataFrame) or table.empty:
        return table.copy() if isinstance(table, pd.DataFrame) else pd.DataFrame()

    output = table.copy()
    if table_name == "capacity":
        output["Technology"] = output["Technology"].map(TECHNOLOGY_LABELS).fillna(output["Technology"])
        output = output.rename(
            columns={
                "Technology": "设备",
                "Capacity": "规划容量",
                "Unit": "单位",
                "Model key": "模型字段",
                "Upper bound": "容量上限",
                "Upper-bound utilization [%]": "容量上限利用率/%",
                "Upper bound binding": "是否达到容量上限",
            }
        )
    elif table_name == "cost":
        output["Cost item"] = output["Cost item"].map(COST_ITEM_LABELS).fillna(output["Cost item"])
        output = _cost_to_wan_cny(output)
        output = output.rename(columns={"Cost item": "成本项目", "Value": "数值", "Unit": "单位"})
    elif table_name == "carbon":
        output["Item"] = output["Item"].map(CARBON_ITEM_LABELS).fillna(output["Item"])
        output["Unit"] = output["Unit"].map(_translated_unit)
        output = output.rename(columns={"Item": "碳指标", "Value": "数值", "Unit": "单位"})
    elif table_name == "metrics":
        output["Metric"] = output["Metric"].map(METRIC_LABELS).fillna(output["Metric"])
        output = _cost_to_wan_cny(output)
        output["Unit"] = output["Unit"].map(_translated_unit)
        output = output.rename(columns={"Metric": "指标", "Value": "数值", "Unit": "单位"})
    elif table_name == "diagnostics":
        output["Diagnostic"] = output["Diagnostic"].map(DIAGNOSTIC_LABELS).fillna(output["Diagnostic"])
        output = output.rename(columns={"Diagnostic": "诊断项目", "Value": "数值"})
    elif table_name == "dispatch":
        available = [column for column in DISPATCH_COLUMN_LABELS if column in output.columns]
        output = output[available].rename(columns=DISPATCH_COLUMN_LABELS)
    return output


def localized_v17_tables(tables: dict[str, pd.DataFrame] | None) -> dict[str, pd.DataFrame]:
    source = tables or {}
    return {
        key: localize_v17_table(key, value)
        for key, value in source.items()
        if isinstance(value, pd.DataFrame)
    }
