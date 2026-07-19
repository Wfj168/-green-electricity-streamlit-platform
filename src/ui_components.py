from __future__ import annotations

import html

import streamlit as st


GRADIENTS = {
    "blue": "linear-gradient(135deg, #0ea5e9, #2563eb)",
    "green": "linear-gradient(135deg, #22c55e, #16a34a)",
    "purple": "linear-gradient(135deg, #a855f7, #ec4899)",
    "orange": "linear-gradient(135deg, #f59e0b, #f97316)",
    "indigo": "linear-gradient(135deg, #6366f1, #7c3aed)",
    "teal": "linear-gradient(135deg, #14b8a6, #0f766e)",
    "cyan": "linear-gradient(135deg, #06b6d4, #0ea5e9)",
    "amber": "linear-gradient(135deg, #f59e0b, #facc15)",
    "red": "linear-gradient(135deg, #ef4444, #f97316)",
    "slate": "linear-gradient(135deg, #64748b, #334155)",
}


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --bg: #f5f7fb;
          --text: #111827;
          --muted: #64748b;
          --line: #e5e7eb;
          --blue: #0ea5e9;
          --green: #22c55e;
        }
        .stApp {
          background: var(--bg);
          color: var(--text);
          font-family: Arial, "Microsoft YaHei", sans-serif;
        }
        [data-testid="stSidebar"] {
          background: #ffffff;
          border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p {
          font-size: 15px;
        }
        .block-container {
          padding-top: 1.2rem;
          padding-bottom: 2.5rem;
          max-width: 1560px;
        }
        .brand-card {
          display: flex;
          gap: 12px;
          align-items: center;
          padding: 18px 10px 22px;
          border-bottom: 1px solid #eef2f7;
          margin-bottom: 10px;
        }
        .brand-logo {
          width: 46px;
          height: 46px;
          border-radius: 12px;
          background: linear-gradient(135deg, #0ea5e9, #22c55e);
          color: #fff;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          font-weight: 800;
        }
        .brand-name {
          font-size: 22px;
          font-weight: 800;
          color: #11a37f;
        }
        .brand-subtitle {
          font-size: 12px;
          color: var(--muted);
          margin-top: 3px;
        }
        .sidebar-note {
          color: #64748b;
          font-size: 12px;
          line-height: 1.6;
          padding: 14px 8px 0;
        }
        .page-title {
          font-size: 34px;
          font-weight: 800;
          margin: 8px 0 4px;
          color: #111827;
        }
        .cockpit-hero {
          position: relative;
          overflow: hidden;
          border: 1px solid #bfdbfe;
          border-radius: 14px;
          background:
            radial-gradient(circle at 90% 10%, rgba(255,255,255,.55), transparent 26%),
            linear-gradient(115deg, #e0f2fe 0%, #eff6ff 45%, #ecfeff 100%);
          box-shadow: 0 18px 42px rgba(37, 99, 235, 0.10);
          padding: 24px 30px;
          margin: 4px 0 18px;
        }
        .cockpit-hero:after {
          content: "";
          position: absolute;
          width: 320px;
          height: 320px;
          right: -110px;
          top: -190px;
          border: 34px solid rgba(37,99,235,.08);
          border-radius: 50%;
        }
        .cockpit-eyebrow {
          color: #2563eb;
          font-size: 12px;
          font-weight: 800;
          letter-spacing: .14em;
          margin-bottom: 5px;
        }
        .cockpit-title {
          color: #0f3b67;
          font-size: 30px;
          font-weight: 900;
          letter-spacing: .03em;
        }
        .cockpit-subtitle {
          color: #526b85;
          font-size: 14px;
          margin-top: 7px;
        }
        .cockpit-status {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          margin-top: 13px;
          padding: 6px 11px;
          border-radius: 999px;
          color: #166534;
          background: rgba(220,252,231,.9);
          border: 1px solid #86efac;
          font-size: 12px;
          font-weight: 700;
        }
        .cockpit-status:before {
          content: "";
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow: 0 0 0 4px rgba(34,197,94,.12);
        }
        .page-subtitle {
          font-size: 17px;
          color: #64748b;
          margin-bottom: 28px;
        }
        .title-underline {
          width: 58px;
          height: 5px;
          border-radius: 99px;
          background: linear-gradient(90deg, #0ea5e9, #22c55e);
          margin: 0 0 22px;
        }
        .section-label {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 22px;
          font-weight: 800;
          margin: 24px 0 14px;
        }
        .section-label:before {
          content: "";
          width: 12px;
          height: 12px;
          border-radius: 3px;
          background: linear-gradient(135deg, #0ea5e9, #22c55e);
          display: inline-block;
        }
        .overview-panel,
        .white-panel,
        .feature-card,
        .route-card,
        .idea-card,
        .innovation-card,
        .mode-card,
        .diagram-card,
        .soft-panel,
        .cost-card,
        .algorithm-card {
          background: #fff;
          border: 1px solid #edf2f7;
          border-radius: 8px;
          padding: 20px;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        }
        .overview-panel {
          padding: 28px 32px;
          box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
          margin-bottom: 20px;
        }
        .overview-title {
          font-size: 26px;
          font-weight: 800;
          margin-bottom: 12px;
        }
        .overview-text {
          color: #475569;
          line-height: 1.8;
          font-size: 16px;
        }
        .metric-card {
          color: #fff;
          padding: 20px 22px;
          border-radius: 8px;
          min-height: 118px;
          box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
          display: flex;
          justify-content: space-between;
          gap: 10px;
        }
        .dashboard-kpi {
          min-height: 112px;
          border: 1px solid #dbeafe;
          border-top: 3px solid var(--kpi-color, #2563eb);
          border-radius: 10px;
          background: linear-gradient(180deg, #ffffff, #f8fbff);
          box-shadow: 0 10px 28px rgba(15, 59, 103, .07);
          padding: 15px 17px;
        }
        .dashboard-kpi small {
          display: block;
          color: #64748b;
          font-size: 12px;
          font-weight: 700;
          margin-bottom: 10px;
        }
        .dashboard-kpi b {
          color: #0f3b67;
          font-size: 24px;
          line-height: 1;
        }
        .dashboard-kpi span {
          color: #526b85;
          font-size: 12px;
          margin-left: 3px;
        }
        .dashboard-kpi em {
          display: block;
          color: #7c8ea3;
          font-size: 11px;
          font-style: normal;
          margin-top: 9px;
        }
        .insight-card {
          min-height: 106px;
          border: 1px solid #dbeafe;
          border-left: 4px solid var(--insight-color, #2563eb);
          border-radius: 10px;
          background: #ffffff;
          box-shadow: 0 8px 22px rgba(15, 59, 103, .06);
          padding: 14px 16px;
          margin-bottom: 10px;
        }
        .insight-card b {
          display: block;
          color: #173b60;
          font-size: 14px;
          margin-bottom: 7px;
        }
        .insight-card span {
          color: #64748b;
          font-size: 12px;
          line-height: 1.55;
        }
        div[data-testid="stPlotlyChart"] {
          background: #fff;
          border: 1px solid #e4edf7;
          border-radius: 10px;
          box-shadow: 0 10px 26px rgba(15, 59, 103, .055);
          padding: 5px;
        }
        .metric-card small {
          display: block;
          opacity: 0.82;
          font-size: 14px;
          margin-bottom: 10px;
        }
        .metric-card b {
          font-size: 29px;
          line-height: 1.1;
        }
        .metric-card span {
          font-size: 14px;
          margin-left: 4px;
          opacity: 0.9;
        }
        .metric-mark {
          width: 54px;
          height: 54px;
          border-radius: 8px;
          background: rgba(255,255,255,0.18);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 800;
        }
        .feature-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 14px;
        }
        .feature-card b,
        .route-card b,
        .idea-card b,
        .innovation-card b,
        .algorithm-card b {
          display: block;
          font-size: 18px;
          margin-bottom: 8px;
        }
        .feature-card span,
        .route-card span,
        .idea-card span,
        .innovation-card span,
        .mode-card span,
        .soft-panel span,
        .algorithm-card span {
          color: #64748b;
          line-height: 1.65;
        }
        .route-card {
          margin-bottom: 16px;
        }
        .flow-arrow {
          min-height: 250px;
          border-radius: 8px;
          background: #fff;
          border: 1px dashed #cbd5e1;
          display: flex;
          align-items: center;
          justify-content: center;
          text-align: center;
          color: #334155;
          font-size: 24px;
          font-weight: 800;
          line-height: 1.7;
        }
        .diagram-card {
          min-height: 250px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 22px;
        }
        .diagram-row {
          display: grid;
          grid-template-columns: 1fr auto 1fr auto 1fr;
          gap: 10px;
          align-items: center;
        }
        .diagram-row span {
          background: #f1f5f9;
          border-radius: 6px;
          padding: 12px;
          text-align: center;
        }
        .diagram-row b {
          color: #0ea5e9;
          font-size: 13px;
        }
        .soft-panel {
          min-height: 118px;
          margin-bottom: 12px;
        }
        .green-panel { background: #ecfdf5; border-color: #86efac; }
        .blue-panel { background: #eff6ff; border-color: #93c5fd; }
        .purple-panel { background: #faf5ff; border-color: #d8b4fe; }
        .orange-panel { background: #fff7ed; border-color: #fdba74; }
        .teal-panel { background: #f0fdfa; border-color: #5eead4; }
        .mode-card {
          min-height: 170px;
          margin-bottom: 16px;
        }
        .mode-card b {
          display: block;
          margin-top: 68px;
          font-size: 19px;
        }
        .mode-green { background: #ecfdf5; border-color: #bbf7d0; }
        .mode-blue { background: #eff6ff; border-color: #bfdbfe; }
        .mode-purple { background: #faf5ff; border-color: #e9d5ff; }
        .innovation-card {
          min-height: 260px;
          text-align: center;
        }
        .innovation-card div {
          width: 70px;
          height: 70px;
          border-radius: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 8px auto 24px;
          color: #fff;
          font-size: 25px;
          font-weight: 800;
          background: linear-gradient(135deg, #0ea5e9, #22c55e);
        }
        .wide-gradient {
          margin: 18px 0 28px;
          border-radius: 8px;
          background: linear-gradient(90deg, #2563eb, #22c55e);
          color: #fff;
          padding: 22px 28px;
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .wide-gradient b {
          font-size: 36px;
        }
        .best-strip {
          padding: 20px 24px;
          border-radius: 8px;
          background: #ecfdf5;
          border: 1px solid #bbf7d0;
          color: #166534;
          text-align: center;
          font-size: 20px;
          margin: 18px 0;
        }
        .cost-card {
          min-height: 150px;
          text-align: center;
        }
        .cost-card.selected {
          box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.2);
        }
        .cost-card b {
          display: block;
          font-size: 18px;
          margin-bottom: 16px;
        }
        .cost-card strong {
          font-size: 30px;
        }
        .empty-hint {
          background: #fff7ed;
          color: #9a3412;
          border: 1px solid #fed7aa;
          border-radius: 8px;
          padding: 18px 20px;
        }
        .badge {
          display: inline-block;
          padding: 8px 14px;
          border-radius: 999px;
          background: #e0f2fe;
          color: #0369a1;
          font-weight: 700;
          margin-bottom: 12px;
        }
        .pill {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 999px;
          background: #eef2ff;
          color: #4338ca;
          font-size: 12px;
          font-weight: 700;
          margin-right: 6px;
          margin-bottom: 6px;
        }
        .ok-box {
          background: #ecfdf5;
          border: 1px solid #bbf7d0;
          color: #166534;
          border-radius: 8px;
          padding: 14px 16px;
        }
        .warn-box {
          background: #fff7ed;
          border: 1px solid #fed7aa;
          color: #9a3412;
          border-radius: 8px;
          padding: 14px 16px;
        }
        div[data-testid="stMetric"] {
          background: #fff;
          padding: 16px;
          border-radius: 8px;
          border: 1px solid #edf2f7;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_title(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="page-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    st.markdown('<div class="title-underline"></div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="page-subtitle">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def section_label(text: str) -> None:
    st.markdown(f'<div class="section-label">{html.escape(text)}</div>', unsafe_allow_html=True)


def badge(text: str) -> None:
    st.markdown(f'<span class="badge">{html.escape(text)}</span>', unsafe_allow_html=True)


def pills(items: list[str]) -> None:
    rendered = "".join(f'<span class="pill">{html.escape(item)}</span>' for item in items)
    st.markdown(rendered, unsafe_allow_html=True)


def metric_card(label: str, value: str, unit: str, color: str = "blue", mark: str = "") -> None:
    gradient = GRADIENTS.get(color, GRADIENTS["blue"])
    st.markdown(
        f"""
        <div class="metric-card" style="background:{gradient}">
          <div>
            <small>{html.escape(label)}</small>
            <b>{html.escape(value)}</b><span>{html.escape(unit)}</span>
          </div>
          <div class="metric-mark">{html.escape(mark or label[:1])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dashboard_kpi(
    label: str,
    value: str,
    unit: str = "",
    note: str = "",
    color: str = "#2563eb",
) -> None:
    st.markdown(
        f"""
        <div class="dashboard-kpi" style="--kpi-color:{html.escape(color)}">
          <small>{html.escape(label)}</small>
          <b>{html.escape(value)}</b><span>{html.escape(unit)}</span>
          <em>{html.escape(note)}</em>
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_card(title: str, body: str, color: str = "#2563eb") -> None:
    st.markdown(
        f"""
        <div class="insight-card" style="--insight-color:{html.escape(color)}">
          <b>{html.escape(title)}</b>
          <span>{html.escape(body)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def green_direct_cost_card(title: str, cost: float, color: str, selected: bool = False) -> None:
    palette = {
        "green": "#16a34a",
        "blue": "#2563eb",
        "purple": "#9333ea",
    }
    st.markdown(
        f"""
        <div class="cost-card {'selected' if selected else ''}">
          <b>{html.escape(title)}</b>
          <span>预期成本</span><br>
          <strong style="color:{palette.get(color, '#2563eb')}">{cost:.1f}</strong>
          <span> 万元</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_hint(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="empty-hint">
          <b>{html.escape(title)}</b><br>
          <span>{html.escape(body)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_box(title: str, body: str, ok: bool = True) -> None:
    cls = "ok-box" if ok else "warn-box"
    st.markdown(
        f'<div class="{cls}"><b>{html.escape(title)}</b><br>{html.escape(body)}</div>',
        unsafe_allow_html=True,
    )
