from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore

from spcal.utils.logger import logger


@dataclass
class FixedPointConfig:
    init_placeholder: float = 0.5  # initial value for all placeholders
    tol: float = 1e-8              # infinity-norm tolerance
    max_iter: int = 500            # max iterations
    damping: float = 0.5           # 0 < damping <= 1
    use_anderson: bool = True      # optional Anderson acceleration
    anderson_m: int = 3            # history size (2..4 typical)

    # Early-stop
    delta_change_tol: float = 1e-12   # threshold on |Δ_t - Δ_{t-1}|
    plateau_patience: int = 5         # consecutive iters satisfying the condition


def solve_placeholders(
    *,
    bdd,  # NetlistGraph._bdd (autoref/cudd/sylvan)
    external_sp_inputs_spec: Dict[str, float],  # PI probabilities
    tasks: Dict[str, Dict[str, Any]],  # from CellIterator.collect_fixed_point_tasks()
    config: Optional[FixedPointConfig] = None,
) -> Dict[str, float]:
    """
    Solve the coupled fixed-point system for placeholders:
        sp(__ph__W) = P( F_W(PI, placeholders) )
    where F_W is the BDD function driving wire W.

    Returns: { "__ph__W1": p1, "__ph__W2": p2, ... }
    """
    if not tasks:
        return {}

    cfg = config or FixedPointConfig()

    model = _CompiledModel(bdd, external_sp_inputs_spec, tasks)
    ph_names = model.placeholder_names
    p = [cfg.init_placeholder] * len(ph_names)

    accelerator = (
        _Anderson(m=cfg.anderson_m)
        if (cfg.use_anderson and len(p) >= 2 and np is not None)
        else None
    )

    total = cfg.max_iter
    progress_every = max(1, total // 20)  # log every ~5%
    logger.info(
        "FixedPoint Start: n_placeholders=%d, max_iter=%d, tol=%.1e, damping=%.3f, anderson=%s",
        len(ph_names),
        cfg.max_iter,
        cfg.tol,
        cfg.damping,
        "on" if accelerator else "off",
    )

    converged = False
    plateau_streak = 0          # counts consecutive "almost no improvement" steps
    prev_max_delta: Optional[float] = None

    for it in range(1, cfg.max_iter + 1):
        model.set_placeholder_vector(p)
        model.evaluate_pass()

        # g(p): probability of each driver's function
        g = [model.prob_of_ref(model.driver_ref_for_placeholder(ph)) for ph in ph_names]

        r = [g[i] - p[i] for i in range(len(p))]
        gp = accelerator.apply(p, g, r) if accelerator is not None else g

        new_p = [
            (1.0 - cfg.damping) * p[i] + cfg.damping * gp[i] for i in range(len(p))
        ]
        max_delta = max(abs(new_p[i] - p[i]) for i in range(len(p)))
        p = new_p

        if it == 1 or it % progress_every == 0:
            done_ratio = min(1.0, it / cfg.max_iter)
            bar_len = 20
            filled = int(bar_len * done_ratio)
            bar = "█" * filled + "─" * (bar_len - filled)
            logger.info(
                "[FixedPoint] iter %d/%d\t| Δ=%.2e | [%s]",
                it,
                cfg.max_iter,
                max_delta,
                bar,
            )

        if max_delta < cfg.tol:
            converged = True
            logger.info(
                "[FixedPoint] iter %d/%d\t| Δ=%.2e | [%s] ",
                it,
                cfg.max_iter,
                max_delta,
                "█" * 20,
            )
            logger.info(
                f"[FixedPoint] Converged in {it} iterations (maxΔ={max_delta:.3e})"
            )
            break

        if prev_max_delta is not None:
            delta_change = abs(max_delta - prev_max_delta)
            if delta_change <= cfg.delta_change_tol:
                plateau_streak += 1
            else:
                plateau_streak = 0

            if plateau_streak >= cfg.plateau_patience:
                logger.warning(
                    "[FixedPoint] Early stop by plateau at iter %d "
                    "(Δ=%.3e, prevΔ=%.3e, |Δ-Δ_prev|=%.3e <= %.1e for %d iters)",
                    it, max_delta, prev_max_delta, delta_change,
                    cfg.delta_change_tol, cfg.plateau_patience
                )
                break

        prev_max_delta = max_delta

    if not converged:
        logger.info(
            "[FixedPoint] iter %d/%d\t| Δ=%.2e | [%s] ",
            it,
            cfg.max_iter,
            max_delta,
            "█" * 20,
        )
        logger.warning(
            f"[FixedPoint] Reached max_iter={cfg.max_iter} without strict convergence"
        )

    return {name: float(p[i]) for i, name in enumerate(ph_names)}


class _CompiledModel:
    """
    Backend-agnostic global DAG compiler:
      - Assigns our own dense SIDs to base (non-complemented) nodes, independent of backend.
      - Stores node table: SID -> (var source, low-ref, high-ref)
      - Builds reverse-topological order over SIDs for single-pass DP.
    A "ref" is:
      - ('t', 1 or 0, neg: bool)  : terminal
      - ('n', sid: int, neg: bool): reference to base node with optional complement edge
    """

    T_TRUE = ("t", 1, False)
    T_FALSE = ("t", 0, False)

    def __init__(
        self, bdd, pi_probs: Dict[str, float], tasks: Dict[str, Dict[str, Any]]
    ):
        self.bdd = bdd
        self.pi_probs_raw = dict(pi_probs)
        self.tasks = tasks

        # stable placeholder order + fast index map
        wires = sorted(tasks.keys())
        self.placeholder_names: List[str] = [tasks[w]["ph_name"] for w in wires]
        self._ph_index: Dict[str, int] = {
            name: i for i, name in enumerate(self.placeholder_names)
        }

        # Will be filled by build:
        # SID -> (('ph'| 'pi', idx), low_ref, high_ref)
        self._nodes: Dict[
            int, Tuple[Tuple[str, int], Tuple[str, int, bool], Tuple[str, int, bool]]
        ] = {}
        self._postorder: List[int] = []
        self._ph_to_driver_ref: Dict[str, Tuple[str, int, bool]] = {}

        # Backend-agnostic SID assignment
        self._base2sid: Dict[Any, int] = {}

        # PI names table (compact index)
        self._pi_names: List[str] = []

        self._build_global()

        # Pre-allocate iteration buffers
        self._ph_vec: List[float] = [0.5] * len(self.placeholder_names)
        self._pi_vals: List[float] = [
            self._resolve_pi_prob(var) for var in self._pi_names
        ]
        self._prob_base: List[float] = [0.0] * len(
            self._postorder
        )  # probability per post-order position
        self._baseid_to_pos: Dict[int, int] = {
            sid: i for i, sid in enumerate(self._postorder)
        }

    # ---------- Build phase (backend-agnostic) ----------

    def _build_global(self):
        """
        Assign our own dense SIDs to base nodes and build node table and post-order.
        We never touch backend internals like '._index'.
        """

        def base_and_sign(f):
            """Return (base_non_complemented_node, is_complemented_reference)."""
            if getattr(f, "negated", False):
                return (~f), True
            return f, False

        def ensure_sid(base_f) -> int:
            """Assign (or return existing) SID for a base, non-complemented node."""
            sid = self._base2sid.get(base_f)
            if sid is not None:
                return sid
            sid = len(self._base2sid)
            self._base2sid[base_f] = sid
            # Materialize children first to be able to reference their SIDs
            # Terminals have no SIDs and are not inserted.
            if base_f != self.bdd.true and base_f != self.bdd.false:
                # Recurse on children to guarantee their SIDs exist when needed.
                self._materialize_children(base_f, base_and_sign, ensure_sid)
            return sid

        def ref_of(f) -> Tuple[str, int, bool]:
            """Return a 'ref' triple for any node (terminal or non-terminal)."""
            if f == self.bdd.true:
                return ("t", 1, False)
            if f == self.bdd.false:
                return ("t", 0, False)
            bf, neg = base_and_sign(f)
            sid = ensure_sid(bf)
            return ("n", sid, bool(neg))

        # Populate from all driver functions, and map placeholder -> driver ref
        for w, info in self.tasks.items():
            f = info["function"]
            ph = info["ph_name"]
            # Ensure the whole subgraph is materialized
            if f != self.bdd.true and f != self.bdd.false:
                bf, _ = base_and_sign(f)
                ensure_sid(bf)
            self._ph_to_driver_ref[ph] = ref_of(f)

        # Build post-order over SIDs
        node_tbl = self._nodes  # will be filled during materialization
        visited: set[int] = set()
        temp: set[int] = set()
        post: List[int] = []

        def dfs_post(sid: int):
            if sid in visited:
                return
            if sid in temp:
                return
            temp.add(sid)
            # children
            var_src, low_ref, high_ref = node_tbl[sid]
            for ref in (low_ref, high_ref):
                if ref[0] == "n":
                    dfs_post(ref[1])
            temp.remove(sid)
            visited.add(sid)
            post.append(sid)

        for sid in list(self._nodes.keys()):
            dfs_post(sid)

        self._postorder = post

    def _materialize_children(self, base_f, base_and_sign, ensure_sid):
        """
        Create node table entry for 'base_f' (non-terminal), after ensuring children SIDs exist.
        """

        # Child refs (terminals keep 't', non-terminals use 'n' and SID)
        def child_ref(child_f) -> Tuple[str, int, bool]:
            if child_f == self.bdd.true:
                return ("t", 1, False)
            if child_f == self.bdd.false:
                return ("t", 0, False)
            cb, cneg = base_and_sign(child_f)
            csid = ensure_sid(cb)
            return ("n", csid, bool(cneg))

        # Compute refs
        low_ref = child_ref(base_f.low)
        high_ref = child_ref(base_f.high)

        # Variable source: placeholder or PI index
        varname = base_f.var
        src_kind, src_idx = self._var_source(varname)

        sid = self._base2sid[base_f]
        self._nodes[sid] = ((src_kind, src_idx), low_ref, high_ref)

    def _var_source(self, varname: str) -> Tuple[str, int]:
        """
        Map a BDD variable name to ('ph', idx) or ('pi', idx) with a compact index.
        """
        k = self._ph_index.get(varname)
        if k is not None:
            return ("ph", k)
        # PI path
        try:
            idx = self._pi_names.index(varname)
        except ValueError:
            idx = len(self._pi_names)
            self._pi_names.append(varname)
        return ("pi", idx)

    # ---------- Iteration-time API ----------

    def set_placeholder_vector(self, ph_vec: List[float]) -> None:
        self._ph_vec = ph_vec

    def evaluate_pass(self) -> None:
        """
        One dynamic-programming pass over the global DAG in reverse-topological order.
        Fills self._prob_base[pos], where pos maps to SID via _baseid_to_pos.
        """
        prob_base = self._prob_base
        nodes = self._nodes
        post = self._postorder
        baseid_to_pos = self._baseid_to_pos
        ph_vec = self._ph_vec
        pi_vals = self._pi_vals

        def P_ref(ref: Tuple[str, int, bool]) -> float:
            kind, val, neg = ref
            if kind == "t":
                p = 1.0 if val == 1 else 0.0
                return 1.0 - p if neg else p
            p = prob_base[baseid_to_pos[val]]
            return 1.0 - p if neg else p

        for i, sid in enumerate(post):
            (src_kind, src_idx), low_ref, high_ref = nodes[sid]
            p_var = ph_vec[src_idx] if src_kind == "ph" else pi_vals[src_idx]
            p_low = P_ref(low_ref)
            p_high = P_ref(high_ref)
            prob_base[i] = (1.0 - p_var) * p_low + p_var * p_high

    def prob_of_ref(self, ref: Tuple[str, int, bool]) -> float:
        kind, val, neg = ref
        if kind == "t":
            p = 1.0 if val == 1 else 0.0
            return 1.0 - p if neg else p
        p = self._prob_base[self._baseid_to_pos[val]]
        return 1.0 - p if neg else p

    def driver_ref_for_placeholder(self, ph_name: str) -> Tuple[str, int, bool]:
        return self._ph_to_driver_ref[ph_name]

    # ---------- Utilities ----------

    def _resolve_pi_prob(self, varname: str) -> float:
        if varname in self._ph_index:
            return 0.5
        if varname in self.pi_probs_raw:
            return self._clamp01(self.pi_probs_raw[varname])
        logger.warning(f"[FixedPoint] Unknown primary input '{varname}', default P=0.5")
        return 0.5

    @staticmethod
    def _clamp01(x: float) -> float:
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        return float(x)


class _Anderson:
    """
    Lightweight Anderson acceleration (type-I). Uses numpy if available;
    otherwise falls back to raw g(p).
    """

    def __init__(self, m: int = 3):
        self.m = max(2, min(8, int(m)))
        self._p_hist: List[List[float]] = []
        self._r_hist: List[List[float]] = []

    def apply(self, p: List[float], g: List[float], r: List[float]) -> List[float]:
        self._p_hist.append(p[:])
        self._r_hist.append(r[:])
        if len(self._r_hist) <= 1 or np is None:
            return g

        m = min(self.m, len(self._r_hist))
        R = np.array(self._r_hist[-m:]).T  # (n, m)
        try:
            RtR = R.T @ R
            reg = 1e-8 * np.eye(m)
            c = np.linalg.solve(RtR + reg, R.T @ np.array(self._r_hist[-1]))
            alphas = c / (np.sum(c) + 1e-12)
            G = np.array(self._g_hist()[-m:]).T  # (n, m)
            g_acc = (G @ alphas).tolist()
            return g_acc
        except Exception:
            return g

    def _g_hist(self) -> List[List[float]]:
        return [
            [pi + ri for pi, ri in zip(p, r)]
            for p, r in zip(self._p_hist, self._r_hist)
        ]
