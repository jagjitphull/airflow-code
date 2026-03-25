# 🔧 Apache Airflow 3.x — Variables, Providers & Connections Guide for Trainees

> **Version:** Apache Airflow 3.1.8  
> **Level:** Beginner → Intermediate  
> **Prerequisite:** Complete the [DAG Creation Guide](./airflow_dag_guide.md) first  
> **Goal:** Learn to manage configuration, credentials, and external integrations in Airflow

---

## 📑 Table of Contents

- [🐳 Docker CLI Setup](#-docker-cli-setup-start-here)
- [Part 1 — Variables](#-part-1--variables)
  - [What Are Variables?](#-what-are-variables)
  - [Create Variables — 4 Ways](#-create-variables--4-ways)
  - [Use Case 1 — Basic Variable Usage](#-use-case-1--basic-variable-usage)
  - [Use Case 2 — JSON Variables](#-use-case-2--json-variables-store-structured-config)
  - [Use Case 3 — Jinja Template Variables](#-use-case-3--jinja-template-variables-best-practice)
  - [Use Case 4 — Environment-Specific Variables](#-use-case-4--environment-specific-variables)
- [Part 2 — Providers](#-part-2--providers)
  - [What Are Providers?](#-what-are-providers)
  - [Installing Providers](#-installing-providers)
  - [Use Case 5 — List and Explore Providers](#-use-case-5--list-and-explore-providers)
- [Part 3 — Connections](#-part-3--connections)
  - [What Are Connections?](#-what-are-connections)
  - [Create Connections — 4 Ways](#-create-connections--4-ways)
  - [Use Case 6 — HTTP Connection](#-use-case-6--http-connection)
  - [Use Case 7 — PostgreSQL Connection with Hook](#-use-case-7--postgresql-connection-with-hook)
  - [Use Case 8 — Connection via Environment Variable](#-use-case-8--connection-via-environment-variable)
  - [Use Case 9 — Using Connections in Jinja Templates](#-use-case-9--using-connections-in-jinja-templates)
- [Part 4 — Putting It All Together](#-part-4--putting-it-all-together)
  - [Use Case 10 — Full Pipeline using Variables + Connections](#-use-case-10--full-pipeline-using-variables--connections)
- [CLI Quick Reference](#-cli-quick-reference)
- [Common Mistakes](#-common-mistakes)
- [Practice Checklist](#-trainee-practice-checklist)

---

# 🐳 Docker CLI Setup (Start Here)

> Since we are using **Docker-based Airflow**, you cannot run `airflow` commands directly in your terminal. All CLI commands must be run **inside the Docker containers**. This section shows you how to set that up properly before anything else.

---

## Step 1 — Verify Docker Setup is Running

Make sure your Airflow Docker stack is up:

```bash
# Check all running containers
docker ps

# You should see containers like:
# airflow-docker-airflow-scheduler-1
# airflow-docker-airflow-api-server-1
# airflow-docker-airflow-worker-1
# airflow-docker-airflow-dag-processor-1
# airflow-docker-postgres-1
# airflow-docker-redis-1
```

If containers are not running, start them:
```bash
cd your-airflow-docker-folder
docker compose up -d
```

---

## Step 2 — Three Ways to Run Airflow CLI in Docker

### Method A — `docker compose run` (Recommended for one-off commands)

This spins up a **new temporary container** just for the command:

```bash
# Syntax
docker compose run airflow-cli airflow <command>

# Examples
docker compose run airflow-cli airflow version
docker compose run airflow-cli airflow variables list
docker compose run airflow-cli airflow connections list
docker compose run airflow-cli airflow providers list
docker compose run airflow-cli airflow dags list
```

### Method B — `docker exec` into scheduler (Faster for multiple commands)

This runs commands **inside the already-running** scheduler container:

```bash
# First find your scheduler container name
docker ps --format "table {{.Names}}" | grep scheduler

# Run a single command
docker exec -it <scheduler-container-name> airflow variables list

# Example with typical container name
docker exec -it airflow-docker-airflow-scheduler-1 airflow variables list
docker exec -it airflow-docker-airflow-scheduler-1 airflow connections list
```

### Method C — Enter the container shell (Best for running many commands)

```bash
# Get into the container's bash shell
docker exec -it airflow-docker-airflow-scheduler-1 bash

# Now you're INSIDE the container — run airflow commands normally
airflow variables list
airflow connections list
airflow providers list
airflow dags list

# Exit when done
exit
```

---

## Step 3 — Create a Shell Alias (Time Saver ⚡)

Instead of typing `docker compose run airflow-cli airflow` every time, create a short alias.

**For Linux/macOS — add to `~/.bashrc` or `~/.zshrc`:**
```bash
# Add this line to your ~/.bashrc or ~/.zshrc
alias airflow='docker compose run --rm airflow-cli airflow'
```

**Reload the shell:**
```bash
source ~/.bashrc
# or
source ~/.zshrc
```

**Now you can run commands just like native Airflow:**
```bash
airflow version
airflow variables list
airflow connections list
airflow dags list
```

> 💡 The `--rm` flag automatically removes the temporary container after the command finishes — keeps Docker clean.

---

## Step 4 — Verify the CLI Works

Run these commands to confirm everything is working:

```bash
# Check Airflow version
docker compose run --rm airflow-cli airflow version

# Expected output:
# 3.1.8

# List DAGs
docker compose run --rm airflow-cli airflow dags list

# Check DB connection
docker compose run --rm airflow-cli airflow db check

# Check scheduler health
docker compose run --rm airflow-cli airflow jobs check --job-type SchedulerJob --local
```

---

## Step 5 — Working Directory for DAG Files

When using Docker, your local `./dags` folder is **mounted** into the container at `/opt/airflow/dags`.

```
Your laptop:                    Inside Docker container:
./dags/my_dag.py    ←mount→    /opt/airflow/dags/my_dag.py
./logs/             ←mount→    /opt/airflow/logs/
./plugins/          ←mount→    /opt/airflow/plugins/
./config/           ←mount→    /opt/airflow/config/
```

So when you create a DAG file in `./dags/` on your laptop, it's **immediately visible** inside all containers.

---

## Step 6 — Import/Export Files in Docker

When working with variable or connection JSON files:

```bash
# Copy a file INTO the container
docker cp variables.json airflow-docker-airflow-scheduler-1:/opt/airflow/variables.json

# Then import inside the container
docker exec airflow-docker-airflow-scheduler-1 \
  airflow variables import /opt/airflow/variables.json

# OR — use a single command with docker compose run
# (the ./dags folder is mounted, so place files there)
cp variables.json ./dags/variables.json
docker compose run --rm airflow-cli airflow variables import /opt/airflow/dags/variables.json

# Export variables (saves inside container — then copy out)
docker exec airflow-docker-airflow-scheduler-1 \
  airflow variables export /opt/airflow/dags/variables_backup.json
# File appears in your local ./dags/ folder automatically!
```

---

## Quick Docker CLI Cheatsheet

| Task | Command |
|---|---|
| Check version | `docker compose run --rm airflow-cli airflow version` |
| List DAGs | `docker compose run --rm airflow-cli airflow dags list` |
| Trigger a DAG | `docker compose run --rm airflow-cli airflow dags trigger my_dag` |
| List variables | `docker compose run --rm airflow-cli airflow variables list` |
| Set a variable | `docker compose run --rm airflow-cli airflow variables set key "value"` |
| Get a variable | `docker compose run --rm airflow-cli airflow variables get key` |
| List connections | `docker compose run --rm airflow-cli airflow connections list` |
| List providers | `docker compose run --rm airflow-cli airflow providers list` |
| Check DB health | `docker compose run --rm airflow-cli airflow db check` |
| Enter container | `docker exec -it airflow-docker-airflow-scheduler-1 bash` |
| View logs | `docker logs airflow-docker-airflow-scheduler-1 -f` |

> 📌 **For the rest of this guide**, every CLI command will show **both** the direct form and the Docker form side by side so you can follow along easily.



## 🧠 What Are Variables?

Airflow **Variables** are a key-value store for configuration values that need to be:
- Shared across multiple DAGs
- Changed without modifying DAG code
- Different between environments (dev/staging/prod)

> 💡 Think of Variables as **global config settings** for your Airflow instance.  
> Never hardcode things like file paths, batch sizes, API URLs, or thresholds in your DAG code — store them as Variables instead.

### Variables vs Other Options

| Storage | Use For | Encrypted? | Visible in UI? |
|---|---|---|---|
| **Variables** | Config values, settings, paths | ✅ (if name contains `secret`, `password`, etc.) | ✅ Yes |
| **Connections** | Credentials to external systems | ✅ Yes | ✅ Yes |
| **Params** | Per-DAG-run values | ❌ No | ✅ Yes |
| **XCom** | Values passed between tasks | ❌ No | ✅ Yes |
| **Env Variables** | System-level config | ❌ No | ❌ No |

---

## 🛠️ Create Variables — 4 Ways

### Way 1 — Airflow UI
1. Go to `http://localhost:8080`
2. Navigate to **Admin → Variables**
3. Click the **+** button
4. Fill in **Key**, **Value**, optional **Description**
5. Click **Save**

### Way 2 — CLI (Docker)

Since we use Docker-based Airflow, prefix all commands with `docker compose run --rm airflow-cli`:

```bash
# Set a simple variable
docker compose run --rm airflow-cli airflow variables set my_key "my_value"

# Set with description
docker compose run --rm airflow-cli airflow variables set batch_size "500" --description "Number of records per batch"

# Get a variable value
docker compose run --rm airflow-cli airflow variables get batch_size

# List all variables
docker compose run --rm airflow-cli airflow variables list

# Delete a variable
docker compose run --rm airflow-cli airflow variables delete old_key

# Export all variables to JSON file
# File saves to /opt/airflow/dags/ which maps to your local ./dags/ folder
docker compose run --rm airflow-cli airflow variables export /opt/airflow/dags/variables_backup.json

# Import variables from JSON file
# First copy file to ./dags/ then import
docker compose run --rm airflow-cli airflow variables import /opt/airflow/dags/variables.json
```

> 💡 **Tip:** If you set up the alias from Step 3 of Docker CLI Setup, just use `airflow variables list` directly.

### Way 3 — JSON Import File
Create a file `variables.json`:
```json
{
  "environment"    : "development",
  "batch_size"     : "500",
  "api_base_url"   : "https://api.example.com",
  "data_folder"    : "/opt/airflow/data",
  "max_retries"    : "3",
  "alert_email"    : "team@company.com",
  "sales_threshold": "10000",
  "db_config"      : "{\"host\": \"localhost\", \"port\": 5432, \"dbname\": \"airflow_db\"}"
}
```

Import with:
```bash
airflow variables import variables.json
# Docker:
docker compose run airflow-cli airflow variables import /opt/airflow/variables.json
```

### Way 4 — Environment Variable
```bash
# Format: AIRFLOW_VAR_{UPPERCASE_KEY}=value
export AIRFLOW_VAR_BATCH_SIZE=500
export AIRFLOW_VAR_API_BASE_URL=https://api.example.com
```

> ⚠️ Environment variable values are not shown in the UI and cannot be edited from UI/CLI.

---

## ✏️ Use Case 1 — Basic Variable Usage

**Scenario:** A pipeline that uses configurable settings stored as variables.

**Step 1 — Create variables via CLI (Docker):**
```bash
docker compose run --rm airflow-cli airflow variables set environment "development"
docker compose run --rm airflow-cli airflow variables set batch_size "500"
docker compose run --rm airflow-cli airflow variables set data_folder "/opt/airflow/data"
docker compose run --rm airflow-cli airflow variables set alert_email "team@company.com"

# Verify they were created
docker compose run --rm airflow-cli airflow variables list
```

**Step 2 — Create the DAG:**

**File:** `dags/var_01_basic.py`

```python
# var_01_basic.py

from airflow.sdk import DAG, task
from airflow.models import Variable
from datetime import datetime

with DAG(
    dag_id="var_01_basic",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["variables", "beginner"],
):

    @task
    def read_variables():
        # ✅ CORRECT — read variables INSIDE task functions (not at top level)
        environment  = Variable.get("environment",  default_var="development")
        batch_size   = int(Variable.get("batch_size",  default_var="100"))
        data_folder  = Variable.get("data_folder",  default_var="/tmp/data")
        alert_email  = Variable.get("alert_email",  default_var="admin@example.com")

        print(f"🌍 Environment  : {environment}")
        print(f"📦 Batch size   : {batch_size}")
        print(f"📁 Data folder  : {data_folder}")
        print(f"📧 Alert email  : {alert_email}")

        return {"env": environment, "batch": batch_size}

    @task
    def process_data(config):
        print(f"⚙️  Processing {config['batch']} records in {config['env']} mode")
        print(f"✅ Processing complete!")

    cfg = read_variables()
    process_data(cfg)
```

### 🎯 What to Observe:
- Change `batch_size` in the UI → re-trigger the DAG → see the new value in logs
- The DAG code never changes — only the variable value changes
- `default_var` prevents errors if a variable doesn't exist yet

### ⚠️ Important Best Practice:
```python
# ❌ BAD — reads variable at parse time (runs every 30s)
batch_size = Variable.get("batch_size")   # top-level code

with DAG(...):
    @task
    def process():
        print(batch_size)   # uses value from parse time, not run time

# ✅ GOOD — reads variable only when task runs
with DAG(...):
    @task
    def process():
        batch_size = Variable.get("batch_size")   # inside task = correct
        print(batch_size)
```

---

## ✏️ Use Case 2 — JSON Variables (Store Structured Config)

**Scenario:** Store a dictionary of database settings as a single JSON variable.

**Step 1 — Create a JSON variable (Docker CLI):**
```bash
# From Docker CLI — value must be valid JSON string
docker compose run --rm airflow-cli airflow variables set db_config \
  '{"host": "db.example.com", "port": 5432, "dbname": "sales", "schema": "public"}'

docker compose run --rm airflow-cli airflow variables set pipeline_config \
  '{"retry_limit": 3, "timeout_minutes": 30, "regions": ["north", "south", "east"], "threshold": 10000}'

# Verify
docker compose run --rm airflow-cli airflow variables get db_config
```

**File:** `dags/var_02_json.py`

```python
# var_02_json.py

from airflow.sdk import DAG, task
from airflow.models import Variable
from datetime import datetime

with DAG(
    dag_id="var_02_json",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["variables", "json"],
):

    @task
    def use_json_variable():
        # deserialize_json=True converts stored JSON string into Python dict
        db_config = Variable.get("db_config", deserialize_json=True,
                                  default_var={"host": "localhost", "port": 5432})

        pipeline_config = Variable.get("pipeline_config", deserialize_json=True,
                                        default_var={"retry_limit": 3, "regions": []})

        print(f"🗄️  Database Host   : {db_config.get('host')}")
        print(f"🗄️  Database Port   : {db_config.get('port')}")
        print(f"🗄️  Database Name   : {db_config.get('dbname')}")

        print(f"🔁 Retry Limit     : {pipeline_config.get('retry_limit')}")
        print(f"⏱️  Timeout Minutes : {pipeline_config.get('timeout_minutes')}")

        # Iterate over list from JSON
        regions = pipeline_config.get("regions", [])
        print(f"🌏 Regions to process: {', '.join(regions)}")

        for region in regions:
            print(f"   → Processing region: {region}")

    use_json_variable()
```

### 🎯 What to Observe:
- Change `pipeline_config` in the UI to add a new region → re-run to see it processed
- No DAG code changes needed — just update the variable value

---

## ✏️ Use Case 3 — Jinja Template Variables (Best Practice)

**Scenario:** Pass variable values to operators using Jinja templates — this is the recommended approach as it avoids database calls at parse time.

**File:** `dags/var_03_jinja.py`

```python
# var_03_jinja.py
# Using Jinja templates to access variables — BEST PRACTICE for operators

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id="var_03_jinja",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["variables", "jinja"],
):

    # Access variable via Jinja template — only evaluated at task runtime
    t1 = BashOperator(
        task_id="print_variable_bash",
        bash_command="echo 'Running in env: {{ var.value.environment }}' && "
                     "echo 'Batch size: {{ var.value.batch_size }}'",
    )

    # Access JSON variable field via Jinja
    t2 = BashOperator(
        task_id="print_json_variable_bash",
        bash_command="echo 'Retry limit: {{ var.json.pipeline_config.retry_limit }}'",
    )

    # Access variable with default value via Jinja
    t3 = BashOperator(
        task_id="print_with_default",
        bash_command="echo 'Threshold: {{ var.value.get(\"sales_threshold\", \"5000\") }}'",
    )

    # Use variable inside Python task via context
    def use_in_python(**context):
        # Templates are rendered before task runs
        env = context["templates_dict"].get("env_var")
        print(f"Running in environment: {env}")

    t4 = PythonOperator(
        task_id="use_in_python",
        python_callable=use_in_python,
        templates_dict={"env_var": "{{ var.value.environment }}"},
    )

    t1 >> t2 >> t3 >> t4
```

### Jinja Variable Syntax Reference:

| Syntax | What It Does |
|---|---|
| `{{ var.value.my_key }}` | Get plain text value of variable `my_key` |
| `{{ var.json.my_key }}` | Get JSON variable as Python dict |
| `{{ var.json.my_key.nested_field }}` | Access nested field in JSON variable |
| `{{ var.value.get("my_key", "default") }}` | Get value with fallback default |

---

## ✏️ Use Case 4 — Environment-Specific Variables

**Scenario:** Use a naming convention to manage dev/staging/prod configurations.

**Step 1 — Create environment-specific variables (Docker CLI):**
```bash
# Development settings
docker compose run --rm airflow-cli airflow variables set dev_api_url "https://dev.api.example.com"
docker compose run --rm airflow-cli airflow variables set dev_batch_size "50"
docker compose run --rm airflow-cli airflow variables set dev_debug_mode "true"

# Production settings
docker compose run --rm airflow-cli airflow variables set prod_api_url "https://api.example.com"
docker compose run --rm airflow-cli airflow variables set prod_batch_size "1000"
docker compose run --rm airflow-cli airflow variables set prod_debug_mode "false"

# Current environment selector
docker compose run --rm airflow-cli airflow variables set current_env "dev"

# Verify all created
docker compose run --rm airflow-cli airflow variables list
```

**File:** `dags/var_04_env_config.py`

```python
# var_04_env_config.py

from airflow.sdk import DAG, task
from airflow.models import Variable
from datetime import datetime

with DAG(
    dag_id="var_04_env_config",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["variables", "environment"],
):

    @task
    def load_env_config():
        # Read which environment we're in
        current_env = Variable.get("current_env", default_var="dev")
        print(f"🌍 Current environment: {current_env}")

        # Dynamically load env-specific variables
        api_url    = Variable.get(f"{current_env}_api_url",    default_var="http://localhost")
        batch_size = Variable.get(f"{current_env}_batch_size", default_var="100")
        debug_mode = Variable.get(f"{current_env}_debug_mode", default_var="false")

        config = {
            "env"       : current_env,
            "api_url"   : api_url,
            "batch_size": int(batch_size),
            "debug"     : debug_mode.lower() == "true",
        }

        print(f"   API URL    : {config['api_url']}")
        print(f"   Batch Size : {config['batch_size']}")
        print(f"   Debug Mode : {config['debug']}")
        return config

    @task
    def run_pipeline(config):
        print(f"🚀 Running pipeline in [{config['env'].upper()}] mode")
        if config["debug"]:
            print("🐛 Debug mode ON — verbose logging enabled")
        print(f"📦 Processing {config['batch_size']} records from {config['api_url']}")
        print("✅ Pipeline complete!")

    cfg = load_env_config()
    run_pipeline(cfg)
```

### 🎯 Experiment:
```bash
# Switch to production
docker compose run --rm airflow-cli airflow variables set current_env "prod"
# Re-trigger DAG — it now uses prod_ prefixed variables automatically!

# Switch back to dev
docker compose run --rm airflow-cli airflow variables set current_env "dev"
```

---

# 🔌 Part 2 — Providers

## 🧠 What Are Providers?

**Providers** are installable packages that extend Airflow with:
- New **operators** (e.g., `S3CopyObjectOperator`, `BigQueryInsertJobOperator`)
- New **hooks** (e.g., `PostgresHook`, `HttpHook`, `SlackHook`)
- New **connection types** (e.g., `aws`, `google_cloud_platform`, `slack`)
- New **sensors** (e.g., `S3KeySensor`, `HttpSensor`)

> 💡 Without providers, Airflow can only run Python and Bash tasks. Providers unlock connections to AWS, GCP, Azure, Postgres, MySQL, Slack, HTTP APIs, and hundreds more.

### Provider Naming Convention:
```
apache-airflow-providers-{service-name}
```

| Provider Package | Connects To |
|---|---|
| `apache-airflow-providers-standard` | BashOperator, PythonOperator (built-in) |
| `apache-airflow-providers-postgres` | PostgreSQL databases |
| `apache-airflow-providers-mysql` | MySQL databases |
| `apache-airflow-providers-amazon` | AWS (S3, RDS, Lambda, SQS, etc.) |
| `apache-airflow-providers-google` | GCP (BigQuery, GCS, Pub/Sub, etc.) |
| `apache-airflow-providers-microsoft-azure` | Azure (Blob, SQL, Data Factory) |
| `apache-airflow-providers-http` | REST API calls |
| `apache-airflow-providers-slack` | Slack notifications |
| `apache-airflow-providers-email` | Email via SMTP |
| `apache-airflow-providers-fab` | Flask App Builder auth (Airflow 3) |

---

## 🛠️ Installing Providers

### Docker Compose setup (Our approach — update `Dockerfile`)

Since we use Docker-based Airflow, providers must be baked into the Docker image. You cannot just `pip install` on your laptop.

**Step 1 — Create a `Dockerfile`** in the same folder as your `docker-compose.yaml`:

```dockerfile
FROM apache/airflow:3.1.8

# Install additional providers
RUN pip install --no-cache-dir \
    apache-airflow-providers-postgres \
    apache-airflow-providers-http \
    apache-airflow-providers-amazon \
    apache-airflow-providers-slack \
    apache-airflow-providers-mysql
```

**Step 2 — Update `docker-compose.yaml`** to use your custom image:

Find this line in `docker-compose.yaml`:
```yaml
# Comment out the image line:
# image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:3.1.8}

# Uncomment the build line:
build: .
```

**Step 3 — Rebuild and restart:**
```bash
# Build the custom image
docker compose build

# Restart all services with new image
docker compose up -d

# Verify providers are installed
docker compose run --rm airflow-cli airflow providers list
```

**Step 4 — Add more providers later:**

Just add to the `Dockerfile` and rebuild:
```bash
docker compose build --no-cache
docker compose up -d
```

### Alternative — `requirements.txt` approach

**Create `requirements.txt`** in the same folder as `docker-compose.yaml`:
```
apache-airflow-providers-postgres
apache-airflow-providers-http
apache-airflow-providers-amazon
apache-airflow-providers-slack
```

**Update `Dockerfile`** to use it:
```dockerfile
FROM apache/airflow:3.1.8
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
```

Rebuild:
```bash
docker compose build
docker compose up -d
```

> ✅ **Recommended:** Use `requirements.txt` so adding providers is just one line in a file, then rebuild.

---

## ✏️ Use Case 5 — List and Explore Providers

```bash
# List all installed providers
docker compose run --rm airflow-cli airflow providers list

# Get details about a specific provider
docker compose run --rm airflow-cli airflow providers get apache-airflow-providers-http

# List all hooks from all providers
docker compose run --rm airflow-cli airflow providers hooks

# List all connection types available
docker compose run --rm airflow-cli airflow providers list --output table

# List behaviours (operators, sensors) from providers
docker compose run --rm airflow-cli airflow providers behaviours
```

Sample output of `airflow providers list`:
```
package_name                         | version | description
apache-airflow-providers-standard    | 1.4.0   | Standard operators
apache-airflow-providers-http        | 4.12.0  | HTTP operators and hooks
apache-airflow-providers-postgres    | 5.13.0  | PostgreSQL operators and hooks
apache-airflow-providers-amazon      | 9.21.0  | Amazon Web Services operators
```

---

# 🔗 Part 3 — Connections

## 🧠 What Are Connections?

Airflow **Connections** store credentials and configuration for external systems — databases, APIs, cloud services, etc.

> 💡 Never hardcode passwords, hostnames, or API keys in your DAG code. Store them as Connections and reference them by `conn_id`.

### Connection Fields:

| Field | Description |
|---|---|
| **Conn Id** | Unique identifier used in DAG code (e.g., `my_postgres_db`) |
| **Conn Type** | Type of system (Postgres, HTTP, AWS, S3, etc.) |
| **Host** | Hostname or IP of the system |
| **Schema** | Database name (for DB connections) |
| **Login** | Username |
| **Password** | Password (stored encrypted) |
| **Port** | Port number |
| **Extra** | JSON for additional connection parameters |

---

## 🛠️ Create Connections — 4 Ways

### Way 1 — Airflow UI
1. Go to `http://localhost:8080`
2. Navigate to **Admin → Connections**
3. Click the **+** button
4. Fill in all fields
5. Click **Save**

### Way 2 — CLI (Docker)

```bash
# Add a PostgreSQL connection
docker compose run --rm airflow-cli airflow connections add 'my_postgres' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-schema 'mydb' \
    --conn-login 'myuser' \
    --conn-password 'mypassword' \
    --conn-port '5432'

# Add an HTTP connection
docker compose run --rm airflow-cli airflow connections add 'my_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com' \
    --conn-port '443'

# Add connection with extra JSON params
docker compose run --rm airflow-cli airflow connections add 'my_aws' \
    --conn-type 'aws' \
    --conn-extra '{"region_name": "us-east-1"}'

# List all connections
docker compose run --rm airflow-cli airflow connections list

# Get connection details
docker compose run --rm airflow-cli airflow connections get my_postgres

# Delete a connection
docker compose run --rm airflow-cli airflow connections delete old_conn

# Export connections to JSON (saves to /opt/airflow/dags/ = your local ./dags/)
docker compose run --rm airflow-cli airflow connections export /opt/airflow/dags/connections_backup.json

# Import connections from JSON
docker compose run --rm airflow-cli airflow connections import /opt/airflow/dags/connections.json
```

### Way 3 — Environment Variable (Secure)
```bash
# Format: AIRFLOW_CONN_{UPPERCASE_CONN_ID}=connection_uri
export AIRFLOW_CONN_MY_POSTGRES='postgresql://myuser:mypassword@localhost:5432/mydb'
export AIRFLOW_CONN_MY_API='http://https%3A%2F%2Fjsonplaceholder.typicode.com'
```

> 💡 Environment variable connections are NOT visible in the UI — great for secrets in production.

### Way 4 — JSON Import File
Create `connections.json`:
```json
[
  {
    "conn_id"   : "my_postgres",
    "conn_type" : "postgres",
    "host"      : "localhost",
    "schema"    : "mydb",
    "login"     : "myuser",
    "password"  : "mypassword",
    "port"      : 5432
  },
  {
    "conn_id"   : "my_http_api",
    "conn_type" : "http",
    "host"      : "https://jsonplaceholder.typicode.com",
    "port"      : 443
  }
]
```
```bash
airflow connections import connections.json
```

---

## ✏️ Use Case 6 — HTTP Connection

**Scenario:** Call a public REST API using an HTTP connection.

**Step 1 — Create the connection (Docker CLI):**
```bash
docker compose run --rm airflow-cli airflow connections add 'jsonplaceholder_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com' \
    --conn-port '443'

# Verify it was created
docker compose run --rm airflow-cli airflow connections get jsonplaceholder_api
```

**Step 2 — Install the HTTP provider (Docker):**

Add to your `requirements.txt`:
```
apache-airflow-providers-http
```

Then rebuild:
```bash
docker compose build
docker compose up -d
```

**File:** `dags/conn_01_http.py`

```python
# conn_01_http.py

from airflow.sdk import DAG, task
from airflow.providers.http.hooks.http import HttpHook
from datetime import datetime

with DAG(
    dag_id="conn_01_http",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["connections", "http"],
):

    @task
    def fetch_users():
        # HttpHook uses the connection stored under 'jsonplaceholder_api'
        hook = HttpHook(
            method="GET",
            http_conn_id="jsonplaceholder_api",   # references stored connection
        )

        response = hook.run(endpoint="/users")    # appended to host
        users = response.json()

        print(f"✅ Fetched {len(users)} users from API")
        for user in users[:3]:
            print(f"   - {user['name']} ({user['email']})")

        return [u["name"] for u in users]

    @task
    def fetch_posts():
        hook = HttpHook(method="GET", http_conn_id="jsonplaceholder_api")
        response = hook.run(endpoint="/posts?_limit=5")
        posts = response.json()

        print(f"📄 Fetched {len(posts)} posts")
        for post in posts:
            print(f"   - [{post['id']}] {post['title'][:40]}...")

        return len(posts)

    @task
    def summarise(user_names, post_count):
        print(f"📊 Summary:")
        print(f"   Users  : {len(user_names)}")
        print(f"   Posts  : {post_count}")

    users = fetch_users()
    posts = fetch_posts()
    summarise(users, posts)
```

### 🎯 What to Observe:
- Trigger the DAG — it fetches live data from jsonplaceholder.typicode.com
- No URL, username, or password in the DAG code — only `conn_id`
- Change the host in the connection → the DAG automatically uses the new URL

---

## ✏️ Use Case 7 — PostgreSQL Connection with Hook

**Scenario:** Query a PostgreSQL database using a stored connection.

**Step 1 — Start a test Postgres container (Docker):**
```bash
# Start a test Postgres on port 5433 (different from Airflow's internal postgres on 5432)
docker run -d \
  --name airflow-test-postgres \
  --network airflow-docker_default \
  -e POSTGRES_USER=testuser \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=testdb \
  -p 5433:5432 \
  postgres:16

# Verify it's running
docker ps | grep airflow-test-postgres
```

> 💡 `--network airflow-docker_default` connects the test Postgres to the same Docker network as Airflow so containers can reach each other.

**Step 2 — Create the Airflow connection (Docker CLI):**
```bash
# Using container name as host (Docker networking)
docker compose run --rm airflow-cli airflow connections add 'my_postgres' \
    --conn-type 'postgres' \
    --conn-host 'airflow-test-postgres' \
    --conn-schema 'testdb' \
    --conn-login 'testuser' \
    --conn-password 'testpass' \
    --conn-port '5432'

# Verify
docker compose run --rm airflow-cli airflow connections get my_postgres
```

**Step 3 — Install the Postgres provider (Docker):**

Add to `requirements.txt`:
```
apache-airflow-providers-postgres
```

Rebuild:
```bash
docker compose build
docker compose up -d
```

**File:** `dags/conn_02_postgres.py`

```python
# conn_02_postgres.py

from airflow.sdk import DAG, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime

with DAG(
    dag_id="conn_02_postgres",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["connections", "postgres"],
):

    @task
    def create_table():
        # PostgresHook uses the stored connection credentials
        hook = PostgresHook(postgres_conn_id="my_postgres")

        hook.run("""
            CREATE TABLE IF NOT EXISTS sales (
                id         SERIAL PRIMARY KEY,
                product    VARCHAR(100),
                amount     NUMERIC(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Table 'sales' created (or already exists)")

    @task
    def insert_data():
        hook = PostgresHook(postgres_conn_id="my_postgres")

        records = [
            ("Laptop",  75000.00),
            ("Phone",   25000.00),
            ("Tablet",  35000.00),
            ("Monitor", 18000.00),
        ]

        hook.insert_rows(
            table="sales",
            rows=records,
            target_fields=["product", "amount"],
        )
        print(f"✅ Inserted {len(records)} records")

    @task
    def query_data():
        hook = PostgresHook(postgres_conn_id="my_postgres")

        records = hook.get_records("SELECT product, amount FROM sales ORDER BY amount DESC")

        print(f"📊 Sales Report ({len(records)} records):")
        print(f"   {'Product':<15} {'Amount':>12}")
        print(f"   {'-'*15} {'-'*12}")
        for product, amount in records:
            print(f"   {product:<15} ₹{amount:>10,.2f}")

        total = sum(r[1] for r in records)
        print(f"   {'TOTAL':<15} ₹{total:>10,.2f}")

    create_table() >> insert_data() >> query_data()
```

### 🎯 What to Observe:
- No connection string anywhere in the DAG code — only `conn_id="my_postgres"`
- Change the password in the connection → code still works without any DAG changes
- Hooks handle connection pooling, retries, and credential management automatically

---

## ✏️ Use Case 8 — Connection via Environment Variable

**Scenario:** Store a connection securely without it being visible in the Airflow UI.

**Step 1 — Set in `docker-compose.yaml` (recommended for Docker):**

Open your `docker-compose.yaml` and find the `x-airflow-common` environment section. Add your connection environment variables:

```yaml
x-airflow-common:
  &airflow-common
  environment:
    &airflow-common-env
    AIRFLOW__CORE__EXECUTOR: CeleryExecutor
    # ... other existing env vars ...

    # Add your connections here:
    AIRFLOW_CONN_SECURE_API: 'http://https%3A%2F%2Fsecure.api.example.com'
    AIRFLOW_CONN_PROD_POSTGRES: 'postgresql://produser:prodpass@prod-db.example.com:5432/proddb'
```

Then restart:
```bash
docker compose down
docker compose up -d
```

**Step 2 — Or use a `.env` file (cleaner approach):**

Create a `.env` file in the same folder as `docker-compose.yaml`:
```bash
# .env file
AIRFLOW_CONN_SECURE_API=http://https%3A%2F%2Fsecure.api.example.com
AIRFLOW_CONN_PROD_POSTGRES=postgresql://produser:prodpass@prod-db.example.com:5432/proddb
```

Reference it in `docker-compose.yaml`:
```yaml
env_file:
  - .env
```

> ⚠️ Add `.env` to your `.gitignore` so credentials are never committed to version control!

```bash
echo ".env" >> .gitignore
```

**File:** `dags/conn_03_env_var.py`

```python
# conn_03_env_var.py

from airflow.sdk import DAG, task
from airflow.providers.http.hooks.http import HttpHook
from datetime import datetime

with DAG(
    dag_id="conn_03_env_var",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["connections", "env-var"],
):

    @task
    def call_secure_api():
        # This uses AIRFLOW_CONN_SECURE_API from environment
        # Note: env-var connections don't appear in Airflow UI
        hook = HttpHook(method="GET", http_conn_id="secure_api")
        print("🔒 Using connection from environment variable (not visible in UI)")
        print("✅ Connection loaded securely from environment")

    call_secure_api()
```

### Connection URI Format:
```
{conn_type}://{login}:{password}@{host}:{port}/{schema}?{extra_params}

# Examples:
postgresql://myuser:mypassword@localhost:5432/mydb
http://apiuser:apikey@api.example.com:443
mysql://root:password@db.example.com:3306/myschema
```

---

## ✏️ Use Case 9 — Using Connections in Jinja Templates

**Scenario:** Access connection fields directly inside Jinja templates without writing Python.

**File:** `dags/conn_04_jinja.py`

```python
# conn_04_jinja.py

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime

with DAG(
    dag_id="conn_04_jinja",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["connections", "jinja"],
):

    # Access connection fields directly in Jinja templates
    t1 = BashOperator(
        task_id="print_conn_host",
        bash_command="echo 'API Host: {{ conn.jsonplaceholder_api.host }}'",
    )

    t2 = BashOperator(
        task_id="print_conn_login",
        bash_command="echo 'DB Login: {{ conn.my_postgres.login }}'",
    )

    t3 = BashOperator(
        task_id="print_conn_schema",
        bash_command="echo 'DB Schema: {{ conn.my_postgres.schema }}'",
    )

    # Access extra JSON fields from connection
    t4 = BashOperator(
        task_id="print_conn_extra",
        bash_command="echo 'Region: {{ conn.my_aws.extra_dejson.region_name }}'",
    )

    t1 >> t2 >> t3 >> t4
```

### Jinja Connection Syntax Reference:

| Template | What It Returns |
|---|---|
| `{{ conn.my_conn.host }}` | Hostname |
| `{{ conn.my_conn.login }}` | Username |
| `{{ conn.my_conn.password }}` | Password |
| `{{ conn.my_conn.port }}` | Port number |
| `{{ conn.my_conn.schema }}` | Schema/database name |
| `{{ conn.my_conn.extra_dejson.key }}` | Field from Extra JSON |

---

# 🏗️ Part 4 — Putting It All Together

## ✏️ Use Case 10 — Full Pipeline using Variables + Connections

**Scenario:** A complete sales report pipeline that uses:
- Variables for config settings
- A Postgres connection for data
- An HTTP connection to post results to an API

**Step 1 — Set up variables (Docker CLI):**
```bash
docker compose run --rm airflow-cli airflow variables set report_title "Daily Sales Report"
docker compose run --rm airflow-cli airflow variables set sales_threshold "10000"
docker compose run --rm airflow-cli airflow variables set report_recipients "manager@company.com,ceo@company.com"
docker compose run --rm airflow-cli airflow variables set max_records "100"

# Verify
docker compose run --rm airflow-cli airflow variables list
```

**Step 2 — Set up connections (Docker CLI):**
```bash
# Postgres for sales data
docker compose run --rm airflow-cli airflow connections add 'sales_db' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-schema 'salesdb' \
    --conn-login 'salesuser' \
    --conn-password 'salespass' \
    --conn-port '5432'

# HTTP for report API
docker compose run --rm airflow-cli airflow connections add 'report_api' \
    --conn-type 'http' \
    --conn-host 'https://jsonplaceholder.typicode.com'

# Verify both connections
docker compose run --rm airflow-cli airflow connections list
```

**File:** `dags/full_pipeline_vars_conns.py`

```python
# full_pipeline_vars_conns.py
# Full pipeline combining Variables + Connections + Providers

from airflow.sdk import DAG, task
from airflow.models import Variable
from airflow.providers.http.hooks.http import HttpHook
from datetime import datetime

with DAG(
    dag_id="full_pipeline_vars_conns",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["variables", "connections", "full-pipeline"],
):

    @task
    def load_config():
        """Load all configuration from Variables."""
        config = {
            "title"      : Variable.get("report_title",      default_var="Daily Report"),
            "threshold"  : float(Variable.get("sales_threshold",  default_var="5000")),
            "recipients" : Variable.get("report_recipients",  default_var="admin@example.com"),
            "max_records": int(Variable.get("max_records",    default_var="50")),
        }
        print(f"⚙️  Config loaded:")
        for k, v in config.items():
            print(f"   {k}: {v}")
        return config

    @task
    def extract_sales(config):
        """Simulate fetching sales from DB using stored Connection."""
        print(f"🗄️  Connecting to sales_db (credentials from Airflow Connection)")
        print(f"   Fetching up to {config['max_records']} records...")

        # Simulated data (in real world: use PostgresHook)
        sales = [
            {"id": 1, "product": "Laptop",  "amount": 75000, "region": "South"},
            {"id": 2, "product": "Phone",   "amount": 25000, "region": "North"},
            {"id": 3, "product": "Tablet",  "amount": 35000, "region": "East"},
            {"id": 4, "product": "Monitor", "amount": 8000,  "region": "West"},
        ]

        print(f"✅ Extracted {len(sales)} sales records")
        return sales

    @task
    def analyse_sales(sales, config):
        """Analyse sales data using threshold from Variables."""
        threshold = config["threshold"]
        total     = sum(s["amount"] for s in sales)
        above     = [s for s in sales if s["amount"] >= threshold]
        below     = [s for s in sales if s["amount"] <  threshold]

        analysis = {
            "total_revenue" : total,
            "record_count"  : len(sales),
            "above_threshold": len(above),
            "below_threshold": len(below),
            "status"        : "GOOD" if total >= threshold * 2 else "NEEDS_ATTENTION",
        }

        print(f"📊 Sales Analysis (threshold: ₹{threshold:,.0f}):")
        print(f"   Total Revenue   : ₹{total:,.2f}")
        print(f"   Above Threshold : {len(above)}")
        print(f"   Below Threshold : {len(below)}")
        print(f"   Status          : {analysis['status']}")
        return analysis

    @task
    def post_report(analysis, config):
        """Post report via HTTP Connection."""
        hook = HttpHook(method="POST", http_conn_id="report_api")

        payload = {
            "title"     : config["title"],
            "status"    : analysis["status"],
            "total"     : analysis["total_revenue"],
            "recipients": config["recipients"].split(","),
        }

        print(f"📤 Posting report to API (using 'report_api' connection)...")
        print(f"   Title  : {payload['title']}")
        print(f"   Status : {payload['status']}")

        # In real world this posts to the API
        # response = hook.run(endpoint="/posts", data=json.dumps(payload))
        print(f"✅ Report posted to: {config['recipients']}")

    cfg    = load_config()
    sales  = extract_sales(cfg)
    result = analyse_sales(sales, cfg)
    post_report(result, cfg)
```

### Flow:
```
load_config (reads Variables)
    │
    ▼
extract_sales (uses sales_db Connection)
    │
    ▼
analyse_sales (uses threshold from Variable)
    │
    ▼
post_report (uses report_api Connection)
```

---

## 💻 CLI Quick Reference

> All commands below are for **Docker-based Airflow**. If you set up the shell alias (`alias airflow='docker compose run --rm airflow-cli airflow'`) you can drop the `docker compose run --rm airflow-cli` prefix.

### Variables:
```bash
# Set / update
docker compose run --rm airflow-cli airflow variables set   <key> <value>

# Read
docker compose run --rm airflow-cli airflow variables get   <key>

# List all
docker compose run --rm airflow-cli airflow variables list

# Delete
docker compose run --rm airflow-cli airflow variables delete <key>

# Export to file (goes to /opt/airflow/dags/ = your local ./dags/)
docker compose run --rm airflow-cli airflow variables export /opt/airflow/dags/backup.json

# Import from file (place file in ./dags/ first)
docker compose run --rm airflow-cli airflow variables import /opt/airflow/dags/variables.json
```

### Connections:
```bash
# Create
docker compose run --rm airflow-cli airflow connections add <conn_id> \
  --conn-type <type> --conn-host <host> --conn-login <user> \
  --conn-password <pass> --conn-port <port> --conn-schema <db>

# Read
docker compose run --rm airflow-cli airflow connections get    <conn_id>

# List all
docker compose run --rm airflow-cli airflow connections list

# Delete
docker compose run --rm airflow-cli airflow connections delete <conn_id>

# Export (goes to /opt/airflow/dags/ = your local ./dags/)
docker compose run --rm airflow-cli airflow connections export /opt/airflow/dags/conns.json

# Import
docker compose run --rm airflow-cli airflow connections import /opt/airflow/dags/conns.json
```

### Providers:
```bash
# List all installed providers
docker compose run --rm airflow-cli airflow providers list

# Get provider details
docker compose run --rm airflow-cli airflow providers get <package-name>

# List all available hooks
docker compose run --rm airflow-cli airflow providers hooks
```

### Other useful Docker commands:
```bash
# Enter container for interactive session (run many commands)
docker exec -it airflow-docker-airflow-scheduler-1 bash

# View real-time logs
docker logs airflow-docker-airflow-scheduler-1 -f

# Restart a single service
docker compose restart airflow-scheduler

# Rebuild custom image (after adding providers to Dockerfile)
docker compose build
docker compose up -d

# Full reset (removes all data — use carefully)
docker compose down --volumes --rmi all
docker compose up airflow-init
docker compose up -d
```

---

## ⚠️ Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Running `airflow` directly on laptop | `command not found: airflow` | Use `docker compose run --rm airflow-cli airflow <cmd>` or set alias |
| Running `docker compose` from wrong folder | `no configuration file provided` | Always `cd` into the folder with `docker-compose.yaml` first |
| Provider added to `requirements.txt` but image not rebuilt | `ModuleNotFoundError` inside container | Run `docker compose build --no-cache` then `docker compose up -d` |
| `Variable.get()` at top-level DAG code | Slow parsing, stale values | Move inside `@task` or use Jinja `{{ var.value.key }}` |
| Hardcoding passwords in DAG code | Security risk, hard to rotate | Always use Connections |
| `Variable.get("key")` without `default_var` | `KeyError` if variable missing | Always add `default_var="fallback"` |
| Using wrong `conn_id` in Hook | `AirflowNotFoundException` | Check exact spelling under Admin → Connections |
| JSON variable without `deserialize_json=True` | Gets string instead of dict | Add `deserialize_json=True` to `Variable.get()` |
| Postgres connection host set to `localhost` in Docker | `connection refused` | Use Docker **container name** as host (e.g. `airflow-test-postgres`) |
| Exporting to wrong path in Docker | File not appearing locally | Export to `/opt/airflow/dags/` which maps to your local `./dags/` |
| Env var connection not visible in UI | Looks missing | Expected — env var connections are runtime-only, hidden from UI by design |
| Env var connection name wrong format | `AirflowNotFoundException` | Format: `AIRFLOW_CONN_{UPPERCASE_CONN_ID}` with underscores |
| Storing secrets in Variables | Plain text visible in UI | Use Connections (encrypted) or a Secrets Backend instead |

---

## 📦 All DAG Files Summary

| # | File | Key Concepts |
|---|---|---|
| 1 | `var_01_basic.py` | `Variable.get()`, `default_var`, inside task |
| 2 | `var_02_json.py` | `deserialize_json=True`, nested JSON access |
| 3 | `var_03_jinja.py` | `{{ var.value.key }}`, `{{ var.json.key.field }}` |
| 4 | `var_04_env_config.py` | Dynamic env-prefix variable naming pattern |
| 5 | `conn_01_http.py` | `HttpHook`, calling REST APIs |
| 6 | `conn_02_postgres.py` | `PostgresHook`, DB create/insert/query |
| 7 | `conn_03_env_var.py` | `AIRFLOW_CONN_*` environment variable connections |
| 8 | `conn_04_jinja.py` | `{{ conn.my_conn.host }}` in templates |
| 9 | `full_pipeline_vars_conns.py` | End-to-end — Variables + Connections + Providers |

---

## ✅ Trainee Practice Checklist

### Level 1 — Docker CLI Setup
- [ ] Run `docker ps` and confirm all Airflow containers are running
- [ ] Run `docker compose run --rm airflow-cli airflow version` — confirm output is `3.1.8`
- [ ] Set up the shell alias: `alias airflow='docker compose run --rm airflow-cli airflow'`
- [ ] Run `airflow providers list` using the alias — confirm it works
- [ ] Enter the scheduler container with `docker exec -it <scheduler-name> bash` and run `airflow dags list`

### Level 2 — Variables Basics
- [ ] Create 5 variables via the UI (Admin → Variables)
- [ ] Create variables via Docker CLI: `docker compose run --rm airflow-cli airflow variables set key "value"`
- [ ] Create `var_01_basic.py` and trigger it
- [ ] Change `batch_size` in the UI → re-trigger → see the new value in logs
- [ ] Export all variables: `docker compose run --rm airflow-cli airflow variables export /opt/airflow/dags/backup.json`
- [ ] Confirm the backup JSON file appears in your local `./dags/` folder

### Level 3 — JSON & Jinja Variables
- [ ] Create a JSON variable `db_config` via Docker CLI
- [ ] Create a JSON variable `pipeline_config` via Docker CLI
- [ ] Create `var_02_json.py` — verify nested JSON fields are printed correctly
- [ ] Create `var_03_jinja.py` — verify Jinja templates work inside BashOperator
- [ ] Add a new region to `pipeline_config` JSON in UI → re-trigger and observe the new region printed

### Level 4 — Environment Config Pattern
- [ ] Create all `dev_*` and `prod_*` prefixed variables via Docker CLI (Use Case 4)
- [ ] Verify all variables are visible in UI under Admin → Variables
- [ ] Switch `current_env` from `dev` to `prod` in the UI
- [ ] Re-trigger `var_04_env_config.py` — confirm prod values are used in logs
- [ ] Switch back to `dev` and verify pipeline uses dev values again

### Level 5 — Providers & Connections
- [ ] Add `apache-airflow-providers-http` to `requirements.txt`
- [ ] Run `docker compose build` then `docker compose up -d`
- [ ] Run `docker compose run --rm airflow-cli airflow providers list` — confirm HTTP provider appears
- [ ] Create HTTP connection `jsonplaceholder_api` via Docker CLI
- [ ] Verify connection in UI under Admin → Connections
- [ ] Create `conn_01_http.py` and trigger it — see live API data in logs
- [ ] Update the host in the connection UI → re-run and verify the new URL is used

### Level 6 — Database Connections
- [ ] Start the test Postgres container with the Docker run command from Use Case 7
- [ ] Add `apache-airflow-providers-postgres` to `requirements.txt` and rebuild Docker image
- [ ] Create the `my_postgres` connection via Docker CLI
- [ ] Create `conn_02_postgres.py` — run all 3 tasks (create table, insert, query)
- [ ] Add a connection via `.env` file and `docker-compose.yaml` — confirm DAG uses it

### Level 7 — Full Pipeline
- [ ] Set up all variables from Use Case 10 via Docker CLI
- [ ] Set up all connections from Use Case 10 via Docker CLI
- [ ] Create `full_pipeline_vars_conns.py` and trigger it end-to-end
- [ ] Change `sales_threshold` → re-trigger → observe different analysis output
- [ ] Add a new variable `report_format` and use it in the `post_report` task
- [ ] Export all variables and connections as JSON backup files

---

## 🔗 Useful Resources

- 📖 [Airflow Variables Docs](https://airflow.apache.org/docs/apache-airflow/stable/howto/variable.html)
- 📖 [Airflow Connections Docs](https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html)
- 📖 [Airflow Providers Docs](https://airflow.apache.org/docs/apache-airflow-providers/)
- 📖 [Jinja Templates Reference](https://airflow.apache.org/docs/apache-airflow/stable/templates-ref.html)
- 📖 [All Provider Connections](https://airflow.apache.org/docs/apache-airflow-providers/core-extensions/connections.html)
- 🔗 [DAG Creation Guide](./airflow_dag_guide.md)
- 🔗 [DAG Branching Guide](./airflow_dag_branching_guide.md)
- 🔗 [Assets Guide](./airflow_assets_guide.md)

---

> 🙌 **Key Rules to Remember:**
>
> 0. **Docker CLI** = always use `docker compose run --rm airflow-cli airflow <cmd>` or set the alias — never run `airflow` directly on your laptop
> 1. **Variables** = config values that change between environments → use `Variable.get()` inside tasks, never at top level
> 2. **Connections** = credentials for external systems → never hardcode passwords in DAGs
> 3. **Providers** = add to `requirements.txt` → rebuild with `docker compose build` → restart with `docker compose up -d`
> 4. **Hooks** = the bridge between your task code and a Connection → always prefer Hooks over raw connections
> 5. **Jinja templates** = the best way to pass Variables/Connections to operators → evaluated only at runtime, not at parse time
