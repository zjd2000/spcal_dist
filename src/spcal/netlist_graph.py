# netlist_graph.py

from __future__ import annotations

import os
import re
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from pydantic import BaseModel, Field, field_validator

from spcal.bdd_manager import BDD
from spcal.utils.load_files import load_functions
from spcal.utils.logger import logger


class NetlistEntry(BaseModel):
    """Base structure for a *cell* instance in a netlist.

    Each **input/output_wires** value stores four attributes:

        $port: {
            "wire":     str,                                    # connected net name
            "formula":  Optional[any],                          # BDD node. Boolean formula read from lib
            "function": Optional[List[any]],                    # BDD node. Boolean function while computing
            "value":    Optional[float]                         # probability result after evaluation
        }

    """

    cell_type: str = Field(..., description="Gate / cell type, e.g. NAND2")
    cell_name: str = Field(..., description="Instance name in the netlist")
    input_wires: Dict[str, Dict[str, Optional[Any]]] = Field(default_factory=dict)
    output_wires: Dict[str, Dict[str, Optional[Any]]] = Field(default_factory=dict)
    # Consider cycle iteration; denote whether the cell has been FULLY computed
    computed: bool = False

    @field_validator("cell_type", "cell_name", mode="before")
    def _strip_ws(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Empty value")
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
        bdd_backend: str,
    ):

        logger.info(
            f"Initializing NetlistGraph with lib_dir: {os.path.normpath(lib_dir)}, configs keys: {list(configs.keys())}, {len(netlist_entries)} netlist entries"
        )
        self._configs = configs
        self._netlist_dict: Dict[str, NetlistEntry] = {}
        self._graph: nx.DiGraph = nx.DiGraph()
        self._cell_names: List[str] = []

        self._has_cycle: bool = False
        self._functions: Dict[str, Dict[str, str]] = load_functions(lib_dir, configs)
        self._external_sp_inputs_spec: Dict[str, float] = configs[
            "external_sp_inputs_spec"
        ]
        self._bdd: BDD = BDD(backend=bdd_backend)
        self._bdd.declare()
        self._bdd_vars: Dict[str, Any] = {}

        self.parse_netlist_entries(netlist_entries)
        self.build_graph()

    def get_graph(self) -> nx.DiGraph:
        return self._graph

    def get_netlist_dict(self) -> Dict[str, NetlistEntry]:
        return self._netlist_dict

    def has_cycle(self) -> bool:
        return self._has_cycle

    def get_cell_names(self) -> List[str]:
        return self._cell_names

    def get_bdd(self):
        return self._bdd

    def cleanup(self) -> None:
        """Clean up BDD node references to avoid assertion errors on exit."""
        logger.info("Cleaning up BDD node references.")
        for entry in self._netlist_dict.values():
            for port_info in entry.input_wires.values():
                port_info["function"] = None
                port_info["formula"] = None
            for port_info in entry.output_wires.values():
                port_info["function"] = None
                port_info["formula"] = None
        self._bdd_vars.clear()

    def _bdd_var(self, name: str):
        node = self._bdd_vars.get(name)
        if node is None:
            self._bdd.declare(name)
            node = self._bdd.var(name)
            self._bdd_vars[name] = node
        return node

    def _parse_bool_formula_to_bdd(self, expr: str):
        s = expr.strip().replace("\n", "").replace(" ", "")
        s = re.sub(r"!", "~", s)
        s = s.replace("*", "&").replace("+", "|")

        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[~&|^()]", s)

        var_names: Set[str] = set(
            t for t in tokens if re.match(r"[A-Za-z_][A-Za-z0-9_]*", t)
        )
        V = {name: self._bdd_var(name) for name in var_names}

        expr_py_parts = []
        for t in tokens:
            if re.match(r"[A-Za-z_][A-Za-z0-9_]*", t):
                expr_py_parts.append(f"_V[{t!r}]")
            else:
                expr_py_parts.append(t)
        expr_py = "".join(expr_py_parts)

        return eval(expr_py, {"__builtins__": {}}, {"_V": V})

    def parse_netlist_entries(self, entries: List[str]) -> None:
        """Convert raw Verilog-style lines into :class:`NetlistEntry` objects."""
        logger.info(f"Parsing {len(entries)} netlist entries ...")
        for idx, entry in enumerate(entries):
            logger.debug(f"Parsing entry {idx + 1}/{len(entries)}: {entry}")
            res = self._parse_entry_line(entry)
            if res:
                self._netlist_dict[res.cell_name] = res
                logger.debug(f"Successfully parsed entry for cell {res.cell_name}")

    def _parse_entry_line(self, entry: str) -> Optional[NetlistEntry]:
        entry = entry.strip().rstrip(";")

        m = re.match(r"(\S+)\s+(\S+)\s*\((.+?)\)$", entry)
        if not m:
            logger.error("Failed to match entry pattern")
            raise ValueError("Unknown verilog")

        cell_type, cell_name, ports_str = m.groups()
        logger.debug(f"Matched cell type: {cell_type}, cell name: {cell_name}")
        self._cell_names.append(cell_name)
        nl_entry = NetlistEntry(cell_type=cell_type, cell_name=cell_name)

        in_prefixes = self._configs["port_prefixes"]["input"]
        out_prefixes = self._configs["port_prefixes"]["output"]

        for port, wire in re.findall(r"\.(\S+)\(\s*(.*?)\s*\)", ports_str):
            wire = wire.strip()
            pinfo: Dict[str, Optional[Any]] = {
                "wire": wire,
                "formula": None,
                "function": [],
                "value": None,
            }
            if any(port.startswith(pref.lstrip(".")) for pref in in_prefixes):
                if wire in self._external_sp_inputs_spec:
                    pinfo["function"] = [self._bdd_var(wire)]
                    logger.debug(
                        f"Input port {port} recognized as external '{wire}', function init with BDD var."
                    )
                nl_entry.input_wires[port] = pinfo
                logger.debug(f"Added input port {port} with wire {wire}")
            elif any(port.startswith(pref.lstrip(".")) for pref in out_prefixes):
                try:
                    raw_formula = self._functions[cell_type][port]
                except KeyError:
                    logger.error(
                        f"Function for {cell_type}:{port} not found in library."
                    )
                    raise ValueError

                try:
                    bdd_formula = self._parse_bool_formula_to_bdd(raw_formula)
                except Exception as e:
                    logger.error(
                        f"Failed to parse formula for {cell_type}:{port} -> {raw_formula}: {e}"
                    )
                    raise RuntimeError

                pinfo["formula"] = bdd_formula
                pinfo["function"] = []
                nl_entry.output_wires[port] = pinfo
                logger.debug(f"Added output port {port} with wire {wire}")
            else:
                logger.error(
                    f"Unknown port name: {port} ; Must check port_prefixes in yaml file."
                )
                raise RuntimeError("Unknown config")

        return nl_entry

    def build_graph(self) -> None:
        logger.debug("Clearing existing graph")
        self._graph.clear()
        wire2cell: Dict[str, str] = {}

        logger.info(f"Adding nodes to graph ...")

        for cell_name, entry in self._netlist_dict.items():
            self._graph.add_node(cell_name, type=entry.cell_type)
            for od in entry.output_wires.values():
                wire2cell[od["wire"]] = cell_name
                logger.debug(f"Added node {cell_name} of type {entry.cell_type}")

        logger.info("Adding edges to graph ...")
        for cell_name, entry in self._netlist_dict.items():
            for idata in entry.input_wires.values():
                drv = wire2cell.get(idata["wire"])
                if drv:
                    self._graph.add_edge(drv, cell_name, wire=idata["wire"])
                    logger.debug(
                        f"Added edge from {drv} to {cell_name} with wire {idata['wire']}"
                    )

        logger.info(
            f"Building graph successful. Number of nodes: {len(self._graph.nodes)}, Number of edges: {len(self._graph.edges)}"
        )

        sccs: List[Set[str]] = list(nx.strongly_connected_components(self._graph))

        if len(sccs) == 0:
            logger.info("No cycle found in the graph.")
            self._has_cycle = False
        else:
            logger.info(f"Found {len(sccs)} strongly connected components.")
            self._has_cycle = True

    def topological_sort(self) -> List[str]:
        if self._has_cycle:
            logger.info("Call relaxed_topological_sort() with cycle detected.")
            self._order = self.relaxed_topological_sort()
        else:
            logger.info("Call basic topological_sort() without cycle.")
            self._order = list(nx.topological_sort(self._graph))
        assert len(self._order) == len(self._graph.nodes), "Topological sort failed."
        logger.info(f"Topological sort is healty")

    def relaxed_topological_sort(self) -> List[str]:
        """
        ONLY FOR HINT, combined in CellIterator now.

        Produce a near-topological order for a directed netlist graph that may contain cycles.

        This routine detects feedback (back) edges with a global DFS and then runs
        Kahn's algorithm while *ignoring* those feedback edges when computing
        in-degrees. The result is a linear order that respects all acyclic
        dependencies and "relaxes" the cyclic ones. Additionally, it records which
        input ports on each node are fed by feedback wires so downstream passes
        (e.g., fixed-point evaluation) can insert placeholders.:

        - Label all back edges (feedback dependencies) with full graph DFS
        - Neglecting the in degree contribution of these back edges in Kahn topology

        Algorithm
        ---------
        1) Build adjacency:
            - `outgoing[u] = [(v, wire), ...]`
            - `incoming[v] = [(u, wire), ...]`
            - `vwire2ports[(v, wire)] = [input_port_names...]`
        2) Global DFS with colors:
            - WHITE (unvisited) → GRAY (on recursion stack) → BLACK (finished).
            - A GRAY target identifies a back edge (u → v, wire), added to `feedback_edges`.
            - BLACK targets (forward/cross edges) are ignored for cycle detection.
        3) Kahn topo on the acyclic remainder:
            - Compute effective in-degrees excluding `feedback_edges`.
            - Pop zero-in-degree nodes in order, updating only along non-feedback edges.
            - If some nodes remain (due to cycles), append them in a stable order.
        4) Placeholders for feedback inputs:
            - For each feedback edge (u → v, wire), look up `v`'s input ports driven by `wire`
            and store them as placeholders in `self._topo_placeholders`.
        """

        g = self._graph
        if g.number_of_nodes() == 0:
            logger.error("Graph is empty; relaxed_topological_sort() aborted.")
            raise ValueError("Empty graph")

        wire2cell: Dict[str, str] = {}
        for cell_name, entry in self._netlist_dict.items():
            for od in entry.output_wires.values():
                wire2cell[od["wire"]] = cell_name

        nodes: List[str] = sorted(self._netlist_dict.keys())

        # outgoing[u] = List[(v, wire)]
        outgoing: Dict[str, List[Tuple[str, str]]] = {n: [] for n in nodes}
        # incoming[v] = List[(u, wire)]
        incoming: Dict[str, List[Tuple[str, str]]] = {n: [] for n in nodes}
        # (v, wire) -> List[port]
        vwire2ports: Dict[Tuple[str, str], List[str]] = {}

        for v in nodes:
            entry_v = self._netlist_dict[v]
            for port, info in entry_v.input_wires.items():
                w = info["wire"]
                u = wire2cell.get(w)
                if not u:
                    continue
                outgoing[u].append((v, w))
                incoming[v].append((u, w))
                vwire2ports.setdefault((v, w), []).append(port)

        # global dfs to detect back edges
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in nodes}
        feedback_edges: Set[Tuple[str, str, str]] = set()  # (u, v, wire)

        for u in nodes:
            outgoing[u].sort(key=lambda t: (t[0], t[1]))  # (v, wire) sort

        def dfs(start: str) -> None:
            """
            standard DFS with colors:
            - WHITE: unvisited
            - GRAY: visiting
            - BLACK: visited
            """
            stack: List[Tuple[str, int]] = [(start, 0)]  # (node, next_edge_idx)
            color[start] = GRAY
            while stack:
                u, idx = stack[-1]
                if idx < len(outgoing[u]):
                    v, w = outgoing[u][idx]
                    stack[-1] = (u, idx + 1)
                    cu = color.get(v, WHITE)
                    if cu == WHITE:
                        color[v] = GRAY
                        stack.append((v, 0))
                    elif cu == GRAY:
                        # only GRAY is back edge
                        feedback_edges.add((u, v, w))
                    else:
                        # BLACK: forward/cross，ignore
                        pass
                else:
                    color[u] = BLACK
                    stack.pop()

        for n in nodes:
            if color[n] == WHITE:
                dfs(n)

        if feedback_edges:
            logger.info(f"Detected {len(feedback_edges)} feedback edges.")
        else:
            logger.error("Call relaxed_topological_sort() but no feedback edges found.")
            raise RuntimeError("Fatal")

        # Kahn topo sort (ignore back edges)
        effective_indeg: Dict[str, int] = {n: 0 for n in nodes}
        for v in nodes:
            indeg = 0
            for u, w in incoming[v]:
                if (u, v, w) not in feedback_edges:
                    indeg += 1
            effective_indeg[v] = indeg

        q = deque(sorted([n for n in nodes if effective_indeg[n] == 0]))
        order: List[str] = []

        while q:
            u = q.popleft()
            order.append(u)
            for v, w in outgoing[u]:
                if (u, v, w) in feedback_edges:
                    continue
                effective_indeg[v] -= 1
                if effective_indeg[v] == 0:
                    q.append(v)

        if len(order) != len(nodes):
            remaining = [n for n in nodes if n not in order]
            logger.warning(
                "relaxed_topological_sort: order does not cover all nodes after removing back edges. "
                f"Falling back by appending remaining nodes: {remaining}"
            )
            order.extend(remaining)

        # gen placeholder tag
        placeholders: Dict[str, List[Tuple[str, str]]] = (
            {}
        )  # cell_name -> List[(port, wire)]
        for u, v, w in feedback_edges:
            ports = vwire2ports.get((v, w), [])
            if not ports:
                logger.error(
                    f"Placeholder mapping: for feedback edge ({u} -> {v}, wire={w}) "
                    f"no input port found on node '{v}'."
                )
                raise RuntimeError("Fatal")
            for p in ports:
                placeholders.setdefault(v, []).append((p, w))

        for v in placeholders:
            placeholders[v] = sorted(
                list(set(placeholders[v])), key=lambda t: (t[0], t[1])
            )

        logger.info(
            "relaxed_topological_sort finished. "
            f"Nodes: {len(nodes)}, Order length: {len(order)}, "
            f"Feedback edges: {len(feedback_edges)}, "
            f"Nodes with placeholders: {len(placeholders)}"
        )

        self._topo_placeholders = placeholders
        self._topo_feedback_edges = feedback_edges

        return order
