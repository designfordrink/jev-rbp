# Service routing

## Why two graphs?

JEV-RBP models the Railroad Blocking Problem with two related but distinct
graphs.

### 1. Physical graph

The physical graph is the rail infrastructure:

- nodes are physical network nodes, including yards;
- links are physical track segments;
- Dijkstra computes physical shortest paths between yards.

The recovered reference loader builds an undirected physical graph for this
purpose. The original link identifier is retained when a physical edge is
traversed in reverse.

### 2. Blocking-service graph

The service graph is a directed graph whose arcs are opened blocks:

\`\`\`
yard A  ---- block A->B ---->  yard B
\`\`\`

A → B and B → A are separate services. Commodity routing is performed on this
graph.

This distinction is not cosmetic. A physical path answers:

> How can a block physically travel from A to B?

The service graph answers:

> Which sequence of opened blocks should a commodity use from its origin to
> its destination?

## Service-arc cost

For a commodity k and block i → j, the recovered reference routing rule is
equivalent to a per-car arc cost:

\`\`\`
transport_cost_coefficient * physical_distance(i,j)
+ handling_cost(j), if j is not the final destination
\`\`\`

The commodity volume is applied after the service route is selected because it
is constant across all candidate paths for that commodity.

This means the service router can use Dijkstra again, but on the directed
block graph rather than on the physical rail network.

## Rerouting

Given a proposed set of opened blocks:

1. Build the directed service graph.
2. Restrict blocks to the commodity's block type.
3. Route every demand through that graph.
4. Reject the candidate if any demand becomes unroutable.
5. Aggregate demand volume over every used block.
6. Remove opened-but-unused blocks.
7. Attach the physical shortest route to each used block.

The resulting object is a complete candidate solution suitable for exact
objective evaluation and independent validation.

## Why rerouting is the expensive boundary

A Drop/Add/Swap action changes the service graph. That can change the route of
many commodities, so evaluating one local action is not just a local arithmetic
operation.

Conceptually:

\`\`\`
local action
    |
    v
changed block graph
    |
    v
Dijkstra for every affected/all commodity demands
    |
    v
new block volumes
    |
    v
objective + feasibility
\`\`\`

This is exactly the boundary where a JEV selector can become useful: JEV can
rank many candidate actions cheaply, while exact rerouting is performed only
for the selected Top-K candidates.

## Current implementation boundary

Implemented now:

- directed service graph;
- commodity-type compatibility;
- Dijkstra over service blocks;
- physical-route caching;
- all-demand rerouting;
- block-volume aggregation;
- unused-block pruning.

Not yet implemented:

- link-capacity-aware physical route selection;
- full C1–C9b validation;
- complete objective;
- exact candidate filters;
- complete reference move evaluator.

These omissions are deliberate: the current layer is a clean, testable routing
boundary rather than a claim of full benchmark equivalence.
