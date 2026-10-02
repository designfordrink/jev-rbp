# Reference VLNS Archaeology

## Purpose
This document records the verified behavior of the public Nicolas Bridelance Railroad Blocking VLNS notebook and the archived solver utilities recovered in this repository.

The archived Python utilities under data/reference/archive/ provide implementation-level evidence for the v0.1 baseline. They are retained as archaeological reference and are not imported by src/jev_rbp.

## 1. Verified search loop
The reference has Drop, Add and Swap moves. The control flow is phase ordered:

```text
iteration
  -> best Drop -> apply if improving
  -> best Add  -> apply if improving
  -> only if neither improved: best Swap -> apply if improving
  -> if nothing improved: stop
```

This is not equivalent to evaluating all three families together and selecting one global best move. An improvement must exceed 1e-6. One iteration can contain both Drop and Add.

## 2. Candidate universe
Every ordered pair of distinct yards with a valid physical shortest path is a candidate service block. Distance, physical path, link IDs and minimum block volume are precomputed.

The physical network is bidirectional; the service graph of open blocks is directed.

## 3. Routing
Every commodity is rerouted independently with Dijkstra on the directed service graph. Per-volume arc cost is transport coefficient times block shortest distance plus handling cost at the arc destination when it is not the commodity destination.

Routing remains an exact evaluation component. JEV may rank candidates but does not replace it.

## 4. Objective
Reference move evaluation uses fixed cost for used blocks, transport over block shortest-path distance, and handling at intermediate yards. The archived evaluator.py exposes interchange too, but its historical toy implementation returns zero.

The current RAS v2.1 benchmark validator/scorer remains the correctness authority.

## 5. Move feasibility
Drop/Add/Swap are rejected when a commodity cannot be rerouted, C4a minimum block volume is violated, or C2 outgoing-track limits are violated. This is a move-level gate, not the full benchmark validator.

## 6. Architecture mapping
| Reference | JEV-RBP |
|---|---|
| Drop | DropAction |
| Add | AddAction |
| Swap | SwapAction |
| service Dijkstra | routing/evaluation |
| move cost | exact evaluator |
| C2/C4a gate | move evaluator |
| full benchmark checks | validator |
| phase-ordered search | VLNSSolver |

## 7. Remaining work
The archive resolves most earlier archaeology questions. Remaining work is to reproduce one small reference run, recover deterministic sample inputs/outputs, verify equal-cost tie behavior, and instrument exact evaluation counts.

## 8. Provenance
Nicolas Bridelance, Railroad Blocking VLNS Metaheuristic and Railroad Blocking MIP Pyomo HiGHS, Kaggle; INFORMS RAS 2026 Problem Solving Competition v2.1; public mirror asu-trans-ai-lab/RAS2026-PSC.