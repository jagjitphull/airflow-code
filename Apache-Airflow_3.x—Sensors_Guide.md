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

If the condition is never met within `timeout` seconds → sensor **FAILS** (or is **skipped** if `soft_fail=True`).

---

## 🔑 Key Sensor Parameters

All sensors share these core parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `poke_interval` | int (seconds) | `60` | How often to check the condition |
| `timeout` | int (seconds) | `604800` (7 days!) | Max time to wait before failing |
| `mode` | string | `"poke"` | How sensor uses worker resources |
| `soft_fail` | bool | `False` | If `True`, mark as **SKIPPED** instead of **FAILED** on timeout |
| `exponential_backoff` | bool | `False` | Increase wait time between checks gradually |
| `max_wait` | int (seconds) | None | Cap on wait when using exponential backoff |

> ⚠️ **CRITICAL:** The default `timeout` is **7 days**! Always set a sensible timeout for your use case. A sensor running for 7 days will block worker slots and waste resources.

---

## 🔄 Sensor Modes: poke vs reschedule vs deferrable

This is the most important concept for efficient sensor usage:

### Mode: `poke` (default)
```
Worker slot: [████████████████████████] OCCUPIED entire time
              │
              sensor keeps checking every poke_interval
              but HOLDS the worker slot the whole time
```
- ✅ Fast response to condition being met
- ❌ Wastes worker slot while waiting
- ✅ Best for **short waits** (seconds to a few minutes)

### Mode: `reschedule`
```
Worker slot: [██]  free  [██]  free  [██]  condition met!
              │           │           │
            check       check       check
```
- ✅ Releases worker slot between checks
- ✅ Much more resource-efficient
- ✅ Best for **long waits** (minutes to hours)
- ❌ Slightly slower to detect when condition is met

### Mode: `deferrable`
```
Worker slot: [██]  (deferred to triggerer process)  [██] complete!
              │                                        │
            check   → handed to triggerer →         callback
```
- ✅ Most resource-efficient — uses async triggerer process
- ✅ Best for **very long waits** in production
- ⚠️ Requires `airflow triggerer` process to be running
- ✅ Use `deferrable=True` parameter to enable

### Rule of Thumb:

```
Wait time < 5 minutes   → poke mode
Wait time 5min - hours  → reschedule mode
Production deployment   → deferrable=True
```

---

## ✏️ Use Case 1 — FileSensor: Wait for a File to Appear

**Scenario:** A daily pipeline that should only run after a CSV file lands in the data folder.

### Step 1 — Set up Docker data folder volume

Add to `docker-compose.yaml` volumes:
```yaml
volumes:
  - ${AIRFLOW_PROJ_DIR:-.}/data:/opt/airflow/data
```

Create the folder:
```bash
mkdir -p ./data
docker compose down && docker compose up -d
```

### Step 2 — Set up the FileSensor connection

FileSensor requires a **filesystem connection** defining the base path:

```bash
# Create fs_default connection pointing to /opt/airflow/data
docker compose run --rm airflow-cli airflow connections add 'fs_default' \
    --conn-type 'fs' \
    --conn-extra '{"path": "/opt/airflow/data"}'

# Verify
docker compose run --rm airflow-cli airflow connections get fs_default
```

### Step 3 — Create the DAG

**File:** `dags/sensor_01_file.py`

```python
# sensor_01_file.py
# Waits for a CSV file to appear before processing it

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

    # ── Step 1: Wait for the file ────────────────────────────────
    wait_for_file = FileSensor(
        task_id="wait_for_sales_csv",
        filepath="sales_data.csv",         # relative to fs_default connection path
        fs_conn_id="fs_default",            # connection we created above
        poke_interval=30,                   # check every 30 seconds
        timeout=300,                        # fail after 5 minutes
        mode="reschedule",                  # release worker slot between checks
        soft_fail=False,                    # FAIL the task if timeout reached
    )

    # ── Step 2: Process the file once it appears ─────────────────
    @task
    def process_file():
        import csv
        filepath = "/opt/airflow/data/sales_data.csv"

        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"✅ File found! Processing {len(rows)} rows...")
        for row in rows:
            print(f"   Product: {row.get('product')}, Amount: {row.get('amount')}")

    # ── Step 3: Generate report ───────────────────────────────────
    @task
    def generate_report():
        print("📊 Generating sales report from processed data...")
        print("✅ Report complete!")

    # Wire up: sensor → process → report
    process = process_file()
    report  = generate_report()

    wait_for_file >> process >> report
```

### Step 4 — Test It

```bash
# Start the DAG
docker compose run --rm airflow-cli airflow dags trigger sensor_01_file

# Watch it wait — check UI, task should show as "sensing" (yellow)

# Now create the file to trigger it
echo "product,amount
Laptop,75000
Phone,25000
Tablet,35000" > ./data/sales_data.csv

# The sensor should detect the file within 30 seconds and turn green!
```

### 🎯 What to Observe in the UI:
- `wait_for_sales_csv` task shows as **yellow/running** while sensing
- In **Grid view**, sensing tasks have a distinct pulsing indicator
- Once file appears → task turns **green** → `process_file` starts automatically
- Check task logs — see each poke attempt logged: `Poking: sales_data.csv`

---

## ✏️ Use Case 2 — HttpSensor: Wait for an API to Be Ready

**Scenario:** Before calling a payment API to process orders, confirm the API is healthy and responding.

### Step 1 — Create the HTTP connection

```bash
docker compose run --rm airflow-cli airflow connections add 'jsonplaceholder_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com'

docker compose run --rm airflow-cli airflow connections get jsonplaceholder_api
```

### Step 2 — Install HTTP provider

Add to `requirements.txt`:
```
apache-airflow-providers-http
```

Rebuild:
```bash
docker compose build && docker compose up -d
```

### Step 3 — Create the DAG

**File:** `dags/sensor_02_http.py`

```python
# sensor_02_http.py
# Waits for an HTTP API to return a healthy response before processing

from airflow.sdk import DAG, task
from airflow.providers.http.sensors.http import HttpSensor
from datetime import datetime

with DAG(
    dag_id="sensor_02_http",
    start_date=datetime(2024, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["sensors", "http"],
):

    # ── Sensor: Wait until API returns a 200 response ────────────
    wait_for_api = HttpSensor(
        task_id="wait_for_api_health",
        http_conn_id="jsonplaceholder_api",
        endpoint="/posts/1",                 # endpoint to check
        method="GET",
        # response_check: return True = condition met, False = keep waiting
        response_check=lambda response: response.status_code == 200,
        poke_interval=20,                    # check every 20 seconds
        timeout=120,                         # fail after 2 minutes
        mode="reschedule",
    )

    # ── Sensor: Wait for specific data in response ────────────────
    wait_for_data = HttpSensor(
        task_id="wait_for_data_ready",
        http_conn_id="jsonplaceholder_api",
        endpoint="/todos/1",
        method="GET",
        # Check that response JSON has 'completed' field
        response_check=lambda response: "completed" in response.json(),
        poke_interval=15,
        timeout=60,
        mode="reschedule",
    )

    # ── Task: Fetch and process once API is ready ─────────────────
    @task
    def fetch_and_process():
        from airflow.providers.http.hooks.http import HttpHook

        hook = HttpHook(method="GET", http_conn_id="jsonplaceholder_api")
        response = hook.run(endpoint="/posts?_limit=3")
        posts = response.json()

        print(f"✅ API ready! Fetched {len(posts)} posts:")
        for post in posts:
            print(f"   [{post['id']}] {post['title'][:40]}...")

    wait_for_api >> wait_for_data >> fetch_and_process()
```

### 🎯 What to Observe:
- Sensor checks the endpoint every `poke_interval` seconds
- If the endpoint returns a non-200 status, sensor keeps retrying
- `response_check` is a lambda that returns `True` (proceed) or `False` (retry)
- Chain multiple HTTP sensors for multi-step API readiness checks

---

## ✏️ Use Case 3 — PythonSensor: Custom Condition

**Scenario:** Wait until a simulated data quality score crosses a threshold before running the ML pipeline.

**File:** `dags/sensor_03_python.py`

```python
# sensor_03_python.py
# Custom sensor using PythonSensor for any condition you can write in Python

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.python import PythonSensor
from datetime import datetime
import random

with DAG(
    dag_id="sensor_03_python",
    start_date=datetime(2024, 1, 1),
    schedule=None,           # manual trigger only
    catchup=False,
    tags=["sensors", "python"],
):

    # ── Use Case A: Wait for data quality score ──────────────────
    def check_data_quality(**context):
        """
        Returns True  → condition met  → sensor succeeds
        Returns False → condition not met → sensor retries after poke_interval
        """
        # Simulate checking a data quality score
        # In real world: query DB, call API, check file stats, etc.
        quality_score = random.randint(60, 100)
        print(f"🔍 Current data quality score: {quality_score}%")

        if quality_score >= 90:
            print("✅ Quality threshold met — proceeding!")
            return True
        else:
            print(f"⏳ Score {quality_score}% is below 90% threshold — retrying...")
            return False

    wait_for_quality = PythonSensor(
        task_id="wait_for_data_quality",
        python_callable=check_data_quality,
        poke_interval=15,      # retry every 15 seconds
        timeout=120,           # fail after 2 minutes
        mode="reschedule",
    )

    # ── Use Case B: Wait for a specific time window ──────────────
    def check_business_hours(**context):
        """Wait until it is between 9am and 6pm on a weekday."""
        from datetime import datetime
        now = datetime.now()
        is_weekday     = now.weekday() < 5           # Mon=0 ... Fri=4
        is_work_hours  = 9 <= now.hour < 18          # 9am to 6pm

        print(f"🕐 Current time: {now.strftime('%H:%M %A')}")
        print(f"   Weekday     : {is_weekday}")
        print(f"   Work hours  : {is_work_hours}")

        return is_weekday and is_work_hours

    wait_for_business_hours = PythonSensor(
        task_id="wait_for_business_hours",
        python_callable=check_business_hours,
        poke_interval=60,       # check every minute
        timeout=3600,           # wait up to 1 hour
        mode="reschedule",
    )

    @task
    def run_ml_pipeline():
        print("🤖 Running ML pipeline — data quality confirmed and business hours verified!")

    wait_for_quality >> wait_for_business_hours >> run_ml_pipeline()
```

---

## ✏️ Use Case 4 — `@task.sensor` Decorator (Modern Airflow 3 Way)

The `@task.sensor` decorator is the cleanest way to write custom sensors in Airflow 3.

**File:** `dags/sensor_04_decorator.py`

```python
# sensor_04_decorator.py
# Modern Airflow 3 way to write sensors using @task.sensor decorator

from airflow.sdk import DAG, task
from airflow.sensors.base import PokeReturnValue
from datetime import datetime
import random

with DAG(
    dag_id="sensor_04_decorator",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sensors", "decorator"],
):

    # ── @task.sensor: returns PokeReturnValue ────────────────────
    @task.sensor(
        task_id="check_inventory_level",
        poke_interval=20,
        timeout=180,
        mode="reschedule",
    )
    def check_inventory() -> PokeReturnValue:
        """
        Check if inventory level is sufficient.
        PokeReturnValue(is_done=True)  → sensor succeeds
        PokeReturnValue(is_done=False) → sensor retries
        xcom_value → value passed to downstream tasks via XCom
        """
        inventory_count = random.randint(0, 100)
        print(f"📦 Current inventory: {inventory_count} units")

        if inventory_count >= 50:
            print(f"✅ Inventory sufficient ({inventory_count} units) — proceeding!")
            return PokeReturnValue(
                is_done=True,
                xcom_value={                   # ← data passed to downstream tasks
                    "inventory_count": inventory_count,
                    "status": "sufficient",
                    "checked_at": str(datetime.now()),
                }
            )
        else:
            print(f"⏳ Inventory low ({inventory_count} units) — waiting for restock...")
            return PokeReturnValue(is_done=False)  # retry

    # ── Downstream task uses xcom_value from sensor ──────────────
    @task
    def process_orders(sensor_result):
        """Receives the xcom_value from the sensor."""
        print(f"🛒 Processing orders with inventory data:")
        print(f"   Count   : {sensor_result['inventory_count']}")
        print(f"   Status  : {sensor_result['status']}")
        print(f"   Checked : {sensor_result['checked_at']}")
        print("✅ Orders processed successfully!")

    # Chain: sensor result automatically passes to next task
    inventory_data = check_inventory()
    process_orders(inventory_data)
```

### Key Difference: `@task.sensor` vs `PythonSensor`

| Feature | `PythonSensor` | `@task.sensor` |
|---|---|---|
| Style | Classic operator | Modern decorator |
| Pass data downstream | Manual XCom push | Via `xcom_value` in `PokeReturnValue` |
| Return type | `True` / `False` | `PokeReturnValue` |
| Airflow 3 recommended | Works | ✅ Preferred |

---

## ✏️ Use Case 5 — ExternalTaskSensor: Wait for Another DAG

**Scenario:** A reporting DAG that should only run after the ETL DAG has successfully completed for the same day.

**File:** `dags/sensor_05_external_dag.py`

```python
# sensor_05_external_dag.py
# Two DAGs: one ETL producer, one report consumer that waits for ETL

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# ── DAG 1: ETL Pipeline (the one being waited on) ────────────────
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
        print("💾 Loading data to warehouse...")
        print("✅ ETL complete!")

    extract() >> transform() >> load()


# ── DAG 2: Report DAG (waits for ETL to finish) ───────────────────
with DAG(
    dag_id="sensor_05_report_dag",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "report"],
):

    # Wait for the ENTIRE ETL DAG to complete
    wait_for_etl = ExternalTaskSensor(
        task_id="wait_for_etl_dag",
        external_dag_id="sensor_05_etl_pipeline",   # DAG to wait for
        external_task_id=None,                        # None = wait for entire DAG
        allowed_states=["success"],                   # only proceed if ETL succeeded
        failed_states=["failed", "skipped"],          # fail immediately if ETL failed
        poke_interval=30,
        timeout=3600,                                  # wait up to 1 hour
        mode="reschedule",
    )

    # Wait for a SPECIFIC TASK in another DAG
    wait_for_load_task = ExternalTaskSensor(
        task_id="wait_for_load_task",
        external_dag_id="sensor_05_etl_pipeline",
        external_task_id="load",                      # wait for just the 'load' task
        allowed_states=["success"],
        poke_interval=30,
        timeout=3600,
        mode="reschedule",
    )

    @task
    def generate_report():
        print("📊 ETL confirmed complete — generating executive report...")
        print("✅ Report generated and sent!")

    # Run sensors in parallel, then generate report
    [wait_for_etl, wait_for_load_task] >> generate_report()
```

### 🎯 What to Observe:
1. Trigger `sensor_05_etl_pipeline` first
2. Then trigger `sensor_05_report_dag` — it will wait in "sensing" state
3. Once the ETL DAG completes, the report DAG sensors turn green
4. `generate_report` then runs automatically

> 💡 **Note:** Both DAGs must run with the **same logical date** for `ExternalTaskSensor` to match them. Trigger both at the same time manually, or let them both run on the same `@daily` schedule.

---

## ✏️ Use Case 6 — Sensor with Timeout & Soft Fail

**Scenario:** A sensor that tries to find a vendor file. If the file doesn't arrive within 10 minutes, **skip** the vendor processing instead of failing the whole pipeline.

**File:** `dags/sensor_06_soft_fail.py`

```python
# sensor_06_soft_fail.py
# soft_fail=True marks the task SKIPPED instead of FAILED on timeout

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.providers.standard.operators.python import PythonOperator
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

    # ── Sensor with soft_fail — SKIPPED instead of FAILED ────────
    wait_for_vendor_file = FileSensor(
        task_id="wait_for_vendor_file",
        filepath="vendor_data.csv",
        fs_conn_id="fs_default",
        poke_interval=30,
        timeout=60,             # wait 1 minute only
        mode="reschedule",
        soft_fail=True,         # ← KEY: SKIP instead of FAIL on timeout
    )

    @task
    def process_vendor_data():
        """This only runs if vendor file was found."""
        print("📦 Processing vendor data...")

    @task
    def generate_final_report():
        """This ALWAYS runs — even if vendor file was skipped."""
        print("📊 Generating final report...")
        print("   (vendor data included if available, skipped if not)")
        print("✅ Report complete!")

    start = start_pipeline()

    start >> wait_for_vendor_file >> process_vendor_data()

    # generate_final_report runs regardless of sensor outcome
    # none_failed_min_one_success allows it to run even if sensor was skipped
    final = generate_final_report()
    final.set_upstream(start)
    final.trigger_rule = "none_failed_min_one_success"
    process_vendor_data() >> final
```

### Behaviour Comparison:

| `soft_fail` | File appears | File doesn't appear |
|---|---|---|
| `False` (default) | ✅ Proceeds | ❌ FAILS — pipeline stops |
| `True` | ✅ Proceeds | 🩷 SKIPPED — pipeline continues |

---

## ✏️ Use Case 7 — Sensor with Exponential Backoff

**Scenario:** Poll an external batch job API that may take 5 minutes or 3 hours to complete. Use exponential backoff to avoid hammering the API.

**File:** `dags/sensor_07_backoff.py`

```python
# sensor_07_backoff.py
# exponential_backoff=True increases wait time between checks gradually

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.python import PythonSensor
from datetime import datetime
import random

# Simulate a batch job that takes random time to complete
_job_check_count = {"count": 0}

def check_batch_job_status(**context):
    """
    Simulates checking an external batch job.
    Returns True after ~5 checks to simulate job completion.
    """
    _job_check_count["count"] += 1
    count = _job_check_count["count"]

    # Simulate job completing after 5 checks
    is_complete = count >= 5
    status = "COMPLETE" if is_complete else "RUNNING"

    print(f"🔍 Batch job check #{count}: status = {status}")

    if is_complete:
        print("✅ Batch job completed!")
    else:
        print(f"⏳ Job still running... (check #{count}/5)")

    return is_complete

with DAG(
    dag_id="sensor_07_backoff",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["sensors", "backoff"],
):

    # ── Without backoff (fixed interval) ─────────────────────────
    wait_fixed = PythonSensor(
        task_id="wait_fixed_interval",
        python_callable=check_batch_job_status,
        poke_interval=10,           # always waits exactly 10 seconds
        timeout=300,
        mode="reschedule",
        exponential_backoff=False,  # fixed interval
    )

    # ── With exponential backoff ──────────────────────────────────
    wait_with_backoff = PythonSensor(
        task_id="wait_with_backoff",
        python_callable=check_batch_job_status,
        poke_interval=5,            # starts at 5 seconds
        timeout=300,
        mode="reschedule",
        exponential_backoff=True,   # 5s → 10s → 20s → 40s...
        max_wait=60,                # cap at 60 seconds max
    )

    @task
    def process_batch_results():
        print("📊 Processing completed batch job results!")

    wait_with_backoff >> process_batch_results()
```

### Exponential Backoff Pattern:

```
poke_interval=5, exponential_backoff=True, max_wait=60

Check 1: wait 5s
Check 2: wait 10s
Check 3: wait 20s
Check 4: wait 40s
Check 5: wait 60s  ← capped by max_wait
Check 6: wait 60s  ← stays at max_wait
...
```

---

## ✏️ Use Case 8 — Full Pipeline with Multiple Sensors

**Scenario:** A complete end-to-end data pipeline that uses sensors at every critical gate:
1. Wait for upstream ETL DAG to finish
2. Wait for raw data file to land
3. Wait for API health check
4. Process and generate report

**File:** `dags/sensor_08_full_pipeline.py`

```python
# sensor_08_full_pipeline.py
# Full pipeline using multiple sensors as gates at each stage

from airflow.sdk import DAG, task
from airflow.providers.standard.sensors.filesystem import FileSensor
from airflow.providers.standard.sensors.python import PythonSensor
from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from airflow.providers.http.sensors.http import HttpSensor
from datetime import datetime

with DAG(
    dag_id="sensor_08_full_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["sensors", "full-pipeline"],
):

    # ── Gate 1: Wait for upstream ETL to complete ─────────────────
    wait_for_etl = ExternalTaskSensor(
        task_id="gate_1_wait_for_etl",
        external_dag_id="sensor_05_etl_pipeline",
        external_task_id=None,
        allowed_states=["success"],
        poke_interval=30,
        timeout=1800,
        mode="reschedule",
    )

    # ── Gate 2: Wait for raw file to land ─────────────────────────
    wait_for_file = FileSensor(
        task_id="gate_2_wait_for_file",
        filepath="daily_sales.csv",
        fs_conn_id="fs_default",
        poke_interval=30,
        timeout=600,
        mode="reschedule",
        soft_fail=False,
    )

    # ── Gate 3: Confirm API is healthy ────────────────────────────
    wait_for_api = HttpSensor(
        task_id="gate_3_wait_for_api",
        http_conn_id="jsonplaceholder_api",
        endpoint="/posts/1",
        response_check=lambda response: response.status_code == 200,
        poke_interval=20,
        timeout=120,
        mode="reschedule",
    )

    # ── Gate 4: Custom readiness check ───────────────────────────
    def check_system_readiness(**context):
        """All systems go check."""
        import random
        score = random.randint(80, 100)
        print(f"🔍 System readiness score: {score}%")
        return score >= 85

    wait_for_readiness = PythonSensor(
        task_id="gate_4_system_readiness",
        python_callable=check_system_readiness,
        poke_interval=15,
        timeout=120,
        mode="reschedule",
    )

    # ── Processing tasks (only run after all gates pass) ──────────
    @task
    def process_data():
        print("⚙️  All gates passed — processing data...")
        print("   ✅ ETL data ready")
        print("   ✅ File landed")
        print("   ✅ API healthy")
        print("   ✅ System ready")

    @task
    def generate_report():
        print("📊 Generating final daily report...")
        print("✅ Pipeline complete!")

    # All 4 sensors run in PARALLEL (faster overall wait)
    # Then processing runs after ALL sensors pass
    [wait_for_etl, wait_for_file, wait_for_api, wait_for_readiness] >> process_data() >> generate_report()
```

### Pipeline Flow:
```
              ┌──→ gate_1_wait_for_etl       ──→┐
              ├──→ gate_2_wait_for_file      ──→ ├──→ process_data ──→ generate_report
              ├──→ gate_3_wait_for_api       ──→┤
              └──→ gate_4_system_readiness   ──→┘
         (all 4 sensors run in parallel)
         (process_data only starts when ALL pass)
```

---

## 🐳 Docker Setup for Sensors

### Required Connections (run these first)

```bash
# 1. Filesystem connection for FileSensor
docker compose run --rm airflow-cli airflow connections add 'fs_default' \
    --conn-type 'fs' \
    --conn-extra '{"path": "/opt/airflow/data"}'

# 2. HTTP connection for HttpSensor
docker compose run --rm airflow-cli airflow connections add 'jsonplaceholder_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com'

# Verify both connections
docker compose run --rm airflow-cli airflow connections list
```

### Required Providers

Add to `requirements.txt`:
```
apache-airflow-providers-standard
apache-airflow-providers-http
```

Rebuild Docker image:
```bash
docker compose build --no-cache
docker compose up -d
```

### Required Volume Mount (for FileSensor)

In `docker-compose.yaml`:
```yaml
volumes:
  - ${AIRFLOW_PROJ_DIR:-.}/dags:/opt/airflow/dags
  - ${AIRFLOW_PROJ_DIR:-.}/logs:/opt/airflow/logs
  - ${AIRFLOW_PROJ_DIR:-.}/plugins:/opt/airflow/plugins
  - ${AIRFLOW_PROJ_DIR:-.}/config:/opt/airflow/config
  - ${AIRFLOW_PROJ_DIR:-.}/data:/opt/airflow/data   # ← ADD THIS
```

```bash
mkdir -p ./data
docker compose down && docker compose up -d
```

### Creating Test Files to Trigger FileSensor

```bash
# Create a test file on your laptop (appears immediately inside container)
echo "product,amount
Laptop,75000
Phone,25000" > ./data/sales_data.csv

# Verify it's visible inside container
docker exec airflow-docker-airflow-scheduler-1 \
  cat /opt/airflow/data/sales_data.csv

# Delete it to reset sensor (for re-testing)
rm ./data/sales_data.csv
```

### Verifying Sensor Status via CLI

```bash
# List all task instances for a DAG run
docker compose run --rm airflow-cli airflow tasks states-for-dag-run \
  sensor_01_file <run_id>

# Check task logs to see sensor poke attempts
docker compose run --rm airflow-cli airflow tasks logs \
  sensor_01_file wait_for_sales_csv <logical_date>

# List recent DAG runs
docker compose run --rm airflow-cli airflow dags list-runs \
  --dag-id sensor_01_file
```

---

## 💻 Sensors CLI Commands

```bash
# Trigger a DAG with a sensor
docker compose run --rm airflow-cli airflow dags trigger sensor_01_file

# Check task state (is sensor still sensing?)
docker compose run --rm airflow-cli airflow tasks state \
  sensor_01_file wait_for_sales_csv <execution_date>

# Manually mark sensor as success (bypass the wait — useful for testing)
docker compose run --rm airflow-cli airflow tasks clear \
  sensor_01_file -t wait_for_sales_csv -y

# Test a single sensor task without a full DAG run
docker compose run --rm airflow-cli airflow tasks test \
  sensor_01_file wait_for_sales_csv 2024-01-01

# View sensor task logs
docker compose run --rm airflow-cli airflow tasks logs \
  sensor_01_file wait_for_sales_csv 2024-01-01T00:00:00+00:00
```

---

## 📊 Sensor Comparison Table

| Sensor | Provider | Use When | Mode Recommendation |
|---|---|---|---|
| `FileSensor` | standard | Waiting for files to land | `reschedule` |
| `HttpSensor` | http | Waiting for API to respond | `reschedule` |
| `PythonSensor` | standard | Any custom Python condition | `reschedule` |
| `@task.sensor` | standard | Custom condition + data passthrough | `reschedule` |
| `ExternalTaskSensor` | standard | Cross-DAG dependencies | `reschedule` |
| `DateTimeSensor` | standard | Wait until specific date/time | `deferrable` |
| `TimeDeltaSensor` | standard | Wait for time to pass | `deferrable` |
| `SqlSensor` | common.sql | Wait for DB records to appear | `reschedule` |
| `S3KeySensor` | amazon | Wait for S3 file | `deferrable` |

---

## ⚠️ Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Not setting `timeout` | Sensor runs for 7 days! | Always set `timeout` — e.g. `timeout=3600` for 1 hour |
| Using `poke` mode for long waits | Worker slots exhausted, other tasks can't run | Use `mode="reschedule"` for waits > 5 minutes |
| `poke_interval` too short | Too many DB queries, scheduler overloaded | Set `poke_interval` ≥ 30 seconds for most cases |
| `response_check` always returns `None` | Sensor never succeeds | Ensure the lambda explicitly returns `True` or `False` |
| FileSensor can't find file | `AirflowSensorTimeout` | Check `fs_conn_id` path + file name spelling |
| `fs_default` connection not created | `KeyError: fs_default` | Create the connection first via CLI or UI |
| ExternalTaskSensor logical dates don't match | Sensor waits forever | Both DAGs must run with same logical date |
| No `./data/` volume mount in Docker | File never visible inside container | Add volume mount to `docker-compose.yaml` and restart |
| `soft_fail` not set, optional file absent | Whole pipeline fails | Use `soft_fail=True` for optional dependencies |
| Using `deferrable=True` without triggerer | Task stays in deferred state forever | Ensure `airflow-triggerer` container is running |

---

## 📦 All DAG Files Summary

| # | File | Sensor Used | Key Concept |
|---|---|---|---|
| 1 | `sensor_01_file.py` | `FileSensor` | Wait for CSV file, `fs_default` connection |
| 2 | `sensor_02_http.py` | `HttpSensor` | Wait for API, `response_check` lambda |
| 3 | `sensor_03_python.py` | `PythonSensor` | Custom Python condition, return `True`/`False` |
| 4 | `sensor_04_decorator.py` | `@task.sensor` | `PokeReturnValue`, pass data downstream |
| 5 | `sensor_05_external_dag.py` | `ExternalTaskSensor` | Cross-DAG dependency |
| 6 | `sensor_06_soft_fail.py` | `FileSensor` + `soft_fail` | Skip instead of fail on timeout |
| 7 | `sensor_07_backoff.py` | `PythonSensor` + backoff | Exponential backoff for external APIs |
| 8 | `sensor_08_full_pipeline.py` | Multiple sensors | Parallel gates, full production pattern |

---

## ✅ Trainee Practice Checklist

### Level 1 — Setup
- [ ] Add `./data:/opt/airflow/data` volume mount to `docker-compose.yaml`
- [ ] Create `./data/` folder and restart Docker: `docker compose down && docker compose up -d`
- [ ] Create `fs_default` connection via Docker CLI
- [ ] Create `jsonplaceholder_api` HTTP connection via Docker CLI
- [ ] Verify both connections with `docker compose run --rm airflow-cli airflow connections list`

### Level 2 — FileSensor Basics
- [ ] Create `sensor_01_file.py` and trigger the DAG
- [ ] Watch the sensor task turn **yellow** in the UI (sensing state)
- [ ] Create `./data/sales_data.csv` — watch sensor turn **green** automatically
- [ ] Check the task logs — see each poke attempt printed
- [ ] Delete the file, re-trigger, let it timeout — observe `FAILED` state
- [ ] Set `soft_fail=True` — re-trigger without file — observe `SKIPPED` state

### Level 3 — HTTP and Python Sensors
- [ ] Create `sensor_02_http.py` — trigger and watch both HTTP sensors
- [ ] Modify `response_check` to check for specific JSON field — test it works
- [ ] Create `sensor_03_python.py` — trigger and observe random quality scores in logs
- [ ] Change the threshold from 90 to 50 — observe sensor succeeds faster

### Level 4 — Modern Decorator & External
- [ ] Create `sensor_04_decorator.py` — trigger and check XCom for inventory data
- [ ] Create `sensor_05_external_dag.py` — trigger ETL first, then trigger report DAG
- [ ] Observe report DAG waiting in sensing state until ETL completes
- [ ] Verify both DAGs need same logical date to connect

### Level 5 — Advanced Patterns
- [ ] Create `sensor_06_soft_fail.py` — trigger without file — confirm `SKIPPED` not `FAILED`
- [ ] Create `sensor_07_backoff.py` — check logs to see wait intervals increasing
- [ ] Create `sensor_08_full_pipeline.py` — trigger all 4 sensors running in parallel
- [ ] Create all required files and connections — confirm full pipeline runs end to end

---

## 🔗 Useful Resources

- 📖 [Airflow Sensors Docs](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html)
- 📖 [FileSensor Docs](https://airflow.apache.org/docs/apache-airflow-providers-standard/stable/sensors/file.html)
- 📖 [ExternalTaskSensor Docs](https://airflow.apache.org/docs/apache-airflow-providers-standard/stable/sensors/external_task_sensor.html)
- 📖 [Deferrable Operators Docs](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/deferring.html)
- 🔗 [DAG Creation Guide](./airflow_dag_guide.md)
- 🔗 [DAG Branching Guide](./airflow_dag_branching_guide.md)
- 🔗 [Assets Guide](./airflow_assets_guide.md)
- 🔗 [Variables, Providers & Connections Guide](./airflow_variables_providers_connections_guide.md)

---

> 🙌 **Key Rules for Sensors:**
>
> 1. **Always set `timeout`** — the default is 7 days which will block worker slots
> 2. **Use `mode="reschedule"`** for any wait longer than 5 minutes
> 3. **Use `soft_fail=True`** for optional dependencies that shouldn't block the pipeline
> 4. **Use `@task.sensor`** when you need to pass data from the sensor to downstream tasks
> 5. **Mount `./data/`** as a Docker volume so FileSensor can actually see your files
> 6. **Create the `fs_default` connection** before using FileSensor — it's not auto-created
