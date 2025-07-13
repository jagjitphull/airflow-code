# dags/parent_dag.py, needs child_dag.py also in the same dag folder.
from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="jp_parent_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@daily",
    catchup=False,
    tags=["jp_parent", "example"],
    doc_md="""
    ### Parent DAG
    This DAG runs daily and has a simple task that the child_dag will wait for.
    """,
) as dag:
    start_task = BashOperator(
        task_id="start_parent_process",
        bash_command="echo 'Starting parent process...'",
    )

    # This is the task the child_dag will wait for
    parent_data_ready_task = BashOperator(
        task_id="parent_data_ready",
        bash_command="echo 'Parent data is ready! Simulating work...'; sleep 5",
    )

    end_task = BashOperator(
        task_id="end_parent_process",
        bash_command="echo 'Parent process finished.'",
    )

    start_task >> parent_data_ready_task >> end_task
