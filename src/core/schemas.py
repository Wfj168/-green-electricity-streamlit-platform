from __future__ import annotations

from dataclasses import dataclass
import math

from src.core.errors import InputValidationError, ValidationIssue


@dataclass(frozen=True, slots=True)
class StoreMoreInputs:
    scenario_name: str
    total_demand: float
    service_life: int
    import_price: float
    export_price: float
    import_export_capacity: float
    rps_constraint: bool
    min_res_share: float
    co2_constraint: bool
    max_co2: float
    ceep_constraint: bool
    max_ceep: float
    optimize_capacity: bool
    restrict_investments: bool
    rolling_days: int
    country_code: str

    def validate(self) -> None:
        issues: list[ValidationIssue] = []
        scenario_name = str(self.scenario_name).strip()
        country_code = str(self.country_code).strip()

        if not scenario_name:
            issues.append(ValidationIssue("scenario_name", "场景名称不能为空"))
        elif len(scenario_name) > 100:
            issues.append(ValidationIssue("scenario_name", "场景名称不能超过100个字符"))
        if not country_code:
            issues.append(ValidationIssue("country_code", "国家或电价分布代码不能为空"))
        elif len(country_code) > 8:
            issues.append(ValidationIssue("country_code", "代码不能超过8个字符"))

        self._positive(issues, "total_demand", self.total_demand)
        self._integer_range(issues, "service_life", self.service_life, 1, 100)
        self._non_negative(issues, "import_price", self.import_price)
        self._non_negative(issues, "export_price", self.export_price)
        self._non_negative(issues, "import_export_capacity", self.import_export_capacity)
        self._percentage(issues, "min_res_share", self.min_res_share)
        self._non_negative(issues, "max_co2", self.max_co2)
        self._percentage(issues, "max_ceep", self.max_ceep)
        self._integer_range(issues, "rolling_days", self.rolling_days, 1, 365)

        if issues:
            raise InputValidationError(issues)

    @staticmethod
    def _finite(value: float | int) -> bool:
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    @classmethod
    def _positive(cls, issues: list[ValidationIssue], field: str, value: float | int) -> None:
        if not cls._finite(value) or float(value) <= 0:
            issues.append(ValidationIssue(field, "必须是大于0的有限数值"))

    @classmethod
    def _non_negative(cls, issues: list[ValidationIssue], field: str, value: float | int) -> None:
        if not cls._finite(value) or float(value) < 0:
            issues.append(ValidationIssue(field, "必须是大于或等于0的有限数值"))

    @classmethod
    def _percentage(cls, issues: list[ValidationIssue], field: str, value: float | int) -> None:
        if not cls._finite(value) or not 0 <= float(value) <= 100:
            issues.append(ValidationIssue(field, "必须在0到100之间"))

    @classmethod
    def _integer_range(
        cls,
        issues: list[ValidationIssue],
        field: str,
        value: float | int,
        minimum: int,
        maximum: int,
    ) -> None:
        if not cls._finite(value) or int(value) != float(value) or not minimum <= int(value) <= maximum:
            issues.append(ValidationIssue(field, f"必须是{minimum}到{maximum}之间的整数"))
