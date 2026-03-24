# 🌿 Apache Airflow 3.x — DAG Branching Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Intermediate  
> **Prerequisite:** Complete the [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to build conditional workflows using BranchPythonOperator

---

## 📑 Table of Contents

- [What is Branching?](#-what-is-branching)
- [How BranchPythonOperator Works](#-how-branchpythonoperator-works)
- [Use Case 1 — Basic Branch (Even / Odd Day)](#-use-case-1--basic-branch-even--odd-day)
- [Use Case 2 — Sales Data Pipeline](#-use-case-2--sales-data-pipeline)
- [Use Case 3 — Multiple Branches (Day of Week)](#-use-case-3--multiple-branches-day-of-week)
- [Use Case 4 — Nested Branching](#-use-case-4--nested-branching-branch-inside-a-branch)
- [trigger_rule Reference](#-trigger_rule-reference-critical-concept)
- [Common Branching Mistakes](#-common-branching-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 What is Branching?

Branching allows a DAG to take **different execution paths** based on a condition — just like an `if/else` statement in Python.

Instead of always running all tasks, Airflow runs **only the relevant branch** and **skips everything else**.

```
                    ┌──→ Task A (branch 1) ──→┐
start → branch_task ┤                         ├──→ end
                    └──→ Task B (branch 2) ──→┘
```

### When to Use Branching:
- Run different tasks based on **data values** (e.g., high/low sales)
- Run different tasks based on **day/time** (e.g., weekday vs weekend)
- Run different tasks based on **environment** (e.g., dev vs prod)
- Run different tasks based on **data quality** results

---

## ⚙️ How BranchPythonOperator Works

```python
from airflow.providers.standard.operators.python import BranchPythonOperator
```

### The 3 Rules:
1. Your branch function **must return a `task_id`** (or list of task IDs)
2. Airflow runs **only the returned task(s)** — all others are **skipped**
3. Tasks **after** a branch join need a special `trigger_rule` to run correctly

```python
def my_branch_function(**context):
    if some_condition:
        return "task_id_for_path_a"    # ← return the task_id string
    else:
        return "task_id_for_path_b"    # ← not the function name, the task_id!

branch_task = BranchPythonOperator(
    task_id="my_branch",
    python_callable=my_branch_function,
)
```

> 💡 **Key Insight:** The branch function returns a **string** (task_id), not a function call.  
> ✅ Correct: `return "send_email"`  
> ❌ Wrong: `return send_email()`

---

## ✏️ Use Case 1 — Basic Branch (Even / Odd Day)

A simple introduction to understand the branching concept.

**File:** `dags/dag_branch_01_basic.py`

```python
# dag_branch_01_basic.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from datetime import datetime

with DAG(
    dag_id="dag_branch_01_basic",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["branching", "beginner"],
):

    # Step 1: Branch function — returns a task_id based on condition
    def choose_branch(**context):
        day = datetime.now().day
        print(f"Today is day number: {day}")

        if day % 2 == 0:
            return "even_day_task"    # ← task_id to run
        else:
            return "odd_day_task"     # ← task_id to run

    # Step 2: BranchPythonOperator wraps the function
    branch = BranchPythonOperator(
        task_id="check_day",
        python_callable=choose_branch,
    )

    # Step 3: Define the two branch tasks
    even = PythonOperator(
        task_id="even_day_task",
        python_callable=lambda: print("📅 Even day — running even pipeline!"),
    )

    odd = PythonOperator(
        task_id="odd_day_task",
        python_callable=lambda: print("📅 Odd day — running odd pipeline!"),
    )

    # Step 4: Wire it up — branch points to BOTH, but only runs ONE
    branch >> [even, odd]
```

### Flow Diagram:
```
              ┌──→ even_day_task  (runs on even days)
check_day ────┤
              └──→ odd_day_task   (runs on odd days)
```

### 🎯 What to Observe in the UI:
- The **running task** turns **green**
- The **skipped task** turns **pink/grey** (this is normal — not a failure!)
- In **Graph view** you can see both paths with arrows

### 🔬 Experiment:
Change the condition to always return one branch and trigger manually:
```python
def choose_branch(**context):
    return "even_day_task"    # force even branch always
```

---

## ✏️ Use Case 2 — Sales Data Pipeline

**Scenario:** After extracting sales data, branch based on performance:
- Sales **> ₹10,000** → Send **success alert** + Generate **report**
- Sales **≤ ₹10,000** → Send **warning alert** + **Escalate** to manager

**File:** `dags/dag_branch_02_sales.py`

```python
# dag_branch_02_sales.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from datetime import datetime

with DAG(
    dag_id="dag_branch_02_sales",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["branching", "sales"],
):

    # ── Task 1: Extract sales data ──────────────────────────────────
    def extract_sales(**context):
        # Simulated sales — change this value to test both branches
        sales_data = {
            "date"       : str(datetime.now().date()),
            "total_sales": 15000,     # 👈 Change to 5000 to test warning branch
            "orders"     : 120,
            "region"     : "South India",
        }
        print(f"📥 Sales extracted: {sales_data}")
        context["ti"].xcom_push(key="sales_data", value=sales_data)

    extract = PythonOperator(
        task_id="extract_sales",
        python_callable=extract_sales,
    )

    # ── Task 2: Branch based on sales threshold ─────────────────────
    def check_sales_threshold(**context):
        sales_data = context["ti"].xcom_pull(
            task_ids="extract_sales", key="sales_data"
        )
        total = sales_data["total_sales"]
        print(f"💰 Total Sales: ₹{total}")

        if total > 10000:
            print("✅ Above target — SUCCESS branch")
            return "send_success_alert"
        else:
            print("⚠️  Below target — WARNING branch")
            return "send_warning_alert"

    branch = BranchPythonOperator(
        task_id="check_threshold",
        python_callable=check_sales_threshold,
    )

    # ── Branch A: SUCCESS path ──────────────────────────────────────
    def send_success_alert(**context):
        data = context["ti"].xcom_pull(task_ids="extract_sales", key="sales_data")
        print(f"✅ SUCCESS: Sales ₹{data['total_sales']} exceeded target!")
        print(f"   Region  : {data['region']}")
        print(f"   Orders  : {data['orders']}")

    def generate_report(**context):
        data = context["ti"].xcom_pull(task_ids="extract_sales", key="sales_data")
        print(f"📊 Generating report for {data['date']}...")
        print(f"   Total Sales : ₹{data['total_sales']}")
        print(f"   Status      : ABOVE TARGET 🎯")

    success_alert = PythonOperator(
        task_id="send_success_alert",
        python_callable=send_success_alert,
    )

    report = PythonOperator(
        task_id="generate_report",
        python_callable=generate_report,
    )

    # ── Branch B: WARNING path ──────────────────────────────────────
    def send_warning_alert(**context):
        data = context["ti"].xcom_pull(task_ids="extract_sales", key="sales_data")
        print(f"⚠️  WARNING: Sales ₹{data['total_sales']} BELOW target ₹10,000!")
        print(f"   Region    : {data['region']}")
        print(f"   Shortfall : ₹{10000 - data['total_sales']}")

    def escalate_to_manager(**context):
        data = context["ti"].xcom_pull(task_ids="extract_sales", key="sales_data")
        print(f"🔺 Escalating to manager...")
        print(f"   Shortfall : ₹{10000 - data['total_sales']}")
        print(f"   Action    : Immediate review required")

    warning_alert = PythonOperator(
        task_id="send_warning_alert",
        python_callable=send_warning_alert,
    )

    escalate = PythonOperator(
        task_id="escalate_to_manager",
        python_callable=escalate_to_manager,
    )

    # ── Final task: runs REGARDLESS of which branch was taken ───────
    def pipeline_complete(**context):
        print("🏁 Daily sales pipeline complete.")

    complete = PythonOperator(
        task_id="pipeline_complete",
        python_callable=pipeline_complete,
        trigger_rule="none_failed_min_one_success",   # ← KEY for post-branch tasks
    )

    # ── Wire everything up ──────────────────────────────────────────
    extract >> branch
    branch >> [success_alert, warning_alert]
    success_alert >> report    >> complete
    warning_alert >> escalate  >> complete
```

### Flow Diagram:
```
                           ┌→ send_success_alert → generate_report   →┐
extract → check_threshold ─┤                                           ├→ pipeline_complete
                           └→ send_warning_alert → escalate_to_manager→┘
```

### 🎯 What to Observe:
- Run with `total_sales = 15000` → success path runs, warning path skipped
- Run with `total_sales = 5000`  → warning path runs, success path skipped
- `pipeline_complete` **always runs** thanks to `trigger_rule`
- Check the **XCom tab** to see `sales_data` passed between tasks

### 🔬 Experiments:
1. Change `total_sales` to `10000` exactly — which branch runs?
2. Remove `trigger_rule` from `pipeline_complete` — what happens?
3. Add `trigger_rule` back — confirm `pipeline_complete` runs correctly

---

## ✏️ Use Case 3 — Multiple Branches (Day of Week)

**Scenario:** Different pipeline logic depending on what day it is:
- **Friday** → Full ETL + weekly summary report
- **Mon–Thu** → Standard daily ETL
- **Weekend** → Light maintenance only

**File:** `dags/dag_branch_03_multipath.py`

```python
# dag_branch_03_multipath.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from datetime import datetime

with DAG(
    dag_id="dag_branch_03_multipath",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["branching", "intermediate"],
):

    # Branch function returning one of THREE possible task_ids
    def decide_by_day(**context):
        day_name = datetime.now().strftime("%A")    # "Monday", "Tuesday"...
        day_num  = datetime.now().weekday()          # 0=Mon ... 6=Sun
        print(f"📅 Today is {day_name} (day {day_num})")

        if day_num == 4:       # Friday
            return "friday_processing"
        elif day_num < 5:      # Monday to Thursday
            return "weekday_processing"
        else:                  # Saturday or Sunday
            return "weekend_processing"

    branch = BranchPythonOperator(
        task_id="decide_by_day",
        python_callable=decide_by_day,
    )

    weekday = PythonOperator(
        task_id="weekday_processing",
        python_callable=lambda: print("💼 Running standard weekday ETL pipeline"),
    )

    friday = PythonOperator(
        task_id="friday_processing",
        python_callable=lambda: print("📊 Friday: ETL + weekly summary report"),
    )

    weekend = PythonOperator(
        task_id="weekend_processing",
        python_callable=lambda: print("🌙 Weekend: Light maintenance tasks only"),
    )

    done = PythonOperator(
        task_id="done",
        python_callable=lambda: print("✅ Daily pipeline complete!"),
        trigger_rule="none_failed_min_one_success",
    )

    # All 3 branches connect back to the same final task
    branch >> [weekday, friday, weekend] >> done
```

### Flow Diagram:
```
               ┌→ weekday_processing  →┐
decide_by_day ─├→ friday_processing   →├→ done
               └→ weekend_processing  →┘
```

### 🎯 What to Observe:
- Only **one** of the three middle tasks runs each time
- The other two are **skipped** (pink in the UI)
- `done` always runs thanks to `trigger_rule`

### 🔬 Experiment:
Modify the function to force a specific branch for testing:
```python
def decide_by_day(**context):
    return "friday_processing"    # force Friday branch
```

---

## ✏️ Use Case 4 — Nested Branching (Branch Inside a Branch)

**Scenario:** First check the environment, then within production, check data quality:
- `dev` → Run with mock data
- `prod` + quality score ≥ 90% → Load to production DB
- `prod` + quality score < 90% → Send quality alert

**File:** `dags/dag_branch_04_nested.py`

```python
# dag_branch_04_nested.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from datetime import datetime

with DAG(
    dag_id="dag_branch_04_nested",
    start_date=datetime(2024, 1, 1),
    schedule=None,           # manual trigger only
    catchup=False,
    params={"environment": "prod"},   # change to "dev" to test dev branch
    tags=["branching", "advanced"],
):

    # ── Level 1 Branch: Environment check ──────────────────────────
    def check_environment(**context):
        env = context["params"].get("environment", "dev")
        print(f"🌍 Environment: {env}")

        if env == "prod":
            return "prod_quality_check"
        else:
            return "dev_run"

    env_branch = BranchPythonOperator(
        task_id="check_environment",
        python_callable=check_environment,
    )

    # ── Level 2 Branch: Data quality check (prod only) ─────────────
    def quality_check(**context):
        # Simulate a quality score — change to test both sub-branches
        quality_score = 95    # 👈 Change to 80 to test quality_alert branch
        print(f"🔍 Data quality score: {quality_score}%")

        if quality_score >= 90:
            return "prod_load"
        else:
            return "quality_alert"

    quality_branch = BranchPythonOperator(
        task_id="prod_quality_check",
        python_callable=quality_check,
    )

    # ── Branch Tasks ────────────────────────────────────────────────
    dev_run = PythonOperator(
        task_id="dev_run",
        python_callable=lambda: print("🛠️  DEV: Running pipeline with mock data"),
    )

    prod_load = PythonOperator(
        task_id="prod_load",
        python_callable=lambda: print("🚀 PROD: Loading verified data to production DB"),
    )

    quality_alert = PythonOperator(
        task_id="quality_alert",
        python_callable=lambda: print("🚨 ALERT: Data quality below 90% threshold!"),
    )

    # ── Final task ──────────────────────────────────────────────────
    end = PythonOperator(
        task_id="end",
        python_callable=lambda: print("🏁 Pipeline finished"),
        trigger_rule="none_failed_min_one_success",
    )

    # ── Wire up (nested structure) ──────────────────────────────────
    env_branch >> [quality_branch, dev_run]
    quality_branch >> [prod_load, quality_alert]
    [dev_run, prod_load, quality_alert] >> end
```

### Flow Diagram:
```
                       ┌→ prod_quality_check ──┬→ prod_load    →┐
check_environment ─────┤                       └→ quality_alert →├→ end
                       └→ dev_run ─────────────────────────────→┘
```

### 🎯 What to Observe:
- 3 possible execution paths through the DAG
- Only the relevant tasks in each path run — rest are skipped
- `end` always runs via `trigger_rule`

### 🔬 Experiments:
1. Trigger with `{"environment": "dev"}` — only `dev_run` runs
2. Trigger with `{"environment": "prod"}` + `quality_score = 95` — `prod_load` runs
3. Trigger with `{"environment": "prod"}` + `quality_score = 80` — `quality_alert` runs

**Trigger with custom params via UI:**
> ▶ → Trigger DAG w/ config → enter `{"environment": "dev"}` → Trigger

---

## 🔁 `trigger_rule` Reference (Critical Concept!)

This is the **most important concept** when tasks need to run after a branch join.

By default (`all_success`), a task only runs if **all** upstream tasks succeed. But after branching, some upstream tasks are **skipped** — so the default rule causes the join task to be skipped too!

### Solution: Use `none_failed_min_one_success`

```python
join_task = PythonOperator(
    task_id="join_task",
    python_callable=my_func,
    trigger_rule="none_failed_min_one_success",   # ✅ correct for post-branch
)
```

### All Available Rules:

| Rule | Meaning | When to Use |
|---|---|---|
| `all_success` *(default)* | ALL upstream must succeed | Normal sequential tasks |
| `none_failed_min_one_success` | At least 1 success, none failed | ✅ **Best for post-branch joins** |
| `one_success` | At least one upstream succeeded | Any branch completing is enough |
| `all_done` | All upstream done (any state OK) | Always run regardless of outcome |
| `none_failed` | None failed (skipped is OK) | Run unless something actually failed |
| `all_failed` | All upstream must have failed | Fallback / recovery tasks |
| `one_failed` | At least one upstream failed | Monitoring / alerting tasks |

### Visual Explanation:

```python
# ❌ WRONG — join_task gets SKIPPED because skipped branches
#             fail the default "all_success" check
branch >> [path_a, path_b]
[path_a, path_b] >> join_task                   # join_task gets skipped!

# ✅ CORRECT — join_task runs as long as one branch succeeded
join_task = PythonOperator(
    task_id="join_task",
    python_callable=...,
    trigger_rule="none_failed_min_one_success",  # handles skipped upstream
)
```

---

## 🔗 Task Dependency Patterns with Branching

### Pattern 1: Simple Fan-out (No Join)
```python
branch >> [task_a, task_b]
# No join — each branch ends independently
```

### Pattern 2: Fan-out with Join
```python
branch >> [task_a, task_b]
[task_a, task_b] >> end_task    # end_task needs trigger_rule!
```

### Pattern 3: Sequential Steps Per Branch
```python
branch >> [task_a, task_b]
task_a >> task_a2 >> end_task
task_b >> task_b2 >> end_task   # end_task needs trigger_rule!
```

### Pattern 4: Branch Returns Multiple Tasks
```python
# Branch function can return a LIST of task_ids to run multiple paths
def my_branch(**context):
    return ["task_a", "task_b"]   # runs BOTH paths

branch = BranchPythonOperator(
    task_id="branch",
    python_callable=my_branch,
)
```

### Pattern 5: Nested Branches
```python
branch1 >> [branch2, task_c]
branch2 >> [task_a, task_b]
[task_a, task_b, task_c] >> end_task  # end_task needs trigger_rule!
```

---

## 💻 Useful CLI Commands for Branching DAGs

```bash
# List all DAGs (check if branching DAGs appear)
airflow dags list

# Trigger a branching DAG manually
airflow dags trigger dag_branch_02_sales

# Trigger with custom config/params
airflow dags trigger dag_branch_04_nested -c '{"environment": "prod"}'

# Check task states after a run
airflow tasks states-for-dag-run dag_branch_02_sales <run_id>

# List all task instances for a DAG run
airflow dags list-runs --dag-id dag_branch_02_sales

# Check import errors
airflow dags list-import-errors
```

**Docker users — prefix with:**
```bash
docker compose run airflow-cli airflow dags trigger dag_branch_02_sales
docker compose run airflow-cli airflow dags trigger dag_branch_04_nested \
  -c '{"environment": "dev"}'
```

---

## ⚠️ Common Branching Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Post-branch task never runs | Join task is **skipped** (pink) | Add `trigger_rule="none_failed_min_one_success"` |
| Branch function returns wrong value | Error or unexpected path | Check the returned string exactly matches a `task_id` |
| Returning a function instead of a string | `TypeError` | Return `"task_id_string"` not `task_function()` |
| All tasks run (no branching) | Every task turns green | Make sure you used `BranchPythonOperator`, not `PythonOperator` |
| Skipped tasks show as "failed" | Confusion in UI | **Normal** — skipped = pink, not a failure |
| Branch function returns `None` | Unexpected skip behaviour | Always return a valid `task_id` from your function |
| Syntax error in DAG file | DAG not in UI | Run `python dags/your_file.py` locally to check |

---

## 🖥️ Reading Branch Results in the UI

| What You See | What It Means |
|---|---|
| 🟢 Green task | Task ran successfully |
| 🩷 Pink / Light purple task | Task was **skipped** (normal after branching) |
| 🔴 Red task | Task **failed** |
| ⬜ White / Grey task | Task hasn't run yet |

> 💡 **Tip:** In **Grid view**, skipped tasks are shown with a strikethrough style.  
> In **Graph view**, skipped tasks are shown with a dashed border.

---

## 📦 All DAG Files Summary

| # | File | Scenario | Key Concepts |
|---|---|---|---|
| 1 | `dag_branch_01_basic.py` | Even / Odd day | Basic BranchPythonOperator |
| 2 | `dag_branch_02_sales.py` | Sales threshold alert | XCom + branching + trigger_rule join |
| 3 | `dag_branch_03_multipath.py` | Day of week logic | 3-way branching |
| 4 | `dag_branch_04_nested.py` | Environment + quality check | Nested branching + params |

---

## ✅ Trainee Practice Checklist

### Level 1 — Basic Understanding
- [ ] Create `dag_branch_01_basic.py` and trigger it
- [ ] Observe the **skipped task** (pink) in the UI — confirm it is NOT a failure
- [ ] Modify the condition to always return `"even_day_task"` — trigger and verify

### Level 2 — XCom + Branch
- [ ] Create `dag_branch_02_sales.py` with `total_sales = 15000`
- [ ] Trigger and confirm `send_success_alert` → `generate_report` runs
- [ ] Change `total_sales = 5000` and trigger again
- [ ] Confirm `send_warning_alert` → `escalate_to_manager` runs instead
- [ ] Open the **XCom tab** on `extract_sales` task — see the `sales_data` dict
- [ ] **Remove** `trigger_rule` from `pipeline_complete` — observe what happens
- [ ] **Add it back** — confirm `pipeline_complete` runs correctly again

### Level 3 — Multiple Paths
- [ ] Create `dag_branch_03_multipath.py`
- [ ] Run it today and observe which branch fires based on current day
- [ ] Force `friday_processing` to run by hardcoding the return value
- [ ] Add a 4th branch for a public holiday scenario

### Level 4 — Nested Branching + Params
- [ ] Create `dag_branch_04_nested.py`
- [ ] Trigger with `{"environment": "dev"}` → verify only `dev_run` executes
- [ ] Trigger with `{"environment": "prod"}` → verify quality check sub-branch runs
- [ ] Change `quality_score` to `80` → verify `quality_alert` fires instead
- [ ] Draw the execution flow on paper for all 3 possible paths

### Level 5 — Build Your Own
- [ ] Build a DAG that branches based on **file size** (small/medium/large)
- [ ] Build a DAG that branches based on **hour of day** (morning/afternoon/night)
- [ ] Combine branching with **parallel tasks** in one DAG

---

## 🔗 Useful Resources

- 📖 [Airflow Branching Docs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#branching)
- 📖 [BranchPythonOperator API](https://airflow.apache.org/docs/apache-airflow/stable/_api/airflow/operators/python/index.html#airflow.operators.python.BranchPythonOperator)
- 📖 [Trigger Rules Docs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#trigger-rules)
- 📖 [XCom Docs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html)
- 🔗 [DAG Creation Guide](./airflow_dag_guide.md) ← Start here if you haven't already

---

> 🙌 **Pro Tip:** Always test your branch function standalone in Python before putting it in a DAG:
> ```python
> # Test your branch logic locally first
> def check_sales_threshold(total):
>     if total > 10000:
>         return "send_success_alert"
>     return "send_warning_alert"
>
> print(check_sales_threshold(15000))   # send_success_alert
> print(check_sales_threshold(5000))    # send_warning_alert
> ```
