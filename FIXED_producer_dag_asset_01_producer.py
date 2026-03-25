#FIXED_producer_dag_asset_01_producer.py


# asset_01_producer.py — FIXED VERSION (actually saves the file)

from airflow.sdk import DAG, Asset
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import csv
import os

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

        # ── Step 1: Make sure the directory exists ──────────────
        output_dir  = "/opt/airflow/data"
        output_file = f"{output_dir}/raw_sales.csv"
        os.makedirs(output_dir, exist_ok=True)   # creates folder if not present

        # ── Step 2: Data to save ────────────────────────────────
        data = [
            {"id": 1, "product": "Laptop",  "amount": 75000},
            {"id": 2, "product": "Phone",   "amount": 25000},
            {"id": 3, "product": "Tablet",  "amount": 35000},
        ]

        # ── Step 3: Actually write the CSV file ─────────────────
        with open(output_file, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "product", "amount"])
            writer.writeheader()
            writer.writerows(data)

        # ── Step 4: Verify it was written ───────────────────────
        file_size = os.path.getsize(output_file)
        print(f"💾 File saved : {output_file}")
        print(f"📏 File size  : {file_size} bytes")
        print(f"✅ Saved {len(data)} records to raw_sales.csv")

    produce_task = PythonOperator(
        task_id="extract_and_save",
        python_callable=extract_and_save,
        outlets=[raw_sales_asset],
    )
