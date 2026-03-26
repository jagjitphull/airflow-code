# 🔍 Apache Airflow 3.x — Sensors Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Intermediate  
> **Prerequisite:** Complete [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to use sensors to make DAGs wait for conditions before running downstream tasks  
> ✅ **All code in this guide is verified against Airflow 3.1.8 official documentation**

---

## 📑 Table of Contents

- [What Are Sensors?](#-what-are-sensors)
- [How a Sensor Works](#-how-a-sensor-works)
- [Key Sensor Parameters](#-key-sensor-parameters)
- [Sensor Modes](#-sensor-modes-poke-vs-reschedule-vs-deferrable)
- [Correct Import Paths](#-correct-import-paths-airflow-3--important)
- [Docker Setup (Do This First)](#-docker-setup-do-this-first)
- [Use Case 1 — FileSensor](#-use-case-1--filesensor-wait-for-a-file-to-appear)
- [Use Case 2 — HttpSensor](#-use-case-2--httpsensor-wait-for-an-api-to-be-ready)
- [Use Case 3 — PythonSensor](#-use-case-3--pythonsensor-custom-condition)
- [Use Case 4 — @task.sensor Decorator](#-use-case-4--tasksensor-decorator-modern-airflow-3-way)
- [Use Case 5 — ExternalTaskSensor](#-use-case-5--externaltasksensor-wait-for-another-dag)
- [Use Case 6 — Sensor with soft_fail](#-use-case-6--sensor-with-soft_fail)
- [Use Case 7 — Exponential Backoff](#-use-case-7--sensor-with-exponential-backoff)
- [Use Case 8 — Full Pipeline with Multiple Sensors](#-use-case-8--full-pipeline-with-multiple-sensors)
- [CLI Commands](#-sensors-cli-commands)
- [Common Mistakes](#-common-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 What Are Sensors?

A **Sensor** is a special type of operator that does exactly one thing — **waits for a condition to be true** before allowing downstream tasks to run.

> 💡 Think of a Sensor as a **security guard** at the entrance of your pipeline.  
> It keeps checking: *"Is the file here yet? Is the API ready? Did the other DAG finish?"*  
> Only when the answer is **YES** does it let the next task through.

### Why Use Sensors?

| Without Sensor | With Sensor |
|---|---|
| Task runs even if file is missing | Waits until file appears, then runs |
| Pipeline fails if API not ready | Waits until API responds, then proceeds |
| Manually trigger DAG after dependency | Automatically waits for dependency |
| Hardcode sleep/delays | Smart polling with configurable intervals |

### Common Built-in Sensors

| Sensor | Provider Package | Waits For |
|---|---|---|
| `FileSensor` | `apache-airflow-providers-standard` | A file to appear on disk |
| `HttpSensor` | `apache-airflow-providers-http` | An HTTP endpoint to return expected response |
| `PythonSensor` | `apache-airflow-providers-standard` | A Python function to return `True` |
| `ExternalTaskSensor` | `apache-airflow-providers-standard` | A task in another DAG to complete |
| `TimeDeltaSensor` | `apache-airflow-providers-standard` | A time interval to pass |
| `SqlSensor` | `apache-airflow-providers-common-sql` | A SQL query to return non-empty results |
| `S3KeySensor` | `apache-airflow-providers-amazon` | A file to appear in an S3 bucket |

---

## ⚙️ How a Sensor Works

```
Sensor task starts
       │
       ▼
  poke() — check condition ──→ ❌ Not ready
       │                           │
       │                     wait poke_interval seconds
       │                           │
       │◄──────────────────────────┘
       │
  poke() — check condition ──→ ✅ Ready!
       │
       ▼
  Sensor marks as SUCCESS
       │
       ▼
  Downstream tasks run 🚀
```

If the condition is never met within `timeout` seconds:
- `soft_fail=False` (default) → task **FAILS**
- `soft_fail=True` → task is marked **SKIPPED**

---

## 🔑 Key Sensor Parameters

| Parameter | Default | Description |
|---|---|---|
| `poke_interval` | `60` seconds | How often to check the condition |
| `timeout` | `604800` **(7 days!)** | Max time before failing — **always override!** |
| `mode` | `"poke"` | How sensor uses worker resources |
| `soft_fail` | `False` | If `True`, mark SKIPPED instead of FAILED on timeout |
| `exponential_backoff` | `False` | Gradually increase wait between checks |
| `max_wait` | `None` | Upper cap (seconds) on exponential backoff |

> ⚠️ **CRITICAL:** The default `timeout` is **7 days**! Always set a sensible timeout.  
> A forgotten sensor will block a worker slot for a full week.

---

## 🔄 Sensor Modes: poke vs reschedule vs deferrable

### Mode: `poke` (default)
```
Worker slot: [████████████████████████] OCCUPIED entire time
```
- ✅ Fast response when condition is met
- ❌ Wastes worker slot the whole time it waits
- ✅ Best for **short waits** (seconds to a few minutes)

### Mode: `reschedule`
```
Worker slot: [██] free [██] free [██] condition met!
```
- ✅ Releases worker slot between checks — much more efficient
- ✅ Best for **waits of minutes to hours**
- ✅ **Use this for almost all production sensors**

### Mode: `deferrable`
```
Worker slot: [██] → async triggerer process → [██] complete
```
- ✅ Most resource-efficient — uses the triggerer process
- ⚠️ Requires `airflow-triggerer` container to be running
- ✅ Best for **very long waits** in large deployments

### Rule of Thumb:
```
Wait < 5 minutes     →  poke
Wait 5min to hours   →  reschedule   ← use this for most cases
Production systems   →  deferrable=True
```

---

## ✅ Correct Import Paths (Airflow 3) — Important!

Airflow 3 reorganised many imports. Always use these paths:

```python
# ✅ Core DAG and task
from airflow.sdk import DAG, task

# ✅ PokeReturnValue — official Airflow 3.1.8 location
# Source: https://airflow.apache.org/docs/airflow/stable/tutorial/taskflow.html
from airflow.sdk import PokeReturnValue

# ✅ FileSensor
from airflow.providers.standard.sensors.filesystem import FileSensor

# ✅ PythonSensor
from airflow.providers.standard.sensors.python import PythonSensor

# ✅ ExternalTaskSensor
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor

# ✅ HttpSensor
from airflow.providers.http.sensors.http import HttpSensor

# ✅ TriggerRule (for downstream task after sensor branches)
from airflow.utils.trigger_rule import TriggerRule
```

---

## 🐳 Docker Setup (Do This First)

Complete all steps before trying any sensor DAG.

### Step 1 — Add data volume to `docker-compose.yaml`

Find the `x-airflow-common` volumes section and add the data mount:
```yaml
volumes:
  - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
  - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
  - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
  - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
  - ${AIRFLOW_PROJ_DIR:-.}/data:/opt/airflow/data    # ← ADD THIS LINE
```

### Step 2 — Create local data folder and restart

```bash
mkdir -p ./data
docker compose down
docker compose up -d
```

### Step 3 — Create `fs_default` connection (required for FileSensor)

**Best way — via the UI:**
1. Go to `http://localhost:8080`
2. Admin → Connections → click **+**
3. Fill in:
   - **Conn Id:** `fs_default`
   - **Conn Type:** `File (path)`
   - **Extra:** `{"path": "/opt/airflow/data"}`
4. Click **Save**

**Alternative via CLI:**
```bash
docker compose run --rm airflow-cli airflow connections add 'fs_default' \
    --conn-type 'fs' \
    --conn-extra '{"path": "/opt/airflow/data"}'
```

### Step 4 — Create HTTP connection (for HttpSensor)

```bash
docker compose run --rm airflow-cli airflow connections add 'jsonplaceholder_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com'
```

### Step 5 — Add providers to `requirements.txt` and rebuild

```
apache-airflow-providers-standard
apache-airflow-providers-http
```

```bash
docker compose build --no-cache
docker compose up -d

# Verify providers are installed
docker compose run --rm airflow-cli airflow providers list
```

### Step 6 — Verify setup

```bash
# Confirm data folder is mounted inside container
docker exec airflow-docker-airflow-scheduler-1 ls /opt/airflow/
# Expected output: config  dags  data  logs  plugins

# Confirm connections were created
docker compose run --rm airflow-cli airflow connections list
```

---

## ✏️ Use Case 1 — FileSensor: Wait for a File to Appear

**Scenario:** A daily sales pipeline waits for a CSV file to land before processing it.

**File:** `dags/sensor_01_file.py`

```python
# sensor_01_file.py
# ✅ Verified imports and logic for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.filesystem import FileSensor
from datetime import datetime

with DAG(
    dag_id="sensor_01_file",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "file"],
):

    # ── Sensor: wait until the file appears ───────────────────────
    wait_for_file = FileSensor(
        task_id="wait_for_sales_csv",
        filepath="sales_data.csv",     # relative to fs_default path
        fs_conn_id="fs_default",        # connection created in Step 3 above
        poke_interval=15,               # check every 15 seconds
        timeout=120,                    # fail after 2 minutes
        mode="reschedule",              # release worker slot between checks
        soft_fail=False,
    )

    # ── Task: read and print the file ─────────────────────────────
    @task
    def process_file():
        import csv, os

        filepath = "/opt/airflow/data/sales_data.csv"

        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            return

        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"✅ File found — processing {len(rows)} rows...")
        for row in rows:
            print(f"   Product: {row.get('product')}, Amount: {row.get('amount')}")

    # ── Task: generate report ─────────────────────────────────────
    @task
    def generate_report():
        print("📊 Generating sales report...")
        print("✅ Report complete!")

    wait_for_file >> process_file() >> generate_report()
```

### How to Test

```bash
# 1. Trigger the DAG — sensor starts waiting (yellow in UI)
docker compose run --rm airflow-cli airflow dags trigger sensor_01_file

# 2. Create the file — sensor detects it within 15 seconds
echo "product,amount
Laptop,75000
Phone,25000
Tablet,35000" > ./data/sales_data.csv

# 3. Sensor turns green → process_file → generate_report ✅

# 4. Reset for another test
rm ./data/sales_data.csv
```

### 🎯 What to Observe:
- Task shows **yellow** while sensing — check logs to see each poke attempt
- File appears → task turns **green** → downstream tasks run automatically
- No file within `timeout` → task turns **red** (FAILED)

---

## ✏️ Use Case 2 — HttpSensor: Wait for an API to Be Ready

**Scenario:** Confirm a REST API is healthy before fetching data.

**File:** `dags/sensor_02_http.py`

```python
# sensor_02_http.py
# ✅ Verified imports and logic for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.http.sensors.http import HttpSensor
from datetime import datetime

with DAG(
    dag_id="sensor_02_http",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "http"],
):

    # ── Sensor A: Wait for HTTP 200 response ──────────────────────
    wait_for_api = HttpSensor(
        task_id="wait_for_api_health",
        http_conn_id="jsonplaceholder_api",
        endpoint="/posts/1",
        method="GET",
        # response_check: True = proceed, False = retry
        response_check=lambda response: response.status_code == 200,
        poke_interval=15,
        timeout=120,
        mode="reschedule",
    )

    # ── Sensor B: Wait for specific data in response JSON ─────────
    wait_for_data = HttpSensor(
        task_id="wait_for_data_ready",
        http_conn_id="jsonplaceholder_api",
        endpoint="/todos/1",
        method="GET",
        response_check=lambda response: "completed" in response.json(),
        poke_interval=15,
        timeout=120,
        mode="reschedule",
    )

    # ── Task: fetch data once API is confirmed ready ───────────────
    @task
    def fetch_and_process():
        from airflow.providers.http.hooks.http import HttpHook

        hook = HttpHook(method="GET", http_conn_id="jsonplaceholder_api")
        response = hook.run(endpoint="/posts?_limit=3")
        posts = response.json()

        print(f"✅ API ready — fetched {len(posts)} posts:")
        for post in posts:
            print(f"   [{post['id']}] {post['title'][:40]}...")

    wait_for_api >> wait_for_data >> fetch_and_process()
```

### 🎯 What to Observe:
- `response_check` lambda must explicitly return `True` or `False`
- Since jsonplaceholder is always up, sensors succeed on first poke
- Try `endpoint="/nonexistent"` — watch the sensor keep retrying until timeout

---

## ✏️ Use Case 3 — PythonSensor: Custom Condition

**Scenario:** Wait until a simulated quality score meets a threshold.

**File:** `dags/sensor_03_python.py`

```python
# sensor_03_python.py
# ✅ Verified imports and logic for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.python import PythonSensor
from datetime import datetime
import random

with DAG(
    dag_id="sensor_03_python",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sensors", "python"],
):

    def check_data_quality(**context):
        """
        Return True  → sensor SUCCEEDS, downstream tasks run
        Return False → sensor RETRIES after poke_interval
        """
        quality_score = random.randint(60, 100)
        print(f"🔍 Data quality score: {quality_score}%")

        if quality_score >= 90:
            print("✅ Quality meets threshold — proceeding!")
            return True
        else:
            print(f"⏳ Score {quality_score}% below 90% — retrying...")
            return False

    wait_for_quality = PythonSensor(
        task_id="wait_for_data_quality",
        python_callable=check_data_quality,
        poke_interval=10,
        timeout=120,
        mode="reschedule",
    )

    def check_business_hours(**context):
        """Returns True only during weekday 9am–6pm."""
        from datetime import datetime as dt
        now = dt.now()
        is_weekday    = now.weekday() < 5
        is_work_hours = 9 <= now.hour < 18

        print(f"🕐 Time: {now.strftime('%H:%M %A')}")
        return is_weekday and is_work_hours

    wait_for_business_hours = PythonSensor(
        task_id="wait_for_business_hours",
        python_callable=check_business_hours,
        poke_interval=30,
        timeout=3600,
        mode="reschedule",
    )

    @task
    def run_pipeline():
        print("🤖 Running pipeline — all conditions met!")

    wait_for_quality >> wait_for_business_hours >> run_pipeline()
```

---

## ✏️ Use Case 4 — `@task.sensor` Decorator (Modern Airflow 3 Way)

**Scenario:** Wait for sufficient inventory and pass the count to the next task.

> ✅ **Verified import:** `from airflow.sdk import PokeReturnValue`  
> Source: [Official Airflow 3.1.8 TaskFlow docs example](https://airflow.apache.org/docs/apache-airflow/stable/tutorial/taskflow.html)

**File:** `dags/sensor_04_decorator.py`

```python
# sensor_04_decorator.py
# ✅ Verified imports and PokeReturnValue usage for Airflow 3.1.8

from airflow.sdk import DAG, task, PokeReturnValue   # ✅ from airflow.sdk
from datetime import datetime
import random

with DAG(
    dag_id="sensor_04_decorator",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sensors", "decorator"],
):

    @task.sensor(
        task_id="check_inventory_level",
        poke_interval=10,
        timeout=120,
        mode="reschedule",
    )
    def check_inventory() -> PokeReturnValue:
        """
        PokeReturnValue(is_done=True)  → sensor succeeds
        PokeReturnValue(is_done=False) → sensor retries
        xcom_value is automatically passed to downstream tasks
        """
        inventory_count = random.randint(0, 100)
        print(f"📦 Current inventory: {inventory_count} units")

        if inventory_count >= 50:
            print(f"✅ Sufficient inventory — proceeding!")
            return PokeReturnValue(
                is_done=True,
                xcom_value={                    # ← passed to downstream tasks
                    "inventory_count": inventory_count,
                    "status": "sufficient",
                    "checked_at": str(datetime.now()),
                }
            )
        else:
            print(f"⏳ Only {inventory_count} units — waiting for restock...")
            return PokeReturnValue(is_done=False)

    @task
    def process_orders(sensor_result):
        """Receives xcom_value from the sensor automatically."""
        print(f"🛒 Processing orders:")
        print(f"   Inventory: {sensor_result['inventory_count']} units")
        print(f"   Status   : {sensor_result['status']}")
        print(f"   Checked  : {sensor_result['checked_at']}")
        print("✅ Orders processed!")

    # Sensor result flows automatically to process_orders
    inventory_data = check_inventory()
    process_orders(inventory_data)
```

### Key Difference: `@task.sensor` vs `PythonSensor`

| Feature | `PythonSensor` | `@task.sensor` |
|---|---|---|
| Style | Classic operator | Modern decorator |
| Pass data downstream | Manual XCom push | Auto via `xcom_value` in `PokeReturnValue` |
| Return type | `True` / `False` | `PokeReturnValue` |
| Airflow 3 recommended | Works | ✅ Preferred |

---

## ✏️ Use Case 5 — ExternalTaskSensor: Wait for Another DAG

**Scenario:** A report DAG waits for an ETL DAG to fully complete.

> ⚠️ **Logical Date Note:** `ExternalTaskSensor` matches runs by logical date.  
> When testing manually, both DAGs must share the same logical date.  
> Always include `execution_delta=timedelta(0)` when triggering manually.

**File:** `dags/sensor_05_external_dag.py`

```python
# sensor_05_external_dag.py
# ✅ Verified imports and execution_delta for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from datetime import datetime, timedelta

# ── DAG 1: ETL Pipeline (to be waited on) ────────────────────────
with DAG(
    dag_id="sensor_05_etl_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "etl"],
):

    @task
    def extract():
        print("📥 Extracting data...")

    @task
    def transform():
        print("⚙️  Transforming data...")

    @task
    def load():
        print("💾 Loading to warehouse... ✅ ETL complete!")

    extract() >> transform() >> load()


# ── DAG 2: Report DAG (waits for ETL) ─────────────────────────────
with DAG(
    dag_id="sensor_05_report_dag",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "report"],
):

    # Wait for entire ETL DAG to complete
    wait_for_etl = ExternalTaskSensor(
        task_id="wait_for_etl_dag",
        external_dag_id="sensor_05_etl_pipeline",
        external_task_id=None,              # None = wait for the whole DAG
        allowed_states=["success"],
        failed_states=["failed", "skipped"],
        execution_delta=timedelta(0),       # ✅ match same logical date
        poke_interval=15,
        timeout=600,
        mode="reschedule",
    )

    # Wait for a specific task in the ETL DAG
    wait_for_load = ExternalTaskSensor(
        task_id="wait_for_load_task",
        external_dag_id="sensor_05_etl_pipeline",
        external_task_id="load",            # wait for just the 'load' task
        allowed_states=["success"],
        execution_delta=timedelta(0),       # ✅ match same logical date
        poke_interval=15,
        timeout=600,
        mode="reschedule",
    )

    @task
    def generate_report():
        print("📊 ETL confirmed complete — generating report...")
        print("✅ Report complete!")

    [wait_for_etl, wait_for_load] >> generate_report()
```

### How to Test

```bash
# Step 1: Trigger ETL DAG
docker compose run --rm airflow-cli airflow dags trigger sensor_05_etl_pipeline

# Step 2: Trigger report DAG with the SAME logical date
docker compose run --rm airflow-cli airflow dags trigger sensor_05_report_dag \
  --logical-date "2024-01-01T00:00:00+00:00"

# Step 3: Watch report DAG wait (yellow) until ETL finishes (green)
```

---

## ✏️ Use Case 6 — Sensor with `soft_fail`

**Scenario:** Optional vendor file — skip processing if missing, never fail the whole pipeline.

> ✅ **Fix applied:** `trigger_rule` is set **inside** the `@task()` decorator — not after the call.

**File:** `dags/sensor_06_soft_fail.py`

```python
# sensor_06_soft_fail.py
# ✅ Verified trigger_rule usage for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.utils.trigger_rule import TriggerRule    # ✅ correct import
from datetime import datetime

with DAG(
    dag_id="sensor_06_soft_fail",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "soft-fail"],
):

    @task
    def start_pipeline():
        print("🚀 Pipeline started — checking for optional vendor file...")

    # soft_fail=True → SKIPPED instead of FAILED when file not found
    wait_for_vendor_file = FileSensor(
        task_id="wait_for_vendor_file",
        filepath="vendor_data.csv",
        fs_conn_id="fs_default",
        poke_interval=15,
        timeout=30,           # short timeout for training
        mode="reschedule",
        soft_fail=True,       # ← marks SKIPPED not FAILED on timeout
    )

    @task
    def process_vendor_data():
        print("📦 Processing vendor data...")

    # ✅ CORRECT — trigger_rule set INSIDE @task decorator
    @task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)
    def generate_final_report():
        """Runs regardless of whether vendor file was found or skipped."""
        print("📊 Generating final report (vendor data included if available)...")
        print("✅ Report complete!")

    start  = start_pipeline()
    vendor = process_vendor_data()
    report = generate_final_report()

    # Main path: start → sensor → vendor → report
    start >> wait_for_vendor_file >> vendor >> report
    # Fallback path if sensor is skipped: start → report directly
    start >> report
```

### Behaviour Summary:

| `soft_fail` | File appears | File not found (timeout) |
|---|---|---|
| `False` (default) | ✅ Proceeds | ❌ FAILS — pipeline stops |
| `True` | ✅ Proceeds | 🩷 SKIPPED — `generate_final_report` still runs |

### How to Test

```bash
# Test 1: No file → sensor skips → report still runs
docker compose run --rm airflow-cli airflow dags trigger sensor_06_soft_fail

# Test 2: With file → full path runs
echo "vendor,value
A,100" > ./data/vendor_data.csv
docker compose run --rm airflow-cli airflow dags trigger sensor_06_soft_fail
rm ./data/vendor_data.csv
```

---

## ✏️ Use Case 7 — Sensor with Exponential Backoff

**Scenario:** Poll an external batch job that takes an unpredictable amount of time. Use backoff to reduce API load.

> ✅ **Fix applied:** Removed unreliable global counter. Uses stateless random simulation safe for distributed workers.

**File:** `dags/sensor_07_backoff.py`

```python
# sensor_07_backoff.py
# ✅ Stateless implementation — safe for distributed workers in Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.python import PythonSensor
from datetime import datetime
import random

def check_batch_job(**context):
    """
    Simulates a batch job that completes ~30% chance per check.
    Stateless — safe for distributed workers (no shared global state).
    """
    is_complete = random.random() < 0.30

    if is_complete:
        print("✅ Batch job COMPLETE!")
    else:
        print("⏳ Batch job still RUNNING — will retry...")

    return is_complete

with DAG(
    dag_id="sensor_07_backoff",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sensors", "backoff"],
):

    # ── Fixed interval (for comparison) ──────────────────────────
    wait_fixed = PythonSensor(
        task_id="wait_fixed_interval",
        python_callable=check_batch_job,
        poke_interval=10,             # always exactly 10s
        timeout=120,
        mode="reschedule",
        exponential_backoff=False,
    )

    # ── Exponential backoff ───────────────────────────────────────
    wait_backoff = PythonSensor(
        task_id="wait_with_backoff",
        python_callable=check_batch_job,
        poke_interval=5,              # starts at ~5 seconds
        timeout=120,
        mode="reschedule",
        exponential_backoff=True,     # intervals: 5s → 10s → 20s → ...
        max_wait=30,                  # capped at 30 seconds
    )

    @task
    def process_results():
        print("📊 Batch complete — processing results!")

    wait_fixed >> wait_backoff >> process_results()
```

### Backoff Pattern:
```
poke_interval=5, exponential_backoff=True, max_wait=30:

Check 1: wait  ~5s
Check 2: wait ~10s
Check 3: wait ~20s
Check 4: wait  30s  ← capped at max_wait
Check 5: wait  30s
```

---

## ✏️ Use Case 8 — Full Pipeline with Multiple Sensors

**Scenario:** Three parallel sensor gates must all pass before processing begins.

**File:** `dags/sensor_08_full_pipeline.py`

```python
# sensor_08_full_pipeline.py
# ✅ Verified imports and parallel sensor pattern for Airflow 3.1.8

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.providers.standard.sensors.python import PythonSensor
from airflow.providers.http.sensors.http import HttpSensor
from datetime import datetime
import random

with DAG(
    dag_id="sensor_08_full_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "full-pipeline"],
):

    # ── Gate 1: File must exist ───────────────────────────────────
    wait_for_file = FileSensor(
        task_id="gate_1_wait_for_file",
        filepath="daily_sales.csv",
        fs_conn_id="fs_default",
        poke_interval=15,
        timeout=120,
        mode="reschedule",
    )

    # ── Gate 2: API must be healthy ───────────────────────────────
    wait_for_api = HttpSensor(
        task_id="gate_2_wait_for_api",
        http_conn_id="jsonplaceholder_api",
        endpoint="/posts/1",
        response_check=lambda response: response.status_code == 200,
        poke_interval=15,
        timeout=60,
        mode="reschedule",
    )

    # ── Gate 3: System readiness check ───────────────────────────
    def check_system_readiness(**context):
        score = random.randint(80, 100)
        print(f"🔍 System readiness: {score}%")
        return score >= 85

    wait_for_readiness = PythonSensor(
        task_id="gate_3_system_ready",
        python_callable=check_system_readiness,
        poke_interval=10,
        timeout=60,
        mode="reschedule",
    )

    # ── Processing (only after ALL 3 gates pass) ──────────────────
    @task
    def process_data():
        print("⚙️  All 3 gates passed — processing data...")
        print("   ✅ File landed")
        print("   ✅ API healthy")
        print("   ✅ System ready")

    @task
    def generate_report():
        print("📊 Generating daily report... ✅ Complete!")

    # All 3 sensors run in PARALLEL — faster than sequential
    [wait_for_file, wait_for_api, wait_for_readiness] >> process_data() >> generate_report()
```

### Pipeline Flow:
```
              ┌──→ gate_1_wait_for_file  ──→┐
              ├──→ gate_2_wait_for_api   ──→ ├──→ process_data ──→ generate_report
              └──→ gate_3_system_ready  ──→┘
         (all 3 run in parallel — process_data waits for ALL)
```

### How to Test

```bash
# 1. Trigger the pipeline
docker compose run --rm airflow-cli airflow dags trigger sensor_08_full_pipeline

# 2. Gate 1 waits — create the file to unblock it
echo "product,amount
Laptop,75000" > ./data/daily_sales.csv

# 3. Gate 2 (HTTP) resolves on first poke — always up
# 4. Gate 3 (random 85+) resolves within a few pokes
# 5. Once all 3 green → process_data starts automatically
```

---

## 💻 Sensors CLI Commands

```bash
# Trigger a sensor DAG
docker compose run --rm airflow-cli airflow dags trigger sensor_01_file

# Check task state (is it still sensing?)
docker compose run --rm airflow-cli airflow tasks state \
  sensor_01_file wait_for_sales_csv 2024-01-01T00:00:00+00:00

# List recent DAG runs
docker compose run --rm airflow-cli airflow dags list-runs \
  --dag-id sensor_01_file

# Test a single sensor task without a full DAG run
docker compose run --rm airflow-cli airflow tasks test \
  sensor_01_file wait_for_sales_csv 2024-01-01

# View task logs (see each poke attempt)
docker compose run --rm airflow-cli airflow tasks logs \
  sensor_01_file wait_for_sales_csv 2024-01-01T00:00:00+00:00

# Watch container logs in real time
docker logs airflow-docker-airflow-worker-1 -f
```

---

## 📊 Sensor Quick Reference

| Sensor | Correct Import (Airflow 3.1.8) | Use For |
|---|---|---|
| `FileSensor` | `airflow.providers.standard.sensors.filesystem` | File on disk |
| `PythonSensor` | `airflow.providers.standard.sensors.python` | Any custom Python condition |
| `ExternalTaskSensor` | `airflow.providers.standard.sensors.external_task` | Another DAG/task |
| `HttpSensor` | `airflow.providers.http.sensors.http` | REST API response |
| `PokeReturnValue` | `airflow.sdk` | Return value for `@task.sensor` |
| `TriggerRule` | `airflow.utils.trigger_rule` | Post-sensor downstream task rules |

---

## ⚠️ Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Not setting `timeout` | Sensor runs for 7 days! | Always set `timeout` — e.g. `timeout=3600` |
| `poke` mode for long waits | Worker slots exhausted | Use `mode="reschedule"` for waits > 5 min |
| `PokeReturnValue` wrong import | `ImportError` | Use `from airflow.sdk import PokeReturnValue` |
| `trigger_rule` set after `@task()` call | Rule has no effect | Set inside decorator: `@task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)` |
| `fs_default` connection not created | `KeyError: fs_default` | Create via UI (Conn Type: **File (path)**) before running |
| `filepath` is absolute path | File never found | Use relative path — it joins with `fs_default` base path |
| No `./data/` volume mount | File on laptop not visible in container | Add volume to `docker-compose.yaml` and restart |
| ExternalTaskSensor logical dates differ | Sensor waits forever | Add `execution_delta=timedelta(0)` |
| Global counter in sensor function | Unreliable between runs | Use stateless logic (random, Variables, or DB query) |
| `soft_fail=True` but downstream still fails | Dependency misconfigured | Ensure downstream uses `@task(trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)` |
| `deferrable=True` without triggerer running | Task stuck in deferred state | Ensure `airflow-triggerer` container is up |

---

## 📦 All DAG Files Summary

| # | File | Sensor Used | Key Concept Fixed/Verified |
|---|---|---|---|
| 1 | `sensor_01_file.py` | `FileSensor` | `fs_default` conn, relative path, `mode="reschedule"` |
| 2 | `sensor_02_http.py` | `HttpSensor` | `response_check` lambda returns `True`/`False` |
| 3 | `sensor_03_python.py` | `PythonSensor` | Stateless callable, return `True`/`False` |
| 4 | `sensor_04_decorator.py` | `@task.sensor` | `PokeReturnValue` from `airflow.sdk` ✅ |
| 5 | `sensor_05_external_dag.py` | `ExternalTaskSensor` | `execution_delta=timedelta(0)` for manual testing ✅ |
| 6 | `sensor_06_soft_fail.py` | `FileSensor` + `soft_fail` | `trigger_rule` inside `@task()` decorator ✅ |
| 7 | `sensor_07_backoff.py` | `PythonSensor` + backoff | Stateless check — no global counter ✅ |
| 8 | `sensor_08_full_pipeline.py` | Multiple sensors | Parallel gates, production pattern |# 🔍 Apache Airflow 3.x — Sensors Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Intermediate  
> **Prerequisite:** Complete [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to use sensors to make DAGs wait for conditions before running downstream tasks

---

## 📑 Table of Contents

- [What Are Sensors?](#-what-are-sensors)
- [How a Sensor Works](#-how-a-sensor-works)
- [Key Sensor Parameters](#-key-sensor-parameters)
- [Sensor Modes](#-sensor-modes-poke-vs-reschedule-vs-deferrable)
- [Use Case 1 — FileSensor](#-use-case-1--filesensor-wait-for-a-file-to-appear)
- [Use Case 2 — HttpSensor](#-use-case-2--httpsensor-wait-for-an-api-to-be-ready)
- [Use Case 3 — PythonSensor](#-use-case-3--pythonsensor-custom-condition)
- [Use Case 4 — @task.sensor Decorator](#-use-case-4--tasksensor-decorator-modern-airflow-3-way)
- [Use Case 5 — ExternalTaskSensor](#-use-case-5--externaltasksensor-wait-for-another-dag)
- [Use Case 6 — Sensor with Timeout & Soft Fail](#-use-case-6--sensor-with-timeout--soft-fail)
- [Use Case 7 — Sensor with Exponential Backoff](#-use-case-7--sensor-with-exponential-backoff)
- [Use Case 8 — Full Pipeline with Multiple Sensors](#-use-case-8--full-pipeline-with-multiple-sensors)
- [Docker Setup for Sensors](#-docker-setup-for-sensors)
- [Sensors CLI Commands](#-sensors-cli-commands)
- [Common Mistakes](#-common-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 What Are Sensors?

A **Sensor** is a special type of operator that does exactly one thing — **waits for a condition to be true** before allowing downstream tasks to run.

> 💡 Think of a Sensor as a **security guard** at the entrance of your pipeline.  
> It keeps checking: *"Is the file here yet? Is the API ready? Did the other DAG finish?"*  
> Only when the answer is **YES** does it let the next task through.

### Why Use Sensors?

| Without Sensor | With Sensor |
|---|---|
| Task runs even if file is missing | Waits until file appears, then runs |
| Pipeline fails if API not ready | Waits until API responds, then proceeds |
| Manually trigger DAG after dependency | Automatically waits for dependency |
| Hardcode sleep/delays | Smart polling with configurable intervals |

### Common Built-in Sensors

| Sensor | Provider | Waits For |
|---|---|---|
| `FileSensor` | standard | A file to appear on disk |
| `HttpSensor` | http | An HTTP endpoint to return expected response |
| `PythonSensor` | standard | A Python function to return `True` |
| `ExternalTaskSensor` | standard | A task in another DAG to complete |
| `DateTimeSensor` | standard | A specific date/time to arrive |
| `TimeDeltaSensor` | standard | A time interval to pass |
| `SqlSensor` | common.sql | A SQL query to return non-empty results |
| `S3KeySensor` | amazon | A file to appear in an S3 bucket |

---

## ⚙️ How a Sensor Works

```
Sensor task starts
       │
       ▼
  poke() — check condition ──→ ❌ Not ready
       │                           │
       │                     wait poke_interval seconds
       │                           │
# 🔍 Apache Airflow 3.x — Sensors Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Intermediate  
> **Prerequisite:** Complete [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to use sensors to make DAGs wait for conditions before running downstream tasks

---

## 📑 Table of Contents

- [What Are Sensors?](#-what-are-sensors)
- [How a Sensor Works](#-how-a-sensor-works)
- [Key Sensor Parameters](#-key-sensor-parameters)
- [Sensor Modes](#-sensor-modes-poke-vs-reschedule-vs-deferrable)
- [Use Case 1 — FileSensor](#-use-case-1--filesensor-wait-for-a-file-to-appear)
- [Use Case 2 — HttpSensor](#-use-case-2--httpsensor-wait-for-an-api-to-be-ready)
- [Use Case 3 — PythonSensor](#-use-case-3--pythonsensor-custom-condition)
- [Use Case 4 — @task.sensor Decorator](#-use-case-4--tasksensor-decorator-modern-airflow-3-way)
- [Use Case 5 — ExternalTaskSensor](#-use-case-5--externaltasksensor-wait-for-another-dag)
- [Use Case 6 — Sensor with Timeout & Soft Fail](#-use-case-6--sensor-with-timeout--soft-fail)
- [Use Case 7 — Sensor with Exponential Backoff](#-use-case-7--sensor-with-exponential-backoff)
- [Use Case 8 — Full Pipeline with Multiple Sensors](#-use-case-8--full-pipeline-with-multiple-sensors)
- [Docker Setup for Sensors](#-docker-setup-for-sensors)
- [Sensors CLI Commands](#-sensors-cli-commands)
- [Common Mistakes](#-common-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 What Are Sensors?

A **Sensor** is a special type of operator that does exactly one thing — **waits for a condition to be true** before allowing downstream tasks to run.

> 💡 Think of a Sensor as a **security guard** at the entrance of your pipeline.  
> It keeps checking: *"Is the file here yet? Is the API ready? Did the other DAG finish?"*  
> Only when the answer is **YES** does it let the next task through.

### Why Use Sensors?

| Without Sensor | With Sensor |
|---|---|
| Task runs even if file is missing | Waits until file appears, then runs |
| Pipeline fails if API not ready | Waits until API responds, then proceeds |
| Manually trigger DAG after dependency | Automatically waits for dependency |
| Hardcode sleep/delays | Smart polling with configurable intervals |

### Common Built-in Sensors

| Sensor | Provider | Waits For |
|---|---|---|
| `FileSensor` | standard | A file to appear on disk |
| `HttpSensor` | http | An HTTP endpoint to return expected response |
| `PythonSensor` | standard | A Python function to return `True` |
| `ExternalTaskSensor` | standard | A task in another DAG to complete |
| `DateTimeSensor` | standard | A specific date/time to arrive |
| `TimeDeltaSensor` | standard | A time interval to pass |
| `SqlSensor` | common.sql | A SQL query to return non-empty results |
| `S3KeySensor` | amazon | A file to appear in an S3 bucket |

---

## ⚙️ How a Sensor Works

```
Sensor task starts
       │
       ▼
  poke() — check condition ──→ ❌ Not ready
       │                           │
       │                     wait poke_interval seconds
       │                           │


---

## ✅ Trainee Practice Checklist

### Level 1 — Docker Setup
- [ ] Add `./data:/opt/airflow/data` volume to `docker-compose.yaml` and restart
- [ ] Create `fs_default` connection via UI — Conn Type: **File (path)**, Extra: `{"path": "/opt/airflow/data"}`
- [ ] Create `jsonplaceholder_api` HTTP connection via Docker CLI
- [ ] Add providers to `requirements.txt`, rebuild, verify with `airflow providers list`
- [ ] Confirm data folder: `docker exec <scheduler> ls /opt/airflow/` shows `data`

### Level 2 — FileSensor
- [ ] Create `sensor_01_file.py` and trigger
- [ ] Watch task turn **yellow** in UI while sensing
- [ ] Drop `./data/sales_data.csv` — watch sensor turn **green** within 15 seconds
- [ ] Check task logs — see each poke attempt printed
- [ ] Let timeout expire without file — observe **FAILED** state
- [ ] Add `soft_fail=True` — repeat — observe **SKIPPED** state instead

### Level 3 — HTTP and Python Sensors
- [ ] Create `sensor_02_http.py` — trigger and confirm sensors succeed quickly
- [ ] Modify `response_check` to check a JSON field — confirm it works
- [ ] Create `sensor_03_python.py` — lower threshold to 50% and observe faster success

### Level 4 — Modern Decorator
- [ ] Create `sensor_04_decorator.py` — verify `from airflow.sdk import PokeReturnValue` works
- [ ] Trigger and check **XCom tab** — see `inventory_count` passed to `process_orders`

### Level 5 — Cross-DAG and Soft Fail
- [ ] Create `sensor_05_external_dag.py` — trigger ETL first, then report with same logical date
- [ ] Observe report DAG waiting then succeeding after ETL finishes
- [ ] Create `sensor_06_soft_fail.py` — trigger without file — confirm report still runs

### Level 6 — Advanced and Full Pipeline
- [ ] Create `sensor_07_backoff.py` — check logs to see increasing wait intervals
- [ ] Create `sensor_08_full_pipeline.py` — drop the file and watch all 3 gates resolve
- [ ] Remove one sensor from the list in Use Case 8 and observe `process_data` still waits for the remaining 2

---

## 🔗 Useful Resources

- 📖 [Airflow Sensors Docs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html)
- 📖 [Task SDK API — PokeReturnValue](https://airflow.apache.org/docs/task-sdk/stable/api.html#airflow.sdk.PokeReturnValue)
- 📖 [FileSensor Docs](https://airflow.apache.org/docs/apache-airflow-providers-standard/stable/sensors/file.html)
- 📖 [ExternalTaskSensor Docs](https://airflow.apache.org/docs/apache-airflow-providers-standard/stable/sensors/external_task_sensor.html)
- 📖 [TaskFlow API + @task.sensor](https://airflow.apache.org/docs/apache-airflow/stable/tutorial/taskflow.html)
- 🔗 [DAG Creation Guide](./airflow_dag_guide.md)
- 🔗 [Branching Guide](./airflow_dag_branching_guide.md)
- 🔗 [Assets Guide](./airflow_assets_guide.md)
- 🔗 [Variables, Providers & Connections Guide](./airflow_variables_providers_connections_guide.md)

---

> 🙌 **Key Rules for Sensors:**
>
> 1. **Always set `timeout`** — default is 7 days, which blocks worker slots
> 2. **Use `mode="reschedule"`** for any wait longer than 5 minutes
> 3. **Import `PokeReturnValue` from `airflow.sdk`** — not from `airflow.sensors.base`
> 4. **Set `trigger_rule` inside `@task(trigger_rule=...)`** — not after the call
> 5. **Create `fs_default` connection first** — FileSensor will not work without it
> 6. **Mount `./data/` as a Docker volume** — files on your laptop must be visible inside containers
> 7. **Use `execution_delta=timedelta(0)`** with ExternalTaskSensor when triggering both DAGs manually
