# JEV-RBP — Product Requirements Document

## 1. Назначение

**JEV-RBP** — исследовательский прототип гибридной системы решения Railroad Blocking Problem (RBP), в которой:

- классический оптимизатор/метаэвристика выполняет основной поиск решения;
- JEV выступает как компактный **System-1 selector** — быстро оценивает локальные действия и выбирает перспективные кандидаты;
- Validator независимо проверяет корректность решения;
- benchmark/score измеряет результат;
- на следующих этапах LLM может проектировать новые алгоритмы поиска, neighborhoods и эвристики.

Главная идея проекта:

> **VLNS ищет решение. LLM ищет алгоритм, которым VLNS будет искать решение. JEV ищет хорошие локальные действия внутри этого алгоритма.**

JEV-RBP является **первым упрощённым экспериментом** более широкой JEV-Star архитектуры. Проект не должен преждевременно превращаться в полноценную LLM-систему: сначала необходимо доказать отдельную гипотезу о ценности JEV как локального селектора.

---

## 2. Контекст

Railroad Blocking Problem — комбинаторная задача оптимизации железнодорожной сети. Нужно одновременно определить, какие блоки открыть, как распределить/маршрутизировать потоки и как сформировать допустимые решения при ограничениях на инфраструктуру, объёмы, мощности и маршруты.

В публичной реализации Nicolas Bridelance использован VLNS (Very Large Neighborhood Search — поиск по очень большим окрестностям), основанный на:

1. Drop — закрытие существующего блока и перераспределение потоков;
2. Add — открытие нового блока;
3. Swap — комбинация Drop + Add;
4. best-improving steepest descent — полный просмотр допустимых ходов и применение лучшего улучшающего хода;
5. Dijkstra для решения routing subproblem.

Этот алгоритм является естественной средой для проверки JEV.

---

## 3. Исследовательская проблема

В обычном VLNS на каждой итерации может генерироваться большое число кандидатов, после чего каждый кандидат требует дорогой оценки.

Возникает вопрос:

> Можно ли обучить небольшой JEV-модель селектировать перспективные локальные действия так, чтобы при том же или меньшем compute budget получить решения не хуже vanilla VLNS, сократив число дорогих точных оценок?

Важно: JEV **не обязан самостоятельно решать RBP**.

Его задача значительно уже:

```
State + Candidate Actions
        ↓
       JEV
        ↓
 ranked / selected candidates
        ↓
 expensive exact evaluation
        ↓
 Validator + Score
```

---

## 4. Цели

### 4.1 Primary goal

Экспериментально проверить гипотезу:

> **JEV может эффективно ранжировать локальные действия внутри VLNS и уменьшать количество дорогих оценок без существенной потери качества решения.**

### 4.2 Secondary goals

1. Воспроизвести и стабилизировать vanilla VLNS baseline.
2. Формализовать state/action интерфейс.
3. Создать генератор legal candidate actions.
4. Собрать датасет из решений vanilla VLNS.
5. Обучить несколько вариантов JEV selector.
6. Сравнить Random / Greedy / JEV при одинаковом compute budget.
7. Измерить влияние JEV на:
   - objective;
   - gap относительно baseline/oracle;
   - число exact evaluations;
   - runtime;
   - feasibility;
   - scalability.
8. Создать основу для последующих экспериментов с LLM-generated heuristics.

### 4.3 Non-goals первого этапа

Не является целью v0.1:

- заменить VLNS нейросетью;
- заменить validator нейросетью;
- использовать LLM для каждого решения;
- решать L3 сразу end-to-end;
- строить полноценный autonomous research agent;
- доказывать глобальную оптимальность;
- делать JEV универсальным решателем RBP.

---

## 5. Исследовательские гипотезы

### H1 — Local ranking

JEV сможет ранжировать локальные действия лучше случайного выбора.

### H2 — Search efficiency

При ограниченном числе expensive evaluations JEV-VLNS сможет получить решение не хуже vanilla VLNS или приблизиться к нему быстрее.

### H3 — Generalization

JEV, обученный на малых/средних instances, сможет сохранять полезность на более крупных instances.

### H4 — Candidate-set dependence

Качество JEV сильно зависит от качества legal candidate generator. Поэтому candidate generation является самостоятельным экспериментальным объектом.

### H5 — Oracle transfer

На малых instances MIP может использоваться как teacher/oracle для формирования более качественных training labels.

---

## 6. Архитектура

### 6.1 Baseline

```
Initial solution
      ↓
VLNS
 ├── generate Drop/Add/Swap
 ├── evaluate candidates
 ├── choose best
 └── repeat
      ↓
Validator
      ↓
Score
```

### 6.2 JEV-VLNS

```
Initial solution
      ↓
VLNS
      ↓
Candidate Generator
      ↓
Legal candidate set
      ↓
JEV Selector
      ↓
Top-K candidates
      ↓
Exact evaluator / routing
      ↓
Validator
      ↓
Score
      ↓
Accept / Reject
      ↓
Next state
```

Ключевой принцип:

> JEV никогда не должен быть источником истины о feasibility. Он только предлагает приоритет. Validator и exact evaluator остаются авторитетными.

---

## 7. State representation

На первом этапе state должен быть компактным и интерпретируемым.

Возможные признаки:

### Network features
- origin/destination yard;
- shortest path distance;
- geographic/network distance;
- detour ratio;
- degree/connectivity;
- number of alternative routes.

### Block features
- block open/closed;
- current block volume;
- remaining capacity;
- fixed cost;
- handling cost;
- number of commodities using block;
- utilization ratio.

### Commodity features
- demand volume;
- origin;
- destination;
- commodity class/type;
- current route;
- current transport cost.

### Local congestion features
- overloaded yards;
- overloaded links;
- capacity slack;
- number of competing commodities;
- local block density.

Сначала использовать фиксированный tabular/vector representation. Graph Neural Network (GNN — нейросеть для графов) оставить отдельным экспериментом.

---

## 8. Action representation

Action — атомарное изменение текущего решения.

Первый набор:

### Drop

```
Drop(block_id)
```

### Add

```
Add(candidate_block)
```

### Swap

```
Swap(drop_block, add_block)
```

В первой версии рекомендуется начать с **одного action family**, чтобы не смешивать несколько источников сложности.

Приоритет:

1. Add/Drop;
2. Swap;
3. sequence/route repair;
4. destroy selection.

---

## 9. Candidate generation

JEV не должен рассматривать весь потенциальный action space.

Pipeline:

```
All possible actions
       ↓
domain constraints
       ↓
cheap feasibility filters
       ↓
candidate pool
       ↓
JEV ranking
       ↓
Top-K
       ↓
expensive evaluation
```

Candidate generator должен быть deterministic/reproducible при фиксированном seed.

Это позволит отдельно измерять:

- качество candidate pool;
- качество JEV ranking;
- качество exact evaluator.

---

## 10. JEV model

На v0.1 JEV рассматривается как небольшой ranking/scoring model.

Минимальный интерфейс:

```
score(state, action) -> scalar
```

или:

```
rank(state, candidate_actions) -> ordered_actions
```

Модель должна быть:

- маленькой;
- быстрой;
- CPU-friendly;
- детерминированной при inference;
- независимой от exact solver;
- заменяемой без изменения VLNS.

Возможные реализации:

1. linear model;
2. shallow MLP;
3. pairwise ranking model;
4. compact tree-based model;
5. небольшой policy network.

JEV не должен начинаться с большой transformer-модели.

---

## 11. Training data

Основной источник данных:

**vanilla VLNS trace**

Для каждой итерации сохранять:

```
state
candidate_action
cheap_features
exact_delta
feasible
accepted
rank
```

Пример:

```text
state_001
  action_001 → Δcost = -120
  action_002 → Δcost = +15
  action_003 → Δcost = -45
  ...
```

Это превращает vanilla VLNS в генератор supervised learning data.

### Oracle dataset

Для маленьких instances можно использовать MIP:

```
state
  ↓
local candidate actions
  ↓
MIP/exact evaluation
  ↓
best action / objective delta
  ↓
training label
```

MIP не используется как основной solver large instances.

---

## 12. Baselines

Обязательные baseline selectors:

### B0 — Random

Случайный выбор legal candidate.

### B1 — Greedy

Простая hand-designed heuristic.

### B2 — Vanilla VLNS

Оценка всех кандидатов и выбор лучшего.

### B3 — JEV

JEV выбирает Top-K кандидатов, после чего exact evaluator выбирает фактически лучший.

### B4 — JEV-1

JEV выбирает один candidate без полного exact scan.

Это позволит измерить trade-off:

```
quality ↔ number of expensive evaluations
```

---

## 13. Evaluation protocol

Каждый эксперимент должен фиксировать:

- dataset version;
- instance;
- random seed;
- initial solution;
- time limit;
- evaluation budget;
- model version;
- candidate pool size;
- K;
- hardware;
- solver versions.

Основные метрики:

### Solution quality

```
objective
fixed cost
transport cost
handling cost
gap
```

### Feasibility

```
C1 ... C7
validator_pass
constraint_violations
```

### Search efficiency

```
exact_evaluations
candidate_evaluations
iterations
accepted_moves
improvements
time
```

### JEV quality

```
top-1 hit rate
top-K hit rate
rank of best action
regret
Kendall/Spearman ranking correlation
```

---

## 14. Controlled comparison

Главное экспериментальное правило:

> При сравнении selector'ов нельзя одновременно менять optimizer, validator, dataset и compute budget.

Для одного benchmark run:

```
same instance
same initial solution
same candidate generator
same validator
same exact evaluator
same time/evaluation budget
different selector
```

Иначе невозможно определить эффект JEV.

---

## 15. Experiment ladder

### E0 — Reproduction

Воспроизвести Greedy + VLNS.

**Результат:** baseline metrics.

### E1 — Instrumented VLNS

Добавить logging всех candidate actions.

**Результат:** search traces.

### E2 — Candidate quality

Исследовать candidate generator.

**Результат:** насколько часто хороший move вообще попадает в candidate pool.

### E3 — JEV ranking

Обучить JEV выбирать лучший candidate.

**Результат:** ranking metrics.

### E4 — JEV-VLNS

Встроить JEV в VLNS.

**Результат:** quality/runtime/evaluation comparison.

### E5 — Oracle-trained JEV

Использовать MIP на малых instances.

**Результат:** проверить transfer from exact teacher.

### E6 — Generalization

Train на small/medium, test на larger.

### E7 — JEV destroy selector

JEV выбирает не только repair/action, но и область разрушения.

### E8 — LLM-generated neighborhoods

LLM предлагает новые destroy/repair heuristics.

### E9 — Evolution

FunSearch/ShinkaEvolve-подобный цикл:

```
LLM
 ↓
heuristic candidates
 ↓
VLNS
 ↓
JEV
 ↓
benchmark
 ↓
score
 ↓
archive
 ↓
LLM
```

---

## 16. Validator architecture

Validator должен быть независимым компонентом.

```
solution
   ↓
validator
 ├── C1 flow conservation
 ├── C2 track limit
 ├── C3 handling capacity
 ├── C4 minimum block volume/linking
 ├── C5 ...
 ├── C6 circuity
 └── C7 unique path / related constraints
```

Точные определения должны быть взяты из authoritative competition specification / validator implementation, а не реконструированы по предположениям.

Validator должен:

- возвращать pass/fail;
- возвращать структурированный список нарушений;
- не зависеть от JEV;
- использоваться в каждом benchmark run.

---

## 17. Reproducibility

Каждый experiment должен создавать artifact:

```
runs/
  <run_id>/
    config.json
    metrics.json
    solution.json
    trace.jsonl
    model/
    logs/
```

Run ID должен позволять однозначно восстановить:

- code commit;
- configuration;
- dataset;
- seed;
- model;
- result.

---

## 18. Proposed repository structure

```
jev-rbp/
├── README.md
├── PRD.md
├── PLAN.md
├── pyproject.toml
├── configs/
├── data/
│   └── README.md
├── docs/
│   ├── architecture.md
│   ├── experiments.md
│   └── research.md
├── src/
│   └── jev_rbp/
│       ├── problem/
│       ├── solver/
│       ├── vlns/
│       ├── candidates/
│       ├── jev/
│       ├── validator/
│       ├── evaluation/
│       ├── data/
│       └── cli.py
├── tests/
├── experiments/
│   ├── e0_reproduction/
│   ├── e1_instrumented_vlns/
│   ├── e2_candidates/
│   ├── e3_jev_ranking/
│   └── e4_jev_vlns/
├── scripts/
└── runs/
```

---

## 19. Interfaces

### Solver

```python
solve(instance, config) -> Solution
```

### Candidate generator

```python
generate(state) -> list[CandidateAction]
```

### JEV

```python
rank(state, candidates) -> RankedCandidates
```

### Exact evaluator

```python
evaluate_move(state, action) -> Evaluation
```

### Validator

```python
validate(solution) -> ValidationResult
```

### Benchmark

```python
benchmark(solution, instance) -> Metrics
```

---

## 20. Acceptance criteria for v0.1

v0.1 считается завершённой, если:

1. Vanilla VLNS воспроизводится на выбранных benchmark instances.
2. Validator работает независимо и возвращает structured results.
3. Candidate actions логируются.
4. Есть reproducible experiment runner.
5. Random и Greedy selectors имеют baseline metrics.
6. JEV обучается на trace data.
7. JEV корректно интегрируется без изменения exact evaluator.
8. Есть controlled comparison Random vs Greedy vs JEV.
9. Результаты сохраняются в reproducible artifacts.
10. README содержит команду запуска полного минимального эксперимента.

На этом этапе **не требуется** превосходство JEV над VLNS.

Научно корректный результат может быть отрицательным: например, JEV может не давать выигрыша или требовать большего candidate pool. Такой результат должен быть сохранён как valid research finding.

---

## 21. Definition of Done для научного эксперимента

Эксперимент считается законченным только если:

- есть hypothesis;
- есть baseline;
- есть controlled comparison;
- есть фиксированный budget;
- есть несколько seeds;
- есть raw traces;
- есть aggregate metrics;
- есть failure analysis;
- есть reproducibility instructions;
- вывод не смешивает качество решения и качество селектора.

---

## 22. Future architecture: JEV-Star

После доказательства локальной гипотезы проект может перейти к рекурсивной архитектуре:

```
                 LLM
                  │
          invent / modify
          search algorithms
                  │
                  ▼
        Destroy / Repair DSL
                  │
                  ▼
                VLNS
                  │
                  ▼
                JEV
                  │
          local action choice
                  │
                  ▼
              Validator
                  │
                  ▼
              Benchmark
                  │
                  ▼
             Archive/Score
                  │
                  └──────────→ LLM
```

Здесь роли принципиально разделены:

- **LLM** — System-2: придумывает/модифицирует стратегии поиска;
- **VLNS** — выполняет поиск решения;
- **JEV** — System-1: быстро выбирает локальные действия;
- **Validator** — определяет допустимость;
- **Benchmark** — измеряет результат;
- **Archive** — сохраняет лучшие алгоритмические находки.

JEV-RBP v0.1 — экспериментальная нижняя часть этой архитектуры, а не конечная система.
