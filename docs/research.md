# Research Notes

## Current reference

The project is based on the public RBP work by Nicolas Bridelance, including a VLNS metaheuristic and a Pyomo/HiGHS MIP formulation.

Reference notebooks:

- https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic
- https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs

The public VLNS description uses Drop, Add and Swap neighborhoods, a best-improving search pattern, and shortest-path routing. The exact implementation should be treated as the reference to reproduce, rather than inferred from the notebook narrative alone.

## Important baseline caveat

The public notebook contains a convergence visualization that interpolates between initial and final objective values. That visualization is not an iteration-by-iteration solver trace and must not be used as training data.

JEV-RBP will instead record the actual search trajectory.

## Research questions

1. How much of the local-search signal can a compact selector learn?
2. How large can the reduction in expensive evaluations be before solution quality degrades?
3. Does a selector trained on VLNS traces generalize to unseen instances?
4. Does MIP-derived supervision produce a better local policy?
5. Is candidate generation a larger bottleneck than candidate ranking?

## Negative results

Failure to outperform vanilla VLNS is a valid result. The project must preserve raw traces and controlled metrics so that such a result is scientifically interpretable.
