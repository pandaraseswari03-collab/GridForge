# Endpoint Integrity + Terminal Connectivity Remediation Plan

## Goal
Restore `core/network/endpoint.py` to valid Python, verify the existing Terminal → Endpoint → TopologyManager boundary, and add focused executable regression coverage without introducing a second connectivity authority.

## Steps
1. Inspect current HEAD, endpoint module, Terminal, Network, TopologyManager, contingency, Power Flow preparation, and relevant tests/callers.
2. Correct only the confirmed syntax/indentation defect in `core/network/endpoint.py`.
3. Add focused Core endpoint/topology tests for import, valid resolution, invalid endpoint, disconnected state, stable identity under collection reordering, attach/detach, and conflicting endpoint behavior according to the actual Terminal contract.
4. Add/adjust integration assertions only where the existing Power Flow/contingency contracts expose the endpoint boundary; do not create new resolver authorities.
5. Verify the exact bus-outage behavior in existing contingency code/tests and classify GF-AUD-005 from evidence rather than assumption.
6. Verify terminal coverage against actual model inventory and classify GF-AUD-006.
7. Trigger and inspect GitHub Actions on this remediation branch. Record exact pass/fail/block state; never claim local execution that is unavailable.
8. Reassess GF-AUD-007 only from executable Power Flow/contingency evidence after the endpoint fix.
9. Update the existing audit ledger/findings with evidence and list only remaining defects.

## Constraints
- No endpoint architecture redesign.
- No second topology or terminal-resolution authority.
- No UI/SLD dependency in Core.
- No positional identity.
- No generic exception swallowing that turns topology errors into disconnection.
- Do not alter stable PowerFlowResult contracts unless endpoint integration proves a genuine defect.
