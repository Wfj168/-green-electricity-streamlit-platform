from __future__ import annotations

import numpy as np
import pandas as pd

from src.core.errors import InputValidationError, ValidationIssue
from src.core.schemas import StoreMoreInputs


def _require_columns(
    table_name: str,
    table: pd.DataFrame,
    required_columns: list[str],
    issues: list[ValidationIssue],
) -> bool:
    missing = [column for column in required_columns if column not in table.columns]
    if missing:
        issues.append(ValidationIssue(table_name, "缺少字段：" + "、".join(missing)))
        return False
    if table.empty:
        issues.append(ValidationIssue(table_name, "参数表不能为空"))
        return False
    return True


def _validate_numeric_columns(
    table_name: str,
    table: pd.DataFrame,
    columns: list[str],
    issues: list[ValidationIssue],
) -> None:
    for column in columns:
        if column not in table.columns:
            continue
        numeric = pd.to_numeric(table[column], errors="coerce")
        invalid = numeric.isna() | ~np.isfinite(numeric) | (numeric < 0)
        if invalid.any():
            rows = ", ".join(str(index + 1) for index in table.index[invalid][:5])
            issues.append(ValidationIssue(f"{table_name}.{column}", f"第{rows}行必须是非负有限数值"))


def validate_simulation_request(
    inputs: StoreMoreInputs,
    generator_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    fuel_df: pd.DataFrame,
    capex_df: pd.DataFrame | None,
) -> None:
    inputs.validate()
    issues: list[ValidationIssue] = []

    generator_columns = [
        "Unit Name",
        "Installed Capacity [MW]",
        "Max Investment [MW]",
        "Capital Investment Cost [M CNY/MW]",
        "CO2 Intensity [tCO2/MWh]",
    ]
    if _require_columns("generator_table", generator_df, generator_columns, issues):
        required_units = {"PP gas", "solar", "wind"}
        units = set(generator_df["Unit Name"].astype(str))
        missing_units = sorted(required_units - units)
        if missing_units:
            issues.append(ValidationIssue("generator_table.Unit Name", "缺少设备：" + "、".join(missing_units)))
        if generator_df["Unit Name"].astype(str).duplicated().any():
            issues.append(ValidationIssue("generator_table.Unit Name", "设备名称不能重复"))
        _validate_numeric_columns("generator_table", generator_df, generator_columns[1:], issues)

    storage_columns = [
        "Unit Name",
        "Installed Capacity [MWh]",
        "Max Investment [MWh]",
        "Efficiency [-]",
        "Storage Ratio [-]",
        "Variable Cost [CNY/MWh]",
        "Hourly storage loss as a share of SOC [-]",
    ]
    if _require_columns("storage_table", storage_df, storage_columns, issues):
        units = set(storage_df["Unit Name"].astype(str))
        if "Liion storage" not in units:
            issues.append(ValidationIssue("storage_table.Unit Name", "缺少Liion storage设备"))
        _validate_numeric_columns("storage_table", storage_df, storage_columns[1:], issues)
        efficiency = pd.to_numeric(storage_df["Efficiency [-]"], errors="coerce")
        if ((efficiency <= 0) | (efficiency > 1)).any():
            issues.append(ValidationIssue("storage_table.Efficiency [-]", "效率必须大于0且不超过1"))
        storage_loss = pd.to_numeric(
            storage_df["Hourly storage loss as a share of SOC [-]"], errors="coerce"
        )
        if (storage_loss >= 1).any():
            issues.append(ValidationIssue("storage_table.Hourly storage loss as a share of SOC [-]", "损耗率必须小于1"))

    fuel_columns = ["Fuel", "Cost", "Unit"]
    if _require_columns("fuel_table", fuel_df, fuel_columns, issues):
        if "Gas" not in set(fuel_df["Fuel"].astype(str)):
            issues.append(ValidationIssue("fuel_table.Fuel", "缺少Gas燃料价格"))
        _validate_numeric_columns("fuel_table", fuel_df, ["Cost"], issues)

    if capex_df is not None:
        capex_columns = ["Technology", "Annual investment cost [M CNY/year]"]
        if _require_columns("capex_table", capex_df, capex_columns, issues):
            _validate_numeric_columns("capex_table", capex_df, [capex_columns[1]], issues)

    if issues:
        raise InputValidationError(issues)
