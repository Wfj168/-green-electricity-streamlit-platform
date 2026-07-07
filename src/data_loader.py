from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "results"


@st.cache_data(show_spinner=False)
def read_csv(relative_path: str) -> pd.DataFrame:
    path = DATA_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def load_summary(kind: str) -> pd.DataFrame:
    if kind == "planning":
        return read_csv("planning_summary_v17_3_1.csv")
    if kind == "operation":
        return read_csv("operation_summary_v17_3_1.csv")
    if kind == "reliability":
        return read_csv("reliability_stress_summary_v17_3_1.csv")
    raise ValueError(f"unknown summary kind: {kind}")


def load_dispatch(group: str, scenario: str) -> pd.DataFrame:
    return read_csv(f"{group}/{scenario}/data/dispatch_results.csv")


def load_metrics(group: str, scenario: str) -> pd.DataFrame:
    return read_csv(f"{group}/{scenario}/data/metrics_results.csv")


def load_capacity(group: str, scenario: str) -> pd.DataFrame:
    return read_csv(f"{group}/{scenario}/data/capacity_results.csv")


def load_carbon_management(name: str = "decomposition") -> pd.DataFrame:
    mapping = {
        "decomposition": "carbon_management_decomposition_v17_3_9.csv",
        "pathway": "carbon_management_pathway_v17_3_9.csv",
        "contribution": "carbon_reduction_contribution_v17_3_9.csv",
    }
    return read_csv(mapping[name])


def metric_from_table(metrics: pd.DataFrame, metric_name: str, default: float = 0.0) -> float:
    if metrics.empty or "Metric" not in metrics.columns:
        return default
    hit = metrics[metrics["Metric"].eq(metric_name)]
    if hit.empty:
        return default
    try:
        return float(hit["Value"].iloc[0])
    except (TypeError, ValueError):
        return default

