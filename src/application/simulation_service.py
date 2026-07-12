from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.core.errors import InputValidationError
from src.core.schemas import StoreMoreInputs
from src.core.validation import validate_simulation_request
from src.storemore_engine import run_storemore_simulation
from src.version import PLATFORM_VERSION, REALTIME_MODEL_VERSION


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    inputs: StoreMoreInputs
    generator_table: pd.DataFrame
    storage_table: pd.DataFrame
    fuel_table: pd.DataFrame
    capex_table: pd.DataFrame | None = None
    uploaded_csv: Any = None


class SimulationService:
    def run(self, request: SimulationRequest) -> dict[str, Any]:
        try:
            validate_simulation_request(
                request.inputs,
                request.generator_table,
                request.storage_table,
                request.fuel_table,
                request.capex_table,
            )
            result = run_storemore_simulation(
                inputs=request.inputs,
                generator_df=request.generator_table,
                storage_df=request.storage_table,
                fuel_df=request.fuel_table,
                capex_df=request.capex_table,
                uploaded_csv=request.uploaded_csv,
            )
            result.setdefault("error", None)
            result["metadata"] = {
                "platform_version": PLATFORM_VERSION,
                "model_version": REALTIME_MODEL_VERSION,
            }
            return result
        except InputValidationError as exc:
            return {"success": False, "message": exc.message, "error": exc.to_dict()}
        except (ValueError, pd.errors.ParserError) as exc:
            return {
                "success": False,
                "message": f"输入数据处理失败：{exc}",
                "error": {"code": "DATA_INPUT_ERROR", "message": str(exc), "issues": [], "details": {}},
            }
