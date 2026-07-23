from __future__ import annotations

from src.application.agri_current_state_audit import (
    CURRENT_STATE_FINDINGS,
    AuditSeverity,
    AuditStatus,
    current_state_audit_summary,
)


def test_current_state_audit_has_unique_traceable_findings() -> None:
    finding_ids = [finding.finding_id for finding in CURRENT_STATE_FINDINGS]
    assert len(finding_ids) == len(set(finding_ids))
    assert all(finding.evidence and finding.impact for finding in CURRENT_STATE_FINDINGS)
    assert all(3 <= finding.remediation_step <= 9 for finding in CURRENT_STATE_FINDINGS)


def test_blockers_cover_data_green_carbon_and_charts() -> None:
    blocker_categories = {
        finding.category
        for finding in CURRENT_STATE_FINDINGS
        if finding.severity is AuditSeverity.BLOCKER
    }
    assert {"数据与负荷", "时间序列", "参数治理", "绿电直连", "碳核算", "结果图"}.issubset(
        blocker_categories
    )


def test_current_state_audit_tracks_completed_remediation_without_erasing_findings() -> None:
    summary = current_state_audit_summary()
    assert summary["finding_count"] == len(CURRENT_STATE_FINDINGS)
    assert summary["open_count"] == len(CURRENT_STATE_FINDINGS) - 16
    resolved_ids = {
        finding.finding_id
        for finding in CURRENT_STATE_FINDINGS
        if finding.status is AuditStatus.RESOLVED
    }
    assert resolved_ids == {
        "PARAM-001",
        "PARAM-002",
        "GREEN-001",
        "GREEN-002",
        "CARBON-001",
        "MODEL-001",
        "MODEL-002",
        "MODEL-003",
        "DATA-002",
        "TIME-001",
        "SCOPE-001",
        "CHART-001",
        "CHART-002",
        "CHART-003",
        "CHART-004",
        "UI-001",
    }
