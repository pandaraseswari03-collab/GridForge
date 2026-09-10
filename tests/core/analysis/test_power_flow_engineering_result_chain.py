import math

import numpy as np

from core.analysis.contingency import ContingencyAnalysis
from core.analysis.power_flow import PowerFlowAnalysis
from core.analysis.power_flow_preparation import PreparedBranch, PreparedPowerFlow, PreparedTransformer
from core.analysis.power_flow_result_conversion import PowerFlowResultConverter
from core.analysis.transformer_flow import TransformerFlowCalculator
from core.numerical.ybus import YBus
from core.solver.power_flow.input import PowerFlowInput
from core.solver.power_flow.result import PowerFlowResult


def _prepared(*, branches=(), transformers=()):
    bus_ids = ("B1", "B2")
    input_data = PowerFlowInput(
        bus_ids=bus_ids,
        bus_types=("SLACK", "PQ"),
        p_spec=(0.0, -0.1),
        q_spec=(0.0, -0.05),
        q_min=(None, None),
        q_max=(None, None),
        initial_vm=(1.0, 1.0),
        initial_va=(0.0, 0.0),
    )
    ybus = YBus(
        matrix=np.zeros((2, 2), dtype=complex),
        bus_ids=bus_ids,
    )
    return PreparedPowerFlow(
        input=input_data,
        ybus=ybus,
        base_mva=100.0,
        bus_voltage_bases={"B1": 110.0, "B2": 110.0},
        branches=branches,
        transformers=transformers,
    )


def test_prepared_equipment_preserves_engineering_ratings():
    branch = PreparedBranch(
        "L1", "B1", "B2", 0.01, 0.1, 0.02,
        rate_mva=50.0,
        rated_current_a=200.0,
        thermal_limit_mva=45.0,
    )
    transformer = PreparedTransformer(
        "T1", "B1", "B2", 0.01, 0.08, 0.02, 1.05, 0.1,
        rated_mva=40.0,
    )

    prepared = _prepared(branches=(branch,), transformers=(transformer,))

    assert prepared.branches[0].rate_mva == 50.0
    assert prepared.branches[0].rated_current_a == 200.0
    assert prepared.branches[0].thermal_limit_mva == 45.0
    assert prepared.transformers[0].rated_mva == 40.0


def test_transformer_flow_uses_the_same_terminal_admittance_as_ybus():
    transformer = PreparedTransformer(
        "T1", "B1", "B2", 0.01, 0.08, 0.04, 1.05, math.radians(7.0)
    )
    prepared = _prepared(transformers=(transformer,))
    V = np.array([1.02 * np.exp(1j * 0.03), 0.98 * np.exp(-1j * 0.02)])

    result = TransformerFlowCalculator.from_prepared(prepared).calculate_prepared(
        transformer, np.abs(V), np.angle(V)
    )

    z = complex(transformer.r_pu, transformer.x_pu)
    y = 1.0 / z
    a = transformer.tap * np.exp(1j * transformer.shift)
    ysh = 1j * transformer.b_pu / 2.0
    i_from = (y / abs(a) ** 2 + ysh) * V[0] - y / np.conj(a) * V[1]
    i_to = -y / a * V[0] + (y + ysh) * V[1]
    s_from = V[0] * np.conj(i_from)
    s_to = V[1] * np.conj(i_to)

    assert np.isclose(result.p_from, s_from.real)
    assert np.isclose(result.q_from, s_from.imag)
    assert np.isclose(result.p_to, s_to.real)
    assert np.isclose(result.q_to, s_to.imag)


def test_engineering_converter_exposes_branch_and_transformer_results():
    numerical = PowerFlowResult(
        success=True,
        iterations=3,
        error=1e-9,
        pv_to_pq=(),
        history=(1.0, 1e-3, 1e-9),
        message="Converged",
        voltage_magnitudes=(1.0, 0.98),
        voltage_angles=(0.0, -0.02),
    )
    prepared = _prepared(
        branches=(PreparedBranch("L1", "B1", "B2", 0.01, 0.1, 0.0, rate_mva=50.0),),
        transformers=(PreparedTransformer("T1", "B1", "B2", 0.01, 0.08, 0.0, 1.0, 0.0, rated_mva=40.0),),
    )

    engineering = PowerFlowResultConverter.to_engineering(numerical, prepared=prepared)

    assert "L1" in engineering.branch_results
    assert "T1" in engineering.transformer_results
    assert engineering.branch_results["L1"].limit_mva == 50.0
    assert engineering.transformer_results["T1"].limit_mva == 40.0
    assert engineering.branch_results["L1"].within_limit is True
    assert engineering.numerical_result.branch_results["L1"]["element_id"] == "L1"


def test_power_flow_result_engineering_payload_is_immutable():
    numerical = PowerFlowResult(
        success=True,
        iterations=0,
        error=0.0,
        pv_to_pq=(),
        history=(),
        message="ok",
        voltage_magnitudes=(1.0,),
        voltage_angles=(0.0,),
    )

    assert not hasattr(numerical, "line_loading")
    assert hasattr(numerical, "branch_results")
    try:
        numerical.branch_results["L1"] = {}
    except TypeError:
        pass
    else:
        raise AssertionError("PowerFlowResult engineering results must be immutable")


def test_contingency_violations_use_stable_id_engineering_results():
    analysis = ContingencyAnalysis.__new__(ContingencyAnalysis)

    class _Bus:
        def __init__(self, bus_id):
            self.id = bus_id

    class _Network:
        buses = [_Bus("B1"), _Bus("B2")]
        lines = []
        transformers = []

    result = PowerFlowResult(
        success=True,
        iterations=1,
        error=0.0,
        pv_to_pq=(),
        history=(0.0,),
        message="Converged",
        voltage_magnitudes=(1.0, 0.98),
        voltage_angles=(0.0, 0.0),
        bus_results={
            "B2": {"voltage_magnitude": 0.90},
            "B1": {"voltage_magnitude": 1.10},
        },
        branch_results={"L-42": {"loading_percent": 125.0, "limit_mva": 80.0, "within_limit": False}},
        transformer_results={"T-7": {"loading_percent": 110.0, "limit_mva": 100.0, "within_limit": False}},
    )

    violations = analysis._detect_violations(
        _Network(), result, voltage_min=0.95, voltage_max=1.05, thermal_limit=100.0
    )

    assert [(v.category, v.element_id) for v in violations] == [
        ("voltage_low", "B2"),
        ("voltage_high", "B1"),
        ("thermal", "L-42"),
        ("transformer_thermal", "T-7"),
    ]
    assert all(v.limit == 100.0 for v in violations[2:])
    assert all(v.severity > 0.0 for v in violations)


def test_power_flow_analysis_keeps_engineering_results_on_same_result_contract(monkeypatch):
    prepared = _prepared(branches=(PreparedBranch("L1", "B1", "B2", 0.01, 0.1, 0.0, rate_mva=50.0),))
    numerical = PowerFlowResult(
        success=True,
        iterations=1,
        error=0.0,
        pv_to_pq=(),
        history=(0.0,),
        message="Converged",
        voltage_magnitudes=(1.0, 0.98),
        voltage_angles=(0.0, -0.02),
    )
    analysis = PowerFlowAnalysis(prepared.input, prepared.ybus, prepared=prepared)
    monkeypatch.setattr(analysis.solver, "solve", lambda: numerical)

    result = analysis.solve()

    assert result is analysis.result
    assert result is not numerical
    assert result.branch_results["L1"]["element_id"] == "L1"
    assert result.branch_results["L1"]["limit_mva"] == 50.0
