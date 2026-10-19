"""opamp-v0: campaign-local op-amp verifier (kaggle/PREREG-OPAMP-V0-D0.md, Stage 1).

    from opamp_v0 import size, evaluate, parse, format_netlist, prefilter
    r = size(netlist_text, spec_dict, seed=1, evals=2500, objective="margin" | "max:gain_db")

Import with kaggle/campaigns/opamp-v0 on sys.path. See README.md for the dialect,
testbench, metrics, objective modes and the deviations D-O*.
"""
from .dialect import (parse, format_netlist, canonical, prefilter, param_space,  # noqa: F401
                      groups, DialectError)
from .sizer import size, evaluate, margins, feasible, PROFILE, RANGES  # noqa: F401
from .sizer import robust_evaluate, robust_check, corners, mm_vectors, mm_groups  # noqa: F401
from .testbench import measure  # noqa: F401
