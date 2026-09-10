"""Power-flow numerical contracts and compatibility exports."""

from .input import PowerFlowBusType, PowerFlowInput
from .nr_solver import NewtonRaphsonSolver
from .q_limit_handler import QLimitHandler
from .result import PowerFlowResult
from .runtime_state import PowerFlowRuntimeState
from .solver_options import SolverOptions
from .sparse_solver import SparseLinearSolver

__all__ = [
    "PowerFlowBusType",
    "PowerFlowInput",
    "PowerFlowStudyConfiguration",
    "PowerFlowPreparation",
    "PreparedPowerFlow",
    "PowerFlowRuntimeState",
    "PowerFlowResult",
    "NewtonRaphsonSolver",
    "QLimitHandler",
    "SolverOptions",
    "SparseLinearSolver",
]


def __getattr__(name: str):
    """Lazily load Analysis-owned compatibility exports.

    PowerFlowStudyConfiguration and PowerFlowPreparation are owned by the
    Analysis layer. Lazy imports preserve their historical solver-package
    import paths without creating an Analysis -> solver -> Analysis cycle.
    """
    if name == "PowerFlowStudyConfiguration":
        from .study_configuration import PowerFlowStudyConfiguration
        return PowerFlowStudyConfiguration
    if name == "PowerFlowPreparation":
        from .preparation import PowerFlowPreparation
        return PowerFlowPreparation
    if name == "PreparedPowerFlow":
        from .preparation import PreparedPowerFlow
        return PreparedPowerFlow
    raise AttributeError(name)
