import logging

import plotly.express as px
import streamlit as st
from psycopg import Error as PsycopgError

from transport_analytics.analysis.dashboard_data import (
    DELAY_THRESHOLD_SECONDS,
    MINIMUM_GROUP_SAMPLE,
    DashboardFilters,
    calculate_overview,
    elevated_delay_lines,
    load_departures,
    load_filter_options,
    partition_sample_groups,
    summarize_delays,
)
from transport_analytics.database.connection import get_database_connection

LOGGER = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def cached_filter_options():
    """Cache warehouse filter metadata briefly across Streamlit reruns."""
    with get_database_connection() as connection:
        return load_filter_options(connection)


@st.cache_data(ttl=300, show_spinner="Loading latest departure estimates…")
def cached_departures(filters: DashboardFilters):
    """Cache one parameterized dashboard query briefly."""
    with get_database_connection() as connection:
        return load_departures(connection, filters)


def format_line_option(
    public_code: str | None,
    line_name: str | None,
    transport_mode: str,
) -> str:
    """Build a readable label without relying on codes being present."""
    identity = public_code or line_name or "Unnamed line"
    if public_code and line_name and line_name != public_code:
        identity = f"{public_code} — {line_name}"
    return f"{identity} ({transport_mode.title()})"


def add_sample_hover(figure) -> None:
    """Keep group sample size visible in Plotly hover labels."""
    figure.update_traces(
        hovertemplate=(
            "%{x}<br>Average expected delay: %{y:.1f} min"
            "<br>Observations: %{customdata[0]:,}<extra></extra>"
        )
    )


def main() -> None:
    """Render the PostgreSQL-backed portfolio dashboard."""
    st.set_page_config(
        page_title="Oslo Public Transport Reliability",
        page_icon="🚉",
        layout="wide",
    )
    st.title("Oslo public transport reliability")
    st.caption(
        "Expected departure delays at five monitored stops, based on Entur "
        "departure-board snapshots. These are estimates, not official "
        "punctuality statistics."
    )

    try:
        options = cached_filter_options()
    except (PsycopgError, ValueError):
        LOGGER.exception("Dashboard filter metadata query failed")
        st.error(
            "The dashboard could not read the PostgreSQL warehouse. Check the "
            "database settings, initialize the schema, and refresh the pipeline."
        )
        st.caption("See the terminal log for technical details.")
        st.stop()

    st.sidebar.header("Filters")
    selected_dates = st.sidebar.date_input(
        "Service date",
        value=(options.minimum_date, options.maximum_date),
        min_value=options.minimum_date,
        max_value=options.maximum_date,
    )
    if len(selected_dates) != 2:
        st.info("Select both a start and end date to display the dashboard.")
        st.stop()

    stop_labels = dict(options.stops)
    selected_stops = st.sidebar.multiselect(
        "Monitored stops",
        options=[stop_key for stop_key, _ in options.stops],
        format_func=lambda stop_key: stop_labels[stop_key],
        placeholder="All monitored stops",
    )
    selected_modes = st.sidebar.multiselect(
        "Transport modes",
        options=list(options.transport_modes),
        format_func=str.title,
        placeholder="All modes",
    )
    line_labels = {
        line_key: format_line_option(public_code, name, mode)
        for line_key, public_code, name, mode in options.lines
    }
    selected_lines = st.sidebar.multiselect(
        "Lines",
        options=list(line_labels),
        format_func=lambda line_key: line_labels[line_key],
        placeholder="All lines",
    )

    filters = DashboardFilters(
        start_date=selected_dates[0],
        end_date=selected_dates[1],
        stop_keys=tuple(selected_stops),
        transport_modes=tuple(selected_modes),
        line_keys=tuple(selected_lines),
    )

    try:
        departures = cached_departures(filters)
    except (PsycopgError, ValueError):
        LOGGER.exception("Dashboard departure query failed")
        st.error("The filtered departure query failed.")
        st.caption("See the terminal log for technical details.")
        st.stop()

    if departures.empty:
        st.warning("No departure estimates match the selected filters.")
        st.stop()

    overview = calculate_overview(departures)
    metrics = st.columns(5)
    metrics[0].metric("Departure estimates", f"{overview['departures']:,}")
    metrics[1].metric(
        "Average expected delay",
        f"{overview['average_delay_seconds'] / 60:.1f} min",
    )
    metrics[2].metric(
        "Over 3 minutes",
        f"{overview['percent_over_threshold']:.1f}%",
    )
    metrics[3].metric("Monitored stops", f"{overview['stops']:,}")
    metrics[4].metric("Lines", f"{overview['lines']:,}")

    if len(departures) < MINIMUM_GROUP_SAMPLE:
        st.warning(
            f"Only {len(departures)} latest departure estimates match these "
            "filters. Treat averages and rates as unstable."
        )
    else:
        st.info(
            "Every row is the latest collected estimate for one scheduled "
            "departure at one monitored stop. Hover charts to inspect group "
            "sample sizes; small groups can be volatile."
        )

    mode_summary = summarize_delays(departures, ["transport_mode"])
    mode_summary, insufficient_modes = partition_sample_groups(mode_summary)
    mode_summary["average_delay_minutes"] = (
        mode_summary["average_delay_seconds"] / 60
    )

    stop_summary = summarize_delays(departures, ["stop_name"])
    stop_summary["average_delay_minutes"] = (
        stop_summary["average_delay_seconds"] / 60
    )
    stop_figure = px.bar(
        stop_summary.sort_values("average_delay_minutes", ascending=False),
        x="stop_name",
        y="average_delay_minutes",
        custom_data=["departures"],
        labels={
            "stop_name": "Monitored stop",
            "average_delay_minutes": "Average expected delay (minutes)",
        },
        title="Expected delay by monitored stop",
    )
    add_sample_hover(stop_figure)

    first_chart, second_chart = st.columns(2)
    first_chart.caption(
        f"Only modes with at least {MINIMUM_GROUP_SAMPLE} observations within "
        "the current filters are compared."
    )
    if not insufficient_modes.empty:
        excluded_modes = ", ".join(
            f"{row.transport_mode.title()} (n={row.departures:,})"
            for row in insufficient_modes.itertuples()
        )
        first_chart.caption(f"Insufficient data, omitted: {excluded_modes}.")

    if mode_summary.empty:
        first_chart.warning(
            "No transport mode meets the minimum sample size for comparison."
        )
    else:
        mode_figure = px.bar(
            mode_summary.sort_values("average_delay_minutes", ascending=False),
            x="transport_mode",
            y="average_delay_minutes",
            custom_data=["departures"],
            labels={
                "transport_mode": "Transport mode",
                "average_delay_minutes": "Average expected delay (minutes)",
            },
            title="Expected delay by transport mode",
        )
        add_sample_hover(mode_figure)
        first_chart.plotly_chart(mode_figure, width="stretch")
    second_chart.plotly_chart(stop_figure, width="stretch")

    hour_summary = summarize_delays(departures, ["departure_hour"])
    hour_summary["average_delay_minutes"] = (
        hour_summary["average_delay_seconds"] / 60
    )
    hour_figure = px.line(
        hour_summary.sort_values("departure_hour"),
        x="departure_hour",
        y="average_delay_minutes",
        markers=True,
        custom_data=["departures"],
        labels={
            "departure_hour": "Local expected departure hour",
            "average_delay_minutes": "Average expected delay (minutes)",
        },
        title="Expected delay by local expected-departure hour",
    )
    add_sample_hover(hour_figure)
    hour_figure.update_xaxes(dtick=1)
    st.plotly_chart(hour_figure, width="stretch")

    st.subheader("Lines with elevated expected-delay rates")
    line_summary = elevated_delay_lines(departures)
    st.caption(
        f"Ranked by the share of estimates over "
        f"{DELAY_THRESHOLD_SECONDS // 60} minutes late. Lines need at least "
        f"{MINIMUM_GROUP_SAMPLE} estimates within the current filters."
    )
    if line_summary.empty:
        st.warning(
            "No line meets the minimum sample size for the current filters."
        )
    else:
        line_summary["line_label"] = line_summary.apply(
            lambda row: format_line_option(
                row["line_public_code"],
                row["line_name"],
                row["transport_mode"],
            ),
            axis=1,
        )
        line_figure = px.bar(
            line_summary.sort_values("percent_over_threshold"),
            x="percent_over_threshold",
            y="line_label",
            orientation="h",
            custom_data=["departures", "average_delay_seconds"],
            labels={
                "line_label": "Line",
                "percent_over_threshold": "Estimates over 3 minutes (%)",
            },
            title="Highest elevated-delay rates",
        )
        line_figure.update_traces(
            hovertemplate=(
                "%{y}<br>Over 3 minutes: %{x:.1f}%"
                "<br>Observations: %{customdata[0]:,}"
                "<br>Average expected delay: %{customdata[1]:.0f} sec"
                "<extra></extra>"
            )
        )
        st.plotly_chart(line_figure, width="stretch")

    with st.expander("Methodology and limitations", expanded=True):
        st.markdown(
            """
- The dashboard queries `analytics.v_latest_departure_estimate`, not the raw
  observation fact table. Repeated five-minute snapshots of the same service
  journey, aimed time, and stop therefore count once.
- Delay is `expected departure time - aimed departure time`. It is an evolving
  operational estimate and can be negative when an early departure is expected.
- Calls without realtime information can have expected time equal to aimed time,
  which can increase the apparent share of zero-delay estimates.
- This is a convenience sample from five selected Oslo stops and a short
  collection window. It is not representative of Norway, Oslo, an operator,
  or a complete service day.
- Missing, cancelled, rerouted, or no-longer-returned departures may be absent.
  The latest collected estimate is not necessarily the final outcome.
- Entur estimates are not official observed arrival/departure measurements.
  Do not present these charts as official punctuality statistics.
            """
        )


if __name__ == "__main__":
    main()
