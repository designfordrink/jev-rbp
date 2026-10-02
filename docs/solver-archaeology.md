# Solver Archaeology — Reference VLNS

This document records implementation-level behavior recovered from data/reference/archive/. The archive is research provenance; src/jev_rbp remains a clean-room implementation.

## 1. Search loop
Reference entry point: solve_vlns(net, initial_solution=None, max_iterations=100, time_limit=300.0, verbose=False).

The key correction to earlier documentation: the search is phase-ordered, not one global scan over Drop/Add/Swap.

Each iteration:
1. Drop: evaluate all open blocks and apply the best improving Drop, if any.
2. Add: after Drop, evaluate all closed candidate blocks and apply the best improving Add, if any.
3. Swap: only when neither Drop nor Add improved, evaluate Drop+Add pairs and apply the best improving Swap.
4. Stop if no phase improved.

An improvement must exceed 1e-6. One iteration can therefore contain both a Drop and an Add.

## 2. Candidate universe
All ordered pairs of distinct yards with a valid physical shortest path are candidate service blocks. The solver precomputes shortest distance, physical path, link IDs and minimum block volume.

The physical graph is bidirectional; the open-block service graph is directed.

## 3. Move semantics
Drop removes one open block, reroutes every commodity from scratch, rejects unroutable/C2/C4a states, and keeps the best improvement.

Add opens one closed candidate, reroutes every commodity, applies the same checks, and keeps the best improvement. A newly opened but unused block does not receive fixed cost because the reference recomputes used blocks from routes.

Swap evaluates every open/closed pair by rerouting on (open - drop) union {add}. It is reached only after Drop and Add both fail.

## 4. Routing
For every candidate block set, commodities are routed independently by Dijkstra on the directed service graph. Arc weight per volume is transport_cost_coefficient * block_shortest_distance + handling_cost(to_yard) when to_yard is not the commodity destination.

Routing is an exact evaluation component. JEV may rank candidates but does not replace routing.

## 5. Objective
Reference move evaluation uses fixed cost for used blocks, transport cost over block shortest-path distance, and handling cost at intermediate yards. The archived evaluator.py also exposes interchange, but returns zero for the historical toy instance.

The current RAS v2.1 benchmark validator/scorer remains the correctness authority; historical solver behavior is not automatically benchmark truth.

## 6. Baseline consequence
The generic VLNSSolver in src/jev_rbp/vlns.py is not yet behaviorally equivalent: it currently chooses one global best move from a combined candidate list. The next implementation change must make Drop -> Add -> conditional Swap explicit.

## 7. Provenance
Primary archive: data/reference/archive/solvers/vlns.py, evaluator.py, validator.py and solvers/greedy.py. Public provenance: Nicolas Bridelance Kaggle Railroad Blocking VLNS Metaheuristic and the INFORMS RAS 2026 v2.1 public mirror.