import re
import csv
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
import plotly.graph_objects as go
import plotly.express as px

# CONFIG
st.set_page_config(layout="wide")

# DATA SOURCE: FILE UPLOAD
st.sidebar.title("Data Upload")

uploaded_file = st.sidebar.file_uploader(
    "Upload exported data file (CSV / MySQL export)",
    type=["csv"]
)

if uploaded_file is None:
    st.warning("Please upload a file to continue")
    st.stop()


@st.cache_data
def load_data(file):

    df = pd.read_csv(
        file,
        sep=",",
        engine="python",
        quotechar='"',
        escapechar="\\",
        on_bad_lines="skip"
    )

    # Clean column names
    df.columns = df.columns.str.strip()

    # Validate required column
    if "occurred_at" not in df.columns:
        st.error(f"'occurred_at' column not found.\nColumns detected: {list(df.columns)}")
        st.stop()

    df["occurred_at"] = (
        df["occurred_at"]
        .astype(str)
        .str.strip()
        .str.replace('"', '', regex=False)
    )

    df["occurred_at"] = pd.to_datetime(
        df["occurred_at"],
        errors="coerce"
    )

    # Drop invalid rows
    df = df.dropna(subset=["occurred_at"])

    # Optional cleanup (safe)
    for col in ["user_id", "session_id", "journey_id"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df

# LOAD DATA
df = load_data(uploaded_file)

# SIDEBAR FILTERS
st.sidebar.title("Filters")

time_filter = st.sidebar.selectbox(
    "Select Time Range",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Custom"],
)

now = pd.Timestamp.utcnow().tz_localize(None)

if time_filter == "Last 24 Hours":
    start_date = now - timedelta(days=1)
    end_date = now
elif time_filter == "Last 7 Days":
    start_date = now - timedelta(days=7)
    end_date = now
elif time_filter == "Last 30 Days":
    start_date = now - timedelta(days=30)
    end_date = now
else:
    start_date = st.sidebar.date_input("Start Date", now - timedelta(days=7))
    end_date = st.sidebar.date_input("End Date", now)
    start_date = datetime.combine(start_date, datetime.min.time())
    end_date = datetime.combine(end_date, datetime.max.time())

df = df[
    (df["occurred_at"] >= start_date) &
    (df["occurred_at"] <= end_date)
]

if df.empty:
    st.warning("No data available for selected range")
    st.write("Min date:", df["occurred_at"].min())
    st.write("Max date:", df["occurred_at"].max())
    st.write("Now:", now)
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Users", df["user_id"].nunique())
col2.metric("Sessions", df["session_id"].nunique())
col3.metric("Journeys", df["journey_id"].nunique())

user_options = ["All Users"] + sorted(df["user_id"].dropna().unique().tolist())
selected_user = st.selectbox("Select User", user_options)

if selected_user != "All Users":
    df = df[df["user_id"] == selected_user]

# FLOW TYPE
flow_type = st.radio(
    "Flow Type",
    ["Pages", "Events"],
    horizontal=True
)

df = df.sort_values(by=["journey_id", "occurred_at"])

if flow_type == "Pages":
    df["node"] = df["page_id"]
else:
    df["node"] = df["event_name"]


# ─────────────────────────────────────────────────────────────
# PLOT 1: User FLOW
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 1: User Flow")

df_plot2 = df.copy()
df_plot2 = df_plot2.sort_values(["journey_id", "occurred_at"])

df_plot2["step"] = df_plot2.groupby("journey_id").cumcount()

df_plot2["prev_node"] = df_plot2.groupby("journey_id")["node"].shift(1)
df_plot2["next_node"] = df_plot2.groupby("journey_id")["node"].shift(-1)

df_plot2["next_time"] = df_plot2.groupby("journey_id")["occurred_at"].shift(-1)
df_plot2["page_time"] = (
    df_plot2["next_time"] - df_plot2["occurred_at"]
).dt.total_seconds().fillna(0).round(2)

df_nodes = df_plot2[df_plot2["node"] != df_plot2["prev_node"]].copy()
df_nodes["node_step"] = df_nodes.groupby("journey_id").cumcount()

df_nodes["prev_time"] = df_nodes.groupby("journey_id")["occurred_at"].shift(1)
df_nodes["time_diff_sec"] = (
    df_nodes["occurred_at"] - df_nodes["prev_time"]
).dt.total_seconds().fillna(0).round(2)

unique_journeys = df_nodes["journey_id"].unique()
colors = px.colors.qualitative.Set2

color_map = {
    jid: colors[i % len(colors)]
    for i, jid in enumerate(unique_journeys)
}

node_order = df_nodes["node"].unique().tolist()
node_to_num = {node: i for i, node in enumerate(node_order)}

jitter_map = {
    jid: (i - len(unique_journeys)/2) * 0.08
    for i, jid in enumerate(unique_journeys)
}

fig_plot2 = go.Figure()

for i, jid in enumerate(unique_journeys):
    d = df_nodes[df_nodes["journey_id"] == jid]

    y_vals = [
        node_to_num[node] + jitter_map[jid]
        for node in d["node"]
    ]

    fig_plot2.add_trace(go.Scatter(
        x=d["node_step"],
        y=y_vals,
        mode="lines+markers",
        name=str(jid),
        line=dict(color=color_map[jid], width=2),
        marker=dict(size=8, color=color_map[jid]),
        hovertext=[
            f"Journey: {jid}"
            f"<br>Step: {step}"
            f"<br>Node: {node}"
            f"<br>Next: {next_node if pd.notna(next_node) else 'END'}"
            f"<br>Time on Page: {page_time}s"
            for node, step, next_node, page_time in zip(
                d["node"],
                d["node_step"],
                d["next_node"],
                d["page_time"]
            )
        ],
        hoverinfo="text"
    ))

fig_plot2.update_layout(
    template="plotly_dark",
    plot_bgcolor="#0e1117",
    paper_bgcolor="#0e1117",
    font=dict(color="white"),
    legend_title="journey_id",
    yaxis=dict(
        tickmode="array",
        tickvals=list(range(len(node_order))),
        ticktext=node_order
    )
)

st.plotly_chart(fig_plot2, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# Plot 2: Steps/Events per Page
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 2: Steps/Events per Page")

col1, col2 = st.columns(2)

with col1:
    selected_node = st.selectbox(
        "Select Page / Event",
        sorted(df["node"].dropna().unique())
    )

with col2:
    top_n = st.slider("Limit journeys", 5, 50, 15)

if selected_node:
    df_plot3 = df[df["node"] == selected_node].copy()
    df_plot3 = df_plot3.sort_values(["journey_id", "occurred_at"])

    df_plot3["step"] = df_plot3.groupby("journey_id").cumcount()

    top_journeys = (
        df_plot3["journey_id"]
        .value_counts()
        .head(top_n)
        .index
    )

    df_plot3 = df_plot3[df_plot3["journey_id"].isin(top_journeys)]

    if flow_type == "Pages":
        df_plot3["drill_node"] = df_plot3["event_name"]
        y_label = "Events"
    else:
        df_plot3["drill_node"] = df_plot3["page_id"]
        y_label = "Pages"

    drill_order = df_plot3["drill_node"].unique().tolist()
    drill_to_num = {node: i for i, node in enumerate(drill_order)}

    journeys = df_plot3["journey_id"].unique()

    jitter_map = {
        jid: (i - len(journeys)/2) * 0.08
        for i, jid in enumerate(journeys)
    }

    fig_plot3 = go.Figure()

    for i, jid in enumerate(journeys):
        d = df_plot3[df_plot3["journey_id"] == jid]

        y_vals = [
            drill_to_num[node] + jitter_map[jid]
            for node in d["drill_node"]
        ]

        fig_plot3.add_trace(go.Scatter(
            x=d["step"],
            y=y_vals,
            mode="lines+markers",
            name=str(jid),
            line=dict(width=2),
            marker=dict(size=8),
            hovertext=[
                f"Journey: {jid}<br>Step: {s}<br>{y_label[:-1]}: {node}"
                for s, node in zip(d["step"], d["drill_node"])
            ],
            hoverinfo="text"
        ))

    fig_plot3.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(drill_order))),
            ticktext=drill_order,
            title=y_label
        ),
        title=f"Steps inside: {selected_node}"
    )

    st.plotly_chart(fig_plot3, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# PLOT 3: AGGREGATED FLOW
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 3: Aggregated User Flow Diagram")

# Compute source -> target relationships
df_sankey = df_nodes.dropna(subset=['prev_node', 'node']).copy()

if not df_sankey.empty:
    links = df_sankey.groupby(['prev_node', 'node']).size().reset_index(name='value')
    
    all_nodes_sankey = list(pd.unique(links[['prev_node', 'node']].values.ravel('K')))
    node_mapping = {n: i for i, n in enumerate(all_nodes_sankey)}
    
    links['source'] = links['prev_node'].map(node_mapping)
    links['target'] = links['node'].map(node_mapping)
    
    fig_sankey = go.Figure(data=[go.Sankey(
        node = dict(
          pad = 15,
          thickness = 20,
          line = dict(color = "black", width = 0.5),
          label = all_nodes_sankey,
          color = "#636EFA"
        ),
        link = dict(
          source = links['source'],
          target = links['target'],
          value = links['value']
        )
    )])
    
    fig_sankey.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white")
    )
    st.plotly_chart(fig_sankey, use_container_width=True)
else:
    st.info("Not enough data transitions to generate Sankey diagram.")


# ─────────────────────────────────────────────────────────────
# PLOT 4: USER JOURNEY FLOW (FINAL CLEAN VERSION)
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 4: User Journey Flow")

# Step index
df["step"] = df.groupby("journey_id").cumcount()
df = df.sort_values(["journey_id", "occurred_at"])

# Time between steps
df["prev_time"] = df.groupby("journey_id")["occurred_at"].shift(1)

df["time_diff_sec"] = (
    (df["occurred_at"] - df["prev_time"])
    .dt.total_seconds()
).fillna(0).round(2)

custom_cols = [
    "journey_id",
    "event_name",
    "page_id",
    "time_diff_sec"
]

fig1 = px.line(
    df,
    x="step",
    y="node",              # page or event based on toggle
    color="journey_id",
    markers=True,
    custom_data=df[custom_cols]
)

if flow_type == "Pages":
    fig1.update_traces(
        hovertemplate=
        "<b>Journey:</b> %{customdata[0]}<br>" +
        "<b>Step:</b> %{x}<br>" +
        "<b>Page:</b> %{y}<br>" +                 # y = page
        "<b>Event:</b> %{customdata[1]}<br>" +
        "<b>Time since last step:</b> %{customdata[3]} sec<br>" +
        "<extra></extra>"
    )
else:
    fig1.update_traces(
        hovertemplate=
        "<b>Journey:</b> %{customdata[0]}<br>" +
        "<b>Step:</b> %{x}<br>" +
        "<b>Event:</b> %{y}<br>" +                # y = event
        "<b>Page:</b> %{customdata[2]}<br>" +
        "<b>Time since last step:</b> %{customdata[3]} sec<br>" +
        "<extra></extra>"
    )

fig1.update_layout(
    template="plotly_dark",
    yaxis_title="Page" if flow_type == "Pages" else "Event"
)

st.plotly_chart(fig1, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# PLOT 5: CORE CONVERSION FUNNEL
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 5: Funnel (All Pages)")

df_funnel = df.copy()
df_funnel = df_funnel.sort_values(["journey_id", "occurred_at"])

df_funnel["node_order"] = df_funnel.groupby("journey_id").cumcount()
df_unique = df_funnel.drop_duplicates(subset=["journey_id", "node"])

# preserve order like Plot 1 (first appearance in data)
node_order_plot1 = df["node"].dropna().unique().tolist()

funnel_counts = (
    df_unique.groupby("node")["journey_id"]
    .nunique()
    .reindex(node_order_plot1)
    .reset_index()
    .rename(columns={"journey_id": "users"})
)

# remove nodes with no data
funnel_counts = funnel_counts.dropna(subset=["users"])

colors = px.colors.qualitative.Set2
color_list = [colors[i % len(colors)] for i in range(len(funnel_counts))]

if not funnel_counts.empty:
    fig_funnel_all = go.Figure(go.Funnel(
        y=funnel_counts["node"],
        x=funnel_counts["users"],
        textinfo="value+percent initial",
        marker=dict(color=color_list)
    ))

    fig_funnel_all.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white")
    )

    st.plotly_chart(fig_funnel_all, use_container_width=True)
else:
    st.info("No data available for funnel.")


# ─────────────────────────────────────────────────────────────
# PLOT 6: REVISIT ANALYSIS
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 6: Revisit Analysis")

df_revisit = df.copy()
df_revisit = df_revisit.sort_values(["user_id", "occurred_at"])

user_sessions = (
    df_revisit.groupby("user_id")["session_id"]
    .nunique()
    .reset_index(name="session_count")
)

user_sessions["user_type"] = user_sessions["session_count"].apply(
    lambda x: "New" if x == 1 else "Returning"
)

col1, col2 = st.columns(2)

with col1:
    st.metric("Returning Users", (user_sessions["user_type"] == "Returning").sum())

with col2:
    st.metric("New Users", (user_sessions["user_type"] == "New").sum())

journey_paths = (
    df_revisit.groupby("journey_id")["node"]
    .apply(lambda x: " → ".join(x))
    .reset_index(name="path")
)

path_counts = (
    journey_paths["path"]
    .value_counts()
    .reset_index()
)

path_counts.columns = ["path", "count"]

repeat_paths = path_counts[path_counts["count"] > 1]

st.markdown("### 🔁 Repeated Journeys")

if not repeat_paths.empty:
    st.dataframe(repeat_paths.head(10), use_container_width=True)
else:
    st.info("No repeated journeys found.")

df_sessions = (
    df.groupby(["user_id", "session_id"])["occurred_at"]
    .min()
    .reset_index()
    .sort_values(["user_id", "occurred_at"])
)

df_sessions["prev_session_time"] = (
    df_sessions.groupby("user_id")["occurred_at"].shift(1)
)

df_sessions["revisit_gap_hours"] = (
    (df_sessions["occurred_at"] - df_sessions["prev_session_time"])
    .dt.total_seconds() / 3600
)

gap_df = df_sessions.dropna(subset=["revisit_gap_hours"])

if not gap_df.empty:
    fig_gap = px.histogram(
        gap_df,
        x="revisit_gap_hours",
        nbins=30,
        title="Revisit Time Between Sessions (hours)"
    )

    fig_gap.update_layout(template="plotly_dark")

    st.plotly_chart(fig_gap, use_container_width=True)
else:
    st.info("Not enough data for revisit timing.")