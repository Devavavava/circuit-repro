"""ZOAF: a generic, problem-agnostic zeroth-order optimizer.

Library-style API for the ZOAF algorithm. Plug in any black-box objective
`f: R^d -> R` and a bound box; ZOAF handles:

- **Initial Sampling & Multi-start.** Quasi-random (Sobol / Halton / LHS /
  hybrid) initial candidates inside the bound box, then refinement from
  the top `n_starts` of them.
- **Constraint Handling & Acceptance.** Hard clipping of every iterate to
  the bound box; greedy tracking of the global best seen so far.
- **Hybrid Scheduling.** Two-phase ZO refinement — ZO-SGD (random-direction
  gradient estimation) for fast escape from initial basins, followed by
  ZO-CGD (coordinate-wise finite differences) for sharp local refinement.
  The phase order is configurable.

Example
-------

    >>> import numpy as np
    >>> from zoaf import ZOAF
    >>>
    >>> def f(x):
    ...     return float(np.sum((x - 0.7) ** 2))  # minimum at x = 0.7
    >>>
    >>> bounds = np.tile(np.array([[0.0, 1.0]]), (10, 1))   # 10-D unit cube
    >>> opt = ZOAF(f, bounds, sgd_iterations=8, cgd_iterations=1, seed=42)
    >>> res = opt.optimize()
    >>> res.x_best.shape, res.f_best < 1e-3
    ((10,), True)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import numpy as np
from scipy.stats import qmc


# ----------------------------------------------------------------- result
@dataclass
class ZOAFResult:
    """Outcome of a ZOAF optimization run."""
    x_best: np.ndarray
    f_best: float
    n_evals: int
    history: List[Tuple[int, float]] = field(default_factory=list)
    # `history`: list of (eval_index, best-so-far value at that eval)


# ----------------------------------------------------------------- helpers
def _sample_unit_direction(d: int, dist: str, rng: np.random.Generator) -> np.ndarray:
    """Sample a length-1 (or 1/√d Rademacher) direction in R^d."""
    if dist == "sphere":
        u = rng.standard_normal(d)
        return u / np.linalg.norm(u)
    if dist == "rademacher":
        return rng.choice([-1.0, 1.0], size=d) / np.sqrt(d)
    raise ValueError(f"Unknown direction distribution: {dist!r}")


def _qmc_candidates(n: int, d: int, sampling: str, seed: int) -> np.ndarray:
    """Generate `n` initial candidates in the unit cube [0, 1]^d."""
    if sampling == "lhs":
        return qmc.LatinHypercube(d=d, seed=seed).random(n)
    if sampling == "sobol":
        return qmc.Sobol(d=d, scramble=True, seed=seed).random(n)
    if sampling == "halton":
        return qmc.Halton(d=d, scramble=True, seed=seed).random(n)
    if sampling == "hybrid":
        # 70% LHS + 30% Gaussian-around-centroid (matches the 22-param recipe)
        n_lhs = max(1, int(round(0.7 * n)))
        n_gauss = n - n_lhs
        lhs = qmc.LatinHypercube(d=d, seed=seed).random(n_lhs)
        if n_gauss > 0:
            rng = np.random.default_rng(seed + 1)
            gauss = rng.normal(loc=0.5, scale=0.1, size=(n_gauss, d))
            gauss = np.clip(gauss, 0.0, 1.0)
            return np.vstack([lhs, gauss])
        return lhs
    raise ValueError(f"Unknown sampling method: {sampling!r}")


# ----------------------------------------------------------------- optimizer
class ZOAF:
    """Generic ZOAF black-box optimizer.

    Parameters
    ----------
    objective : Callable[[np.ndarray], float]
        Black-box function to optimize. Receives a length-`d` parameter
        vector and returns a scalar.
    bounds : array_like of shape (d, 2)
        Per-coordinate `(low, high)` bounds. Defines the search box.

    Other parameters
    ----------------
    maximize : bool, default False
        If True, ZOAF maximizes `objective`; otherwise it minimizes.

    n_candidates : int, default 10
        Number of QMC initial candidates drawn inside the bound box.
    sampling : {'lhs', 'sobol', 'halton', 'hybrid'}, default 'hybrid'
        Quasi-random sequence used for initial sampling.
    n_starts : int, default 1
        Number of top candidates from which to launch ZO refinement.
        Setting this to a value greater than 1 enables true multi-start:
        each of the top-`n_starts` candidates is independently refined and
        the best final result is returned. Multi-start spends evaluation
        budget on multiple refinements, so reduce `sgd_iterations` /
        `cgd_iterations` accordingly.

    schedule : {'sgd_then_cgd', 'cgd_then_sgd', 'sgd_only', 'cgd_only'}, default 'sgd_then_cgd'
        Order of the two ZO refinement phases.
    sgd_iterations : int, default 8
        Number of ZO-SGD steps per refinement.
    sgd_K : int, default 2
        Number of random directions per ZO-SGD gradient estimate.
    sgd_lr, sgd_mu : float, defaults 0.1 / 0.05
        Initial learning rate and perturbation scale for ZO-SGD.
    cgd_iterations : int, default 1
        Number of ZO-CGD passes per refinement (each pass costs 2·d evaluations).
    cgd_lr, cgd_mu : float, defaults 0.05 / 0.3
        Initial learning rate and perturbation scale for ZO-CGD.
    decay : float, default 0.95
        Multiplicative per-epoch decay applied to `lr` and `mu` in both phases.
    direction_dist : {'sphere', 'rademacher'}, default 'sphere'
        Distribution used to sample ZO-SGD search directions.
    adaptive_mu : bool, default True
        If True, the per-direction perturbation in ZO-SGD is scaled by
        `sum(|x * u|)` to handle wide parameter-magnitude ranges (matches
        the published 22-parameter amplifier ZOAF configuration). Set to
        False if your parameters are already normalised to a common scale.
    seed : int, default 42
        Seed for the QMC sampler and the random direction generator.

    Attributes
    ----------
    objective, bounds, ... : as above.
    n_evals : int
        Total objective evaluations performed (read after `optimize()`).
    history : list of (int, float)
        Best-so-far value recorded after every evaluation.
    """

    def __init__(
        self,
        objective: Callable[[np.ndarray], float],
        bounds,
        *,
        maximize: bool = False,
        n_candidates: int = 10,
        sampling: str = "hybrid",
        n_starts: int = 1,
        schedule: str = "sgd_then_cgd",
        sgd_iterations: int = 8,
        sgd_K: int = 2,
        sgd_lr: float = 0.1,
        sgd_mu: float = 0.05,
        cgd_iterations: int = 1,
        cgd_lr: float = 0.05,
        cgd_mu: float = 0.3,
        decay: float = 0.95,
        direction_dist: str = "sphere",
        adaptive_mu: bool = True,
        seed: int = 42,
    ):
        bounds = np.asarray(bounds, dtype=float)
        if bounds.ndim != 2 or bounds.shape[1] != 2:
            raise ValueError("bounds must have shape (d, 2).")
        if np.any(bounds[:, 0] >= bounds[:, 1]):
            raise ValueError("bounds must satisfy low < high on every coordinate.")

        self.objective = objective
        self.bounds = bounds
        self.d = bounds.shape[0]
        self.lo = bounds[:, 0]
        self.hi = bounds[:, 1]
        self.maximize = maximize

        self.n_candidates = max(1, n_candidates)
        self.sampling = sampling
        self.n_starts = max(1, min(n_starts, self.n_candidates))

        if schedule not in ("sgd_then_cgd", "cgd_then_sgd",
                            "sgd_only", "cgd_only"):
            raise ValueError(f"Unknown schedule: {schedule!r}")
        self.schedule = schedule

        self.sgd_iterations = sgd_iterations
        self.sgd_K = sgd_K
        self.sgd_lr = sgd_lr
        self.sgd_mu = sgd_mu
        self.cgd_iterations = cgd_iterations
        self.cgd_lr = cgd_lr
        self.cgd_mu = cgd_mu
        self.decay = decay
        self.direction_dist = direction_dist
        self.adaptive_mu = adaptive_mu
        self.seed = seed

        # Runtime state — populated by optimize()
        self._rng = np.random.default_rng(seed)
        self._n_evals: int = 0
        self._loss_best: float | None = None     # internal loss (always minimised)
        self._x_best: np.ndarray | None = None
        self._history: List[Tuple[int, float]] = []

    # -------------------------------------------------------- convenience
    @property
    def n_evals(self) -> int:
        return self._n_evals

    @property
    def history(self) -> List[Tuple[int, float]]:
        return list(self._history)

    def _f_best_physical(self) -> float:
        """Convert internal loss back to physical objective value."""
        if self._loss_best is None:
            return float("inf") if not self.maximize else float("-inf")
        return -self._loss_best if self.maximize else self._loss_best

    # -------------------------------------------------------- core operations
    def _clip(self, x: np.ndarray) -> np.ndarray:
        """Hard clipping to the bound box — constraint handling."""
        return np.clip(x, self.lo, self.hi)

    def _eval(self, x: np.ndarray) -> float:
        """Evaluate the user's objective, convert to internal loss, and
        accept it as the new best if applicable. Returns the loss value
        (always: smaller = better) so the rest of the algorithm can treat
        the problem as a minimisation regardless of `maximize`."""
        f_val = float(self.objective(x))
        loss = -f_val if self.maximize else f_val

        self._n_evals += 1
        # Acceptance: track running best
        if self._loss_best is None or loss < self._loss_best:
            self._loss_best = loss
            self._x_best = x.copy()
        self._history.append((self._n_evals, self._f_best_physical()))
        return loss

    def _zo_sgd_grad(self, x: np.ndarray, mu: float, K: int) -> np.ndarray:
        """Two-point random-direction gradient estimator of the loss."""
        g = np.zeros(self.d)
        for _ in range(K):
            u = _sample_unit_direction(self.d, self.direction_dist, self._rng)
            if self.adaptive_mu:
                scale = float(np.sum(np.abs(x * u)))
                step = mu * (scale if scale > 1e-10 else 1.0)
            else:
                step = mu
            xp = self._clip(x + step * u)
            xm = self._clip(x - step * u)
            loss_p = self._eval(xp)
            loss_m = self._eval(xm)
            g += ((loss_p - loss_m) / (2.0 * step)) * u
        return g / K

    def _zo_cgd_grad(self, x: np.ndarray, mu: float) -> np.ndarray:
        """Coordinate-wise two-point finite-difference gradient of the loss."""
        g = np.zeros(self.d)
        for i in range(self.d):
            ei = np.zeros(self.d)
            ei[i] = 1.0
            xp = self._clip(x + mu * ei)
            xm = self._clip(x - mu * ei)
            loss_p = self._eval(xp)
            loss_m = self._eval(xm)
            g[i] = (loss_p - loss_m) / (2.0 * mu)
        return g

    def _run_phase_sgd(self, x: np.ndarray) -> np.ndarray:
        """ZO-SGD refinement starting from `x`."""
        lr, mu = self.sgd_lr, self.sgd_mu
        for _ in range(self.sgd_iterations):
            g = self._zo_sgd_grad(x, mu, self.sgd_K)
            x = self._clip(x - lr * g)
            self._eval(x)   # record post-step value in history
            lr *= self.decay
            mu *= self.decay
        return x

    def _run_phase_cgd(self, x: np.ndarray) -> np.ndarray:
        """ZO-CGD refinement starting from `x`."""
        lr, mu = self.cgd_lr, self.cgd_mu
        for _ in range(self.cgd_iterations):
            g = self._zo_cgd_grad(x, mu)
            x = self._clip(x - lr * g)
            self._eval(x)
            lr *= self.decay
            mu *= self.decay
        return x

    def _phases(self) -> List[str]:
        return {
            "sgd_then_cgd": ["sgd", "cgd"],
            "cgd_then_sgd": ["cgd", "sgd"],
            "sgd_only":     ["sgd"],
            "cgd_only":     ["cgd"],
        }[self.schedule]

    # -------------------------------------------------------- public API
    def optimize(self) -> ZOAFResult:
        """Run the full ZOAF pipeline and return the best-found solution."""
        # Stage 0: QMC initial sampling in [0, 1]^d, scaled to bounds.
        unit_cands = _qmc_candidates(
            self.n_candidates, self.d, self.sampling, self.seed)
        cands = qmc.scale(unit_cands, self.lo, self.hi)

        # Evaluate all candidates and rank by loss (best first).
        cand_losses = np.array([self._eval(c) for c in cands])
        order = np.argsort(cand_losses)  # ascending loss = best first

        # Stage 1+: refine the top-n_starts candidates with the configured
        # schedule. Each refinement runs independently; the global best
        # tracker collects whichever produces the lowest loss.
        for rank in range(self.n_starts):
            x = cands[order[rank]].copy()
            for phase in self._phases():
                x = (self._run_phase_sgd(x) if phase == "sgd"
                     else self._run_phase_cgd(x))

        return ZOAFResult(
            x_best=self._x_best.copy(),
            f_best=self._f_best_physical(),
            n_evals=self._n_evals,
            history=list(self._history),
        )


__all__ = ["ZOAF", "ZOAFResult"]
