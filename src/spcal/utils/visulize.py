from typing import Dict

import matplotlib.pyplot as plt
import networkx as nx
import plotly.graph_objects as go
from networkx.drawing.nx_agraph import graphviz_layout

from spcal.netlist_graph import NetlistEntry


def visualize_netlist_graph(graph: nx.DiGraph, filename="netlist_graph.png"):
    """
    Visualize the netlist graph using matplotlib and networkx, and save it to a file.
    """
    plt.figure(figsize=(20, 16))
    pos = nx.spring_layout(graph)

    nx.draw_networkx_nodes(graph, pos, node_size=500, node_color="lightblue")
    nx.draw_networkx_labels(graph, pos, font_size=10)

    nx.draw_networkx_edges(graph, pos, arrowstyle="->", arrowsize=20)
    edge_labels = nx.get_edge_attributes(graph, "wire")
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=8)

    plt.title("Netlist Graph Visualization")
    plt.axis("off")

    plt.savefig(filename)
    plt.close()
    # print(f"Graph saved as {filename}")


def visualize_interactive_netlist_graph(
    graph: nx.DiGraph, filename="netlist_graph_interactive.html"
):
    """
    Visualize the netlist graph as an interactive plot using Plotly and save it as an HTML file.
    """
    pos = nx.spring_layout(graph)

    x_nodes = [pos[node][0] for node in graph.nodes]
    y_nodes = [pos[node][1] for node in graph.nodes]
    node_text = [f"{node} ({graph.nodes[node]['type']})" for node in graph.nodes]

    edge_x = []
    edge_y = []
    edge_text = []

    for edge in graph.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_text.append(f"{edge[0]} -> {edge[1]} (wire: {edge[2].get('wire', '')})")

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="black"),
        hoverinfo="text",
        text=edge_text,
        mode="lines",
    )

    node_trace = go.Scatter(
        x=x_nodes,
        y=y_nodes,
        mode="markers+text",
        text=node_text,
        hoverinfo="text",
        marker=dict(size=10, color="lightblue", line_width=2),
    )

    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title="Interactive Netlist Graph",
            titlefont_size=16,
            showlegend=False,
            hovermode="closest",
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        ),
    )

    fig.write_html(filename)
    # print(f"Interactive graph saved as {filename}")
