# Norwegian Public Transport Analytics

An end-to-end analytics project that collects open Entur departure-board data
and examines expected public-transport delays at five monitored Oslo stops.
It demonstrates a local batch pipeline from recurring API snapshots through
PySpark and PostgreSQL to an interactive Streamlit dashboard.

## Business problem

Passengers and transport planners need a simple way to see where and when
expected delays are concentrated. This project asks:

- How large are expected departure delays across transport modes and monitored
  stops?
- Which local departure hours show higher expected delays?
- Which lines have an elevated share of estimates more than three minutes late?
- How much data supports each result?

The dashboard is an exploratory operational view of a small convenience sample.
It is not a system for assessing contractual performance or publishing official
punctuality statistics.

## Key findings

The recorded sample covers **3–8 September 2026: 20,222 unique departure
estimates, five monitored stops and 84 lines**. Here, a departure is counted
once per monitored stop. Results below come from [the analytical SQL](sql/business_analysis.sql).

| Mode | Estimates (n) | Mean expected delay | Median | Over 3 minutes |
| --- | ---: | ---: | ---: | ---: |
| Bus | 8,996 | 135.9 sec | 90 sec | 26.3% |
| Tram | 2,643 | 117.7 sec | 90 sec | 23.7% |
| Metro | 5,399 | 103.4 sec | 69 sec | 17.0% |
| Rail | 3,181 | 44.6 sec | 0 sec | 6.9% |

- **Bus showed the highest expected delays** among modes with meaningful sample
  sizes; rail estimates were substantially lower. Coach has only three estimates
  and is excluded from meaningful comparisons.
- **Hourly mean estimates were highest at 16:00 and 17:00**: 163.1 seconds
  (n=1,481) and 151.1 seconds (n=1,691), respectively, in Oslo local time.
- **Jernbanetorget had the highest mean among the five monitored stops**:
  142.3 seconds, with 28.4% over three minutes (n=6,067).
- **Individual lines varied considerably**: bus 54 had 55.0% of estimates over
  three minutes (n=262), and bus 81 had 49.7% (n=680).

These are descriptive associations from a short convenience sample, using
expected times rather than verified final departures. Stops and hours have
different mixes of modes and lines; these comparisons do not establish causes
or rank the whole Oslo network.

## Dashboard preview

![Oslo Public Transport Reliability dashboard](dokumenter/bilder/dashboard-overview.png)

The interactive dashboard provides filters for date, stop, transport mode and line, together with overview metrics and comparisons of expected departure delays.

## Architecture and data pipeline

```text
Entur APIs → Python collection → local raw JSON
          → PySpark ETL → Parquet partitioned by service_date
          → PostgreSQL staging → dimensions + observation fact
          → latest-estimate SQL view → Streamlit + Plotly / analytical SQL
```

1. **Collect:** the Geocoder REST client helps identify stops. The Journey
   Planner GraphQL client requests 20 upcoming calls per stop; the Python runner
   repeats collection every five minutes for the five configured Oslo stops.
   Timestamped JSON preserves the source responses locally.
2. **Transform:** PySpark flattens nested calls, parses timestamps, derives delay
   and local date/hour, filters incomplete departure keys/times, and removes
   duplicate observations. Parquet provides a rebuildable intermediate dataset.
3. **Load:** Python streams Parquet rows into PostgreSQL staging. SQL upserts
   date, stop, quay and line dimensions, then the departure-observation fact.
4. **Analyse:** a SQL view selects each departure's latest estimate. Dashboard
   queries filter this view; Pandas calculates chart summaries and Plotly renders
   them in Streamlit.

**Why PostgreSQL?** It keeps observation history in relational tables, enforces
keys and relationships, and gives the dashboard and standalone SQL a shared
analytical definition. The dimensions describe when, where and which service;
the fact table stores the observations and delay measures.

Python handles collection and loading; PySpark handles batch transformation;
PostgreSQL and SQL handle storage and the analytical grain; Pandas, Streamlit
and Plotly handle exploration. Pytest and Ruff support repeatable checks. This
is a local learning project: its modest data volume does not require a Spark
cluster, and no distributed infrastructure is used.

## Warehouse grain and repeated observations

`analytics.fact_departure_observation` has one row per collected estimate for
one service journey, at one monitored stop, for one aimed departure time. Its
natural uniqueness is:

```text
collected_at_utc + stop + service_journey_id + aimed_departure_utc
```

Because collection runs every five minutes, the fact table can contain many
estimates of the same logical departure. Treating them as independent departures
would over-weight services that remained on the board through more collection
cycles.

`analytics.v_latest_departure_estimate` corrects this analytical issue. It
partitions observations by stop, service journey, and aimed departure time,
then retains the row with the newest `collected_at_utc`. Its grain is therefore
one latest collected estimate per logical departure at each monitored stop.
The dashboard queries this view exclusively. In the recorded sample, 34,000
warehouse observations become 20,222 latest departure estimates.

## Run locally

Prerequisites:

- Python 3.11 or 3.12
- a Java runtime compatible with the installed PySpark version
- PostgreSQL and the `psql` client

Create the environment and install the project:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
```

Run all commands from the repository root. Edit `.env` with your Entur client
identifier and PostgreSQL settings. The file is git-ignored. `POSTGRES_PASSWORD`
can remain empty when local PostgreSQL authentication does not require one.

Create the database separately, then initialize its schema once. Substitute
your configured host, port, user, and database if they differ:

```bash
createdb -h localhost -p 5432 -U your_local_postgres_user transport_analytics
psql -h localhost -p 5432 -U your_local_postgres_user \
  -d transport_analytics -f sql/create_schema.sql
```

### Collect and refresh data

Collect one snapshot for all configured stops:

```bash
.venv/bin/python -m transport_analytics.ingestion.collection_runner
```

For recurring five-minute collection, run this in a dedicated terminal and stop
it with Control+C:

```bash
.venv/bin/python -m transport_analytics.ingestion.collection_runner \
  --repeat --interval-seconds 300
```

After snapshots exist and the database schema is initialized, this is the
single pipeline-refresh command:

```bash
.venv/bin/refresh-transport-pipeline
```

It runs, in order:

1. raw JSON to partitioned Parquet PySpark ETL;
2. Parquet to PostgreSQL staging and dimensional warehouse loading;
3. creation or replacement of the analytical views.

Progress is logged stage by stage. A failure stops subsequent stages and names
the failed stage. The ETL intentionally overwrites only the generated processed
Parquet output; it does not delete raw snapshots or the database.

An optional processed-data quality report is available after ETL:

```bash
.venv/bin/python -m transport_analytics.processing.data_quality
```

### Run the dashboard

With PostgreSQL running and the warehouse refreshed:

```bash
.venv/bin/streamlit run dashboard/app.py
```

New collections produce different results from the recorded September sample.
Raw JSON and generated Parquet are git-ignored and are not included in the repo.
If the database or view is unavailable, the dashboard shows setup guidance.

## Data quality approach

- Raw responses are written atomically using a temporary file and preserved
  locally for reproducibility.
- PySpark reads an explicit nested schema, converts timestamps in UTC, derives
  service date/hour from the expected time in `Europe/Oslo`, and filters rows
  missing stop/service-journey IDs or aimed/expected departure times.
- Duplicate rows within the same collected snapshot are removed using the
  collection time and departure identifiers.
- PostgreSQL dimensions use stable Entur IDs, fact loading is idempotent at the
  observation grain, and foreign keys protect dimensional consistency.
- The processed-data quality report surfaces missing journey IDs/timestamps,
  negative delays, absolute delays over two hours, realtime coverage and summary
  statistics. It is not a count of raw rows rejected before transformation.
- Analytical queries use only the latest estimate for a logical departure and
  display sample sizes alongside results. Transport-mode comparisons and line
  rankings require at least 30 observations per group.

## Methodology and limitations

**Expected delay = expected departure time − aimed departure time.** Positive
values indicate expected lateness; negative values indicate expected early
departure. “Over three minutes” means strictly greater than 180 seconds.
`actual_departure_utc` is not used as a substitute for this measure.

Dates and hours are derived from **expected departure time in Europe/Oslo**.
The field called `service_date` is this local calendar date, not an operator's
operating-day definition. Hourly means pool estimates across the sampled dates.

- **Coverage:** six calendar dates at five selected stops do not represent all
  Oslo services or complete service days. Collection gaps and the limit of 20
  upcoming calls per snapshot affect which departures are captured.
- **Interpretation:** stop and hourly comparisons partly reflect differences in
  the services operating there. They are descriptive, not causal.
- **Outcomes:** departures may disappear before a final estimate is collected;
  cancelled, rerouted or missing calls may be absent. The latest available
  estimate is not a verified actual departure or an official punctuality measure.
- **Realtime coverage:** calls without realtime information can have expected
  time equal to aimed time, increasing the apparent share of zero delays.
- **Uncertainty:** small groups produce volatile averages and percentages. The
  30-estimate comparison floor is a practical guardrail, not a statistical
  significance test. Extreme and negative estimates are retained, not clipped.

## Testing and checks

External Entur calls and database behavior are mocked or isolated in unit tests;
unit tests do not require live Entur access. The PySpark transformation test
does require a working local Java/PySpark setup.

Run the full project checks from the repository root:

```bash
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/python -c "import dashboard.app"
```

The dashboard import is a safe smoke test: rendering and PostgreSQL access happen
only when Streamlit executes `main()`.

## Repository structure

```text
dashboard/app.py                         Streamlit application
data/raw/                                Local JSON snapshots (ignored)
data/processed/                          Local partitioned Parquet (ignored)
data/samples/                            Reserved for safe public samples
sql/create_schema.sql                    PostgreSQL staging/star schema
sql/load_warehouse.sql                   Dimension and fact upserts
sql/create_analytics_views.sql           Latest-estimate view
sql/business_analysis.sql                Reusable analytical queries
src/transport_analytics/ingestion/       Entur clients and collection runner
src/transport_analytics/processing/      PySpark schema, ETL, quality report
src/transport_analytics/database/        Connections, loading, view creation
src/transport_analytics/analysis/        Dashboard query and metric logic
src/transport_analytics/pipeline_refresh.py  Refresh orchestration
tests/                                   Unit and PySpark transformation tests
```

No raw or processed dataset is committed. Entur data is open, but the local
collection is intentionally kept out of version control to keep the portfolio
repository small and to avoid publishing an uncontrolled snapshot archive.

## Possible future extensions

Collect a longer period with more even coverage, compare stops within the same
mode or line, and examine how estimates change before a departure. These would
address the current analytical limitations before adding more tooling.
