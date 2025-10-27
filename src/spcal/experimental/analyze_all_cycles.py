# main.py
import os
import pickle
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import plotly.graph_objects as go
import typer
from pydantic import BaseModel, Field, field_validator

from spcal.utils.load_files import load_config, load_functions, load_netlist
from spcal.utils.logger import logger

os.environ["LOG_LEVEL"] = "INFO"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

app = typer.Typer()
base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")


class NetlistEntry(BaseModel):
    """Pydantic model for a *single* cell instance in a flattened netlist.

    Each **port** now stores three parallel attributes::

        {
            "wire":     str,                                    # connected net name
            "function": Optional[str],                          # Boolean function (filled on demand)
            "value":    Optional[Union[float, List[float]]]}    # probability result after evaluation
        }

    The *function* field is lazily annotated, whereas *value* is filled when the
    evaluator computes probabilities.  This change is fully backward-compatible
    for code that only read the old keys (`wire`, `function`).

    """

    cell_type: str = Field(..., description="Gate / cell type, e.g. NAND2")
    cell_name: str = Field(..., description="Instance name in the netlist")
    input_wires: Dict[str, Dict[str, Optional[Any]]] = Field(default_factory=dict)
    output_wires: Dict[str, Dict[str, Optional[Any]]] = Field(default_factory=dict)
    computed: bool = False

    @field_validator("cell_type", "cell_name", mode="before")
    def _strip_ws(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("value must not be empty")
        return v


class NetlistGraph:
    """Facade around *networkx* that keeps **all** pin functions in RAM.

    *   `load_functions()` is invoked once during construction, parsing every
        library JSON listed in `configs["libraries"]`.  The resulting mapping
        `cell_type ➜ { port_name : function }` is cached in `self._functions`.
    *   During reverse-BFS we merely look up the already-loaded dictionary to
        annotate the handful of cells along the critical path.
    """

    def __init__(
        self,
        lib_dir: str,
        configs: Dict[str, Any],
        netlist_entries: List[str],
        ignore_cycle=False,
    ):

        logger.info(
            f"Initializing NetlistGraph with lib_dir: {lib_dir}, configs keys: {list(configs.keys())}, {len(netlist_entries)} netlist entries"
        )

        self._configs = configs
        self._ignore_cycle = ignore_cycle
        self._functions: Dict[str, Dict[str, str]] = load_functions(lib_dir, configs)
        self._netlist_dict: Dict[str, NetlistEntry] = {}
        self._graph: nx.DiGraph = nx.DiGraph()
        self._cycles: List[List[str]] = []
        self._dag: nx.DiGraph = nx.DiGraph()
        self._node2cycle: Dict[str, int] = {}

        self.parse_netlist_entries(netlist_entries)
        self.build_graph()

    def get_graph(self) -> nx.DiGraph:
        return self._graph

    def get_netlist_dict(self) -> Dict[str, NetlistEntry]:
        return self._netlist_dict

    def get_all_cycles(self) -> List[List[str]]:
        return self._cycles

    def get_acyclic_graph(self) -> nx.DiGraph:
        return self._dag

    def has_cycle(self) -> bool:
        return self._cycles != []

    def get_node_cycle_id(self, node: str) -> int:
        return self._node2cycle.get(node, -1)

    def get_cycle(self, cycle_id: int) -> List[str]:
        return self._cycles[cycle_id]

    def parse_netlist_entries(self, entries: List[str]) -> None:
        """Convert raw Verilog-style lines into :class:`NetlistEntry` objects."""
        logger.info(f"Parsing {len(entries)} netlist entries ...")
        for idx, entry in enumerate(entries):
            logger.debug(f"Parsing entry {idx + 1}/{len(entries)}: {entry}")
            res = self._parse_nl_entry(entry)
            if res:
                self._netlist_dict[res.cell_name] = res
                logger.debug(f"Successfully parsed entry for cell {res.cell_name}")

    def _parse_nl_entry(self, entry: str) -> Optional[NetlistEntry]:
        entry = entry.strip().rstrip(";")
        logger.debug(f"Processing cleaned entry: {entry}")
        m = re.match(r"(\S+)\s+(\S+)\s*\((.+?)\)$", entry)
        if not m:
            logger.error("Failed to match entry pattern")
            raise ValueError("Invalid netlist entry format.")

        cell_type, cell_name, ports_str = m.groups()
        logger.debug(f"Matched cell type: {cell_type}, cell name: {cell_name}")
        nl_entry = NetlistEntry(cell_type=cell_type, cell_name=cell_name)

        in_prefixes = self._configs["port_prefixes"]["input"]
        out_prefixes = self._configs["port_prefixes"]["output"]
        # logger.info(f"Input prefixes: {in_prefixes}, Output prefixes: {out_prefixes}")

        for port, wire in re.findall(r"\.(\S+)\(\s*(.*?)\s*\)", ports_str):
            pinfo = {"wire": wire, "function": None, "value": None}
            if any(port.startswith(pref[1:]) for pref in in_prefixes):
                nl_entry.input_wires[port] = pinfo
                logger.debug(f"Added input port {port} with wire {wire}")
            elif any(port.startswith(pref[1:]) for pref in out_prefixes):
                nl_entry.output_wires[port] = pinfo
                logger.debug(f"Added output port {port} with wire {wire}")
            else:
                logger.error(
                    f"Unknown port name: {port} ; Must check port_prefixes in yaml file."
                )
                raise RuntimeError(f"Unknown port connection: {port}")
        return nl_entry

    def build_graph(self) -> None:
        logger.debug("Clearing existing graph")
        self._graph.clear()
        wire2driver: Dict[str, str] = {}

        logger.info(f"Adding nodes to graph ...")

        for cell_name, entry in self._netlist_dict.items():
            self._graph.add_node(
                cell_name, type=entry.cell_type, input_wires=entry.input_wires
            )
            for od in entry.output_wires.values():
                wire2driver[od["wire"]] = cell_name
            logger.debug(f"Added node {cell_name} of type {entry.cell_type}")

        logger.info("Adding edges to graph ...")
        for cell_name, entry in self._netlist_dict.items():
            for idata in entry.input_wires.values():
                drv = wire2driver.get(idata["wire"])
                if drv:
                    self._graph.add_edge(drv, cell_name, wire=idata["wire"])
                    logger.debug(
                        f"Added edge from {drv} to {cell_name} with wire {idata['wire']}"
                    )

        logger.info(
            f"Building graph successful. Number of nodes: {len(self._graph.nodes)}, Number of edges: {len(self._graph.edges)}"
        )

        if self._ignore_cycle:
            logger.warning(
                f"User force ignoring cycles. May occor failare in computing!"
            )
            self._dag = self._graph
            return

        sccs: List[Set[str]] = list(nx.strongly_connected_components(self._graph))
        self._cycles = []
        for comp in sccs:
            if len(comp) <= 1:
                continue
            cycle_nodes = next(nx.simple_cycles(self._graph.subgraph(comp)))
            self._cycles.append(cycle_nodes)

        if self._cycles is []:
            logger.info(f"Graph has no cycle.")
            self._dag = self._graph
            return

        for cid, comp in enumerate(self._cycles):
            for n in comp:
                self._node2cycle[n] = cid
        for n in self._graph.nodes:
            self._node2cycle.setdefault(n, -1)

        def cycle_node(cid: int) -> str:
            return f"__CYCLE_{cid}__"

        for cid, comp in enumerate(self._cycles):
            self._dag.add_node(
                cycle_node(cid),
                is_cycle=True,
                members=comp,
            )

        for n in self._graph.nodes:
            if self._node2cycle[n] == -1:
                self._dag.add_node(n, is_cycle=False)

        for u, v, data in self._graph.edges(data=True):
            su = cycle_node(self._node2cycle[u]) if self._node2cycle[u] != -1 else u
            sv = cycle_node(self._node2cycle[v]) if self._node2cycle[v] != -1 else v
            if su != sv:
                if not self._dag.has_edge(su, sv):
                    self._dag.add_edge(su, sv, **data)

        assert not list(
            nx.simple_cycles(self._dag)
        ), "Condensed graph unexpectedly contains cycles"


def generate_cycle_report(graph: nx.DiGraph, output_dir: str) -> None:

    os.makedirs(output_dir, exist_ok=True)

    logger.info("Detecting all cycles ...")
    all_cycles: List[List[str]] = list(nx.simple_cycles(graph))
    logger.info(f"Total cycles detected: {len(all_cycles)}")

    def cyc_edges(cyc: List[str]) -> Set[Tuple[str, str]]:
        return {(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))}

    edge_sets = [cyc_edges(c) for c in all_cycles]
    label = ["unclassified"] * len(all_cycles)
    for i, ei in enumerate(edge_sets):
        if label[i] != "unclassified":
            continue
        label[i] = "single"
        for j in range(i + 1, len(edge_sets)):
            if label[j] == "unclassified" and ei & edge_sets[j]:
                label[i] = label[j] = "multi"

    single_ids, multi_ids = [], []
    seen = set()
    for i, lab in enumerate(label):
        fs = frozenset(edge_sets[i])
        if fs in seen:
            continue
        seen.add(fs)
        (single_ids if lab == "single" else multi_ids).append(i)

    txt_single_path = os.path.join(output_dir, "single_cycle_details.txt")
    txt_multi_path = os.path.join(output_dir, "multi_cycle_details.txt")
    with open(txt_single_path, "w") as f:
        f.write("== SINGLE CYCLES ==\n")
        for rank, idx in enumerate(single_ids):
            f.write(f"{rank}. [{idx}]: {' → '.join(all_cycles[idx])}\n")
        logger.info(
            f"[Report] single_cycle_details.txt written with {len(single_ids)} entries"
        )

    with open(txt_multi_path, "w") as f:
        f.write("\n== MULTI/OVERLAPPING CYCLES ==\n")
        for rank, idx in enumerate(multi_ids, start=len(single_ids)):
            f.write(f"{rank}. [{idx}]: {' → '.join(all_cycles[idx])}\n")
        logger.info(
            f"[Report] multi_cycle_details.txt written with {len(multi_ids)} entries"
        )

    dump_obj = {
        "all_cycles": all_cycles,  # list[list[str]]
        "single_ids": single_ids,  # list[int]
        "multi_ids": multi_ids,  # list[int]
    }
    dump_path = os.path.join(output_dir, "cycle_data.pkl")
    with open(dump_path, "wb") as fp:
        pickle.dump(dump_obj, fp)
    logger.info(f"[Dump] cycle_data.pkl saved ({dump_path})")


def draw_cycle_groups(
    dump_path: str,
    output_dir: str,
    cycle_groups: List[List[int]],
) -> None:

    if not os.path.exists(dump_path):
        raise FileNotFoundError(f"{dump_path} not found, run build first")

    with open(dump_path, "rb") as fp:
        data = pickle.load(fp)
    all_cycles: List[List[str]] = data["all_cycles"]

    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Loaded {len(all_cycles)} cycles from dump. Start drawing ...")

    COLORS = [
        "#1f77b4",  # blue
        "#d62728",  # red
        "#2ca02c",  # green
        "#9467bd",  # purple
        "#ff7f0e",  # orange
        "#17becf",  # cyan
        "#e377c2",  # pink
        "#bcbd22",  # olive
        "#8c564b",  # brown
        "#7f7f7f",  # gray
    ]

    for g_idx, id_list in enumerate(cycle_groups):
        id_tag = "_".join(str(i) for i in id_list)
        out_html = os.path.join(output_dir, f"cycle_[{id_tag}].html")

        if os.path.exists(out_html):
            logger.warning(f"[Draw] Group {g_idx} already exists, skip")
            continue

        cycles = [all_cycles[i] for i in id_list if i < len(all_cycles)]
        if not cycles:
            logger.warning(f"Group {g_idx} empty, skip")
            continue

        node_cnt: Dict[str, int] = {}
        edge_cnt: Dict[Tuple[str, str], int] = {}
        for cyc in cycles:
            for n in cyc:
                node_cnt[n] = node_cnt.get(n, 0) + 1
            for e in [(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))]:
                edge_cnt[e] = edge_cnt.get(e, 0) + 1

        overlap_nodes = {n for n, c in node_cnt.items() if c > 1}
        overlap_edges = {e for e, c in edge_cnt.items() if c > 1}

        sub_g = nx.DiGraph()
        for cyc in cycles:
            sub_g.add_nodes_from(cyc)
            sub_g.add_edges_from(
                (cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))
            )
        try:
            pos = nx.kamada_kawai_layout(sub_g)
        except Exception:
            pos = nx.spring_layout(sub_g, seed=42)

        N = sub_g.number_of_nodes()
        node_size = max(6, min(30, int(200 / np.sqrt(N))))
        font_size = max(8, min(16, int(120 / np.sqrt(N))))
        canvas = max(600, min(2000, 40 * N))

        cyc_color_map: Dict[int, str] = {}
        for idx, cyc_id in enumerate(id_list):
            cyc_color_map[cyc_id] = COLORS[idx % len(COLORS)]

        node_color_single: Dict[str, str] = {}
        for cyc_id, cyc in zip(id_list, cycles):
            color_hex = cyc_color_map[cyc_id]
            for n in cyc:
                if n not in overlap_nodes:
                    node_color_single[n] = color_hex

        fig = go.Figure()

        # private edge
        for cyc_id, cyc in zip(id_list, cycles):
            color_hex = cyc_color_map[cyc_id]
            edges_cyc = [(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))]
            edges_unique = [e for e in edges_cyc if e not in overlap_edges]
            if not edges_unique:
                continue
            x, y = [], []
            for u, v in edges_unique:
                x += [pos[u][0], pos[v][0], None]
                y += [pos[u][1], pos[v][1], None]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    line=dict(width=1.5, color=color_hex),
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        # public edge
        if overlap_edges:
            mix_rgb = (
                np.mean(
                    [
                        np.array(
                            tuple(int(c.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
                        )
                        for c in cyc_color_map.values()
                    ],
                    axis=0,
                )
                / 255.0
            )
            mix_hex = "rgb({},{},{})".format(
                int(mix_rgb[0] * 255), int(mix_rgb[1] * 255), int(mix_rgb[2] * 255)
            )
            x, y = [], []
            for u, v in overlap_edges:
                x += [pos[u][0], pos[v][0], None]
                y += [pos[u][1], pos[v][1], None]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    line=dict(width=3, color=mix_hex),
                    hoverinfo="none",
                    showlegend=False,
                )
            )

        # private node
        if node_color_single:
            x = [pos[n][0] for n in node_color_single]
            y = [pos[n][1] for n in node_color_single]
            color_list = list(node_color_single.values())
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers+text",
                    marker=dict(
                        size=node_size,
                        symbol="circle-open",
                        color=color_list,
                        line=dict(width=1),
                    ),
                    text=[n for n in node_color_single],
                    textposition="top center",
                    textfont=dict(size=font_size),
                    hoverinfo="text",
                    showlegend=False,
                )
            )

        # public node
        if overlap_nodes:
            x = [pos[n][0] for n in overlap_nodes]
            y = [pos[n][1] for n in overlap_nodes]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="markers+text",
                    marker=dict(
                        size=node_size + 4,
                        symbol="circle",
                        color=mix_hex,
                        line=dict(width=1),
                    ),
                    text=[n for n in overlap_nodes],
                    textposition="top center",
                    textfont=dict(size=font_size),
                    hoverinfo="text",
                    showlegend=False,
                )
            )

        fig.update_layout(
            title=f"Cycle Group {g_idx}: {id_list}",
            width=canvas,
            height=canvas,
            xaxis=dict(showgrid=False, zeroline=False, visible=False),
            yaxis=dict(showgrid=False, zeroline=False, visible=False),
            plot_bgcolor="white",
        )

        fig.write_html(out_html, include_plotlyjs="cdn")
        logger.info(f"[Draw] Group {g_idx} saved to {out_html}")


@app.command(name="sp")
def sp(
    cell,
    data_dir,
    netlist,
    config,
    output,
    overwrite,
):

    output_dir = os.path.join(base_dir, output)
    lib_dir = os.path.join(base_dir, data_dir, "lib")

    os.makedirs(os.path.join(base_dir, "outputs"), exist_ok=True)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    elif overwrite:
        os.system(f"rm -rf {output_dir}")
        os.makedirs(output_dir)
    else:
        typer.confirm(
            f"Output directory '{output_dir}' already exists. Do you want to continue?",
            abort=True,
        )

    if cell == "":
        cell = typer.prompt("Enter the target cell to compute the SP on the call path")

    start_time = time.perf_counter()
    cfg = load_config(os.path.join(base_dir, config))
    netlist_entries = load_netlist(os.path.join(base_dir, netlist))
    netlist_graph_obj = NetlistGraph(lib_dir, cfg, netlist_entries, True)
    generate_cycle_report(netlist_graph_obj.get_graph(), output_dir)
    logger.info(f"Build Time: {time.perf_counter() - start_time:.2f} seconds")


def build():
    arg = {
        "cell": "NAND2_6",
        "data_dir": "spcal_data",
        "netlist": "demo/riscv/riscv_flattened.v",
        "config": "demo/riscv/riscv.yaml",
        "output": "demo/riscv/results",
        "overwrite": "True",
    }

    sp(**arg)


def draw(my_groups):
    arg = {
        "dump_path": "demo/riscv/results/cycle_data.pkl",
        "output_dir": "demo/riscv/results/figs",
    }

    draw_cycle_groups(**arg, cycle_groups=my_groups)


def main(run_build, run_draw, fig_groups):
    assert run_build != run_draw

    if run_build:
        build()
    elif run_draw:
        draw(fig_groups)


if __name__ == "__main__":

    run_build = 0
    run_draw = 1
    fig_groups = [[82498], [0, 1, 2, 3], [39900, 39901, 39902]]

    main(run_build, run_draw, fig_groups)
