# 🚀 Apache Airflow 3.x — DAG Creation Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Beginner → Intermediate  
> **Goal:** Learn to create, run, and manage DAGs step by step

---

## 📑 Table of Contents

- [Key Concepts](#-key-concepts)
- [Setup](#-setup)
- [DAG 1 — Hello World](#-dag-1--hello-world-simplest-possible-dag)
- [DAG 2 — Sequential Tasks](#-dag-2--multiple-tasks-in-sequence)
- [DAG 3 — Parallel Tasks](#-dag-3--parallel-tasks)
- [DAG 4 — TaskFlow API](#-dag-4--taskflow-api-modern-airflow-3-way)
- [DAG 5 — BashOperator](#-dag-5--bashoperator)
- [DAG 6 — Schedules](#-dag-6--schedule-options)
- [DAG 7 — Runtime Parameters](#-dag-7--passing-runtime-parameters)
- [Task Dependencies Cheatsheet](#-task-dependencies-cheatsheet)
- [Schedule Reference](#-schedule-reference)
- [Common Mistakes](#-common-beginner-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 Key Concepts

| Term | Meaning |
|---|---|
| **DAG** | Directed Acyclic Graph — your workflow/pipeline |
| **Task** | A single unit of work inside a DAG |
| **Operator** | Defines what a task does (BashOperator, PythonOperator, etc.) |
| **Schedule** | When the DAG runs automatically |
| **DAG Run** | One execution instance of a DAG |
| **Paused** | DAG exists but scheduler ignores it |
| **Active** | DAG is unpaused and runs on schedule |
| **catchup** | Whether to backfill missed scheduled runs |

---

## ⚙️ Setup

### Find Your DAGs Folder

**Local setup:**
```bash
ls ~/airflow/dags/
```

**Docker setup:**
```bash
ls ./dags/     # inside your airflow-docker project folder
```

All `.py` files placed here are **automatically detected** by Airflow's scheduler.

> 💡 After adding a DAG file, wait ~30 seconds and refresh the UI — it will appear automatically.

---

## ✏️ DAG 1 — Hello World (Simplest Possible DAG)

**File:** `dags/dag_01_hello_world.py`

```python
# dag_01_hello_world.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Define the DAG
with DAG(
    dag_id="dag_01_hello_world",      # unique name shown in UI
    start_date=datetime(2024, 1, 1),  # when scheduling starts
    schedule="@daily",                 # run once per day
    catchup=False,                     # don't backfill missed runs
    tags=["beginner"],                 # for filtering in UI
):

    # Define a Python function
    def say_hello():
        print("👋 Hello, Airflow World!")
        print("This is my first DAG task!")

    # Wrap the function in a PythonOperator
    task_hello = PythonOperator(
        task_id="say_hello",
        python_callable=say_hello,
    )
```

### ▶️ How to Run:
1. Open `http://localhost:8080`
2. Find `dag_01_hello_world` in the DAG list
3. Toggle it **ON** (unpause) using the toggle switch
4. Click **▶** → **Trigger DAG**
5. Click the DAG name → **Grid view** → click the green task box → **Logs**

### 🎯 What to observe:
- The DAG appears in the UI after ~30 seconds
- The toggle switch controls pause/unpause
- Task logs show your `print()` output

---

## ✏️ DAG 2 — Multiple Tasks in Sequence

**File:** `dags/dag_02_sequence.py`

```python
# dag_02_sequence.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="dag_02_sequence",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["beginner"],
):

    def task_one():
        print("🔵 Task 1: Extract data")

    def task_two():
        print("🟡 Task 2: Transform data")

    def task_three():
        print("🟢 Task 3: Load data")

    t1 = PythonOperator(task_id="extract",   python_callable=task_one)
    t2 = PythonOperator(task_id="transform", python_callable=task_two)
    t3 = PythonOperator(task_id="load",      python_callable=task_three)

    # >> sets the execution ORDER
    t1 >> t2 >> t3
```

### Flow:
```
extract ──→ transform ──→ load
```

### 🎯 What to observe:
- In **Graph view**, you can see tasks connected with arrows
- Tasks run one after another — `transform` only starts after `extract` succeeds
- If you click on a task, you can see its status and logs separately

---

## ✏️ DAG 3 — Parallel Tasks

**File:** `dags/dag_03_parallel.py`

```python
# dag_03_parallel.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="dag_03_parallel",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["beginner"],
):

    def start():
        print("🚀 Pipeline started!")

    def fetch_orders():
        print("📦 Fetching orders data...")

    def fetch_customers():
        print("👥 Fetching customers data...")

    def fetch_products():
        print("🛒 Fetching products data...")

    def finish():
        print("✅ All data fetched! Pipeline complete.")

    t_start     = PythonOperator(task_id="start",           python_callable=start)
    t_orders    = PythonOperator(task_id="fetch_orders",    python_callable=fetch_orders)
    t_customers = PythonOperator(task_id="fetch_customers", python_callable=fetch_customers)
    t_products  = PythonOperator(task_id="fetch_products",  python_callable=fetch_products)
    t_finish    = PythonOperator(task_id="finish",          python_callable=finish)

    # List [] means tasks run in PARALLEL
    t_start >> [t_orders, t_customers, t_products] >> t_finish
```

### Flow:
```
              ┌──→ fetch_orders    ──→┐
start ──────→ ├──→ fetch_customers ──→├──→ finish
              └──→ fetch_products  ──→┘
```

### 🎯 What to observe:
- In the **Grid view**, the 3 middle tasks turn green at the same time
- `finish` only runs after **all 3** parallel tasks complete
- This is how you speed up independent work

---

## ✏️ DAG 4 — TaskFlow API (Modern Airflow 3 Way)

**File:** `dags/dag_04_taskflow.py`

```python
# dag_04_taskflow.py

from airflow.sdk import dag, task
from datetime import datetime

@dag(
    dag_id="dag_04_taskflow",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["beginner"],
)
def my_pipeline():

    @task
    def extract():
        print("📥 Extracting data...")
        data = {"name": "Alice", "score": 95}
        return data                           # return value passed to next task automatically

    @task
    def transform(raw_data):
        print(f"⚙️  Transforming: {raw_data}")
        raw_data["grade"] = "A" if raw_data["score"] >= 90 else "B"
        return raw_data

    @task
    def load(final_data):
        print(f"💾 Loading to DB: {final_data}")
        print(f"   Name : {final_data['name']}")
        print(f"   Score: {final_data['score']}")
        print(f"   Grade: {final_data['grade']}")

    # Chain tasks — data flows automatically
    raw   = extract()
    clean = transform(raw)
    load(clean)

# Instantiate the DAG
my_pipeline()
```

### 🎯 What to observe:
- `@task` decorator replaces `PythonOperator` — much cleaner code
- Return values are **automatically passed** to the next task via XCom
- Check **XCom tab** in the UI to see data passed between tasks
- This is the **recommended modern style** for Airflow 3

---

## ✏️ DAG 5 — BashOperator

**File:** `dags/dag_05_bash.py`

```python
# dag_05_bash.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="dag_05_bash",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["beginner"],
):

    t1 = BashOperator(
        task_id="print_date",
        bash_command="date",
    )

    t2 = BashOperator(
        task_id="print_hello",
        bash_command="echo 'Hello from Bash!'",
    )

    t3 = BashOperator(
        task_id="check_disk",
        bash_command="df -h",
    )

    t4 = BashOperator(
        task_id="list_files",
        bash_command="ls -la /opt/airflow/dags/",
    )

    t1 >> t2 >> t3 >> t4
```

### 🎯 What to observe:
- BashOperator runs shell commands directly
- Useful for running scripts, checking system info, calling CLI tools
- Output appears in the task logs
- Try changing the `bash_command` to any shell command you want

---

## ✏️ DAG 6 — Schedule Options

**File:** `dags/dag_06_schedules.py`

```python
# dag_06_schedules.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="dag_06_schedules",
    start_date=datetime(2024, 1, 1),

    # 👇 Try changing this one at a time and observe behavior in UI
    schedule="@daily",          # every day at midnight
    # schedule="@hourly",       # every hour
    # schedule="@weekly",       # every Monday midnight
    # schedule="@monthly",      # 1st day of every month
    # schedule="0 9 * * *",     # every day at 9:00 AM (cron)
    # schedule="0 9 * * 1",     # every Monday at 9:00 AM
    # schedule="*/15 * * * *",  # every 15 minutes
    # schedule=None,            # manual trigger only — never auto-runs

    catchup=False,
    tags=["beginner"],
):

    def run():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏰ DAG ran at: {now}")

    PythonOperator(task_id="run_task", python_callable=run)
```

### ⏰ Schedule Presets:

| Preset | Meaning |
|---|---|
| `@once` | Run exactly one time |
| `@hourly` | Every hour (`0 * * * *`) |
| `@daily` | Every day at midnight (`0 0 * * *`) |
| `@weekly` | Every Monday midnight (`0 0 * * 1`) |
| `@monthly` | 1st day of month at midnight (`0 0 1 * *`) |
| `None` | Never auto-run — manual trigger only |

### 🕐 Cron Format:
```
┌─── minute     (0–59)
│  ┌── hour      (0–23)
│  │  ┌─ day     (1–31)
│  │  │  ┌ month (1–12)
│  │  │  │  ┌ weekday (0=Sun … 6=Sat)
│  │  │  │  │
*  *  *  *  *
```

### Cron Examples:
```
0 9 * * *       → 9:00 AM every day
0 9 * * 1       → 9:00 AM every Monday
0 0 1 * *       → Midnight on the 1st of every month
*/30 * * * *    → Every 30 minutes
0 8,17 * * 1-5  → 8 AM and 5 PM on weekdays only
```

> 💡 Use [crontab.guru](https://crontab.guru) to test and translate cron expressions.

---

## ✏️ DAG 7 — Passing Runtime Parameters

**File:** `dags/dag_07_params.py`

```python
# dag_07_params.py

from airflow.sdk import dag, task
from datetime import datetime

@dag(
    dag_id="dag_07_params",
    start_date=datetime(2024, 1, 1),
    schedule=None,               # manual trigger only
    catchup=False,
    params={                     # default parameter values
        "name": "Trainee",
        "city": "Mumbai",
        "department": "Engineering",
    },
    tags=["beginner"],
)
def parameterized_dag():

    @task
    def greet(params=None):
        name       = params["name"]
        city       = params["city"]
        department = params["department"]
        print(f"👋 Hello {name}!")
        print(f"📍 City      : {city}")
        print(f"🏢 Department: {department}")

    greet()

parameterized_dag()
```

### ▶️ How to Trigger with Custom Parameters:
1. Go to UI → find `dag_07_params`
2. Click **▶** → **Trigger DAG w/ config**
3. In the JSON box, enter:
```json
{
  "name": "Ravi",
  "city": "Pune",
  "department": "Data Engineering"
}
```
4. Click **Trigger** and check the task logs

### 🎯 What to observe:
- Default params are used when triggered without config
- Custom JSON overrides the defaults
- Great for on-demand DAGs that need different inputs each time

---

## 🔗 Task Dependencies Cheatsheet

```python
# Sequential — one after another
t1 >> t2 >> t3

# Same as above, written differently
t1.set_downstream(t2)
t2.set_downstream(t3)

# Parallel — t2 and t3 run at the same time after t1
t1 >> [t2, t3]

# Fan-in — t3 waits for BOTH t1 and t2
[t1, t2] >> t3

# Diamond pattern
t1 >> [t2, t3] >> t4

# Complex
t1 >> t2
t1 >> t3
t2 >> t4
t3 >> t4
t4 >> t5
```

### Visual Patterns:

```
# Sequential
A → B → C → D

# Fan-out
        ┌→ B
A ──────┼→ C
        └→ D

# Fan-in
A →┐
B →├──→ D
C →┘

# Diamond
        ┌→ B →┐
A ──────┤     ├──→ D
        └→ C →┘
```

---

## 📋 Schedule Reference

| Expression | Meaning |
|---|---|
| `@once` | Run exactly once |
| `@hourly` | Every hour |
| `@daily` | Every day at midnight |
| `@weekly` | Every Monday |
| `@monthly` | 1st of every month |
| `None` | Manual only — never auto-runs |
| `"0 9 * * *"` | Every day at 9 AM |
| `"0 9 * * 1-5"` | Weekdays at 9 AM |
| `"*/15 * * * *"` | Every 15 minutes |
| `"0 0 1,15 * *"` | 1st and 15th of each month |

---

## ⚠️ Common Beginner Mistakes

| Mistake | Why It Happens | Fix |
|---|---|---|
| DAG not appearing in UI | Syntax error in file, or wrong folder | Check terminal for Python errors, confirm file is in `dags/` |
| DAG not running automatically | DAG is paused (default) | Toggle ON in UI or run `airflow dags unpause dag_id` |
| Too many old runs triggered | `catchup=True` with old `start_date` | Always set `catchup=False` unless you need backfill |
| Tasks run out of order | No `>>` dependency set | Define dependencies with `>>` between tasks |
| Import errors on Airflow 3 | Using old Airflow 2 imports | Use `from airflow.sdk import DAG, task` |
| `dag_id` already exists error | Duplicate `dag_id` in another file | Every DAG must have a **unique** `dag_id` |
| Changes not reflecting | Scheduler hasn't re-parsed yet | Wait ~30 seconds and refresh UI |

---

## 🖥️ UI Navigation Guide

| What to do | Where to find it |
|---|---|
| See all DAGs | Home → DAGs list |
| Pause / Unpause DAG | Toggle switch left of DAG name |
| Manually trigger DAG | ▶ button → Trigger DAG |
| Trigger with params | ▶ button → Trigger DAG w/ config |
| See task run history | Click DAG name → Grid view |
| View task logs | Grid view → click task box → Logs |
| See DAG structure | Click DAG name → Graph view |
| View XCom data | Grid view → click task → XCom tab |
| Check DAG code | Click DAG name → Code tab |

---

## 💻 Useful CLI Commands

```bash
# List all DAGs
airflow dags list

# Trigger a DAG manually
airflow dags trigger dag_id

# Pause a DAG
airflow dags pause dag_id

# Unpause a DAG
airflow dags unpause dag_id

# Test a single task without creating a DAG run
airflow tasks test dag_id task_id 2024-01-01

# List all tasks in a DAG
airflow tasks list dag_id

# View DAG details
airflow dags show dag_id
```

**Docker users — prefix with:**
```bash
docker compose run airflow-cli airflow dags list
# OR
docker exec -it <scheduler-container-name> airflow dags list
```

---

## ✅ Trainee Practice Checklist

### Level 1 — Basics
- [ ] Create `dag_01_hello_world.py` and see it appear in the UI
- [ ] Manually trigger the DAG and view task logs
- [ ] Toggle DAG ON and OFF (pause / unpause)
- [ ] Change the `dag_id` and verify the new name appears in UI

### Level 2 — Task Flow
- [ ] Create `dag_02_sequence.py` and observe sequential flow in Graph view
- [ ] Create `dag_03_parallel.py` and observe parallel tasks running simultaneously
- [ ] Add a 4th task to `dag_02_sequence.py` and chain it

### Level 3 — Modern Syntax
- [ ] Create `dag_04_taskflow.py` using `@task` decorator
- [ ] Check XCom tab to see data passed between tasks
- [ ] Modify the `transform()` function to change the grading logic

### Level 4 — Operators & Scheduling
- [ ] Create `dag_05_bash.py` and modify the bash commands
- [ ] Create `dag_06_schedules.py` and change the schedule 3 different times
- [ ] Use [crontab.guru](https://crontab.guru) to write a custom cron schedule

### Level 5 — Advanced Practice
- [ ] Create `dag_07_params.py` and trigger it with custom JSON parameters
- [ ] Build your own DAG combining sequential + parallel tasks
- [ ] Create a DAG with `schedule=None` and trigger it via the REST API

---

## 📦 All DAG Files Summary

| # | File | Key Concept |
|---|---|---|
| 1 | `dag_01_hello_world.py` | Basic DAG structure, single task |
| 2 | `dag_02_sequence.py` | Multiple tasks, `>>` ordering |
| 3 | `dag_03_parallel.py` | Parallel tasks with `[]` |
| 4 | `dag_04_taskflow.py` | `@task` decorator, automatic data passing |
| 5 | `dag_05_bash.py` | BashOperator — run shell commands |
| 6 | `dag_06_schedules.py` | Cron & preset schedules |
| 7 | `dag_07_params.py` | Runtime parameters via JSON config |

---

## 🔗 Useful Resources

- 📖 [Official Airflow Docs](https://airflow.apache.org/docs/apache-airflow/stable/)
- 🔄 [Cron Expression Builder](https://crontab.guru)
- 💬 [Airflow Slack Community](https://apache-airflow-slack.herokuapp.com/)
- 🐙 [Airflow GitHub](https://github.com/apache/airflow)
- 📦 [Airflow PyPI](https://pypi.org/project/apache-airflow/)

---

> 🙌 **Happy Learning!** Start from DAG 1 and work your way through. Each DAG builds on the previous one. Don't skip — the concepts compound!
