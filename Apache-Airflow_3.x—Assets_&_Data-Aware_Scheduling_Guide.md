# 📦 Apache Airflow 3.x — Assets & Data-Aware Scheduling Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Intermediate → Advanced  
> **Prerequisite:** Complete [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to build event-driven, data-aware pipelines using Airflow Assets

---

## 📑 Table of Contents

- [What Are Assets?](#-what-are-assets)
- [Key Terminology](#-key-terminology)
- [Use Case 1 — Basic Producer & Consumer](#-use-case-1--basic-producer--consumer)
- [Use Case 2 — ETL Pipeline with @asset Decorator](#-use-case-2--etl-pipeline-with-asset-decorator)
- [Use Case 3 — Multiple Assets (AND Logic)](#-use-case-3--multiple-assets-and-logic)
- [Use Case 4 — Multiple Assets (OR Logic)](#-use-case-4--multiple-assets-or-logic)
- [Use Case 5 — Asset with Metadata](#-use-case-5--asset-with-metadata)
- [Use Case 6 — Asset + Time Schedule Combined](#-use-case-6--asset--time-schedule-combined)
- [Use Case 7 — Full Data Pipeline (Real World)](#-use-case-7--full-data-pipeline-real-world)
- [Manual Asset Events (UI & API)](#-manual-asset-events-ui--api)
- [Viewing Assets in the UI](#-viewing-assets-in-the-ui)
- [Assets CLI Commands](#-assets-cli-commands)
- [Common Mistakes](#-common-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

## 🧠 What Are Assets?

In Airflow 3, an **Asset** is a logical representation of a piece of data — a file, database table, ML model, or any data product.

> 💡 **Think of it this way:** Instead of saying *"run this DAG every day at 6am"*, you say *"run this DAG whenever this data is ready"*. That's data-aware scheduling with Assets.

```
Old way (time-based):
  run_daily_etl   ──→ schedule: "@daily"  (runs whether data is ready or not)

New way (asset-based):
  raw_data_asset  ──→ updated by producer DAG
                       │
                       ▼
  consumer DAG    ──→ schedule: [raw_data_asset]  (only runs when data is fresh)
```

### Why Use Assets?
- Avoid running a pipeline before upstream data is ready
- Create **cross-DAG dependencies** without tight coupling
- Build pipelines that react to **real data events**, not just clocks
- Visualize data flow across DAGs in the **Assets tab** in the UI

---

## 📖 Key Terminology

| Term | Meaning |
|---|---|
| **Asset** | A logical data entity defined by a name and optional URI |
| **URI** | Unique identifier for the data location (e.g., `s3://bucket/file.csv`) |
| **Producer Task** | A task that updates an asset using `outlets=[my_asset]` |
| **Consumer DAG** | A DAG that runs when an asset is updated using `schedule=[my_asset]` |
| **Asset Event** | A record created each time an asset is updated |
| **`outlets`** | Task parameter — marks assets this task produces/updates |
| **`inlets`** | Task parameter — marks assets this task reads/consumes |
| **`@asset` decorator** | Airflow 3 shorthand — creates a DAG + task + asset in one block |

---

## ✏️ Use Case 1 — Basic Producer & Consumer

**Scenario:** A simple pipeline where one DAG produces data and a second DAG automatically runs when that data is ready.

### File 1 — Producer DAG

**File:** `dags/asset_01_producer.py`

```python
# asset_01_producer.py
# This DAG runs on a schedule and PRODUCES an asset

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Step 1: Define the Asset (name + optional URI)
raw_sales_asset = Asset(
    name="raw_sales_data",
    uri="file:///opt/airflow/data/raw_sales.csv",
)

with DAG(
    dag_id="asset_01_producer",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["assets", "producer"],
):

    def extract_and_save(**context):
        print("📥 Extracting sales data from source system...")
        print("💾 Saving raw_sales.csv to data folder...")

        # Simulate writing data
        data = [
            {"id": 1, "product": "Laptop",  "amount": 75000},
            {"id": 2, "product": "Phone",   "amount": 25000},
            {"id": 3, "product": "Tablet",  "amount": 35000},
        ]
        print(f"✅ Saved {len(data)} records to raw_sales.csv")
        print(f"   Asset will be marked as UPDATED after this task completes")

    # Step 2: outlets=[asset] marks the asset as updated when task succeeds
    produce_task = PythonOperator(
        task_id="extract_and_save",
        python_callable=extract_and_save,
        outlets=[raw_sales_asset],    # ← KEY: this updates the asset
    )
```

### File 2 — Consumer DAG

**File:** `dags/asset_01_consumer.py`

```python
# asset_01_consumer.py
# This DAG runs AUTOMATICALLY when raw_sales_asset is updated

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Step 1: Reference the SAME asset (must match name exactly)
raw_sales_asset = Asset(
    name="raw_sales_data",
    uri="file:///opt/airflow/data/raw_sales.csv",
)

with DAG(
    dag_id="asset_01_consumer",
    start_date=datetime(2024, 1, 1),
    schedule=[raw_sales_asset],    # ← KEY: triggers when asset updates
    catchup=False,
    tags=["assets", "consumer"],
):

    def process_sales(**context):
        print("📊 Consumer DAG triggered — raw_sales_data asset was updated!")
        print("🔄 Processing raw sales data...")
        print("✅ Processed and ready for reporting")

    consume_task = PythonOperator(
        task_id="process_sales",
        python_callable=process_sales,
    )
```

### Flow:
```
asset_01_producer (runs @daily)
   └→ extract_and_save [outlets: raw_sales_asset]
             │
             │ asset event created ✅
             ▼
asset_01_consumer (triggered automatically)
   └→ process_sales
```

### 🎯 What to Observe:
1. Trigger `asset_01_producer` manually
2. After it completes, **`asset_01_consumer` starts automatically** — no manual trigger needed
3. Go to UI → **Assets tab** → see `raw_sales_data` listed with its event history
4. The consumer DAG has **no cron schedule** — it only runs when data arrives

---

## ✏️ Use Case 2 — ETL Pipeline with `@asset` Decorator

The `@asset` decorator is the **modern Airflow 3 shorthand** — it creates a DAG + task + asset all in one block.

**Scenario:** A 3-step ETL pipeline where each step is an asset that triggers the next.

**File:** `dags/asset_02_etl_decorator.py`

```python
# asset_02_etl_decorator.py
# Modern Airflow 3 style using @asset decorator

from airflow.sdk import asset
from datetime import datetime

# ── Step 1: Extract ─────────────────────────────────────────────────────────
# @asset creates: an Asset named "raw_orders", a DAG named "raw_orders",
#                 and a task named "raw_orders" — all in one block!
@asset(
    uri="file:///opt/airflow/data/raw_orders.json",
    schedule="@daily",                # runs on a time schedule to produce data
)
def raw_orders():
    """Extract raw orders from source system."""
    print("📥 Extracting orders from API / database...")

    orders = [
        {"order_id": "ORD001", "customer": "Alice", "amount": 1500, "status": "new"},
        {"order_id": "ORD002", "customer": "Bob",   "amount": 3200, "status": "new"},
        {"order_id": "ORD003", "customer": "Carol", "amount": 800,  "status": "new"},
    ]

    print(f"✅ Extracted {len(orders)} orders")
    return orders


# ── Step 2: Transform ────────────────────────────────────────────────────────
@asset(
    uri="file:///opt/airflow/data/cleaned_orders.json",
    schedule=[raw_orders],            # triggers when raw_orders asset updates
)
def cleaned_orders(raw_orders):
    """Clean and validate extracted orders."""
    print("🔄 Cleaning and validating orders...")
    print(f"   Input asset: raw_orders")

    # Simulate transformation
    print("   - Removing duplicates")
    print("   - Validating amounts")
    print("   - Standardizing customer names")
    print("✅ Orders cleaned and validated")


# ── Step 3: Load ─────────────────────────────────────────────────────────────
@asset(
    uri="file:///opt/airflow/data/orders_report.csv",
    schedule=[cleaned_orders],        # triggers when cleaned_orders updates
)
def orders_report(cleaned_orders):
    """Generate final orders report."""
    print("📊 Generating orders report...")
    print("   - Aggregating by customer")
    print("   - Calculating totals")
    print("   - Writing to report CSV")
    print("✅ Report generated and saved!")
```

### Chain:
```
raw_orders (@daily)
    │ updates asset
    ▼
cleaned_orders (triggered by raw_orders)
    │ updates asset
    ▼
orders_report (triggered by cleaned_orders)
```

### 🎯 What to Observe:
- Three separate DAGs appear in the UI, each named after the function
- Triggering `raw_orders` kicks off the **entire chain automatically**
- In the **Assets tab**, you can see all 3 assets and their dependencies
- This is the **most concise way** to write asset-driven pipelines in Airflow 3

---

## ✏️ Use Case 3 — Multiple Assets (AND Logic)

**Scenario:** A reporting DAG that should only run when **both** sales data AND inventory data have been updated.

**File:** `dags/asset_03_and_logic.py`

```python
# asset_03_and_logic.py
# Consumer waits for ALL assets to be updated (AND logic)

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Define two independent assets
sales_asset     = Asset(name="daily_sales",     uri="file:///opt/airflow/data/sales.csv")
inventory_asset = Asset(name="daily_inventory", uri="file:///opt/airflow/data/inventory.csv")

# ── Producer 1: Sales DAG ────────────────────────────────────────────────────
with DAG(
    dag_id="asset_03_sales_producer",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["assets", "producer"],
):
    def produce_sales(**context):
        print("📦 Extracting daily sales data...")
        print("✅ Sales data ready — updating daily_sales asset")

    PythonOperator(
        task_id="produce_sales",
        python_callable=produce_sales,
        outlets=[sales_asset],         # ← updates sales asset
    )

# ── Producer 2: Inventory DAG ────────────────────────────────────────────────
with DAG(
    dag_id="asset_03_inventory_producer",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["assets", "producer"],
):
    def produce_inventory(**context):
        print("🏭 Extracting daily inventory data...")
        print("✅ Inventory data ready — updating daily_inventory asset")

    PythonOperator(
        task_id="produce_inventory",
        python_callable=produce_inventory,
        outlets=[inventory_asset],     # ← updates inventory asset
    )

# ── Consumer: Report DAG (waits for BOTH) ────────────────────────────────────
with DAG(
    dag_id="asset_03_combined_report",
    start_date=datetime(2024, 1, 1),
    schedule=[sales_asset, inventory_asset],   # AND — waits for BOTH
    catchup=False,
    tags=["assets", "consumer"],
):
    def generate_combined_report(**context):
        print("📊 Both assets updated — generating combined report!")
        print("   ✅ Sales data    : ready")
        print("   ✅ Inventory data: ready")
        print("   🖨️  Combined report generated!")

    PythonOperator(
        task_id="generate_report",
        python_callable=generate_combined_report,
    )
```

### Flow:
```
asset_03_sales_producer     ─→ daily_sales asset updated     ─→┐
                                                                 ├→ asset_03_combined_report
asset_03_inventory_producer ─→ daily_inventory asset updated ─→┘
         (BOTH must update before consumer runs)
```

### 🎯 What to Observe:
- Trigger only `asset_03_sales_producer` — consumer does **NOT** run yet
- Trigger `asset_03_inventory_producer` — consumer **NOW runs automatically**
- In the Assets tab, you can see a **"queued event"** waiting after the first producer runs
- This ensures the report always has fresh data from **both** sources

---

## ✏️ Use Case 4 — Multiple Assets (OR Logic)

**Scenario:** A notification DAG that should run when **either** high-priority orders OR urgent inventory alerts are posted.

**File:** `dags/asset_04_or_logic.py`

```python
# asset_04_or_logic.py
# Consumer triggers when ANY one asset is updated (OR logic)

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Define assets
priority_orders_asset = Asset(name="priority_orders",  uri="file:///opt/airflow/data/priority.csv")
urgent_alerts_asset   = Asset(name="urgent_alerts",    uri="file:///opt/airflow/data/alerts.csv")

# ── Producer 1: Priority Orders ──────────────────────────────────────────────
with DAG(
    dag_id="asset_04_priority_orders",
    start_date=datetime(2024, 1, 1),
    schedule=None,        # manual trigger for demo
    catchup=False,
    tags=["assets", "producer"],
):
    PythonOperator(
        task_id="post_priority_orders",
        python_callable=lambda: print("🚨 Priority orders posted!"),
        outlets=[priority_orders_asset],
    )

# ── Producer 2: Urgent Alerts ────────────────────────────────────────────────
with DAG(
    dag_id="asset_04_urgent_alerts",
    start_date=datetime(2024, 1, 1),
    schedule=None,        # manual trigger for demo
    catchup=False,
    tags=["assets", "producer"],
):
    PythonOperator(
        task_id="post_urgent_alerts",
        python_callable=lambda: print("⚠️  Urgent inventory alert posted!"),
        outlets=[urgent_alerts_asset],
    )

# ── Consumer: Notification DAG (triggers on EITHER asset) ───────────────────
with DAG(
    dag_id="asset_04_notification",
    start_date=datetime(2024, 1, 1),
    schedule=(priority_orders_asset | urgent_alerts_asset),   # OR logic with |
    catchup=False,
    tags=["assets", "consumer"],
):
    def send_notification(**context):
        print("🔔 Notification triggered — one or more assets updated!")
        print("   Checking which asset fired...")
        print("   Sending alert to operations team...")

    PythonOperator(
        task_id="send_notification",
        python_callable=send_notification,
    )
```

### Logic Summary:

| Syntax | Meaning |
|---|---|
| `schedule=[asset_a, asset_b]` | AND — wait for **both** to update |
| `schedule=(asset_a & asset_b)` | AND — same as above, explicit syntax |
| `schedule=(asset_a \| asset_b)` | OR — trigger when **either** updates |
| `schedule=(asset_a \| (asset_b & asset_c))` | Complex — a OR (b AND c) |

### 🎯 What to Observe:
- Trigger **either** producer alone → consumer runs immediately
- Trigger **both** → consumer runs twice (once per event)
- Compare behavior with Use Case 3 (AND) — spot the difference

---

## ✏️ Use Case 5 — Asset with Metadata

**Scenario:** Attach extra information to an asset event — like row count, file size, or processing stats. This metadata can be read by downstream tasks.

**File:** `dags/asset_05_metadata.py`

```python
# asset_05_metadata.py
# Attach metadata to asset events and read them downstream

from airflow.sdk import DAG, Asset, Metadata
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# Define assets
processed_data_asset = Asset(
    name="processed_customer_data",
    uri="file:///opt/airflow/data/customers_processed.csv",
)

# ── Producer: Attaches metadata to the asset event ──────────────────────────
with DAG(
    dag_id="asset_05_producer_with_metadata",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["assets", "metadata"],
):

    def process_customers(**context):
        print("👥 Processing customer data...")

        # Simulate processing
        records_processed = 1500
        records_failed    = 12
        file_size_kb      = 234

        print(f"   Records processed : {records_processed}")
        print(f"   Records failed    : {records_failed}")
        print(f"   File size (KB)    : {file_size_kb}")

        # Attach metadata to the asset event using outlet_events
        context["outlet_events"][processed_data_asset].extra = {
            "row_count"    : records_processed,
            "failed_count" : records_failed,
            "file_size_kb" : file_size_kb,
            "processed_by" : "asset_05_producer",
        }

        print("✅ Metadata attached to asset event")

    PythonOperator(
        task_id="process_customers",
        python_callable=process_customers,
        outlets=[processed_data_asset],
    )

# ── Consumer: Reads metadata from the asset event ───────────────────────────
with DAG(
    dag_id="asset_05_consumer_reads_metadata",
    start_date=datetime(2024, 1, 1),
    schedule=[processed_data_asset],
    catchup=False,
    tags=["assets", "metadata"],
):

    def use_metadata(**context):
        print("📥 Consumer DAG triggered — reading asset metadata...")

        # Read metadata from the triggering asset event
        events = context["inlet_events"][processed_data_asset]

        if events:
            last_event = events[-1]              # most recent event
            extra      = last_event.extra or {}

            print(f"   Row count    : {extra.get('row_count', 'N/A')}")
            print(f"   Failed count : {extra.get('failed_count', 'N/A')}")
            print(f"   File size KB : {extra.get('file_size_kb', 'N/A')}")
            print(f"   Processed by : {extra.get('processed_by', 'N/A')}")

            # Use metadata to make decisions
            row_count = extra.get("row_count", 0)
            if row_count > 1000:
                print("📊 Large dataset — running full analytics pipeline")
            else:
                print("📊 Small dataset — running lightweight summary")
        else:
            print("⚠️  No asset event metadata found")

    PythonOperator(
        task_id="use_metadata",
        python_callable=use_metadata,
        inlets=[processed_data_asset],    # ← declare what assets this task reads
    )
```

### 🎯 What to Observe:
- Trigger the producer DAG
- Check the **Assets tab** → click on `processed_customer_data` → see the event with extra data
- The consumer reads `row_count` and uses it to make a processing decision
- `inlets` declares what the task reads — `outlets` declares what it writes

---

## ✏️ Use Case 6 — Asset + Time Schedule Combined

**Scenario:** A dashboard refresh that should run when data is updated **OR** at least once every morning at 9am — whichever comes first.

**File:** `dags/asset_06_asset_or_time.py`

```python
# asset_06_asset_or_time.py
# Run when asset updates OR on a time schedule (whichever comes first)

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from airflow.timetables.assets import AssetOrTimeSchedule
from airflow.timetables.trigger import CronTriggerTimetable
from datetime import datetime

# Asset that the dashboard depends on
dashboard_data_asset = Asset(
    name="dashboard_data",
    uri="file:///opt/airflow/data/dashboard.json",
)

# ── Producer: Updates dashboard data ────────────────────────────────────────
with DAG(
    dag_id="asset_06_data_producer",
    start_date=datetime(2024, 1, 1),
    schedule=None,        # manually triggered for demo
    catchup=False,
    tags=["assets", "combined-schedule"],
):
    PythonOperator(
        task_id="update_dashboard_data",
        python_callable=lambda: print("📊 Dashboard data updated!"),
        outlets=[dashboard_data_asset],
    )

# ── Consumer: Runs on asset update OR at 9am every day ──────────────────────
with DAG(
    dag_id="asset_06_dashboard_refresh",
    start_date=datetime(2024, 1, 1),
    schedule=AssetOrTimeSchedule(
        timetable=CronTriggerTimetable("0 9 * * *", timezone="UTC"),  # 9am daily
        assets=[dashboard_data_asset],                                 # OR on update
    ),
    catchup=False,
    tags=["assets", "combined-schedule"],
):

    def refresh_dashboard(**context):
        print("🖥️  Refreshing dashboard...")
        print(f"   Run type: {context.get('run_type', 'unknown')}")
        print("✅ Dashboard refreshed!")

    PythonOperator(
        task_id="refresh_dashboard",
        python_callable=refresh_dashboard,
    )
```

### Behaviour:
```
Scenario A: Data updated at 2pm
   → dashboard_refresh runs immediately at 2pm (asset-triggered)

Scenario B: No data update all day
   → dashboard_refresh still runs at 9am (time-triggered)

Best of both worlds! ✅
```

### 🎯 What to Observe:
- Trigger `asset_06_data_producer` at any time → dashboard refreshes immediately
- Without triggering producer, dashboard still refreshes at 9am UTC every day
- Check `run_type` in logs to see whether it was asset-triggered or time-triggered

---

## ✏️ Use Case 7 — Full Data Pipeline (Real World)

**Scenario:** A complete data engineering pipeline with 4 stages:
1. **Ingest** raw data daily
2. **Transform** when raw data is ready
3. **Validate** when transformed data is ready
4. **Publish** report only when **both** validation AND an ML model asset are ready

**File:** `dags/asset_07_full_pipeline.py`

```python
# asset_07_full_pipeline.py
# Full end-to-end asset-driven data pipeline

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

# ── Define all assets ────────────────────────────────────────────────────────
raw_data_asset        = Asset(name="raw_data",        uri="file:///opt/airflow/data/raw.csv")
transformed_asset     = Asset(name="transformed_data", uri="file:///opt/airflow/data/transformed.csv")
validated_asset       = Asset(name="validated_data",   uri="file:///opt/airflow/data/validated.csv")
ml_model_asset        = Asset(name="ml_model",         uri="file:///opt/airflow/models/model_v1.pkl")
final_report_asset    = Asset(name="final_report",     uri="file:///opt/airflow/reports/report.pdf")

# ── Stage 1: Ingestion (runs on schedule) ────────────────────────────────────
with DAG(
    dag_id="asset_07_stage1_ingest",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",      # every day at 2am
    catchup=False,
    tags=["assets", "pipeline", "stage-1"],
):
    def ingest(**context):
        print("🌐 Stage 1: Ingesting raw data from source...")
        print("   Connecting to data source API...")
        print("   Downloading latest records...")
        print("✅ Raw data saved — raw_data asset updated")

    PythonOperator(
        task_id="ingest_raw_data",
        python_callable=ingest,
        outlets=[raw_data_asset],
    )

# ── Stage 2: Transform (triggered by Stage 1) ────────────────────────────────
with DAG(
    dag_id="asset_07_stage2_transform",
    start_date=datetime(2024, 1, 1),
    schedule=[raw_data_asset],
    catchup=False,
    tags=["assets", "pipeline", "stage-2"],
):
    def transform(**context):
        print("⚙️  Stage 2: Transforming raw data...")
        print("   Cleaning nulls and duplicates...")
        print("   Applying business rules...")
        print("   Normalising column formats...")
        print("✅ Transformation complete — transformed_data asset updated")

    PythonOperator(
        task_id="transform_data",
        python_callable=transform,
        outlets=[transformed_asset],
    )

# ── Stage 3: Validate (triggered by Stage 2) ─────────────────────────────────
with DAG(
    dag_id="asset_07_stage3_validate",
    start_date=datetime(2024, 1, 1),
    schedule=[transformed_asset],
    catchup=False,
    tags=["assets", "pipeline", "stage-3"],
):
    def validate(**context):
        print("🔍 Stage 3: Validating transformed data...")
        print("   Running schema checks...")
        print("   Checking for anomalies...")
        print("   Data quality score: 97.3%")
        print("✅ Validation passed — validated_data asset updated")

    PythonOperator(
        task_id="validate_data",
        python_callable=validate,
        outlets=[validated_asset],
    )

# ── ML Model Producer (independent schedule) ─────────────────────────────────
with DAG(
    dag_id="asset_07_ml_model_trainer",
    start_date=datetime(2024, 1, 1),
    schedule="0 1 * * 1",     # every Monday at 1am
    catchup=False,
    tags=["assets", "pipeline", "ml"],
):
    def train_model(**context):
        print("🤖 Training ML model on latest data...")
        print("   Accuracy: 94.2%")
        print("✅ Model trained and saved — ml_model asset updated")

    PythonOperator(
        task_id="train_ml_model",
        python_callable=train_model,
        outlets=[ml_model_asset],
    )

# ── Stage 4: Publish (waits for BOTH validated data AND ml model) ─────────────
with DAG(
    dag_id="asset_07_stage4_publish",
    start_date=datetime(2024, 1, 1),
    schedule=[validated_asset, ml_model_asset],   # AND — needs both
    catchup=False,
    tags=["assets", "pipeline", "stage-4"],
):
    def publish(**context):
        print("📤 Stage 4: Publishing final report...")
        print("   Combining validated data + ML model predictions...")
        print("   Generating PDF report...")
        print("   Sending to stakeholders...")
        print("✅ Report published — final_report asset updated")

    PythonOperator(
        task_id="publish_report",
        python_callable=publish,
        outlets=[final_report_asset],
    )
```

### Full Pipeline Flow:
```
[2am daily]                    [Monday 1am]
     │                              │
     ▼                              ▼
stage1_ingest              ml_model_trainer
   raw_data ──→                  ml_model ──→┐
     │                                       │
     ▼                                       │
stage2_transform                             │
   transformed_data ──→                      │
     │                                       │
     ▼                                       │
stage3_validate                              │
   validated_data ──→──────────────────────→┤
                                             │
                              (BOTH needed) │
                                             ▼
                                   stage4_publish
                                    final_report
```

### 🎯 What to Observe:
- Run stages 1→2→3 manually to simulate the daily pipeline
- Run `ml_model_trainer` manually to simulate the weekly model update
- Only after **both** `validated_data` AND `ml_model` are updated does `stage4_publish` run
- This mirrors a real-world ML-powered reporting pipeline

---

## 🖱️ Manual Asset Events (UI & API)

You can **manually trigger an asset event** without running the producer DAG. Useful for testing consumers.

### Via UI:
1. Go to **Assets** tab in the top navigation
2. Click on any asset name
3. Click **"Create Asset Event"** button (top right)
4. Choose:
   - **Materialize** — runs the full producer DAG
   - **Manual** — directly creates the event (for testing only)

### Via REST API:
```bash
# Manually create an asset event
curl -X POST "http://localhost:8080/api/v2/assets/events" \
  -H "Content-Type: application/json" \
  -u airflow:airflow \
  -d '{
    "asset_uri": "file:///opt/airflow/data/raw_sales.csv",
    "extra": {"source": "manual_test", "row_count": 500}
  }'
```

### Via CLI:
```bash
# Check asset events
airflow assets list

# Trigger a DAG that uses asset schedule manually
airflow dags trigger asset_01_consumer
```

---

## 🖥️ Viewing Assets in the UI

| Location | What You See |
|---|---|
| Top nav → **Assets** | All assets, their URIs, last update time |
| Assets → click asset name | Event history, upstream/downstream DAGs |
| Assets → **Dependencies graph** | Visual map of asset → DAG relationships |
| DAG → **Graph view** | Assets shown as orange diamonds on task edges |
| DAG → **Grid view** | Asset events shown alongside DAG run history |

### What to look for in the Assets tab:
```
Asset: raw_sales_data
  URI: file:///opt/airflow/data/raw_sales.csv
  Last Updated: 2024-03-24 10:30:00

  Producing DAGs:  asset_01_producer
  Consuming DAGs:  asset_01_consumer

  Event History:
  ├── 2024-03-24 10:30:00  (from asset_01_producer)
  ├── 2024-03-23 10:28:00  (from asset_01_producer)
  └── 2024-03-22 10:31:00  (from asset_01_producer)
```

---

## 💻 Assets CLI Commands

```bash
# List all registered assets
airflow assets list

# Check asset details
airflow assets get --name raw_sales_data

# List all asset events
airflow assets materialize --name raw_sales_data

# List DAGs that consume a specific asset
airflow dags list | grep asset

# Check if consumer DAG is queued after asset update
airflow dags list-runs --dag-id asset_01_consumer
```

**Docker users — prefix with:**
```bash
docker compose run airflow-cli airflow assets list
docker compose run airflow-cli airflow dags list-runs --dag-id asset_01_consumer
```

---

## 📊 Key Concepts Summary

### `outlets` vs `inlets`

```python
# outlets = assets this task PRODUCES / UPDATES
PythonOperator(
    task_id="write_data",
    python_callable=my_func,
    outlets=[my_asset],    # task produces this asset
)

# inlets = assets this task READS / CONSUMES
PythonOperator(
    task_id="read_data",
    python_callable=my_func,
    inlets=[my_asset],     # task reads this asset (for lineage tracking)
)
```

### Asset vs Schedule

```python
# Time-based (old way) — runs whether data is ready or not
with DAG(schedule="@daily"):  ...

# Asset-based (new way) — runs only when data is ready
with DAG(schedule=[my_asset]):  ...

# Combined — runs on asset update OR at minimum on a schedule
with DAG(schedule=AssetOrTimeSchedule(...)):  ...
```

---

## ⚠️ Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Asset name mismatch between producer and consumer | Consumer never triggers | Use **exact same** `name` in both DAGs |
| Task fails but asset event still expected | Consumer triggers on failure | Asset event is only created on **task success** |
| Consumer not running after producer | DAG may still be paused | Unpause the consumer DAG in the UI |
| Using `schedule=my_asset` instead of `schedule=[my_asset]` | TypeError | Always wrap in a **list**: `schedule=[my_asset]` |
| Asset not visible in Assets tab | DAG not parsed yet | Wait 30-60s or run `airflow dags reserialize` |
| Consumer runs too many times | OR logic creates many events | Use AND (`&`) if you need all assets to update first |
| Storing credentials in asset URI | Security risk | URIs are stored in **plaintext** — never store secrets |

---

## 📦 All DAG Files Summary

| # | File | Scenario | Key Concept |
|---|---|---|---|
| 1 | `asset_01_producer.py` + `asset_01_consumer.py` | Basic event chain | `outlets`, `schedule=[asset]` |
| 2 | `asset_02_etl_decorator.py` | 3-step ETL pipeline | `@asset` decorator, chaining |
| 3 | `asset_03_and_logic.py` | Wait for both sources | AND logic with `[asset_a, asset_b]` |
| 4 | `asset_04_or_logic.py` | React to any source | OR logic with `asset_a \| asset_b` |
| 5 | `asset_05_metadata.py` | Pass stats to downstream | `Metadata`, `outlet_events`, `inlet_events` |
| 6 | `asset_06_asset_or_time.py` | Best-effort freshness | `AssetOrTimeSchedule` |
| 7 | `asset_07_full_pipeline.py` | End-to-end ML pipeline | Multi-stage, AND logic, independent producers |

---

## ✅ Trainee Practice Checklist

### Level 1 — Basics
- [ ] Create `asset_01_producer.py` and `asset_01_consumer.py`
- [ ] Trigger the producer — confirm the consumer runs **automatically**
- [ ] Check the **Assets tab** in the UI — find `raw_sales_data`
- [ ] View the **event history** for the asset
- [ ] Manually create an asset event from the UI — verify consumer triggers

### Level 2 — Decorator Style
- [ ] Create `asset_02_etl_decorator.py`
- [ ] Confirm 3 separate DAGs appear in the UI
- [ ] Trigger `raw_orders` — confirm the full chain fires automatically
- [ ] View the **asset dependency graph** in the Assets tab

### Level 3 — Multi-Asset Logic
- [ ] Create `asset_03_and_logic.py` (AND)
- [ ] Trigger only `sales_producer` — confirm consumer does NOT run
- [ ] Trigger `inventory_producer` — confirm consumer NOW runs
- [ ] Create `asset_04_or_logic.py` (OR)
- [ ] Trigger either producer alone — confirm consumer runs immediately
- [ ] Explain the difference between AND and OR behavior to a teammate

### Level 4 — Metadata & Combined Schedule
- [ ] Create `asset_05_metadata.py`
- [ ] Trigger producer — check asset event extra data in the Assets tab
- [ ] Confirm consumer reads and prints the `row_count` from metadata
- [ ] Create `asset_06_asset_or_time.py`
- [ ] Trigger the producer manually — confirm dashboard refreshes immediately
- [ ] Check scheduled run history to see time-triggered runs

### Level 5 — Full Pipeline
- [ ] Create `asset_07_full_pipeline.py` (all 5 DAGs in one file)
- [ ] Run stages 1 → 2 → 3 in sequence manually
- [ ] Run `ml_model_trainer` manually
- [ ] Confirm `stage4_publish` only runs after **both** validated_data AND ml_model are ready
- [ ] Draw the full asset dependency graph on paper
- [ ] Add a 5th stage that reads the `final_report` asset

---

## 🔗 Useful Resources

- 📖 [Airflow Asset Definitions Docs](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html)
- 📖 [Asset-Aware Scheduling Docs](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html)
- 📖 [Event-Driven Scheduling Docs](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/event-scheduling.html)
- 🔗 [DAG Creation Guide](./airflow_dag_guide.md)
- 🔗 [DAG Branching Guide](./airflow_dag_branching_guide.md)

---

> 🙌 **Key Mindset Shift for Assets:**
>
> **Old thinking:** *"When should I run this DAG?"*  
> **New thinking:** *"When is this data ready?"*
>
> Assets let your pipelines react to data — not just clocks. Start with Use Case 1, understand the producer/consumer pattern deeply, then work your way up. The `@asset` decorator in Use Case 2 is the future of Airflow pipeline design!
