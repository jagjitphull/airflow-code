# dags/child_dag.py
from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor
from datetime import timedelta

with DAG(
    dag_id="jp_child_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
    tags=["jp_child", "example"],
    doc_md="""
    ### Child DAG
    This DAG waits for a specific task in the 'parent_dag' to succeed before
    executing its own tasks.
    """,
) as dag:
    # --- ExternalTaskSensor Definition ---
    # This sensor waits for the 'parent_data_ready' task in 'parent_dag'
    wait_for_parent_task = ExternalTaskSensor(
        task_id="wait_for_parent_data",
        external_dag_id="jp_parent_dag",  # The DAG to wait for
        external_task_id="parent_data_ready",  # The specific task in the external DAG
        # The execution_delta ensures it waits for the parent DAG run
        # corresponding to the *same* logical date as the child DAG.
        # This is CRUCIAL if DAGs have the same schedule.
        execution_delta=timedelta(minutes=0), # For same logical date
        # OR:
        # execution_date_fn=lambda dt: dt, # Another way to achieve the same logical date mapping

        # How often the sensor pokes (checks the status)
        poke_interval=10,  # Check every 10 seconds

        # How long the sensor will wait before failing
        timeout=60 * 10,  # 10 minutes (60 seconds * 10 = 600 seconds)

        # What states are considered a success for the external task
        allowed_states=["success"],

        # What states are considered a failure for the external task (optional)
        # failed_states=["failed", "skipped"],

        # 'reschedule' mode releases the worker slot while waiting,
        # 'poke' mode holds the worker slot. Reschedule is generally
        # preferred for longer waits.
        mode="reschedule",

        # If set to True, the sensor immediately fails if the external task/DAG doesn't exist
        check_existence=True,
    )

    start_child_process = BashOperator(
        task_id="start_child_process",
        bash_command="echo 'Parent data is ready! Starting child process...'",
    )

    process_child_data = BashOperator(
        task_id="process_child_data",
        bash_command="echo 'Processing child data...'; sleep 10",
    )

    end_child_process = BashOperator(
        task_id="end_child_process",
        bash_command="echo 'Child process finished.'",
    )

    # Define the dependency:
    # The child process starts only after the sensor confirms the parent task succeeded.
    wait_for_parent_task >> start_child_process >> process_child_data >> end_child_process
