# JEV-RBP Architecture

## 1. Research boundary

The project separates four authorities:

\`\`\`
Candidate Generator
       |
       v
     JEV
       |
       v
Exact Evaluator
       |
       v
   Validator
       |
       v
  Benchmark
\`\`\`

Their responsibilities are different:

| Component | Question |
|---|---|
| Candidate generator | What actions are legal and worth considering? |
| JEV selector | Which candidates should be checked first? |
| Exact evaluator | What is the actual objective/feasibility effect? |
| Validator | Is the resulting solution valid? |
| Benchmark | How should the final result be measured? |

JEV must not silently take over the evaluator or validator.

## 2. Current RBP search loop

The recovered public VLNS reference uses:

\`\`\`
for iteration:
    best Drop
    if Drop improves:
        apply Drop

    best Add
    if Add improves:
        apply Add

    if neither Drop nor Add improved:
        best Swap
        if Swap improves:
            apply Swap

    if nothing improved:
        stop
\`\`\`

This phase ordering is now represented by \`ReferenceVLNSSolver\`.

The generic \`VLNSSolver\` remains available as a simpler orchestration shell
for experiments where one candidate family is deliberately isolated.

## 3. Two graph layers

\`\`\`
                    RBP instance
                         |
             +-----------+-----------+
             |                       |
             v                       v
      Physical network       Open block design
             |                       |
        Dijkstra                 directed
             |                  service graph
             v                       |
       physical route        commodity routing
             |                       |
             +-----------+-----------+
                         |
                         v
                  exact evaluator
                         |
                         v
                     validator
\`\`\`

The physical network and service network must never be conflated.

## 4. Module boundaries

| Module | Responsibility |
|---|---|
| \`problem.py\` | canonical RBP data model |
| \`actions.py\` | typed Drop/Add/Swap actions |
| \`routing.py\` | physical shortest-path routing |
| \`service.py\` | directed block-service routing |
| \`rerouting.py\` | reroute all demands after a proposed block design |
| \`evaluation.py\` | exact-evaluation interface |
| \`objective.py\` | objective components |
| \`vlns.py\` | generic and reference-shaped VLNS orchestration |
| \`selectors.py\` | Random/identity baselines and future JEV |
| \`validator.py\` | current independent structural validation |

## 5. JEV insertion point

The intended production experiment is:

\`\`\`
all legal candidates
       |
       v
cheap feature extraction
       |
       v
JEV ranking
       |
       v
Top-K
       |
       v
exact rerouting
       |
       v
objective + validator
       |
       v
accept best improving move
\`\`\`

For the vanilla baseline, Top-K is replaced by the complete candidate set.

Therefore:

\`\`\`
Vanilla VLNS = exact scan of all candidates
JEV-VLNS    = JEV ranking + exact scan of Top-K
\`\`\`

This is the central controlled comparison of the project.

## 6. Clean-room principle

The recovered implementation under \`data/reference/archive/\` is evidence about
behavior. It is not the implementation target to copy line-by-line.

The clean-room implementation should reproduce externally observable behavior
where required while keeping the architecture explicit and testable.
