# cell_iterator.py

from __future__ import annotations

import json
import os
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from dd.autoref import BDD

from spcal.utils.logger import logger

from .netlist_graph import NetlistEntry, NetlistGraph


class CellIterator:
    """
    Build symbolic BDD functions for each netlist port.
    """

    def __init__(self, netlist: NetlistGraph):
        self.net = netlist
        self.g: nx.DiGraph = netlist.get_graph()
        self.entries: Dict[str, NetlistEntry] = netlist.get_netlist_dict()
        self.bdd: BDD = netlist._bdd  # type: ignore[attr-defined]

        # Graph topology
        self._nodes: List[str] = []
        self._outgoing: Dict[str, List[Tuple[str, str]]] = {}
        self._incoming: Dict[str, List[Tuple[str, str]]] = {}
        self._vwire2ports: Dict[Tuple[str, str], List[str]] = {}
        self._wire2src: Dict[str, str] = {}

        # Feedback edges from DFS
        self._feedback_edges: Set[Tuple[str, str, str]] = set()

        # Record which placeholders were injected: {cell: {port: "__ph__wire"}}
        self._injected_placeholders: Dict[str, Dict[str, str]] = {}

    def run(
        self,
        max_rounds: int = 1000,
        dump_path: Optional[str] = None,
        dump_format: str = "dag",
    ):

        self._build_indices()
        self._detect_feedback_edges()

        logger.info("CellIterator First pass (near-topo)")
        pending = self._first_pass()
        assert not pending, f"First pass failed: {pending}"

        # Optionally dump results
        if dump_path is not None:
            self.dump_functions(
                dump_path, include_formulas=True, dump_format=dump_format
            )

        summary = {
            "nodes": len(self._nodes),
            "feedback_edges": len(self._feedback_edges),
            "placeholders_injected": self._injected_placeholders,
            "dump_path": dump_path,
            "dump_format": dump_format,
        }
        logger.info(f"CellIterator Finished. Summary: {summary}")
        return summary

    def _build_indices(self) -> None:
        """Build adjacency and (v, wire)->ports mapping."""
        self._nodes = sorted(self.entries.keys())
        self._outgoing = {n: [] for n in self._nodes}
        self._incoming = {n: [] for n in self._nodes}
        self._vwire2ports = {}
        self._wire2src = {}

        # Map wire -> source cell
        for u, ent_u in self.entries.items():
            for od in ent_u.output_wires.values():
                self._wire2src[od["wire"]] = u

        # Build adjacency
        for v, ent_v in self.entries.items():
            for p, info in ent_v.input_wires.items():
                w = info["wire"]
                u = self._wire2src.get(w)
                if not u:
                    continue
                self._outgoing[u].append((v, w))
                self._incoming[v].append((u, w))
                self._vwire2ports.setdefault((v, w), []).append(p)

        # Deterministic ordering
        for u in self._nodes:
            self._outgoing[u].sort(key=lambda t: (t[0], t[1]))
        for v in self._nodes:
            self._incoming[v].sort(key=lambda t: (t[0], t[1]))
        logger.debug(f"[indices] outgoing={len(self._outgoing)}")
        logger.debug(f"[indices] incoming={len(self._incoming)}")

    def _detect_feedback_edges(self):
        """Detect back-edges via DFS color marking."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in self._nodes}
        self._feedback_edges.clear()

        def dfs(start: str):
            stack = [(start, 0)]
            color[start] = GRAY
            while stack:
                u, idx = stack[-1]
                outs = self._outgoing[u]
                if idx < len(outs):
                    v, w = outs[idx]
                    stack[-1] = (u, idx + 1)
                    if color[v] == WHITE:
                        color[v] = GRAY
                        stack.append((v, 0))
                    elif color[v] == GRAY:
                        self._feedback_edges.add((u, v, w))
                else:
                    color[u] = BLACK
                    stack.pop()

        for n in self._nodes:
            if color[n] == WHITE:
                dfs(n)

        logger.info(f"Detected {len(self._feedback_edges)} feedback edges")
        if self._feedback_edges:
            logger.debug(f"[feedback] edges={self._feedback_edges}")

    def _first_pass(self) -> Set[str]:
        """
        Perform near-topological propagation ignoring feedback in-degrees.
        Return nodes that still need cycle propagation.
        """
        fbedge = self._feedback_edges
        indeg = {n: 0 for n in self._nodes}
        for v in self._nodes:
            indeg[v] = sum(1 for (u, w) in self._incoming[v] if (u, v, w) not in fbedge)

        q = deque(n for n in self._nodes if indeg[n] == 0)
        visited = set()
        pending = set()

        logger.info(f"[first] queue={list(q)}")
        while q:
            u = q.popleft()
            visited.add(u)
            logger.debug(f"[first] pop: {u}")

            self._try_compute_node(u, phase="first")

            for v, w in self._outgoing[u]:
                if (u, v, w) not in fbedge:
                    indeg[v] -= 1
                    if indeg[v] == 0 and v not in visited:
                        q.append(v)

        for n in self._nodes:
            if n not in visited:
                pending.add(n)

        logger.info(f"[first] pending nodes={sorted(pending)}")
        return pending

    def _try_compute_node(self, u: str, *, phase: str):
        """
        For node u, attempt to produce output port functions by substituting
        known or placeholder-based input functions into the formula.

        Enforces per-output-port admission constraint:
            one placeholder -> at most one f(placeholder).
        """
        ent = self.entries[u]

        for oport, oinfo in ent.output_wires.items():
            formula = oinfo.get("formula")
            if formula is None:
                continue

            needed_ports = sorted(self.bdd.support(formula))
            logger.debug(
                f"[{phase}][{u}:{oport}] needs={needed_ports}:{[ent.input_wires[p].get('wire') for p in needed_ports]}"
            )

            # Prepare input candidate lists; lazy-inject placeholders where needed.
            port_funcs: List[Any] = []
            complete = True
            for p in needed_ports:
                f_in = ent.input_wires[p].get("function") or []
                if not f_in:
                    if self._is_feedback_input(u, p):
                        ph_node = self._inject_placeholder(u, p)  # write-back + record
                        f_in = [ph_node]
                    else:
                        complete = False
                port_funcs.append(f_in)

            if not complete:
                logger.error(f"[{phase}][{u}:{oport}] skip due to incomplete inputs")
                continue

            candidate_set: Set[Any] = set()

            # only use the first function for each port
            mapping = {
                p: func_list[0] for p, func_list in zip(needed_ports, port_funcs)
            }
            out = self.bdd.let(mapping, formula)
            candidate_set.add(out)
            logger.debug(
                f"[{phase}][{u}:{oport}] let({mapping}) -> {out} ({[v for v in self.bdd.support(out) if isinstance(v, str)]})"
            )

            if not candidate_set:
                logger.debug(
                    f"[{phase}][{u}:{oport}] no new candidates after filtering"
                )
                continue

            # UNION with existing output functions, deduplicate
            dst = oinfo.get("function") or []
            added = False
            s = set(dst)
            for f in candidate_set:
                if f not in s:
                    dst.append(f)
                    s.add(f)
                    added = True
            oinfo["function"] = dst

            # Push to downstream
            if added:
                self._push_output_to_sinks(u, oinfo["wire"], list(candidate_set))
                logger.debug(
                    f"[{phase}][{u}:{oport}] +{len(candidate_set)} new funcs (total={len(dst)})"
                )

    def _is_feedback_input(self, cell: str, port: str) -> bool:
        """Return True iff input (cell,port) is driven by a feedback edge."""
        wire = self.entries[cell].input_wires[port]["wire"]
        drv = self._wire2src.get(wire)
        if not drv:
            return False
        return (drv, cell, wire) in self._feedback_edges

    def _inject_placeholder(self, cell: str, port: str):
        """
        Lazy inject __ph__{wire} placeholder and WRITE it into the input port
        function list. Also record it for debugging.
        """
        wire = self.entries[cell].input_wires[port]["wire"]
        ph_name = f"__ph__{wire}"

        # BDD declare if not exists
        if ph_name not in self.net._bdd_vars:  # type: ignore[attr-defined]
            self.net._bdd.declare(ph_name)  # type: ignore[attr-defined]
            self.net._bdd_vars[ph_name] = self.net._bdd.var(ph_name)  # type: ignore[attr-defined]
            logger.debug(f"[placeholder] declared BDD var {ph_name}")

        node = self.net._bdd_vars[ph_name]  # type: ignore[attr-defined]

        # WRITE BACK into the input port functions (idempotent)
        pinfo = self.entries[cell].input_wires[port]
        flist = pinfo.get("function")
        if not flist:
            pinfo["function"] = [node]
        else:
            if node not in flist:
                flist.append(node)

        # Record for debugging
        self._injected_placeholders.setdefault(cell, {})[port] = ph_name
        logger.info(f"[placeholder] injected {ph_name} into {cell}.{port} (feedback)")

        return node

    def _push_output_to_sinks(self, u: str, wire: str, new_funcs: List[Any]) -> None:
        """
        For each successor v that consumes 'wire', append the new functions
        to the corresponding input ports of v (append-unique).
        """
        for v, w in self._outgoing[u]:
            if w != wire:
                continue
            ports = self._vwire2ports.get((v, wire), [])
            if not ports:
                continue
            ent_v = self.entries[v]
            for p in ports:
                flist = ent_v.input_wires[p].get("function")
                if not flist:
                    ent_v.input_wires[p]["function"] = list(new_funcs)
                else:
                    s = set(flist)
                    for f in new_funcs:
                        if f not in s:
                            flist.append(f)
                            s.add(f)

    def dump_functions(
        self, path: str, include_formulas: bool = True, dump_format: str = "dag"
    ):
        """
        Dump all port functions and (optionally) raw formulas.
        Formats:
          - "dag": compact BDD DAG with node table
          - "expr": human-readable boolean expressions
        Placeholders keep the '__ph__' prefix.
        """
        logger.info(f"[dump] writing => {path} (format={dump_format})")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        if dump_format == "dag":
            payload = self._dump_as_dag(include_formulas)
        elif dump_format == "expr":
            payload = self._dump_as_expr(include_formulas)
        else:
            raise ValueError('dump_format must be "dag" or "expr"')

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.info(f"[dump] file written: {path}")

    def _dump_as_dag(self, include_formulas: bool) -> Dict[str, Any]:
        """
        Dump a compact BDD DAG with a node table, *preserving complemented-edge signs*.
        """
        nodes_tbl: Dict[str, Dict[str, str]] = {}

        # Map a backend base node object (non-complemented) -> our structural id string
        struct_id_map: Dict[Any, str] = {}
        next_sid = 0  # auto-increment id

        def base_and_sign(f):
            """
            Return (base_non_complemented_node, is_complemented_reference).
            Works across autoref/cudd backends since we only use public ops.
            """
            if getattr(f, "negated", False):
                return (~f), True
            return f, False

        def ensure_struct_id(base_f) -> str:
            """
            Assign (or return existing) structural id for a base, non-complemented node.
            """
            nonlocal next_sid
            sid = struct_id_map.get(base_f)
            if sid is None:
                sid = str(next_sid)
                struct_id_map[base_f] = sid
                next_sid += 1
            return sid

        def ref_id(f) -> str:
            """
            Return the *reference ID* string for any function `f`.
            - For terminals, return "1" or "0".
            - For non-terminals, return "<sign><sid>", where sign is "" or "-".
            """
            if f == self.bdd.true:
                return "1"
            if f == self.bdd.false:
                return "0"
            base_f, is_neg = base_and_sign(f)
            sid = ensure_struct_id(base_f)
            return f"-{sid}" if is_neg else sid

        def materialize_structure(f) -> None:
            """
            Ensure the *structural* (non-complemented) node for function `f` is present
            in the node table, and recursively materialize its children.
            """
            if f == self.bdd.true or f == self.bdd.false:
                return

            base_f, _ = base_and_sign(f)
            sid = ensure_struct_id(base_f)
            if sid in nodes_tbl:
                return  # already materialized

            # Materialize children first (their refs include sign if complemented).
            low_ref = ref_id(base_f.low)
            high_ref = ref_id(base_f.high)

            # Record current node
            nodes_tbl[sid] = {
                "var": base_f.var,
                "low": low_ref,
                "high": high_ref,
            }

            # Recurse on children using their *base* to populate the structural DAG
            materialize_structure(base_f.low)
            materialize_structure(base_f.high)

        # Build cells → resolve and collect references; formulas optionally included.
        cells: Dict[str, Any] = {}

        def collect_ids(fs: List[Any]) -> List[str]:
            ids = []
            for f in fs:
                materialize_structure(f)       # ensure structure exists
                ids.append(ref_id(f))          # signed reference id
            return ids

        for cname, ent in self.entries.items():
            cin, cout = {}, {}

            # Inputs
            for p, info in ent.input_wires.items():
                ids = collect_ids(info.get("function") or [])
                cin[p] = {"wire": info.get("wire"), "functions": ids}

            # Outputs (+ optional formulas)
            for p, info in ent.output_wires.items():
                ids = collect_ids(info.get("function") or [])
                o = {"wire": info.get("wire"), "functions": ids}
                if include_formulas and info.get("formula") is not None:
                    materialize_structure(info["formula"])
                    o["formula"] = ref_id(info["formula"])
                cout[p] = o

            cells[cname] = {"inputs": cin, "outputs": cout}

        return {
            "meta": {"generator": "CellIterator", "format": "dag"},
            "cells": cells,
            "bdd_nodes": nodes_tbl,  # structural DAG; references may be signed (e.g., "-17")
            "placeholders_injected": self._injected_placeholders,
        }

    def _dump_as_expr(self, include_formulas: bool):
        """
        Dump all port functions (and optionally raw formulas) as human-readable
        boolean expressions, *preserving complemented edges*.

        Returns:
        Dict[str, Any]: JSON-serializable payload
        """
        # Cache string expressions by *function object* to avoid exponential blow-up.
        # Using the object itself is safe across autoref/cudd backends.
        cache: Dict[Any, str] = {}

        def to_expr(f):
            """Render a BDD function `f` to a boolean expression string."""
            # Terminals first (consider complemented edges via quick flips).
            if f == self.bdd.true:
                return "1"
            if f == self.bdd.false:
                return "0"

            # If this function is represented by a complemented edge, de-complement
            # and wrap the whole expression in "~(...)". Use cache on the complemented object.
            if getattr(f, "negated", False):
                if f in cache:
                    return cache[f]
                inner = to_expr(
                    ~f
                )  # ~f is the same structure with the complement bit toggled off
                res = f"~({inner})"
                cache[f] = res
                return res

            # Now `f` is a non-complemented node.
            if f in cache:
                return cache[f]

            var = f.var
            # Recursively render low/high branches (they may be complemented).
            low = to_expr(f.low)
            high = to_expr(f.high)

            # Standard Shannon expansion → compact boolean rendering.
            if low == high:
                res = low
            elif low == "0" and high == "1":
                res = var
            elif low == "1" and high == "0":
                res = f"~{var}"
            else:
                # Mixed cases: build readable, minimal-ish combinations.
                if high == "0":
                    res = f"~{var} & ({low})"
                elif high == "1":
                    if low == "0":
                        res = var
                    else:
                        res = f"({var}) | ({low})"
                elif low == "0":
                    res = f"{var} & ({high})"
                elif low == "1":
                    res = f"~{var} | ({high})"
                else:
                    res = f"({var} & ({high})) | (~{var} & ({low}))"

            cache[f] = res
            return res

        cells = {}
        for cname, ent in self.entries.items():
            cin, cout = {}, {}

            # Inputs
            for p, info in ent.input_wires.items():
                cin[p] = {
                    "wire": info.get("wire"),
                    "functions": [to_expr(f) for f in (info.get("function") or [])],
                }

            # Outputs (+ optional formulas)
            for p, info in ent.output_wires.items():
                exprs = [to_expr(f) for f in (info.get("function") or [])]
                o = {"wire": info.get("wire"), "functions": exprs}
                if include_formulas and info.get("formula") is not None:
                    o["formula"] = to_expr(info["formula"])
                cout[p] = o

            cells[cname] = {"inputs": cin, "outputs": cout}

        return {
            "meta": {"generator": "CellIterator", "format": "expr"},
            "cells": cells,
            "placeholders": self._injected_placeholders,
        }

    def collect_fixed_point_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        tasks: Dict[wire, Dict[str, Any]]
          {
            wire: {
              "ph_name": "__ph__{wire}",
              "driver_cell": "U1",
              "driver_port": "Y",
              "function": <BDD node of F_wire>
            },
            ...
          }
        """
        
        tasks: Dict[str, Dict[str, Any]] = {}

        # Optional map of placeholder name -> BDD var node, used to detect trivial cases.
        ph_nodes = dict(getattr(self.net, "_bdd_vars", {}))

        def is_trivial_placeholder(f, ph_node) -> bool:
            # Exact identity check is enough for dd.autoref BDD nodes
            return (ph_node is not None) and (f is ph_node)

        def support_names(f) -> set:
            # self.bdd.support(f) returns variable names used by f (strings)
            return set(self.bdd.support(f))

        def pick_best(candidates: List[Any], ph_name: str) -> Optional[Any]:
            """
            Select the most appropriate candidate:
            1) must contain ph_name in support;
            2) not equal to the placeholder node itself;
            3) among those, prefer smaller support-size (tiebreaker: earliest).
            If nothing matches, return None.
            """
            ph_node = ph_nodes.get(ph_name)
            filtered = []
            for f in candidates:
                if is_trivial_placeholder(f, ph_node):
                    continue
                supp = support_names(f)
                if ph_name in supp:
                    filtered.append((len(supp), f))
            if filtered:
                filtered.sort(key=lambda t: t[0])  # smaller support first
                return filtered[0][1]
            return None

        for consumer_cell, port2ph in self._injected_placeholders.items():
            ent_cons = self.entries[consumer_cell]
            for in_port, ph_name in port2ph.items():
                wire = ent_cons.input_wires[in_port]["wire"]

                drv = self._wire2src.get(wire)
                if not drv:
                    continue
                ent_drv = self.entries[drv]
                driver_port = None
                driver_fs: List[Any] = []
                for op, oinfo in ent_drv.output_wires.items():
                    if oinfo.get("wire") == wire:
                        driver_port = op
                        driver_fs = oinfo.get("function") or []
                        break
                if driver_port is None:
                    continue

                consumer_fs: List[Any] = ent_cons.input_wires[in_port].get("function") or []

                driver_fun = pick_best(consumer_fs, ph_name)

                if driver_fun is None and driver_fs:
                    driver_fun = pick_best(driver_fs, ph_name)

                if driver_fun is None:
                    ph_node = ph_nodes.get(ph_name)
                    for f in consumer_fs:
                        if not is_trivial_placeholder(f, ph_node):
                            driver_fun = f
                            break

                if driver_fun is None and driver_fs:
                    driver_fun = driver_fs[0]

                if driver_fun is None:
                    # No usable candidate; skip this wire.
                    continue

                logger.debug(
                    f"[tasks] wire={wire} ph={ph_name} driver={drv}.{driver_port} "
                    f"chosen_support={support_names(driver_fun)}"
                )

                tasks[wire] = {
                    "ph_name": ph_name,
                    "driver_cell": drv,
                    "driver_port": driver_port,
                    "function": driver_fun,
                }

        return tasks