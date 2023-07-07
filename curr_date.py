#!/usr/bin/env python3

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime


#Python Callable Function
def currentDateTime():
    return datetime.now()

with DAG(dag_id="DateTime",
        start_date=datetime(2023,7,1),
        schedule_interval='@daily',
        catchup=False) as dag:

#define python tasks
        taskA=PythonOperator(
        task_id="taskA",
        python_callable=currentDateTime)

#define bash task
        taskB=BashOperator(
        task_id="taskB",
        bash_command="echo 'Datetime displayed successfully' ")

#Define dependency
taskA >> taskB

#Using set_downstrams method
taskA.set_downstream(taskB)
