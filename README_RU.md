# JEV-RBP

**JEV-RBP** — исследовательский прототип, на котором мы проверяем конкретную
гипотезу внутри задачи **Railroad Blocking Problem (RBP)** — оптимизации
блокирования железнодорожных грузов.

Ключевая идея проекта:

> **VLNS ищет решение. LLM ищет алгоритм, которым VLNS будет искать решение.
> JEV ищет хорошие локальные действия внутри этого алгоритма.**

JEV-RBP — это **первый упрощённый экспериментальный слой** более широкой
архитектуры JEV-Star. Поэтому на этом этапе мы сознательно не пытаемся
заменить VLNS, точный оцениватель или Validator нейросетью.

## Что именно мы проверяем?

Railroad Blocking Problem — комбинаторная задача, в которой нужно определить,
какие направленные блоки открыть, как провести грузы через сеть блоков и какие
физические маршруты использовать, соблюдая ограничения железнодорожной сети.

В качестве baseline используется **VLNS (Very Large Neighborhood Search —
поиск по очень большим окрестностям)**. Это метаэвристика, которая
последовательно изменяет текущее решение локальными действиями:

- **Drop** — закрыть существующий блок;
- **Add** — открыть новый блок;
- **Swap** — закрыть один блок и открыть другой.

Из восстановленной reference-реализации следует важная последовательность:

\`\`\`
текущее решение
      |
      +--> лучший Drop ----> применить, если улучшает
      |
      +--> лучший Add  ----> применить, если улучшает
      |
      +--> если ни Drop, ни Add не улучшили:
             лучший Swap --> применить, если улучшает
      |
      +--> если улучшения нет: остановиться
\`\`\`

Это **не один общий поиск лучшего хода среди Drop + Add + Swap**.
Сначала полностью рассматривается Drop; если найдено улучшение, оно сразу
применяется. Только после этого формируются и оцениваются Add.

JEV появляется только после стабилизации этого baseline:

\`\`\`
кандидатные действия
        |
        v
     JEV rank
        |
        v
      Top-K
        |
        v
точная переоценка + rerouting
        |
        v
    Validator
        |
        v
  принять / отклонить
\`\`\`

То есть JEV — **селектор**, а не источник истины.

## Текущий статус

**Phase 3 — clean-room воспроизведение vanilla VLNS**

Уже реализовано:

- каноническая модель RBP;
- загрузчик GMNS/RAS CSV;
- двунаправленный shortest-path routing физической сети;
- отдельный направленный граф блоков;
- rerouting грузов через открытые блоки;
- агрегация объёмов блоков;
- удаление открытых, но фактически не используемых блоков;
- типизированные Drop/Add/Swap actions;
- control flow Drop → Add → conditional Swap;
- детерминированные baseline-selectors;
- независимый seed-validator;
- начальные компоненты objective;
- regression tests для физической и сервисной маршрутизации.

Ещё предстоит:

- полностью восстановить candidate generation и фильтры reference VLNS;
- реализовать точный Drop/Add/Swap move evaluator;
- реализовать полный benchmark Validator C1–C9b;
- реализовать полный operating objective: fixed + transport + handling +
  interchange;
- учитывать capacity при выборе физических маршрутов;
- сделать benchmark runner и reproducible artifacts;
- собирать traces для обучения JEV.

Reference-код не копируется в \`src/\`. Восстановленная реализация хранится в
\`data/reference/archive/\` как археологический источник. Основной solver
пишется заново, чтобы отделить поведение алгоритма от исторической реализации.

## Два разных графа

Одна из ключевых идей реализации — **физическая сеть и сеть блоков являются
разными графами**.

### Физическая сеть

Она состоит из физических track links. Через неё мы ищем физический
shortest path (кратчайший физический маршрут) для каждого блока.

В восстановленном reference loader физические связи используются как
двунаправленные для shortest-path computation, даже если строка CSV содержит
направление \`from_node_id -> to_node_id\`.

### Сеть блоков

Block — это **направленная сервисная дуга**:

\`\`\`
Yard A  ----block---->  Yard B
\`\`\`

A → B и B → A — разные блоки с разными fixed costs.

Груз сначала выбирает последовательность таких сервисных блоков, а каждый
блок имеет отдельный физический маршрут.

\`\`\`
физический граф                 граф блоков

track links                     opened blocks
     |                               |
     v                               v
Dijkstra shortest path         routing commodities
     |                               |
     +----------> block <------------+
\`\`\`

Подробности: [docs/service-routing.md](docs/service-routing.md).

## Где что находится

\`\`\`
jev-rbp/
├── README.md
├── README_RU.md
├── PRD.md
├── PLAN.md
├── data/reference/archive/    # восстановленный reference-код
├── docs/
│   ├── architecture.md
│   ├── benchmark-archaeology.md
│   ├── experiments.md
│   ├── reference-vlns.md
│   ├── rbp.md
│   ├── research.md
│   ├── service-routing.md
│   └── solver-archaeology.md
├── src/jev_rbp/
│   ├── actions.py
│   ├── core.py
│   ├── evaluation.py
│   ├── greedy.py
│   ├── io.py
│   ├── objective.py
│   ├── problem.py
│   ├── rerouting.py
│   ├── routing.py
│   ├── selectors.py
│   ├── service.py
│   ├── validator.py
│   └── vlns.py
└── tests/
\`\`\`

## Запуск

Требуется Python 3.11+.

\`\`\`bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
jev-rbp
\`\`\`

## Исследовательский roadmap

1. Воспроизвести control flow reference VLNS.
2. Воспроизвести candidate generation и exact move evaluation.
3. Воспроизвести benchmark validator и objective.
4. Добавить instrumentation и собирать search traces.
5. Измерить качество candidate pool.
6. Обучить небольшой JEV ranker.
7. Сравнить Random / Greedy / Vanilla VLNS / JEV Top-K.
8. Проверить generalization.
9. Использовать MIP как exact teacher на маленьких instances.
10. Разрешить LLM генерировать новые neighborhoods и search heuristics.
11. Перейти к JEV-Star.

## Документация

- [PRD](PRD.md) — требования, гипотезы и экспериментальная методология.
- [PLAN](PLAN.md) — текущий план реализации.
- [Architecture](docs/architecture.md) — архитектурные границы.
- [Service routing](docs/service-routing.md) — физический граф и граф блоков.
- [Solver archaeology](docs/solver-archaeology.md) — восстановление reference VLNS.
- [Benchmark archaeology](docs/benchmark-archaeology.md) — контракт RAS v2.1.
- [Experiments](docs/experiments.md) — протокол контролируемых экспериментов.
- [RBP model](docs/rbp.md) — модель задачи.

## Почему JEV не должен заменять Validator

Это принципиальный экспериментальный инвариант:

> JEV может ошибаться. Validator — нет.

JEV отвечает только на вопрос:

**«Какой из допустимых кандидатов стоит проверить первым?»**

Exact evaluator отвечает:

**«Что реально произойдёт, если применить этот ход?»**

Validator отвечает:

**«Получилось ли допустимое решение?»**

Именно такое разделение позволит впоследствии честно измерить пользу JEV.

## Статус исследования

Цель v0.1 — не доказать заранее, что JEV лучше VLNS.

Мы хотим получить воспроизводимый эксперимент, в котором можно измерить
trade-off:

\`\`\`
качество решения
        ↕
число дорогих exact evaluations
        ↕
время поиска
\`\`\`

Если JEV не даст выигрыша — это тоже полезный результат, если эксперимент
проведён при одинаковом candidate generator, evaluator, validator и compute
budget.

Более общая архитектура JEV-Star рассматривается отдельно от
RBP-специфического эксперимента.
