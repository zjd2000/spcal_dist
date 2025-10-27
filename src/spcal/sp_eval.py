# sp_eval.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from spcal.netlist_graph import NetlistGraph
from spcal.utils.logger import logger


def evaluate_cells(
    netlist_graph: NetlistGraph,
    probs: Dict[str, float],
    cell_names: List[str],
) -> Dict[str, Dict[str, float]]:
    """
    Evaluate signal probabilities for the (first) computed function of each output
    port of the given cells, using a backend-agnostic compiled DAG + DP evaluation.
    """
    ndict = netlist_graph.get_netlist_dict()
    bdd = netlist_graph.get_bdd()

    # 1) Collect all output root functions we need to evaluate
    targets: List[Tuple[str, str, Any]] = []  # (cell, port, root_function)
    for cname in cell_names:
        ent = ndict.get(cname)
        if ent is None:
            logger.warning("[sp_eval] Cell '%s' not found; skipping.", cname)
            continue
        for oport, oinfo in ent.output_wires.items():
            funcs = oinfo.get("function") or []
            if funcs:
                targets.append((cname, oport, funcs[0]))
            else:
                logger.error(
                    "[sp_eval] %s.%s has no 'function'" "cannot evaluate probability.",
                    cname,
                    oport,
                )
                raise KeyError

    if not targets:
        return {}

    # 2) Compile a single global DAG covering all targets, then evaluate once
    evaluator = _Evaluator(bdd=bdd, probs=probs)
    for _, _, root in targets:
        evaluator.materialize(root)
    evaluator.build_postorder()
    evaluator.evaluate()

    # 3) Read out each root's probability
    results: Dict[str, Dict[str, float]] = {}
    for cname, oport, root in targets:
        p = evaluator.prob_of(root)
        results.setdefault(cname, {})[oport] = float(p)
    return results


# ---------------- Internal evaluator (backend-agnostic) ---------------- #


class _Evaluator:
    """
    Compile-time evaluator:
      - Normalizes complemented edges per reference (store sign on the edge).
      - Assigns dense SIDs to base (non-complemented) nodes (backend independent).
      - Builds one reverse-topological order over all needed nodes.
      - Single DP sweep per evaluation.
    """

    def __init__(self, *, bdd, probs: Dict[str, float]):
        self.bdd = bdd
        self.probs = probs

        # base node -> SID
        self._base2sid: Dict[Any, int] = {}
        # SID -> (varname: str, low_ref, high_ref)
        self._nodes: Dict[
            int, Tuple[str, Tuple[str, int, bool], Tuple[str, int, bool]]
        ] = {}
        # postorder of SIDs
        self._post: List[int] = []

        # root refs cache
        self._root_ref: Dict[int, Tuple[str, int, bool]] = {}

        # computed probabilities per SID (aligned with post)
        self._sid2pos: Dict[int, int] = {}
        self._prob_base: List[float] = []

    # ---------- graph building ----------

    def materialize(self, f) -> None:
        """Ensure 'f' and all its reachable base nodes are in the table."""

        def base_and_sign(g):
            if getattr(g, "negated", False):
                return (~g), True
            return g, False

        def is_true(g) -> bool:
            return (g is self.bdd.true) or (g == self.bdd.true)

        def is_false(g) -> bool:
            return (g is self.bdd.false) or (g == self.bdd.false)

        def ensure_sid(base_g) -> int:
            sid = self._base2sid.get(base_g)
            if sid is not None:
                return sid
            sid = len(self._base2sid)
            self._base2sid[base_g] = sid

            # terminals don't get SIDs
            if is_true(base_g) or is_false(base_g):
                return sid  # won't be used as 'n' ref; safe to return

            # ensure children first
            low_ref = child_ref(base_g.low)
            high_ref = child_ref(base_g.high)
            self._nodes[sid] = (base_g.var, low_ref, high_ref)
            return sid

        def child_ref(h) -> Tuple[str, int, bool]:
            if is_true(h):
                return ("t", 1, False)
            if is_false(h):
                return ("t", 0, False)
            hb, hneg = base_and_sign(h)
            sid = ensure_sid(hb)
            return ("n", sid, bool(hneg))

        # remember a canonical ref for the root as well
        if is_true(f):
            self._root_ref[id(f)] = ("t", 1, False)
            return
        if is_false(f):
            self._root_ref[id(f)] = ("t", 0, False)
            return
        bf, neg = base_and_sign(f)
        sid = ensure_sid(bf)
        self._root_ref[id(f)] = ("n", sid, bool(neg))

    def build_postorder(self) -> None:
        """Create reverse-topological order over SIDs already materialized."""
        visited, temp, post = set(), set(), []

        def dfs(sid: int):
            if sid in visited or sid not in self._nodes:
                return
            if sid in temp:
                return
            temp.add(sid)
            _, low_ref, high_ref = self._nodes[sid]
            for ref in (low_ref, high_ref):
                if ref[0] == "n":
                    dfs(ref[1])
            temp.remove(sid)
            visited.add(sid)
            post.append(sid)

        for sid in list(self._nodes.keys()):
            dfs(sid)

        self._post = post
        self._sid2pos = {sid: i for i, sid in enumerate(self._post)}
        self._prob_base = [0.0] * len(self._post)

    def evaluate(self) -> None:
        """One DP sweep over the compiled DAG."""

        def P_ref(ref: Tuple[str, int, bool]) -> float:
            kind, val, neg = ref
            if kind == "t":
                p = 1.0 if val == 1 else 0.0
                return 1.0 - p if neg else p
            p = self._prob_base[self._sid2pos[val]]
            return 1.0 - p if neg else p

        for i, sid in enumerate(self._post):
            var, low_ref, high_ref = self._nodes[sid]
            p_var = _var_prob_strict(var, self.probs)
            if p_var <= 0.0:
                self._prob_base[i] = P_ref(low_ref)
            elif p_var >= 1.0:
                self._prob_base[i] = P_ref(high_ref)
            else:
                p_low = P_ref(low_ref)
                p_high = P_ref(high_ref)
                self._prob_base[i] = (1.0 - p_var) * p_low + p_var * p_high

    def prob_of(self, f) -> float:
        """Return probability of root function 'f' after evaluate()."""
        ref = self._root_ref.get(id(f))
        if ref is None:
            # in case caller queries a root not seen during materialize()
            self.materialize(f)
            self.build_postorder()
            self.evaluate()
            ref = self._root_ref[id(f)]
        kind, val, neg = ref
        if kind == "t":
            p = 1.0 if val == 1 else 0.0
            return 1.0 - p if neg else p
        p = self._prob_base[self._sid2pos[val]]
        return 1.0 - p if neg else p


def _var_prob_strict(varname: str, probs: Dict[str, float]) -> float:
    """Strict: missing → KeyError; out-of-range → ValueError."""
    if varname not in probs:
        raise KeyError(f"[sp_eval] Missing probability for variable '{varname}'.")
    p = probs[varname]
    if not isinstance(p, (int, float)):
        raise TypeError(
            f"[sp_eval] Probability for variable '{varname}' must be numeric; got {type(p)}."
        )
    if p < 0.0 or p > 1.0:
        raise ValueError(
            f"[sp_eval] Probability for variable '{varname}' out of range [0,1]: {p}."
        )
    return float(p)
