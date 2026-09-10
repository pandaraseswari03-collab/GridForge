from types import MappingProxyType

from core.solver.power_flow.result import PowerFlowResult


def test_power_flow_result_keeps_stable_id_engineering_payload_immutable():
    result = PowerFlowResult(
        success=True,
        iterations=2,
        error=1e-9,
        pv_to_pq=(),
        history=(1.0, 1e-9),
        message="Converged.",
        voltage_magnitudes=(1.0, 0.99),
        voltage_angles=(0.0, -0.01),
        branch_results={
            "L1": {
                "element_id": "L1",
                "loading_percent": 75.0,
                "limit_mva": 100.0,
                "within_limit": True,
            }
        },
        transformer_results={
            "T1": {
                "element_id": "T1",
                "loading_percent": 105.0,
                "limit_mva": 80.0,
                "within_limit": False,
            }
        },
    )

    assert isinstance(result.branch_results, MappingProxyType)
    assert isinstance(result.transformer_results, MappingProxyType)
    assert result.branch_results["L1"]["loading_percent"] == 75.0
    assert result.transformer_results["T1"]["within_limit"] is False

    try:
        result.branch_results["L2"] = {}
    except TypeError:
        pass
    else:
        raise AssertionError("branch_results must be immutable")

    try:
        result.branch_results["L1"]["loading_percent"] = 99.0
    except TypeError:
        pass
    else:
        raise AssertionError("nested engineering records must be immutable")
