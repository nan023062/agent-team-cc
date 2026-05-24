# Workflow tests — Report 001

## Run

- **Start**: 2026-05-24 09:26:11
- **End**: 2026-05-24 09:37:54
- **Git**: master @ 8e1c293
- **Pytest exit**: 1
- **Cases**: 13 total — 7 pass, 6 fail (pass rate 54%)
- **Wall**: 672.0s total, avg 51.7s/case
- **Tokens**: in ?, out ?

## Per-case results

| Case | Status | Sub | Wall | In tok | Out tok | Log |
| --- | --- | --- | --- | --- | --- | --- |
| `test_loop_execution_positive` | pass | 0/0 | 201.1s | ? | ? | `report-001/logs/test_loop_execution_positive.log` |
| `test_loop_execution_negative` | pass | 0/0 | 6.8s | ? | ? | `report-001/logs/test_loop_execution_negative.log` |
| `test_loop_architect_positive` | pass | 0/0 | 33.4s | ? | ? | `report-001/logs/test_loop_architect_positive.log` |
| `test_loop_architect_negative` | pass | 0/0 | 13.3s | ? | ? | `report-001/logs/test_loop_architect_negative.log` |
| `test_loop_hr_positive` | pass | 0/0 | 25.0s | ? | ? | `report-001/logs/test_loop_hr_positive.log` |
| `test_loop_hr_negative` | pass | 0/0 | 9.4s | ? | ? | `report-001/logs/test_loop_hr_negative.log` |
| `test_loop_memory_positive` | fail | 0/0 | 19.0s | ? | ? | `report-001/logs/test_loop_memory_positive.log` |
| `test_loop_memory_negative` | pass | 0/0 | 6.4s | ? | ? | `report-001/logs/test_loop_memory_negative.log` |
| `test_loop_audit_agent_fission_positive` | fail | 0/0 | 156.7s | ? | ? | `report-001/logs/test_loop_audit_agent_fission_positive.log` |
| `test_loop_audit_dna_fission_positive` | fail | 0/0 | 87.0s | ? | ? | `report-001/logs/test_loop_audit_dna_fission_positive.log` |
| `test_loop_audit_index_positive` | fail | 0/0 | 78.3s | ? | ? | `report-001/logs/test_loop_audit_index_positive.log` |
| `test_loop_audit_memory_positive` | fail | 0/0 | 18.7s | ? | ? | `report-001/logs/test_loop_audit_memory_positive.log` |
| `test_loop_audit_tree_positive` | fail | 0/0 | 16.8s | ? | ? | `report-001/logs/test_loop_audit_tree_positive.log` |

## Per-group summary

| Group | Pass / Total | Wall | In tok | Out tok |
|---|---|---|---|---|
| architect | 2/2 | 46.7s | ? | ? |
| test_loop_audit_agent_fission_positive | 0/1 | 156.7s | ? | ? |
| test_loop_audit_dna_fission_positive | 0/1 | 87.0s | ? | ? |
| test_loop_audit_index_positive | 0/1 | 78.3s | ? | ? |
| test_loop_audit_memory_positive | 0/1 | 18.7s | ? | ? |
| test_loop_audit_tree_positive | 0/1 | 16.8s | ? | ? |
| execution | 2/2 | 207.9s | ? | ? |
| hr | 2/2 | 34.4s | ? | ? |
| memory | 1/2 | 25.4s | ? | ? |

## Diagnostics

### `test_loop_memory_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106eec7d0>
- sub-checks: 0/0

### `test_loop_audit_agent_fission_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106e37890>
- sub-checks: 0/0

### `test_loop_audit_dna_fission_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106e1dcd0>
- sub-checks: 0/0

### `test_loop_audit_index_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106e88b90>
- sub-checks: 0/0

### `test_loop_audit_memory_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106e7dbf0>
- sub-checks: 0/0

### `test_loop_audit_tree_positive`

- top failure: workflow_target = <v1.tests.framework.target.TmpProject object at 0x106e1d940>
- sub-checks: 0/0

