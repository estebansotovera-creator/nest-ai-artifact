"""Evidence chain / provenance visualization.

Builds a small directed graph following the actual interface flow (Solis ->
interface variable -> Tharsis -> Meridian) rather than a generic force-directed
layout, so a viewer can read variable names and interface metadata directly
off the diagram.
"""

from typing import Optional

import networkx as nx
import plotly.graph_objects as go

from src.models import ExchangedVariable, Scenario

_MODEL_COLORS = {
    "Solis": "#1f77b4",
    "Interface": "#ff7f0e",
    "Tharsis": "#2ca02c",
    "Meridian": "#d62728",
}
_LAYER_LABELS = {0: "Solis", 1: "Interface", 2: "Tharsis", 3: "Meridian"}


def _get_exchanged(scenario: Scenario, variable_name: str) -> Optional[ExchangedVariable]:
    for v in scenario.exchanged_variables:
        if v.variable_name == variable_name:
            return v
    return None


def build_trace_graph(scenario: Scenario) -> nx.DiGraph:
    g = nx.DiGraph()
    ev = _get_exchanged(scenario, "available_power_mw")

    def add(node_id: str, label: str, layer: int, model: str) -> None:
        g.add_node(node_id, label=label, layer=layer, model=model)

    add(
        "solar_capacity_mw",
        f"Solar capacity\n{scenario.solis.solar_capacity_mw} MW",
        0,
        "Solis",
    )
    add(
        "battery_capacity_mw",
        f"Battery capacity\n{scenario.solis.battery_capacity_mw} MW",
        0,
        "Solis",
    )

    if ev is not None:
        interface_label = (
            f"available_power_mw = {ev.value} {ev.unit}\n"
            f"source: {ev.source_model} ({ev.source_version})\n"
            f"resolution: {ev.time_resolution} | confidence: {ev.confidence or 'n/a'}"
        )
    else:
        interface_label = "available_power_mw\n(no interface record)"
    add("available_power_mw", interface_label, 1, "Interface")

    add(
        "peak_demand_mw",
        f"Peak demand\n{scenario.tharsis.peak_demand_mw} MW",
        2,
        "Tharsis",
    )
    add(
        "critical_load_served_pct",
        f"Critical load served\n{scenario.tharsis.critical_load_served_pct}%",
        2,
        "Tharsis",
    )

    add(
        "required_critical_service_pct",
        f"Required critical service\n{scenario.meridian.required_critical_service_pct}%",
        3,
        "Meridian",
    )
    add(
        "stress_definition",
        f"Stress event: {scenario.meridian.stress_event}\nDuration: {scenario.meridian.duration_hours}h",
        3,
        "Meridian",
    )

    g.add_edge("solar_capacity_mw", "available_power_mw")
    g.add_edge("battery_capacity_mw", "available_power_mw")
    g.add_edge("available_power_mw", "peak_demand_mw", label="capacity check")
    g.add_edge("peak_demand_mw", "critical_load_served_pct", label="operational simulation")
    g.add_edge("critical_load_served_pct", "required_critical_service_pct", label="resilience check")
    g.add_edge("stress_definition", "required_critical_service_pct", label="stress context")

    return g


def render_trace_figure(g: nx.DiGraph) -> go.Figure:
    layer_nodes: dict = {}
    for node, data in g.nodes(data=True):
        layer_nodes.setdefault(data["layer"], []).append(node)

    pos = {}
    for layer, nodes in layer_nodes.items():
        count = len(nodes)
        for i, node in enumerate(nodes):
            y = (i - (count - 1) / 2) * 1.4
            pos[node] = (layer, y)

    edge_x, edge_y = [], []
    annotations = []
    for u, v, data in g.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        if data.get("label"):
            annotations.append(
                dict(
                    x=(x0 + x1) / 2,
                    y=(y0 + y1) / 2,
                    text=data["label"],
                    showarrow=False,
                    font=dict(size=10, color="#666"),
                    bgcolor="rgba(255,255,255,0.85)",
                )
            )

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines", line=dict(width=1.5, color="#999"), hoverinfo="none"
    )

    node_x, node_y, node_text, node_color, node_hover = [], [], [], [], []
    for node, data in g.nodes(data=True):
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(data["label"].split("\n")[0])
        node_color.append(_MODEL_COLORS.get(data["model"], "#888"))
        node_hover.append(data["label"].replace("\n", "<br>"))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="bottom center",
        hovertext=node_hover,
        hoverinfo="text",
        marker=dict(size=26, color=node_color, line=dict(width=1, color="white")),
    )

    for layer, label in _LAYER_LABELS.items():
        annotations.append(
            dict(x=layer, y=1.7, text=f"<b>{label}</b>", showarrow=False, font=dict(size=12))
        )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False,
        height=440,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(visible=False, range=[-0.6, 3.6]),
        yaxis=dict(visible=False, range=[-2.2, 2.2]),
        annotations=annotations,
        plot_bgcolor="white",
    )
    return fig
