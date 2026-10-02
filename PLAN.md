# JEV-RBP — Project Plan

## 0. Стратегия

Проект строится как последовательность небольших воспроизводимых экспериментов.

Главное правило:

> Не добавлять следующий уровень сложности, пока предыдущий не измерен.

Порядок:

```
RBP understanding
      ↓
VLNS reproduction
      ↓
instrumentation
      ↓
candidate generator
      ↓
training data
      ↓
JEV ranking
      ↓
JEV-VLNS
      ↓
oracle / generalization
      ↓
LLM-generated heuristics
      ↓
JEV-Star
```

---

# Phase 0 — Repository foundation

### Tasks

- [ ] создать Python project;
- [ ] добавить pyproject.toml;
- [ ] настроить test framework;
- [ ] настроить lint/format;
- [ ] добавить GitHub Actions;
- [ ] определить Python version;
- [ ] создать базовую структуру src/tests/experiments/docs;
- [ ] добавить README;
- [ ] добавить PRD;
- [ ] добавить PLAN.

### Exit criteria

Repository устанавливается одной командой и запускает пустой test suite.

---

# Phase 1 — RBP specification

## Цель

Создать собственное canonical описание RBP для проекта.

### Tasks

- [ ] собрать authoritative problem specification;
- [ ] зафиксировать dataset version;
- [ ] описать C1–C7;
- [ ] описать objective;
- [ ] описать solution format;
- [ ] описать Block Design;
- [ ] описать Blocking Sequence;
- [ ] описать Block Route;
- [ ] определить допустимые actions;
- [ ] определить terminology.

### Deliverable

`docs/rbp.md`

### Exit criteria

Разработчик может понять задачу без чтения внешнего notebook.

---

# Phase 2 — Baseline archaeology

## Цель

Не переписывать VLNS вслепую.

### Tasks

- [ ] получить исходный код reference VLNS;
- [ ] получить MIP implementation;
- [ ] выделить solution representation;
- [ ] выделить candidate generation;
- [ ] выделить routing;
- [ ] выделить objective;
- [ ] выделить acceptance;
- [ ] выделить termination;
- [ ] документировать зависимости;
- [ ] определить, какие части можно адаптировать;
- [ ] зафиксировать provenance/reference commit.

### Deliverable

`docs/reference-vlns.md`

---

# Phase 3 — Vanilla VLNS reproduction

## Цель

Получить полностью воспроизводимый baseline.

### Tasks

- [ ] загрузка dataset;
- [ ] greedy initial solution;
- [ ] Drop;
- [ ] Add;
- [ ] Swap;
- [ ] exact routing;
- [ ] objective;
- [ ] validator;
- [ ] stopping criteria;
- [ ] benchmark runner.

### Metrics

- objective;
- runtime;
- iterations;
- improvements;
- number of candidate evaluations;
- feasibility.

### Exit criteria

На контрольных instances результаты согласуются с reference implementation в пределах заранее определённого tolerance.

---

# Phase 4 — Validator

## Цель

Сделать validator first-class component.

### Tasks

- [ ] реализовать structured ValidationResult;
- [ ] реализовать C1;
- [ ] реализовать C2;
- [ ] реализовать C3;
- [ ] реализовать C4;
- [ ] реализовать C5;
- [ ] реализовать C6;
- [ ] реализовать C7;
- [ ] добавить negative tests;
- [ ] добавить property tests;
- [ ] проверить edge cases.

### Exit criteria

Невалидные решения обнаруживаются независимо от optimizer.

---

# Phase 5 — Instrumentation

## Цель

Превратить VLNS в генератор research traces.

### На каждой итерации сохранять

```
run_id
instance_id
iteration
state_id
action_id
action_type
features
feasible
objective_before
objective_after
delta
accepted
rank
runtime
```

### Tasks

- [ ] JSONL trace writer;
- [ ] state hashing;
- [ ] candidate IDs;
- [ ] action serialization;
- [ ] timing instrumentation;
- [ ] exact evaluation counter;
- [ ] experiment metadata.

### Exit criteria

Один run можно полностью проанализировать offline.

---

# Phase 6 — Candidate Generator

## Цель

Отделить "какие действия вообще возможны" от "какое действие выбрать".

### Tasks

- [ ] all candidate actions;
- [ ] cheap feasibility filters;
- [ ] domain-specific filters;
- [ ] deterministic candidate ordering;
- [ ] candidate pool statistics.

### Experiments

Измерять:

```
candidate_pool_size
best_action_in_pool
feasible_fraction
duplicate_fraction
candidate_generation_time
```

### Ключевой вопрос

Как часто оптимальное/лучшее локальное действие вообще присутствует в candidate pool?

Если редко — улучшение JEV не поможет.

---

# Phase 7 — Selector baselines

## Цель

Создать controlled selector benchmark.

### Selectors

- [ ] Random;
- [ ] Uniform random with seed;
- [ ] Greedy hand-designed;
- [ ] Oracle best;
- [ ] JEV placeholder.

### Important

Все selectors должны использовать один и тот же:

- state;
- candidate set;
- evaluator;
- validator;
- budget.

---

# Phase 8 — JEV dataset

## Цель

Сформировать первый dataset для обучения JEV.

### Sources

1. vanilla VLNS traces;
2. optionally MIP oracle on small instances.

### Dataset format

```
state_features
candidate_features
action_type
objective_delta
feasible
rank
best_action
```

### Tasks

- [ ] dataset exporter;
- [ ] train/validation/test split;
- [ ] split by instance, not random rows;
- [ ] prevent state leakage;
- [ ] normalization;
- [ ] feature schema versioning.

### Exit criteria

Есть frozen dataset version.

---

# Phase 9 — JEV v0

## Цель

Проверить, способен ли компактный model rank local actions.

### Models

Порядок:

1. linear scorer;
2. shallow MLP;
3. pairwise ranker.

Не использовать большую LLM.

### Metrics

- Top-1 accuracy;
- Top-5 / Top-K recall;
- rank correlation;
- regret;
- inference latency.

### Exit criteria

Есть объективное сравнение с Random и Greedy.

---

# Phase 10 — JEV-VLNS

## Цель

Встроить JEV в search loop.

### Architecture

```
VLNS state
   ↓
candidate generator
   ↓
JEV
   ↓
Top-K
   ↓
exact evaluator
   ↓
best candidate
   ↓
accept
```

### Experimental matrix

| Selector | Exact evaluations | Quality | Runtime |
|---|---:|---:|---:|
| Random | baseline | measure | measure |
| Greedy | baseline | measure | measure |
| Vanilla VLNS | all | measure | measure |
| JEV Top-1 | reduced | measure | measure |
| JEV Top-5 | reduced | measure | measure |
| JEV Top-10 | reduced | measure | measure |

### Главный результат

Не только "JEV дал лучше objective".

Главный результат:

```
quality achieved
      /
expensive evaluations
```

---

# Phase 11 — Generalization

## Цель

Проверить, не запоминает ли JEV конкретные instances.

### Splits

- train: small;
- validation: medium;
- test: unseen medium/large.

### Additional tests

- unseen seeds;
- unseen network regions;
- unseen demand distributions;
- larger candidate pools.

### Exit criteria

Получена карта зависимости качества JEV от размера и distribution shift.

---

# Phase 12 — MIP Oracle

## Цель

Использовать MIP там, где он действительно полезен.

### Small instances

```
MIP
 ↓
optimal solution
 ↓
local candidate evaluation
 ↓
teacher labels
 ↓
JEV
```

### Tasks

- [ ] generate small instances;
- [ ] solve with MIP;
- [ ] derive oracle labels;
- [ ] compare MIP-trained JEV vs VLNS-trained JEV;
- [ ] test transfer to larger instances.

### Research question

Даёт ли обучение от exact oracle более полезную локальную policy, чем imitation of VLNS?

---

# Phase 13 — JEV Destroy Selector

## Цель

Перейти от выбора действия к выбору места поиска.

Вместо:

```
Which repair action?
```

JEV отвечает:

```
Where should VLNS search next?
```

Candidates:

- overloaded yard;
- underutilized block;
- high-cost commodity;
- congested region;
- high-circuity route.

---

# Phase 14 — LLM-generated neighborhoods

## Цель

Добавить System-2 слой.

LLM не решает конкретный RBP.

LLM генерирует:

- destroy strategy;
- repair strategy;
- candidate filter;
- acceptance rule;
- feature hypothesis.

### Preferred representation

Structured heuristic DSL:

```yaml
name: overloaded_yard_escape

destroy:
  target: overloaded_yards
  radius: 2

repair:
  actions:
    - add_block
    - reroute_commodity

selection:
  objective: transport_cost_delta
```

Это безопаснее и воспроизводимее, чем позволять LLM произвольно менять весь solver.

---

# Phase 15 — Evolution of heuristics

## Цель

Добавить evolutionary search / FunSearch-like loop.

```
heuristic population
       ↓
evaluate on benchmark
       ↓
score
       ↓
select
       ↓
LLM mutation / synthesis
       ↓
new heuristics
       ↺
```

### Tasks

- [ ] heuristic DSL;
- [ ] evaluator sandbox;
- [ ] archive;
- [ ] mutation;
- [ ] deduplication;
- [ ] benchmark budget;
- [ ] reproducible seeds.

---

# Phase 16 — Full JEV-Star experiment

## Final architecture

```
                    LLM
                     │
              algorithm invention
                     │
                     ▼
              heuristic / DSL
                     │
                     ▼
              candidate search
                     │
                     ▼
                   VLNS
                     │
                     ▼
                   JEV
                     │
                local action
                     │
                     ▼
                 Validator
                     │
                     ▼
                 Benchmark
                     │
                     ▼
              Score / Archive
                     │
                     └──────→ LLM
```

### Research question

Можно ли получить систему, которая не просто ищет решение, а **улучшает сам способ поиска решения**?

---

# Milestones

## M0 — Foundation

Repository + tooling + docs.

## M1 — Reproduction

Greedy + VLNS + Validator.

## M2 — Instrumentation

Search traces.

## M3 — Candidate science

Candidate pool analysis.

## M4 — JEV

Standalone ranking model.

## M5 — JEV-VLNS

Controlled integrated experiment.

## M6 — Oracle/generalization

MIP teacher + unseen instances.

## M7 — Algorithm invention

LLM-generated heuristics.

## M8 — JEV-Star

Closed research loop.

---

# Priority

## P0 — Must have

- RBP specification;
- reference VLNS understanding;
- reproducible baseline;
- validator;
- trace logging;
- candidate generator;
- Random/Greedy baselines;
- JEV ranking;
- JEV-VLNS;
- controlled evaluation.

## P1 — Important

- MIP oracle;
- generalization;
- destroy selector;
- experiment dashboard.

## P2 — Research extensions

- GNN;
- LLM heuristic DSL;
- evolutionary heuristic search;
- FunSearch-like loop;
- autonomous research agent.

---

# Immediate next steps

1. Получить reference `src/solvers/vlns.py`.
2. Получить reference `src/solvers/mip.py`.
3. Построить точную карту функций VLNS.
4. Реализовать минимальный RBP data model.
5. Реализовать/адаптировать Validator.
6. Воспроизвести Greedy → VLNS.
7. Добавить trace instrumentation.
8. Только после этого реализовать JEV interface.

**Первый научный эксперимент проекта:**

> При одинаковом candidate generator, exact evaluator, validator, initial solution и evaluation budget сравнить Random, Greedy и JEV как локальные selectors внутри VLNS.
