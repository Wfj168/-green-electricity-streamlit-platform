from __future__ import annotations

from io import BytesIO
import zipfile

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from src.core.schemas import StoreMoreInputs
from src.core.validation import validate_simulation_request
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError:  # Streamlit Cloud installs matplotlib from requirements; this keeps local imports robust.
    plt = None


def default_generator_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Unit Name": ["PP gas", "solar", "wind"],
            "Installed Capacity [MW]": [0.0, 10.0, 20.0],
            "Max Investment [MW]": [0.0, 300.0, 300.0],
            "Efficiency [share]": [0.31, 0.0, 0.0],
            "Capital Investment Cost [M EUR/MW]": [1.3, 0.56, 1.1],
            "CO2 Intensity [tCO2/MWh]": [0.398, 0.0, 0.0],
        }
    )


def default_storage_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Unit Name": [
                "Liion storage",
                "Gravity storage",
                "CAES",
                "LAES",
                "VRFB",
                "SMES",
                "Flywheel storage",
                "Ultracapacitor",
            ],
            "Max Investment [MWh]": [300.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "Installed Capacity [MWh]": [2.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "Efficiency [-]": [0.90, 0.84, 0.51, 0.50, 0.75, 0.925, 0.90, 0.92],
            "Storage Ratio [-]": [0.5, 0.17, 0.07, 0.5, 0.1, 360.0, 360.3, 360.0],
            "Variable Cost [EUR/MWh]": [1.0, 15.0, 30.0, 80.0, 60.0, 55.0, 35.0, 55.0],
            "Input/output capacity [MW]": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "Maximum investment into input/output system [MW]": [0.0] * 8,
            "Hourly storage loss as a share of SOC [-]": [
                0.00002,
                0.000001,
                0.000001,
                0.000001,
                0.00001,
                0.0,
                0.001,
                0.0,
            ],
        }
    )


def default_capex_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Technology": [
                "Heat pumps",
                "Boilers",
                "Electrolyzers",
                "Li-ion battery",
                "Gravity-based energy storage",
                "Compressed Air Energy Storage",
                "Liquid Air Energy Storage",
                "Vanadium Redox Flow Battery",
                "Superconducting Magnetic Energy Storage",
                "Flywheel energy storage",
                "Ultracapacitor energy storage",
            ],
            "Annual investment cost [M EUR/year]": [0.0, 0.0, 0.0, 0.56, 1.0, 0.8, 1.2, 0.9, 2.0, 0.7, 0.6],
        }
    )


def default_fuel_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Fuel": ["Gas", "Solar", "Wind", "Biogas", "Biomass", "Coal", "Oil", "Diesel"],
            "Cost": [60.0, 0.0, 0.0, 65.0, 45.0, 35.0, 80.0, 95.0],
            "Unit": ["EUR/MWh"] * 8,
        }
    )


def get_table_value(df: pd.DataFrame, unit_name: str, column_name: str, default_value: float = 0.0) -> float:
    try:
        value = df.loc[df["Unit Name"] == unit_name, column_name].iloc[0]
        return float(value)
    except Exception:
        return float(default_value)


def generate_profiles(total_demand: float, import_price: float, export_price: float, hours: int = 192) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    t = np.arange(hours)
    average_load = total_demand / 8760
    demand = average_load * (
        1.0
        + 0.18 * np.sin(2 * np.pi * (t % 24 - 8) / 24)
        + 0.04 * rng.normal(size=hours)
    )
    demand = np.maximum(demand, average_load * 0.55)
    solar_cf = np.maximum(0, np.sin(np.pi * ((t % 24) - 6) / 12))
    wind_cf = np.clip(
        0.35 + 0.15 * np.sin(2 * np.pi * t / 72) + 0.06 * rng.normal(size=hours),
        0,
        0.85,
    )
    price = import_price * (1.0 + 0.18 * np.sin(2 * np.pi * (t % 24 - 17) / 24))
    price = np.maximum(price, 1)
    return pd.DataFrame(
        {
            "Period": t + 1,
            "Demand": demand,
            "Solar CF": solar_cf,
            "Wind CF": wind_cf,
            "Import price": price,
            "Export price": export_price,
        }
    )


def csv_template(total_demand: float = 1_000_000, import_price: float = 90, export_price: float = 70) -> pd.DataFrame:
    return generate_profiles(total_demand, import_price, export_price, 8760).rename(
        columns={
            "Period": "period",
            "Demand": "demand",
            "Solar CF": "solar_cf",
            "Wind CF": "wind_cf",
            "Import price": "import_price",
            "Export price": "export_price",
        }
    )


def load_profiles_from_csv(
    uploaded_file,
    country_code: str,
    total_demand: float,
    import_price: float,
    export_price: float,
    required_hours: int,
) -> tuple[pd.DataFrame, str]:
    if uploaded_file is None:
        profiles = generate_profiles(total_demand, import_price, export_price, required_hours)
        return profiles, "Using internally generated default profiles."

    uploaded_file.seek(0)
    raw = pd.read_csv(uploaded_file)
    raw.columns = [str(c).strip() for c in raw.columns]
    normalized_columns = {c.lower().replace(" ", "_").replace("-", "_"): c for c in raw.columns}

    def find_column(possible_names: list[str]) -> str | None:
        for name in possible_names:
            key = name.lower().replace(" ", "_").replace("-", "_")
            if key in normalized_columns:
                return normalized_columns[key]
        return None

    period_col = find_column(["period", "hour", "time"])
    demand_col = find_column(["demand", "electricity_demand", "load"])
    solar_col = find_column(["solar_cf", "solar availability", "solar_availability", "pv_cf"])
    wind_col = find_column(["wind_cf", "wind availability", "wind_availability"])
    import_price_col = find_column(["import_price", "electricity_price", "price"])
    export_price_col = find_column(["export_price"])

    if demand_col is not None and solar_col is not None and wind_col is not None and import_price_col is not None:
        if len(raw) < required_hours:
            raise ValueError(f"Uploaded CSV has {len(raw)} rows, but {required_hours} rows are required.")

        profiles = pd.DataFrame()
        profiles["Period"] = pd.to_numeric(raw[period_col], errors="coerce") if period_col else np.arange(1, len(raw) + 1)
        profiles["Demand"] = pd.to_numeric(raw[demand_col], errors="coerce")
        profiles["Solar CF"] = pd.to_numeric(raw[solar_col], errors="coerce")
        profiles["Wind CF"] = pd.to_numeric(raw[wind_col], errors="coerce")
        profiles["Import price"] = pd.to_numeric(raw[import_price_col], errors="coerce")
        profiles["Export price"] = (
            pd.to_numeric(raw[export_price_col], errors="coerce") if export_price_col else export_price
        )
        profiles = profiles.iloc[:required_hours].copy()
        profiles["Period"] = np.arange(1, required_hours + 1)
        profiles["Demand"] = profiles["Demand"].ffill().bfill()
        profiles["Solar CF"] = profiles["Solar CF"].fillna(0).clip(0, 1)
        profiles["Wind CF"] = profiles["Wind CF"].fillna(0).clip(0, 1)
        profiles["Import price"] = profiles["Import price"].fillna(import_price).clip(lower=1)
        profiles["Export price"] = profiles["Export price"].fillna(export_price).clip(lower=0)
        return profiles, "Using uploaded full profile CSV."

    price_col = next((col for col in raw.columns if col.strip().upper() == country_code.upper()), None)
    if price_col is not None:
        if len(raw) < required_hours:
            raise ValueError(f"Uploaded price CSV has {len(raw)} rows, but {required_hours} rows are required.")
        profiles = generate_profiles(total_demand, import_price, export_price, required_hours)
        price_multiplier = pd.to_numeric(raw[price_col], errors="coerce").fillna(1).values[:required_hours]
        profiles["Import price"] = import_price * price_multiplier
        return profiles, f"Using uploaded StoreMore-style price distribution CSV with country code {country_code}."

    raise ValueError("CSV format not recognized. Upload a full profile CSV or a StoreMore-style price distribution CSV.")


def make_forecast_profiles(real_next_day: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    forecast = real_next_day.copy()
    forecast["Demand"] = forecast["Demand"] * (1 + rng.normal(0, 0.06, len(forecast)))
    forecast["Solar CF"] = forecast["Solar CF"] * (1 + rng.normal(0, 0.10, len(forecast)))
    forecast["Wind CF"] = forecast["Wind CF"] * (1 + rng.normal(0, 0.12, len(forecast)))
    forecast["Import price"] = forecast["Import price"] * (1 + rng.normal(0, 0.05, len(forecast)))
    forecast["Demand"] = np.maximum(forecast["Demand"], 0)
    forecast["Solar CF"] = np.clip(forecast["Solar CF"], 0, 1)
    forecast["Wind CF"] = np.clip(forecast["Wind CF"], 0, 1)
    forecast["Import price"] = np.maximum(forecast["Import price"], 1)
    return forecast


def simple_capacity_planning(
    generator_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    total_demand: float,
    optimize_capacity: bool,
    restrict_investments: bool = True,
) -> tuple[float, float, float]:
    average_load = total_demand / 8760
    solar_max_invest = get_table_value(generator_df, "solar", "Max Investment [MW]", 0.0)
    wind_max_invest = get_table_value(generator_df, "wind", "Max Investment [MW]", 0.0)
    liion_max_invest = get_table_value(storage_df, "Liion storage", "Max Investment [MWh]", 0.0)
    if optimize_capacity:
        targets = (average_load * 2.2, average_load * 2.5, average_load * 2.0)
        if restrict_investments:
            return (
                min(solar_max_invest, targets[0]),
                min(wind_max_invest, targets[1]),
                min(liion_max_invest, targets[2]),
            )
        return targets
    return 0.0, 0.0, 0.0


def solve_linear_dispatch(
    profiles: pd.DataFrame,
    solar_capacity: float,
    wind_capacity: float,
    gas_capacity: float,
    storage_capacity: float,
    storage_power: float,
    storage_efficiency: float,
    storage_loss: float,
    import_export_capacity: float,
    gas_cost: float,
    storage_variable_cost: float,
    rps_constraint: bool,
    min_res_share: float,
    co2_constraint: bool,
    max_co2: float,
    gas_co2_intensity: float,
    ceep_constraint: bool,
    max_ceep: float,
    initial_soc: float,
) -> tuple[pd.DataFrame | None, float | str]:
    t_len = len(profiles)
    n_var = 10 * t_len
    idx_solar = slice(0, t_len)
    idx_wind = slice(t_len, 2 * t_len)
    idx_gas = slice(2 * t_len, 3 * t_len)
    idx_import = slice(3 * t_len, 4 * t_len)
    idx_export = slice(4 * t_len, 5 * t_len)
    idx_charge = slice(5 * t_len, 6 * t_len)
    idx_discharge = slice(6 * t_len, 7 * t_len)
    idx_soc = slice(7 * t_len, 8 * t_len)
    idx_excess = slice(8 * t_len, 9 * t_len)
    idx_unmet = slice(9 * t_len, 10 * t_len)

    c = np.zeros(n_var)
    c[idx_gas] = gas_cost
    c[idx_import] = profiles["Import price"].values
    c[idx_export] = -0.2 * profiles["Export price"].values
    c[idx_charge] = storage_variable_cost
    c[idx_discharge] = storage_variable_cost
    c[idx_excess] = 20.0
    c[idx_unmet] = 100000.0

    bounds = []
    bounds.extend((0, solar_capacity * profiles["Solar CF"].iloc[t]) for t in range(t_len))
    bounds.extend((0, wind_capacity * profiles["Wind CF"].iloc[t]) for t in range(t_len))
    bounds.extend((0, gas_capacity) for _ in range(t_len))
    bounds.extend((0, import_export_capacity) for _ in range(t_len))
    bounds.extend((0, import_export_capacity) for _ in range(t_len))
    bounds.extend((0, storage_power) for _ in range(t_len))
    bounds.extend((0, storage_power) for _ in range(t_len))
    bounds.extend((0, storage_capacity) for _ in range(t_len))
    bounds.extend((0, None) for _ in range(t_len))
    bounds.extend((0, None) for _ in range(t_len))

    a_eq = []
    b_eq = []
    for t in range(t_len):
        row = np.zeros(n_var)
        row[idx_solar.start + t] = 1
        row[idx_wind.start + t] = 1
        row[idx_gas.start + t] = 1
        row[idx_import.start + t] = 1
        row[idx_discharge.start + t] = 1
        row[idx_unmet.start + t] = 1
        row[idx_charge.start + t] = -1
        row[idx_export.start + t] = -1
        row[idx_excess.start + t] = -1
        a_eq.append(row)
        b_eq.append(profiles["Demand"].iloc[t])

    for t in range(t_len):
        row = np.zeros(n_var)
        row[idx_soc.start + t] = 1
        row[idx_charge.start + t] = -storage_efficiency
        row[idx_discharge.start + t] = 1 / storage_efficiency if storage_efficiency > 0 else 1
        if t == 0:
            b_value = initial_soc * (1 - storage_loss)
        else:
            row[idx_soc.start + t - 1] = -(1 - storage_loss)
            b_value = 0
        a_eq.append(row)
        b_eq.append(b_value)

    a_ub = []
    b_ub = []
    if rps_constraint:
        r = min_res_share / 100
        row = np.zeros(n_var)
        row[idx_solar] = r - 1
        row[idx_wind] = r - 1
        row[idx_gas] = r
        a_ub.append(row)
        b_ub.append(0)
    if co2_constraint:
        row = np.zeros(n_var)
        row[idx_gas] = gas_co2_intensity
        a_ub.append(row)
        b_ub.append(max_co2 * t_len / 8760)
    if ceep_constraint:
        row = np.zeros(n_var)
        row[idx_excess] = 1
        a_ub.append(row)
        b_ub.append(max_ceep / 100 * profiles["Demand"].sum())

    result = linprog(
        c=c,
        A_ub=np.array(a_ub) if a_ub else None,
        b_ub=np.array(b_ub) if b_ub else None,
        A_eq=np.array(a_eq),
        b_eq=np.array(b_eq),
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        return None, result.message

    x = result.x
    dispatch_df = pd.DataFrame(
        {
            "Period": profiles["Period"].values,
            "Demand": profiles["Demand"].values,
            "Import price": profiles["Import price"].values,
            "Export price": profiles["Export price"].values,
            "Solar": x[idx_solar],
            "Wind": x[idx_wind],
            "Gas": x[idx_gas],
            "Import": x[idx_import],
            "Export": x[idx_export],
            "Storage charge": x[idx_charge],
            "Storage discharge": x[idx_discharge],
            "SOC": x[idx_soc],
            "Excess": x[idx_excess],
            "Unmet": x[idx_unmet],
        }
    )
    return dispatch_df, float(result.fun)


def solve_rolling_dispatch(
    full_profiles: pd.DataFrame,
    rolling_days: int,
    solar_capacity: float,
    wind_capacity: float,
    gas_capacity: float,
    storage_capacity: float,
    storage_power: float,
    storage_efficiency: float,
    storage_loss: float,
    import_export_capacity: float,
    gas_cost: float,
    storage_variable_cost: float,
    rps_constraint: bool,
    min_res_share: float,
    co2_constraint: bool,
    max_co2: float,
    gas_co2_intensity: float,
    ceep_constraint: bool,
    max_ceep: float,
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, str]:
    all_saved_results = []
    rolling_logs = []
    current_soc = storage_capacity * 0.5
    for day in range(rolling_days):
        start_hour = day * 24
        real_24h = full_profiles.iloc[start_hour : start_hour + 24].copy()
        real_next_24h = full_profiles.iloc[start_hour + 24 : start_hour + 48].copy()
        forecast_24h = make_forecast_profiles(real_next_24h, seed=100 + day)
        window_48h = pd.concat([real_24h, forecast_24h], ignore_index=True)
        dispatch_48h, objective_value = solve_linear_dispatch(
            profiles=window_48h,
            solar_capacity=solar_capacity,
            wind_capacity=wind_capacity,
            gas_capacity=gas_capacity,
            storage_capacity=storage_capacity,
            storage_power=storage_power,
            storage_efficiency=storage_efficiency,
            storage_loss=storage_loss,
            import_export_capacity=import_export_capacity,
            gas_cost=gas_cost,
            storage_variable_cost=storage_variable_cost,
            rps_constraint=rps_constraint,
            min_res_share=min_res_share,
            co2_constraint=co2_constraint,
            max_co2=max_co2,
            gas_co2_intensity=gas_co2_intensity,
            ceep_constraint=ceep_constraint,
            max_ceep=max_ceep,
            initial_soc=current_soc,
        )
        if dispatch_48h is None:
            return None, None, f"Rolling optimization failed on day {day + 1}: {objective_value}"
        saved_24h = dispatch_48h.iloc[:24].copy()
        saved_24h["Rolling day"] = day + 1
        saved_24h["Window type"] = "real 24h result"
        all_saved_results.append(saved_24h)
        current_soc = float(saved_24h["SOC"].iloc[-1])
        rolling_logs.append(
            {
                "Rolling day": day + 1,
                "Window start period": int(real_24h["Period"].iloc[0]),
                "Window end period": int(real_next_24h["Period"].iloc[-1]),
                "Saved periods": "first 24 hours",
                "Final SOC after saved horizon [MWh]": current_soc,
                "Objective value of 48h window": objective_value,
            }
        )
    return pd.concat(all_saved_results, ignore_index=True), pd.DataFrame(rolling_logs), "success"


def summarize_indicators(
    result_df: pd.DataFrame,
    gas_cost: float = 60.0,
    storage_variable_cost: float = 1.0,
    gas_co2_intensity: float = 0.398,
    investment_cost_meur: float = 0.0,
) -> pd.DataFrame:
    total_generation = result_df[["Solar", "Wind", "Gas", "Import", "Storage discharge"]].sum().sum()
    total_renewable = result_df[["Solar", "Wind"]].sum().sum()
    total_demand = result_df["Demand"].sum()
    operating_cost = (
        result_df["Gas"].sum() * gas_cost
        + (result_df["Import"] * result_df["Import price"]).sum()
        - 0.2 * (result_df["Export"] * result_df["Export price"]).sum()
        + (result_df["Storage charge"].sum() + result_df["Storage discharge"].sum()) * storage_variable_cost
        + result_df["Excess"].sum() * 20.0
        + result_df["Unmet"].sum() * 100000.0
    )
    co2_emissions = result_df["Gas"].sum() * gas_co2_intensity
    ceep_share = result_df["Excess"].sum() / total_demand * 100 if total_demand > 0 else 0
    metrics = {
        "Total electricity demand [MWh]": total_demand,
        "Total renewable generation [MWh]": total_renewable,
        "Total gas generation [MWh]": result_df["Gas"].sum(),
        "Total import [MWh]": result_df["Import"].sum(),
        "Total export [MWh]": result_df["Export"].sum(),
        "Total excess electricity [MWh]": result_df["Excess"].sum(),
        "Total unmet demand [MWh]": result_df["Unmet"].sum(),
        "Renewable share [%]": total_renewable / total_generation * 100 if total_generation > 0 else 0,
        "CEEP share [%]": ceep_share,
        "CO2 emissions [tCO2]": co2_emissions,
        "Operating cost proxy [EUR]": operating_cost,
        "Annualized investment cost [M EUR/year]": investment_cost_meur,
        "Total cost proxy [EUR]": operating_cost + investment_cost_meur * 1_000_000,
    }
    return pd.DataFrame({"Metric": list(metrics.keys()), "Value": list(metrics.values())})


def fig_to_bytes(fig) -> bytes:
    if plt is None:
        return b""
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    buffer.seek(0)
    image_bytes = buffer.getvalue()
    plt.close(fig)
    return image_bytes


def _svg_line_chart(title: str, series: dict[str, pd.Series | np.ndarray], x: pd.Series | np.ndarray) -> bytes:
    width, height = 900, 360
    margin_left, margin_right, margin_top, margin_bottom = 52, 20, 40, 42
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    x_arr = np.asarray(x, dtype=float)
    values = [np.asarray(v, dtype=float) for v in series.values()]
    y_min = min([float(np.nanmin(v)) for v in values] + [0.0])
    y_max = max([float(np.nanmax(v)) for v in values] + [1.0])
    if y_max <= y_min:
        y_max = y_min + 1.0
    x_min, x_max = float(np.nanmin(x_arr)), float(np.nanmax(x_arr))
    if x_max <= x_min:
        x_max = x_min + 1.0
    colors = ["#0ea5e9", "#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4"]

    def px(xv: float) -> float:
        return margin_left + (xv - x_min) / (x_max - x_min) * plot_w

    def py(yv: float) -> float:
        return margin_top + (1 - (yv - y_min) / (y_max - y_min)) * plot_h

    polylines = []
    legend = []
    for idx, (name, arr) in enumerate(series.items()):
        color = colors[idx % len(colors)]
        points = " ".join(f"{px(x_arr[i]):.1f},{py(arr[i]):.1f}" for i in range(min(len(x_arr), len(arr))))
        polylines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.4" points="{points}" />')
        legend_x = margin_left + idx * 130
        legend.append(
            f'<rect x="{legend_x}" y="{height - 20}" width="10" height="10" fill="{color}" />'
            f'<text x="{legend_x + 14}" y="{height - 11}" font-size="12" fill="#334155">{name}</text>'
        )
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <rect width="100%" height="100%" fill="#ffffff"/>
      <text x="{margin_left}" y="24" font-size="18" font-family="Arial" font-weight="700" fill="#111827">{title}</text>
      <line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#cbd5e1"/>
      <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#cbd5e1"/>
      <text x="8" y="{margin_top + 12}" font-size="12" font-family="Arial" fill="#64748b">{y_max:.1f}</text>
      <text x="8" y="{margin_top + plot_h}" font-size="12" font-family="Arial" fill="#64748b">{y_min:.1f}</text>
      {''.join(polylines)}
      {''.join(legend)}
    </svg>
    """
    return svg.encode("utf-8")


def _svg_bar_chart(title: str, labels: list[str], values: list[float]) -> bytes:
    width, height = 640, 360
    margin_left, margin_right, margin_top, margin_bottom = 52, 20, 42, 60
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    max_value = max([float(v) for v in values] + [1.0])
    bar_w = plot_w / max(len(values), 1) * 0.55
    bars = []
    colors = ["#0ea5e9", "#22c55e", "#f59e0b"]
    for idx, (label, value) in enumerate(zip(labels, values)):
        x = margin_left + (idx + 0.25) * plot_w / len(values)
        h = float(value) / max_value * plot_h
        y = margin_top + plot_h - h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{colors[idx % len(colors)]}"/>'
            f'<text x="{x + bar_w/2:.1f}" y="{height - 28}" text-anchor="middle" font-size="12" fill="#334155">{label}</text>'
            f'<text x="{x + bar_w/2:.1f}" y="{max(y - 6, 54):.1f}" text-anchor="middle" font-size="12" fill="#334155">{value:.1f}</text>'
        )
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
      <rect width="100%" height="100%" fill="#ffffff"/>
      <text x="{margin_left}" y="24" font-size="18" font-family="Arial" font-weight="700" fill="#111827">{title}</text>
      <line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#cbd5e1"/>
      <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#cbd5e1"/>
      {''.join(bars)}
    </svg>
    """
    return svg.encode("utf-8")


def create_result_figures(result_df: pd.DataFrame, solar_invest: float, wind_invest: float, storage_invest: float) -> dict[str, bytes]:
    figures = {}
    if plt is None:
        x = result_df["Period"]
        figures["power_generation.svg"] = _svg_line_chart(
            "Power generation",
            {column: result_df[column] for column in ["Solar", "Wind", "Gas", "Import", "Storage discharge"]},
            x,
        )
        figures["generation_investment.svg"] = _svg_bar_chart("Generation investments", ["Solar", "Wind"], [solar_invest, wind_invest])
        figures["storage_investment.svg"] = _svg_bar_chart("Storage investments", ["Liion"], [storage_invest])
        figures["storage_input_output.svg"] = _svg_line_chart(
            "Input/output to storage",
            {"Discharge": result_df["Storage discharge"], "Charge": -result_df["Storage charge"]},
            x,
        )
        figures["storage_soc.svg"] = _svg_line_chart("Storage SOC", {"SOC": result_df["SOC"]}, x)
        total_supply = result_df[["Solar", "Wind", "Gas", "Import", "Storage discharge"]].sum(axis=1)
        figures["demand_supply_balance.svg"] = _svg_line_chart(
            "Demand and supply balance",
            {"Demand": result_df["Demand"], "Total supply": total_supply},
            x,
        )
        figures["excess_unmet.svg"] = _svg_line_chart(
            "Excess electricity and unmet demand",
            {"Excess": result_df["Excess"], "Unmet": result_df["Unmet"]},
            x,
        )
        return figures

    fig1, ax1 = plt.subplots(figsize=(10, 4))
    for column in ["Solar", "Wind", "Gas", "Import", "Storage discharge"]:
        ax1.plot(result_df["Period"], result_df[column], label=column)
    ax1.set_xlabel("Period")
    ax1.set_ylabel("Power [MW]")
    ax1.set_title("Power generation")
    ax1.legend()
    figures["power_generation.png"] = fig_to_bytes(fig1)

    fig2, ax2 = plt.subplots(figsize=(6, 4))
    ax2.bar(["Solar", "Wind"], [solar_invest, wind_invest])
    ax2.set_ylabel("Additional capacity [MW]")
    ax2.set_title("Investments into generation capacities")
    figures["generation_investment.png"] = fig_to_bytes(fig2)

    fig3, ax3 = plt.subplots(figsize=(6, 4))
    ax3.bar(["Liion storage"], [storage_invest])
    ax3.set_ylabel("Additional capacity [MWh]")
    ax3.set_title("Investments into storage capacities")
    figures["storage_investment.png"] = fig_to_bytes(fig3)

    fig4, ax4 = plt.subplots(figsize=(10, 4))
    ax4.plot(result_df["Period"], result_df["Storage discharge"], label="Discharge")
    ax4.plot(result_df["Period"], -result_df["Storage charge"], label="Charge")
    ax4.axhline(0, linewidth=0.8)
    ax4.set_xlabel("Period")
    ax4.set_ylabel("Power [MW]")
    ax4.set_title("Input/output to storage")
    ax4.legend()
    figures["storage_input_output.png"] = fig_to_bytes(fig4)

    fig5, ax5 = plt.subplots(figsize=(10, 4))
    ax5.plot(result_df["Period"], result_df["SOC"], label="SOC")
    ax5.set_xlabel("Period")
    ax5.set_ylabel("SOC [MWh]")
    ax5.set_title("Storage SOC")
    ax5.legend()
    figures["storage_soc.png"] = fig_to_bytes(fig5)

    fig6, ax6 = plt.subplots(figsize=(10, 4))
    ax6.plot(result_df["Period"], result_df["Demand"], label="Demand")
    total_supply = result_df[["Solar", "Wind", "Gas", "Import", "Storage discharge"]].sum(axis=1)
    ax6.plot(result_df["Period"], total_supply, label="Total supply")
    ax6.set_xlabel("Period")
    ax6.set_ylabel("Power [MW]")
    ax6.set_title("Demand and supply balance")
    ax6.legend()
    figures["demand_supply_balance.png"] = fig_to_bytes(fig6)

    fig7, ax7 = plt.subplots(figsize=(10, 4))
    ax7.plot(result_df["Period"], result_df["Excess"], label="Excess electricity")
    ax7.plot(result_df["Period"], result_df["Unmet"], label="Unmet demand")
    ax7.set_xlabel("Period")
    ax7.set_ylabel("Energy [MWh]")
    ax7.set_title("Excess electricity and unmet demand")
    ax7.legend()
    figures["excess_unmet.png"] = fig_to_bytes(fig7)
    return figures


def run_storemore_simulation(
    inputs: StoreMoreInputs,
    generator_df: pd.DataFrame,
    storage_df: pd.DataFrame,
    fuel_df: pd.DataFrame,
    capex_df: pd.DataFrame | None = None,
    uploaded_csv=None,
) -> dict[str, object]:
    validate_simulation_request(inputs, generator_df, storage_df, fuel_df, capex_df)
    required_hours = int(inputs.rolling_days) * 24 + 24
    profiles, profile_source_message = load_profiles_from_csv(
        uploaded_file=uploaded_csv,
        country_code=inputs.country_code,
        total_demand=inputs.total_demand,
        import_price=inputs.import_price,
        export_price=inputs.export_price,
        required_hours=required_hours,
    )
    solar_invest, wind_invest, storage_invest = simple_capacity_planning(
        generator_df,
        storage_df,
        inputs.total_demand,
        inputs.optimize_capacity,
        inputs.restrict_investments,
    )
    solar_capacity = get_table_value(generator_df, "solar", "Installed Capacity [MW]", 0.0) + solar_invest
    wind_capacity = get_table_value(generator_df, "wind", "Installed Capacity [MW]", 0.0) + wind_invest
    average_load = inputs.total_demand / 8760
    gas_installed = get_table_value(generator_df, "PP gas", "Installed Capacity [MW]", 0.0)
    gas_capacity = max(gas_installed, average_load * 0.5)
    storage_capacity = get_table_value(storage_df, "Liion storage", "Installed Capacity [MWh]", 0.0) + storage_invest
    storage_efficiency = get_table_value(storage_df, "Liion storage", "Efficiency [-]", 0.9)
    storage_loss = get_table_value(storage_df, "Liion storage", "Hourly storage loss as a share of SOC [-]", 0.00002)
    storage_ratio = get_table_value(storage_df, "Liion storage", "Storage Ratio [-]", 0.5)
    storage_variable_cost = get_table_value(storage_df, "Liion storage", "Variable Cost [EUR/MWh]", 1.0)
    if storage_capacity <= 0:
        storage_power = 0.0
    else:
        storage_power = storage_capacity * storage_ratio if storage_ratio <= 1 else storage_capacity / storage_ratio
    try:
        gas_cost = float(fuel_df.loc[fuel_df["Fuel"] == "Gas", "Cost"].iloc[0])
    except Exception:
        gas_cost = 60.0
    gas_co2_intensity = get_table_value(generator_df, "PP gas", "CO2 Intensity [tCO2/MWh]", 0.398)

    result_df, rolling_log_df, optimization_info = solve_rolling_dispatch(
        full_profiles=profiles,
        rolling_days=int(inputs.rolling_days),
        solar_capacity=solar_capacity,
        wind_capacity=wind_capacity,
        gas_capacity=gas_capacity,
        storage_capacity=storage_capacity,
        storage_power=storage_power,
        storage_efficiency=storage_efficiency,
        storage_loss=storage_loss,
        import_export_capacity=inputs.import_export_capacity,
        gas_cost=gas_cost,
        storage_variable_cost=storage_variable_cost,
        rps_constraint=inputs.rps_constraint,
        min_res_share=inputs.min_res_share,
        co2_constraint=inputs.co2_constraint,
        max_co2=inputs.max_co2,
        gas_co2_intensity=gas_co2_intensity,
        ceep_constraint=inputs.ceep_constraint,
        max_ceep=inputs.max_ceep,
    )
    if result_df is None or rolling_log_df is None:
        return {"success": False, "message": optimization_info}

    investment_df = pd.DataFrame(
        {
            "Technology": ["Solar", "Wind", "Liion storage"],
            "Additional capacity": [solar_invest, wind_invest, storage_invest],
            "Final capacity": [solar_capacity, wind_capacity, storage_capacity],
            "Unit": ["MW", "MW", "MWh"],
        }
    )
    solar_capex = get_table_value(generator_df, "solar", "Capital Investment Cost [M EUR/MW]", 0.56)
    wind_capex = get_table_value(generator_df, "wind", "Capital Investment Cost [M EUR/MW]", 1.1)
    storage_capex = 0.56
    if capex_df is not None and {"Technology", "Annual investment cost [M EUR/year]"}.issubset(capex_df.columns):
        match = capex_df.loc[
            capex_df["Technology"].astype(str).str.lower().str.contains("li-ion|liion", regex=True),
            "Annual investment cost [M EUR/year]",
        ]
        if not match.empty:
            storage_capex = float(match.iloc[0])
    investment_cost_meur = solar_invest * solar_capex + wind_invest * wind_capex + storage_invest * storage_capex
    investment_df["Annualized cost proxy [M EUR/year]"] = [
        solar_invest * solar_capex,
        wind_invest * wind_capex,
        storage_invest * storage_capex,
    ]
    metric_df = summarize_indicators(
        result_df,
        gas_cost=gas_cost,
        storage_variable_cost=storage_variable_cost,
        gas_co2_intensity=gas_co2_intensity,
        investment_cost_meur=investment_cost_meur,
    )
    summary_df = pd.DataFrame(
        {
            "Item": [
                "Scenario name",
                "Platform version",
                "Realtime model version",
                "RPS constraint",
                "CO2 constraint",
                "CEEP constraint",
                "Optimize generation capacity",
                "Restrict investments",
                "Total electricity demand [MWh]",
                "Service life [years]",
                "Import/export capacity [MW]",
                "Minimum RES share [%]",
                "Maximum CO2 emissions [tCO2]",
                "Maximum CEEP [%]",
                "Country code",
                "Rolling days",
                "Rolling window length [h]",
                "Saved horizon per window [h]",
                "Profile source",
            ],
            "Value": [
                inputs.scenario_name,
                PLATFORM_VERSION,
                REALTIME_MODEL_VERSION,
                inputs.rps_constraint,
                inputs.co2_constraint,
                inputs.ceep_constraint,
                inputs.optimize_capacity,
                inputs.restrict_investments,
                inputs.total_demand,
                inputs.service_life,
                inputs.import_export_capacity,
                inputs.min_res_share,
                inputs.max_co2,
                inputs.max_ceep,
                inputs.country_code,
                int(inputs.rolling_days),
                48,
                24,
                profile_source_message,
            ],
        }
    )
    figures = create_result_figures(result_df, solar_invest, wind_invest, storage_invest)
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        zip_file.writestr("input_summary.csv", summary_df.to_csv(index=False))
        zip_file.writestr("input_profiles_used.csv", profiles.to_csv(index=False))
        zip_file.writestr("dispatch_results.csv", result_df.to_csv(index=False))
        zip_file.writestr("investment_results.csv", investment_df.to_csv(index=False))
        zip_file.writestr("key_indicators.csv", metric_df.to_csv(index=False))
        zip_file.writestr("rolling_log.csv", rolling_log_df.to_csv(index=False))
        if capex_df is not None:
            zip_file.writestr("capex_inputs.csv", capex_df.to_csv(index=False))
        for file_name, image_bytes in figures.items():
            zip_file.writestr(file_name, image_bytes)
    zip_buffer.seek(0)
    return {
        "success": True,
        "message": "MODEL SOLVED",
        "profiles": profiles,
        "summary": summary_df,
        "dispatch": result_df,
        "rolling_log": rolling_log_df,
        "investment": investment_df,
        "metrics": metric_df,
        "figures": figures,
        "zip": zip_buffer,
    }
