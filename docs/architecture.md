# JEV-RBP Architecture

## 1. Boundary between search and judgment

JEV-RBP separates four responsibilities:

1. **Candidate generation** — determines which actions are legal and worth considering.
2. **JEV selector** — ranks candidates cheaply.
3. **Exact evaluator** — computes the actual objective effect of an action.
4. **Validator** — independently decides whether the resulting solution is feasible.

The selector is therefore never an authority.

```
state
  |
  v
candidate generator
  |
  v
legal candidates
  |
  +------> JEV ------> ranking
  |                     |
  |                     v
  +-----------------> Top-K
                        |
                        v
                 exact evaluation
                        |
                        v
                    validator
                        |
                        v
                     accept
```

## 2. Why this boundary matters

A learned selector can be wrong. That is acceptable because it is not allowed to certify feasibility or objective value.

This gives the first prototype a clean failure mode:

- bad candidate generation -> the useful action is absent;
- bad JEV ranking -> the useful action is ranked too low;
- bad exact evaluator -> solver correctness is broken;
- bad validator -> experiment correctness is broken.

These failure modes must be measured separately.

## 3. Core interfaces

The initial public interfaces are intentionally small:

```python
generate(state) -> list[CandidateAction]
rank(state, candidates) -> list[RankedCandidate]
evaluate_move(state, action) -> Evaluation
validate(solution) -> ValidationResult
```

The concrete RBP implementation can evolve without changing the selector contract.

## 4. Research architecture

The first prototype is the lower layer of the broader JEV-Star idea:

```
LLM
  |
  | invent / modify search strategy
  v
VLNS
  |
  | generate and explore neighborhoods
  v
JEV
  |
  | choose promising local actions
  v
Exact evaluator
  |
  v
Validator
  |
  v
Benchmark / Archive
  |
  +--------------------> LLM
```

The LLM layer is deliberately out of scope for v0.1.
