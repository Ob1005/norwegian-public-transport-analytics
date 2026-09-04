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

## Architecture

```text
Entur Geocoder + Journey Planner APIs
                |
                v
Recurring Python collection (five-minute JSON snapshots)
                |
                v
data/raw/departures/                    [local, git-ignored]
                |
                v
PySpark validation, flattening, features, and de-duplication
                |
                v
Partitioned Parquet by service_date     [local, git-ignored]
                |
                v
PostgreSQL staging -> dimensions + observation fact
                |
                v
analytics.v_latest_departure_estimate
                |
                v
Streamlit + Plotly dashboard / analytical SQL
```

The pipeline keeps immutable API responses as the local source layer, produces
rebuildable Parquet, and loads a dimensional warehouse. Versioned SQL creates
the latest-estimate semantic view used by every dashboard result.

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
The dashboard queries this view exclusively.

## Setup

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

Edit `.env` with a local Entur client identifier and PostgreSQL settings. The
file is git-ignored. Never commit it. `POSTGRES_PASSWORD` can remain empty when
the local PostgreSQL authentication configuration does not require a password.

Create the database separately, then initialize its schema once. Substitute
your configured host, port, user, and database if they differ:

```bash
psql -h localhost -p 5432 -U your_local_postgres_user \
  -d transport_analytics -f sql/create_schema.sql
```

## Collect and refresh data

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

## Run the dashboard

With PostgreSQL running and the warehouse refreshed:

```bash
.venv/bin/streamlit run dashboard/app.py
```

The dashboard provides overview KPIs; service-date, stop, mode, and line
filters; expected delay by mode, stop, and local expected-departure hour; and a
ranking of lines with elevated delay rates. Transport-mode comparisons and line
rankings require at least 30 matching observations. Modes below the threshold
are omitted from the comparison and listed beside the chart. Every chart's
hover labels expose its group observation count.

The application deliberately fails with setup guidance when PostgreSQL or the
latest-estimate view is unavailable. It does not silently mix production query
results with sample data.

## Data quality approach

- Raw responses are written atomically using a temporary file and preserved
  locally for reproducibility.
- PySpark reads an explicit nested schema, converts timestamps in UTC, derives
  service date/hour from the expected time in `Europe/Oslo`, and filters rows
  missing identifiers or aimed/expected departure times.
- Duplicate rows within the same collected snapshot are removed using the
  collection time and departure identifiers.
- PostgreSQL dimensions use stable Entur IDs, fact loading is idempotent at the
  observation grain, and foreign keys protect dimensional consistency.
- The quality report surfaces missing keys/timestamps, negative delays, delays
  over two hours, realtime coverage, and core distribution statistics.
- Analytical queries use only the latest estimate for a logical departure and
  display sample sizes alongside results. Transport-mode comparisons and line
  rankings require at least 30 observations per group.

## Method and preliminary limitations

Delay is defined as `expected_departure_utc - aimed_departure_utc`. A positive
value means the departure was expected late when last observed; a negative value
means it was expected early. `actual_departure_utc` is often unavailable and is
not substituted for a final observed outcome.

Important limitations:

- Five selected Oslo hubs are a convenience sample, not a representative sample
  of Oslo or Norwegian public transport.
- The collection window is short and may omit nights, weekends, seasons, and
  disruption periods.
- A departure can disappear from the API before a final estimate is collected;
  cancellations, rerouting, and missing calls can therefore create selection
  bias.
- Calls without realtime information can have expected time equal to aimed time,
  which can increase the apparent share of zero-delay estimates.
- Latest-estimate de-duplication removes repeated-snapshot weighting, but the
  latest available estimate is not guaranteed to be the final estimate.
- Small groups produce volatile averages and percentages; the dashboard warns
  about small filtered samples and applies a minimum to mode comparisons and
  line rankings.
- Extreme or negative estimates are retained for transparency and surfaced by
  the quality checks rather than silently clipped.

### Estimates are not official punctuality statistics

The source fields are scheduled and expected departure times returned by Entur's
Journey Planner at collection time. The resulting metrics describe **expected
departure estimates** in this project's snapshots. They are not verified actual
departures, do not follow an operator or regulator's complete-service rules, and
must not be presented as official punctuality statistics.

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

## Possible future extensions

Longer collection periods, broader geographic coverage, orchestrated scheduling,
deployment, and carefully evaluated predictive modelling are intentionally out
of this MVP. They should be considered only after coverage and outcome quality
support them.
