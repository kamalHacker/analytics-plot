import re
import csv
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

# CONFIG
st.set_page_config(layout="wide")

# DATA SOURCE: FILE UPLOAD
st.sidebar.title("Data Upload")

uploaded_file = st.sidebar.file_uploader(
    "Upload Analytics Events CSV",
    type=["csv"],
    key="analytics_csv"
)

uploaded_auth_file = st.sidebar.file_uploader(
    "Upload Auth Events CSV (Optional)",
    type=["csv"],
    key="auth_csv"
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

# LOAD AUTH EVENTS FILE
if uploaded_auth_file is not None:

    df_auth = load_data(uploaded_auth_file)

else:

    df_auth = pd.DataFrame()
    
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
    if not df_auth.empty and "user_id" in df_auth.columns:
        df_auth = df_auth[df_auth["user_id"] == selected_user].copy()


# Canonical page nomenclature used across all plots.
page_name_map = {
    "landing_page": "Login_page",
    "personalize_page": "Options_page",
    "options_page": "Options_page",
    "freestyle_page": "Search_page",
    "guided_page": "Search_page",
    "recommendation_page": "Recommendation_page",
    "product_detail_page": "FitDetail_page",
    "studio_rendering_page": "StudioRender_page",
    "compare_page": "Compare_page",
    "tryon_page": "VTO_page",
    "cart_page": "Cart_page",
    "checkout_page": "Checkout_page",
    "conversational_discovery_page": "ChatBot_page",
}

df["page_label"] = df["page_id"].map(page_name_map).fillna(df["page_id"])

# Exclude conversational chatbot page from analysis plots.
df = df[df["page_label"] != "ChatBot_page"].copy()

# FLOW TYPE (INLINE RADIO)
flow_type = st.radio(
    "Flow Type",
    ["Pages", "Events"],
    horizontal=True
)

df = df.sort_values(by=["journey_id", "occurred_at"])

if flow_type == "Pages":
    df["node"] = df["page_label"]
else:
    df["node"] = df["event_name"]


def normalize_event_key(event_name: str) -> str:
    if pd.isna(event_name):
        return ""
    return (
        str(event_name)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def get_page_prefix(page_label: str) -> str:
    if pd.isna(page_label) or not str(page_label).strip():
        return "Page"
    return str(page_label).split("_")[0]

STANDARD_FLOW_BY_PAGE = {

    "Options_page": [
        {
            "event": "Options_categorycard_button",
            "type": "neutral",
        },
    ],

    "Search_page": [

        {
            "event": "Search_switchguided_button",
            "type": "neutral",
        },

        {
            "event": "Search_switchfreestyle_button",
            "type": "neutral",
        },

        {
            "event": "Search_categorypanel_toggle",
            "type": "neutral",
        },

        {
            "event": "Search_suggestionpanel_toggle",
            "type": "neutral",
        },

        {
            "event": "Search_suggestion_button",
            "type": "neutral",
        },

        {
            "event": "Search_input_typed",
            "type": "positive",
        },

        {
            "event": "Search_keyword_typed",
            "type": "positive",
        },

        {
            "event": "Search_image_attached",
            "type": "positive",
        },

        {
            "event": "Search_audio_recording_started",
            "type": "positive",
        },

        {
            "event": "Search_audio_recording_stopped",
            "type": "neutral",
        },

        {
            "event": "Search_productfilter_selected",
            "type": "positive",
        },

        {
            "event": "Search_lifestylefilter_selected",
            "type": "positive",
        },

        {
            "event": "Search_inspirationfilter_selected",
            "type": "positive",
        },

        {
            "event": "Search_budget_set",
            "type": "positive",
        },

        {
            "event": "Search_search_submit",
            "type": "positive",
        },

        {
            "event": "Search_image_removed",
            "type": "negative",
        },

        {
            "event": "Search_audio_removed",
            "type": "negative",
        },

        {
            "event": "Search_productfilter_deselected",
            "type": "negative",
        },

        {
            "event": "Search_lifestylefilter_deselected",
            "type": "negative",
        },

        {
            "event": "Search_inspirationfilter_deselected",
            "type": "negative",
        },

        {
            "event": "Search_budget_cleared",
            "type": "negative",
        },

        {
            "event": "Search_tag_removed",
            "type": "negative",
        },
    ],

    "Recommendation_page": [

        {
            "event": "Recommendation_search_complete",
            "type": "positive",
        },

        {
            "event": "Recommendation_pagechange_button",
            "type": "neutral",
        },

        {
            "event": "Recommendation_producttype_toggle",
            "type": "neutral",
        },

        {
            "event": "Recommendation_budget_toggle",
            "type": "neutral",
        },

        {
            "event": "Recommendation_relatedproduct_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_fitdetails_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_trycompare_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_trycompare_toggle",
            "type": "positive",
        },

        {
            "event": "Recommendation_addtocart_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_cart_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_gotocart_button",
            "type": "positive",
        },

        {
            "event": "Recommendation_searchagain_button",
            "type": "neutral",
        },

        {
            "event": "Recommendation_search_error",
            "type": "negative",
        },
    ],

    "FitDetail_page": [

        {
            "event": "FitDetail_asp_loaded",
            "type": "positive",
        },

        {
            "event": "FitDetail_relateddrawer_toggle",
            "type": "neutral",
        },

        {
            "event": "FitDetail_360view_button",
            "type": "positive",
        },

        {
            "event": "FitDetail_relatedproduct_button",
            "type": "positive",
        },

        {
            "event": "FitDetail_trycompare_toggle",
            "type": "positive",
        },

        {
            "event": "FitDetail_addtocart_button",
            "type": "positive",
        },

        {
            "event": "FitDetail_gotocart_button",
            "type": "positive",
        },

        {
            "event": "FitDetail_back_button",
            "type": "neutral",
        },

        {
            "event": "FitDetail_asp_error",
            "type": "negative",
        },
    ],

    "StudioRender_page": [

        {
            "event": "StudioRender_images_upload",
            "type": "positive",
        },

        {
            "event": "StudioRender_generate_started",
            "type": "neutral",
        },

        {
            "event": "StudioRender_generate_completed",
            "type": "positive",
        },

        {
            "event": "StudioRender_back_button",
            "type": "neutral",
        },

        {
            "event": "StudioRender_generate_error",
            "type": "negative",
        },
    ],

    "Compare_page": [

        {
            "event": "Compare_tryon_button",
            "type": "positive",
        },

        {
            "event": "Compare_addtocart_button",
            "type": "positive",
        },

        {
            "event": "Compare_gotocart_button",
            "type": "positive",
        },

        {
            "event": "Compare_back_button",
            "type": "neutral",
        },

        {
            "event": "Compare_item_removed",
            "type": "negative",
        },
    ],

    "VTO_page": [

        {
            "event": "VTO_camera_opened",
            "type": "neutral",
        },

        {
            "event": "VTO_photo_uploaded",
            "type": "positive",
        },

        {
            "event": "VTO_generation_started",
            "type": "neutral",
        },

        {
            "event": "VTO_generation_completed",
            "type": "positive",
        },

        {
            "event": "VTO_cacheresult_loaded",
            "type": "positive",
        },

        {
            "event": "VTO_addtocart_button",
            "type": "positive",
        },

        {
            "event": "VTO_gotocart_button",
            "type": "positive",
        },

        {
            "event": "VTO_back_button",
            "type": "neutral",
        },

        {
            "event": "VTO_camera_error",
            "type": "negative",
        },

        {
            "event": "VTO_camera_cancelled",
            "type": "negative",
        },

        {
            "event": "VTO_generation_error",
            "type": "negative",
        },
    ],

    "Cart_page": [

        {
            "event": "Cart_checkout_button",
            "type": "positive",
        },

        {
            "event": "Cart_back_button",
            "type": "neutral",
        },

        {
            "event": "Cart_item_removed",
            "type": "negative",
        },

        {
            "event": "Cart_clear_button",
            "type": "negative",
        },
    ],

    "Checkout_page": [

        {
            "event": "Checkout_charity_toggle",
            "type": "neutral",
        },

        {
            "event": "Checkout_payment_attempt",
            "type": "positive",
        },

        {
            "event": "Checkout_back_button",
            "type": "neutral",
        },
    ],
}


STANDARD_EVENT_TIMELINE = {

    "Search_page": [

        ("Search_switchguided_button", 0),

        ("Search_categorypanel_toggle", 2),

        ("Search_input_typed", 5),

        ("Search_keyword_typed", 8),

        ("Search_productfilter_selected", 12),

        ("Search_lifestylefilter_selected", 16),

        ("Search_budget_set", 20),

        ("Search_search_submit", 26),
    ],

    "Recommendation_page": [

        ("Recommendation_search_complete", 0),

        ("Recommendation_pagechange_button", 5),

        ("Recommendation_producttype_toggle", 9),

        ("Recommendation_budget_toggle", 13),

        ("Recommendation_relatedproduct_button", 18),

        ("Recommendation_fitdetails_button", 24),

        ("Recommendation_trycompare_button", 30),

        ("Recommendation_trycompare_toggle", 33),

        ("Recommendation_addtocart_button", 40),

        ("Recommendation_gotocart_button", 45),
    ],

    "FitDetail_page": [

        ("FitDetail_asp_loaded", 0),

        ("FitDetail_relateddrawer_toggle", 4),

        ("FitDetail_360view_button", 10),

        ("FitDetail_relatedproduct_button", 16),

        ("FitDetail_trycompare_toggle", 22),

        ("FitDetail_addtocart_button", 30),

        ("FitDetail_gotocart_button", 36),
    ],

    "StudioRender_page": [

        ("StudioRender_images_upload", 0),

        ("StudioRender_generate_started", 6),

        ("StudioRender_generate_completed", 30),
    ],

    "Compare_page": [

        ("Compare_tryon_button", 0),

        ("Compare_addtocart_button", 8),

        ("Compare_gotocart_button", 14),
    ],

    "VTO_page": [

        ("VTO_camera_opened", 0),

        ("VTO_photo_uploaded", 6),

        ("VTO_generation_started", 12),

        ("VTO_generation_completed", 35),

        ("VTO_cacheresult_loaded", 38),

        ("VTO_addtocart_button", 48),

        ("VTO_gotocart_button", 54),
    ],

    "Cart_page": [

        ("Cart_checkout_button", 0),
    ],

    "Checkout_page": [

        ("Checkout_charity_toggle", 4),

        ("Checkout_payment_attempt", 12),
    ],
}

STANDARD_PAGE_FLOW = [
    # "Login_page",
    "Options_page",
    "Search_page",
    "Recommendation_page",
    "FitDetail_page",
    "StudioRender_page",
    "Compare_page",
    "VTO_page",
    "Cart_page",
    "Checkout_page",
]


# ─────────────────────────────────────────────────────────────
# PLOT 1: USER FLOW
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 1: User Flow")

df_plot1 = df.copy()
df_plot1 = df_plot1.sort_values(["journey_id", "occurred_at"])

df_plot1["step"] = df_plot1.groupby("journey_id").cumcount()

df_plot1["prev_node"] = df_plot1.groupby("journey_id")["node"].shift(1)
df_plot1["next_node"] = df_plot1.groupby("journey_id")["node"].shift(-1)

df_plot1["next_time"] = df_plot1.groupby("journey_id")["occurred_at"].shift(-1)
df_plot1["page_time"] = (
    df_plot1["next_time"] - df_plot1["occurred_at"]
).dt.total_seconds().fillna(0).round(2)

df_plot1_nodes = df_plot1[df_plot1["node"] != df_plot1["prev_node"]].copy()
df_plot1_nodes["node_step"] = df_plot1_nodes.groupby("journey_id").cumcount()

df_plot1_nodes["prev_time"] = df_plot1_nodes.groupby("journey_id")["occurred_at"].shift(1)
df_plot1_nodes["time_diff_sec"] = (
    df_plot1_nodes["occurred_at"] - df_plot1_nodes["prev_time"]
).dt.total_seconds().fillna(0).round(2)
df_plot1_nodes["journey_start_time"] = df_plot1_nodes.groupby("journey_id")["occurred_at"].transform("min")
df_plot1_nodes["elapsed_sec"] = (
    df_plot1_nodes["occurred_at"] - df_plot1_nodes["journey_start_time"]
).dt.total_seconds().fillna(0).round(2)

def first_non_null(series):
    s = series.dropna()
    return s.iloc[0] if len(s) > 0 else pd.NA

journey_bounds = (
    df_plot1_nodes.groupby("journey_id", as_index=False)
    .agg(
        journey_user_id=("user_id", first_non_null),
        journey_start_time=("occurred_at", "min"),
        journey_end_time=("occurred_at", "max"),
    )
)

unique_journeys = df_plot1_nodes["journey_id"].unique()
colors = px.colors.qualitative.Set2

def format_user_label(v):
    if pd.isna(v):
        return "Guest"
    return f"User {int(v)}" if str(v).isdigit() else f"User {v}"

journey_user_map = (
    df_plot1_nodes.groupby("journey_id")["user_id"]
    .first()
    .to_dict()
)
user_label_map = {jid: format_user_label(uid) for jid, uid in journey_user_map.items()}
unique_user_labels = list(dict.fromkeys([user_label_map.get(jid, "Guest") for jid in unique_journeys]))
user_color_map = {
    ulabel: colors[i % len(colors)]
    for i, ulabel in enumerate(unique_user_labels)
}

node_order = df_plot1_nodes["node"].unique().tolist()
if flow_type == "Pages":
    node_order = STANDARD_PAGE_FLOW.copy()
node_to_num = {node: i for i, node in enumerate(node_order)}

jitter_map = {
    jid: (i - len(unique_journeys)/2) * 0.08
    for i, jid in enumerate(unique_journeys)
}

fig_plot1 = go.Figure()
seen_user_legend = set()

for i, jid in enumerate(unique_journeys):
    d = df_plot1_nodes[df_plot1_nodes["journey_id"] == jid]
    if flow_type == "Pages":
        d = d[d["node"].isin(STANDARD_PAGE_FLOW)].copy()
        if d.empty:
            continue
    user_label = user_label_map.get(jid, "Guest")
    show_user_legend = user_label not in seen_user_legend
    seen_user_legend.add(user_label)

    y_vals = [
        node_to_num[node] + jitter_map[jid]
        for node in d["node"]
    ]

    fig_plot1.add_trace(go.Scatter(
        x=d["elapsed_sec"],
        y=y_vals,
        mode="lines+markers",
        name=user_label,
        legendgroup=user_label,
        showlegend=show_user_legend,
        line=dict(color=user_color_map[user_label], width=2),
        marker=dict(size=8, color=user_color_map[user_label]),
        hovertext=[
            f"Journey: {jid}"
            f"<br>User: {user_label}"
            f"<br>Session: {sid if pd.notna(sid) else 'NA'}"
            f"<br>Elapsed: {elapsed}s"
            f"<br>Time: {time}"
            f"<br>Node: {node}"
            f"<br>Next: {next_node if pd.notna(next_node) else 'END'}"
            f"<br>Time on Page: {page_time}s"
            for node, sid, elapsed, time, next_node, page_time in zip(
                d["node"],
                d["session_id"] if "session_id" in d.columns else pd.Series([None] * len(d)),
                d["elapsed_sec"],
                d["occurred_at"],
                d["next_node"],
                d["page_time"]
            )
        ],
        hoverinfo="text"
    ))

# STANDARD JOURNEY OVERLAY WITH IDEAL TIME FLOW
if flow_type == "Pages":

    standard_journey = [
        ("Options_page", 0),

        # Options -> Search (2s)
        ("Search_page", 2),

        # Search -> Recommendation (12s)
        ("Recommendation_page", 14),

        # Recommendation -> Fit Detail (25s)
        ("FitDetail_page", 39),

        # Fit Detail -> Studio Render (20s)
        ("StudioRender_page", 59),

        # Studio Render -> Fit Detail (2s back)
        ("FitDetail_page", 61),

        # Fit Detail -> Recommendation (2s back)
        ("Recommendation_page", 63),

        # Recommendation -> Compare (4s)
        ("Compare_page", 67),

        # Compare -> VTO (8s)
        ("VTO_page", 75),

        # VTO -> Cart (20s)
        ("Cart_page", 95),

        # Cart -> Checkout (5s)
        ("Checkout_page", 100),
    ]

    standard_x = [x[1] for x in standard_journey]

    standard_y = [
        node_to_num[x[0]]
        for x in standard_journey
        if x[0] in node_to_num
    ]

    fig_plot1.add_trace(go.Scatter(
        x=standard_x,
        y=standard_y,
        mode="lines+markers",
        name="Standard Journey",
        line=dict(
            color="yellow",
            width=5,
            dash="dash"
        ),
        marker=dict(
            size=12,
            color="yellow",
            symbol="diamond"
        ),
        hovertext=[
            f"Page: {page}<br>Ideal Time: {time}s"
            for page, time in standard_journey
        ],
        hoverinfo="text"
    ))

fig_plot1.update_layout(
    template="plotly_dark",
    plot_bgcolor="#0e1117",
    paper_bgcolor="#0e1117",
    font=dict(color="white"),
    legend_title="user_id",
    yaxis=dict(
        tickmode="array",
        tickvals=list(range(len(node_order))),
        ticktext=node_order
    ),
    xaxis_title="Elapsed Time (s)",
    yaxis_title="Page"
)

st.plotly_chart(fig_plot1, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# PLOT 2: ACTIVITY (CLICKS PER PAGE PER USER)
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 2: Activity by Page (Clicks per User)")

df_plot2_activity = df.copy()
df_plot2_activity["event_name_str"] = df_plot2_activity["event_name"].fillna("").astype(str)

# Prefer click-like events; fallback to all events if click labels are unavailable.
click_mask = df_plot2_activity["event_name_str"].str.contains(
    r"click|clicked|tap|tapped|press|pressed|button",
    case=False,
    regex=True,
)

if click_mask.any():
    df_plot2_activity = df_plot2_activity[click_mask].copy()

plot2_click_counts = (
    df_plot2_activity.groupby(["user_id", "page_label"], as_index=False)
    .size()
    .rename(columns={"size": "click_count"})
)

if plot2_click_counts.empty:
    st.info("No click activity data available for page-level plot.")
else:
    # Keep page axis in standard journey order.
    plot2_click_counts["page_label"] = pd.Categorical(
        plot2_click_counts["page_label"],
        categories=STANDARD_PAGE_FLOW,
        ordered=True,
    )
    plot2_click_counts = plot2_click_counts.dropna(subset=["page_label"]).copy()

    fig_plot2_activity = px.bar(
        plot2_click_counts,
        x="page_label",
        y="click_count",
        color=plot2_click_counts["user_id"].astype(str),
        barmode="stack",
        category_orders={"page_label": STANDARD_PAGE_FLOW},
        labels={
            "page_label": "Page Type",
            "click_count": "Clicks",
            "color": "UserID",
        },
    )
    fig_plot2_activity.update_layout(
        template="plotly_dark",
        xaxis_title="Page Type",
        yaxis_title="Count of Clicks",
        legend_title="UserID",
    )
    st.plotly_chart(fig_plot2_activity, use_container_width=True)

# ─────────────────────────────────────────────────────────────
# Plot 3: Steps/Events per Page
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 3: Steps/Events per Page")

col1, col2 = st.columns(2)

with col1:

    if flow_type == "Pages":

        page_nodes_present = (
            df["node"]
            .dropna()
            .unique()
            .tolist()
        )

        ordered_page_nodes = [
            p for p in STANDARD_PAGE_FLOW
            if p in page_nodes_present
        ]

        extra_page_nodes = [
            p for p in page_nodes_present
            if p not in STANDARD_PAGE_FLOW
        ]

        node_options_plot3 = (
            ordered_page_nodes +
            extra_page_nodes
        )

    else:

        node_options_plot3 = sorted(
            df["node"]
            .dropna()
            .unique()
        )

    selected_node = st.selectbox(
        "Select Page / Event",
        node_options_plot3
    )

with col2:

    top_n = st.slider(
        "Limit journeys",
        5,
        50,
        15
    )

if selected_node:

    df_plot3 = df[
        df["node"] == selected_node
    ].copy()

    df_plot3 = df_plot3.sort_values([
        "journey_id",
        "occurred_at"
    ])

    excluded_event_pattern = (
        r"(^|_)page(_)?(view|viewed|exit)(_|$)"
    )

    df_plot3 = df_plot3[
        ~df_plot3["event_name"]
        .fillna("")
        .str.lower()
        .str.contains(
            excluded_event_pattern,
            regex=True
        )
    ].copy()

    df_plot3["journey_start"] = (
        df_plot3.groupby("journey_id")["occurred_at"]
        .transform("min")
    )

    df_plot3["time_sec"] = (
        df_plot3["occurred_at"]
        - df_plot3["journey_start"]
    ).dt.total_seconds().round(2)

    top_journeys = (
        df_plot3["journey_id"]
        .value_counts()
        .head(top_n)
        .index
    )

    df_plot3 = df_plot3[
        df_plot3["journey_id"]
        .isin(top_journeys)
    ]

    if flow_type == "Pages":

        df_plot3["drill_node"] = (
            df_plot3["event_name"]
        )

        configured_flow = STANDARD_FLOW_BY_PAGE.get(
            selected_node,
            []
        )

        configured_order = [
            item["event"]
            for item in configured_flow
        ]

        configured_keys = [
            normalize_event_key(e)
            for e in configured_order
        ]

        df_plot3["drill_key"] = (
            df_plot3["drill_node"]
            .map(normalize_event_key)
        )

        df_plot3 = df_plot3[
            df_plot3["drill_key"]
            .isin(configured_keys)
        ].copy()

        drill_order = configured_keys

        y_label = "Events"

    else:

        df_plot3["drill_node"] = (
            df_plot3["page_id"]
        )

        drill_order = (
            df_plot3["drill_node"]
            .dropna()
            .unique()
            .tolist()
        )

        y_label = "Pages"

    drill_to_num = {
        node: i
        for i, node in enumerate(drill_order)
    }

    journeys = (
        df_plot3["journey_id"]
        .unique()
    )

    def format_user_label_plot3(v):

        if pd.isna(v):
            return "Guest"

        return (
            f"User {int(v)}"
            if str(v).isdigit()
            else f"User {v}"
        )

    journey_user_map_plot3 = (
        df_plot3.groupby("journey_id")["user_id"]
        .first()
        .to_dict()
    )

    user_label_map_plot3 = {
        jid: format_user_label_plot3(uid)
        for jid, uid in journey_user_map_plot3.items()
    }

    unique_user_labels_plot3 = list(dict.fromkeys([
        user_label_map_plot3.get(jid, "Guest")
        for jid in journeys
    ]))

    colors_plot3 = px.colors.qualitative.Set2

    user_color_map_plot3 = {
        ulabel: colors_plot3[i % len(colors_plot3)]
        for i, ulabel in enumerate(unique_user_labels_plot3)
    }

    seen_user_legend_plot3 = set()

    fig_plot3 = go.Figure()

    for jid in journeys:

        d = df_plot3[
            df_plot3["journey_id"] == jid
        ].copy()

        if d.empty:
            continue

        user_label_plot3 = (
            user_label_map_plot3.get(
                jid,
                "Guest"
            )
        )

        show_legend = (
            user_label_plot3
            not in seen_user_legend_plot3
        )

        seen_user_legend_plot3.add(
            user_label_plot3
        )

        if flow_type == "Pages":

            y_vals = [
                drill_to_num.get(k)
                for k in d["drill_key"]
            ]

        else:

            y_vals = [
                drill_to_num.get(n)
                for n in d["drill_node"]
            ]

        fig_plot3.add_trace(go.Scatter(

            x=d["time_sec"],

            y=y_vals,

            mode="lines+markers",

            name=user_label_plot3,

            legendgroup=user_label_plot3,

            showlegend=show_legend,

            line=dict(
                width=2,
                color=user_color_map_plot3[
                    user_label_plot3
                ],
            ),

            marker=dict(
                size=8,
                color=user_color_map_plot3[
                    user_label_plot3
                ]
            ),

            hoverinfo="text",

            hovertext=[
                (
                    f"Journey: {jid}"
                    f"<br>User: {user_label_plot3}"
                    f"<br>Time: {t}s"
                    f"<br>{y_label[:-1]}: {e}"
                )
                for t, e in zip(
                    d["time_sec"],
                    d["drill_node"]
                )
            ],
        ))
    
    # ─────────────────────────────────────────
    # STANDARD FLOW OVERLAY
    # ─────────────────────────────────────────

    if flow_type == "Pages":

        standard_timeline = STANDARD_EVENT_TIMELINE.get(
            selected_node,
            []
        )

        if standard_timeline:

            standard_x = []
            standard_y = []

            for event_name, t in standard_timeline:

                event_key = normalize_event_key(
                    event_name
                )

                if event_key in drill_to_num:

                    standard_x.append(t)

                    standard_y.append(
                        drill_to_num[event_key]
                    )

            if standard_x and standard_y:

                fig_plot3.add_trace(go.Scatter(

                    x=standard_x,

                    y=standard_y,

                    mode="lines+markers",

                    name="Standard Flow",

                    line=dict(
                        color="yellow",
                        width=5,
                        dash="dash",
                    ),

                    marker=dict(
                        size=12,
                        color="yellow",
                        symbol="diamond",
                    ),

                    hoverinfo="text",

                    hovertext=[
                        (
                            f"Standard Event: {e}"
                            f"<br>Ideal Time: {t}s"
                        )
                        for e, t in standard_timeline
                    ],
                ))

    fig_plot3.update_layout(

        template="plotly_dark",

        plot_bgcolor="#0e1117",

        paper_bgcolor="#0e1117",

        font=dict(color="white"),

        xaxis_title="Time (seconds)",

        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(drill_order))),
            ticktext=drill_order,
            title=y_label
        ),

        legend_title="user_id",

        title=f"Steps inside: {selected_node}",
    )

    st.plotly_chart(
        fig_plot3,
        use_container_width=True
    )

# ─────────────────────────────────────────────────────────────
# PLOT 3A: STANDARD EVENT ACTIVITY ON PAGE
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 3a: Standard Event Activity on Selected Page")

page_labels_present_3a = (
    df["page_label"]
    .dropna()
    .unique()
    .tolist()
)

page_options_plot3a = [
    p for p in STANDARD_PAGE_FLOW
    if p in page_labels_present_3a
]

selected_page_plot3a = st.selectbox(
    "Plot 3a - Select Page Type",
    page_options_plot3a,
)

df_plot3a = df[
    df["page_label"] == selected_page_plot3a
].copy()

df_plot3a["event_name"] = (
    df_plot3a["event_name"]
    .fillna("Unknown Event")
)

df_plot3a["event_key"] = (
    df_plot3a["event_name"]
    .map(normalize_event_key)
)

configured_flow = STANDARD_FLOW_BY_PAGE.get(
    selected_page_plot3a,
    []
)

ordered_events_3a = [
    normalize_event_key(item["event"])
    for item in configured_flow
]

event_type_map_3a = {
    normalize_event_key(item["event"]): item["type"]
    for item in configured_flow
}

df_plot3a = df_plot3a[
    df_plot3a["event_key"]
    .isin(ordered_events_3a)
].copy()

plot3a_counts = (
    df_plot3a.groupby(
        ["event_key", "user_id"],
        as_index=False
    )
    .size()
    .rename(columns={
        "size": "event_count"
    })
)

if plot3a_counts.empty:

    st.info("No standardized events available.")

else:

    fig_plot3a = px.bar(

        plot3a_counts,

        x="event_key",

        y="event_count",

        color=plot3a_counts["user_id"].astype(str),

        barmode="stack",

        category_orders={
            "event_key": ordered_events_3a
        },

        labels={
            "event_key": "Event Type",
            "event_count": "Event Count",
            "color": "UserID",
        },
    )

    fig_plot3a.update_layout(

        template="plotly_dark",

        plot_bgcolor="#0e1117",

        paper_bgcolor="#0e1117",

        font=dict(color="white"),

        xaxis_title=f"Events on {selected_page_plot3a}",

        yaxis_title="Count",

        legend_title="UserID",
    )

    st.plotly_chart(
        fig_plot3a,
        use_container_width=True
    )

# ─────────────────────────────────────────────────────────────
# PLOT 3B: STANDARD FLOW TIMELINE
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 3b: Standard Flow Timeline")

page_labels_present_3b = (
    df["page_label"]
    .dropna()
    .unique()
    .tolist()
)

page_options_plot3b = [
    p for p in STANDARD_PAGE_FLOW
    if p in page_labels_present_3b
]

selected_page_plot3b = st.selectbox(
    "Plot 3b - Select Page Type",
    page_options_plot3b,
)

df_plot3b = df[
    df["page_label"] == selected_page_plot3b
].copy()

df_plot3b["event_name"] = (
    df_plot3b["event_name"]
    .fillna("unknown_event")
)

df_plot3b["event_key"] = (
    df_plot3b["event_name"]
    .map(normalize_event_key)
)

configured_flow = STANDARD_FLOW_BY_PAGE.get(
    selected_page_plot3b,
    []
)

ordered_events_plot3b = [
    normalize_event_key(item["event"])
    for item in configured_flow
]

event_type_map = {
    normalize_event_key(item["event"]): item["type"]
    for item in configured_flow
}

df_plot3b = df_plot3b[
    df_plot3b["event_key"]
    .isin(ordered_events_plot3b)
].copy()

if df_plot3b.empty:

    st.info("No standardized events found.")

else:

    # ─────────────────────────────────────────
    # Y POSITION MAP
    # ─────────────────────────────────────────

    y_position_map = {}

    positive_index = 1
    negative_index = -1

    for item in configured_flow:

        event_key = normalize_event_key(
            item["event"]
        )

        event_type = item["type"]

        if event_type == "positive":

            y_position_map[event_key] = positive_index
            positive_index += 1

        elif event_type == "neutral":

            y_position_map[event_key] = 0

        else:

            y_position_map[event_key] = negative_index
            negative_index -= 1

    # ─────────────────────────────────────────
    # SORTING
    # ─────────────────────────────────────────

    df_plot3b = df_plot3b.sort_values([
        "journey_id",
        "occurred_at"
    ])

    df_plot3b["journey_start"] = (
        df_plot3b.groupby("journey_id")["occurred_at"]
        .transform("min")
    )

    df_plot3b["time_sec"] = (
        df_plot3b["occurred_at"]
        - df_plot3b["journey_start"]
    ).dt.total_seconds().round(2)

    df_plot3b["y_pos"] = (
        df_plot3b["event_key"]
        .map(y_position_map)
    )

    # ─────────────────────────────────────────
    # USER LABELS
    # ─────────────────────────────────────────

    def format_user_label_plot3b(v):

        if pd.isna(v):
            return "Guest"

        return (
            f"User {int(v)}"
            if str(v).isdigit()
            else f"User {v}"
        )

    journey_user_map_plot3b = (
        df_plot3b.groupby("journey_id")["user_id"]
        .first()
        .to_dict()
    )

    user_label_map_plot3b = {
        jid: format_user_label_plot3b(uid)
        for jid, uid in journey_user_map_plot3b.items()
    }

    journeys_plot3b = (
        df_plot3b["journey_id"]
        .dropna()
        .unique()
        .tolist()
    )

    unique_user_labels_plot3b = list(dict.fromkeys([
        user_label_map_plot3b.get(jid, "Guest")
        for jid in journeys_plot3b
    ]))

    colors_plot3b = px.colors.qualitative.Set2

    user_color_map_plot3b = {
        ulabel: colors_plot3b[i % len(colors_plot3b)]
        for i, ulabel in enumerate(unique_user_labels_plot3b)
    }

    # ─────────────────────────────────────────
    # FIGURE
    # ─────────────────────────────────────────

    fig_plot3b = go.Figure()

    seen_user_legend_plot3b = set()

    for jid in journeys_plot3b:

        d = df_plot3b[
            df_plot3b["journey_id"] == jid
        ].copy()

        if d.empty:
            continue

        user_label_plot3b = (
            user_label_map_plot3b.get(
                jid,
                "Guest"
            )
        )

        show_legend = (
            user_label_plot3b
            not in seen_user_legend_plot3b
        )

        seen_user_legend_plot3b.add(
            user_label_plot3b
        )

        fig_plot3b.add_trace(go.Scatter(

            x=d["time_sec"],

            y=d["y_pos"],

            mode="lines+markers",

            name=user_label_plot3b,

            legendgroup=user_label_plot3b,

            showlegend=show_legend,

            line=dict(
                width=3,
                color=user_color_map_plot3b[
                    user_label_plot3b
                ],
            ),

            marker=dict(
                size=8,
                color=user_color_map_plot3b[
                    user_label_plot3b
                ]
            ),

            hoverinfo="text",

            hovertext=[
                (
                    f"Journey: {j}"
                    f"<br>User: {user_label_plot3b}"
                    f"<br>Time: {t}s"
                    f"<br>Event: {e}"
                    f"<br>Type: {event_type_map.get(k)}"
                )
                for j, t, e, k in zip(
                    d["journey_id"],
                    d["time_sec"],
                    d["event_name"],
                    d["event_key"],
                )
            ],
        ))

    # ─────────────────────────────────────────
    # Y AXIS LABELS
    # ─────────────────────────────────────────

    tickvals = []
    ticktext = []

    for e in ordered_events_plot3b:

        if e in y_position_map:

            tickvals.append(
                y_position_map[e]
            )

            ticktext.append(e)

    # CENTER LINE

    fig_plot3b.add_hline(
        y=0,
        line_dash="dash",
        line_color="yellow",
        line_width=1.5,
    )

    # ─────────────────────────────────────────
    # LAYOUT
    # ─────────────────────────────────────────

    fig_plot3b.update_layout(

        template="plotly_dark",

        plot_bgcolor="#0e1117",

        paper_bgcolor="#0e1117",

        font=dict(color="white"),

        xaxis_title="Time (seconds)",

        yaxis_title="Event Impact Flow",

        legend_title="user_id",

        hovermode="closest",

        yaxis=dict(
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
        ),
    )

    st.plotly_chart(
        fig_plot3b,
        use_container_width=True
    )


# # ─────────────────────────────────────────────────────────────
# # PLOT 4: AGGREGATED FLOW
# # ─────────────────────────────────────────────────────────────
# st.subheader("Plot 4: Aggregated User Flow Diagram")

# # Compute source -> target relationships
# df_plot3_sankey = df_plot1_nodes.dropna(subset=['prev_node', 'node']).copy()

# if not df_plot3_sankey.empty:
#     links = df_plot3_sankey.groupby(['prev_node', 'node']).size().reset_index(name='value')
    
#     all_nodes_sankey = list(pd.unique(links[['prev_node', 'node']].values.ravel('K')))
#     node_mapping = {n: i for i, n in enumerate(all_nodes_sankey)}
    
#     links['source'] = links['prev_node'].map(node_mapping)
#     links['target'] = links['node'].map(node_mapping)
    
#     fig_plot3 = go.Figure(data=[go.Sankey(
#         node = dict(
#           pad = 15,
#           thickness = 20,
#           line = dict(color = "black", width = 0.5),
#           label = all_nodes_sankey,
#           color = "#636EFA"
#         ),
#         link = dict(
#           source = links['source'],
#           target = links['target'],
#           value = links['value']
#         )
#     )])
    
#     fig_plot3.update_layout(
#         template="plotly_dark",
#         plot_bgcolor="#0e1117",
#         paper_bgcolor="#0e1117",
#         font=dict(color="white")
#     )
#     st.plotly_chart(fig_plot3, use_container_width=True)
# else:
#     st.info("Not enough data transitions to generate Sankey diagram.")


# ─────────────────────────────────────────────────────────────
# PLOT 5: CORE CONVERSION FUNNEL
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 5: Funnel (Standard Journey Flow)")

df_plot5 = df.copy()

# Use standardized page labels only
df_plot5 = df_plot5[df_plot5["page_label"].isin(STANDARD_PAGE_FLOW)].copy()

# Sort journey properly
df_plot5 = df_plot5.sort_values(
    ["journey_id", "occurred_at"]
)

# Remove duplicate page revisits inside same journey
df_plot5_unique = df_plot5.drop_duplicates(
    subset=["journey_id", "page_label"]
)

# Count unique journeys reaching each page
plot5_counts = (
    df_plot5_unique.groupby("page_label")["journey_id"]
    .nunique()
    .reindex(STANDARD_PAGE_FLOW)
    .reset_index()
    .rename(columns={
        "page_label": "page",
        "journey_id": "users"
    })
)

# Remove empty pages
plot5_counts = plot5_counts.dropna(subset=["users"])

colors = px.colors.qualitative.Set2
color_list = [
    colors[i % len(colors)]
    for i in range(len(plot5_counts))
]

if not plot5_counts.empty:

    fig_plot5 = go.Figure(go.Funnel(
        y=plot5_counts["page"],
        x=plot5_counts["users"],

        textinfo="value+percent initial",

        marker=dict(
            color=color_list
        )
    ))

    fig_plot5.update_layout(
        template="plotly_dark",
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),

        xaxis_title="Users",
        yaxis_title="Standard Journey Pages",
    )

    st.plotly_chart(
        fig_plot5,
        use_container_width=True
    )

else:
    st.info("No funnel data available.")

# ─────────────────────────────────────────────────────────────
# PLOT 6: REVISIT ANALYSIS
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 6: Revisit Analysis (stacked by UserID)")
df_plot6_sessions = (
    df.groupby(["user_id", "session_id"], as_index=False)["occurred_at"]
    .min()
    .sort_values(["user_id", "occurred_at"])
)
df_plot6_sessions["prev_session_time"] = df_plot6_sessions.groupby("user_id")["occurred_at"].shift(1)
df_plot6_sessions["revisit_gap_hours"] = (
    (df_plot6_sessions["occurred_at"] - df_plot6_sessions["prev_session_time"]).dt.total_seconds() / 3600
)

df_plot6_revisit_counts = (
    df_plot6_sessions.dropna(subset=["revisit_gap_hours"])
    .groupby("user_id", as_index=False)
    .size()
    .rename(columns={"size": "revisit_count"})
)
df_plot6_gap = df_plot6_sessions.dropna(subset=["revisit_gap_hours"]).copy()

if df_plot6_revisit_counts.empty:
    st.info("Not enough data for revisit analysis.")
else:
    total_users = int(df["user_id"].dropna().nunique())
    revisited_users = int(df_plot6_revisit_counts["user_id"].nunique())
    revisit_pct = (revisited_users / total_users * 100.0) if total_users > 0 else 0.0

    avg_gap_h = float(df_plot6_gap["revisit_gap_hours"].mean())
    med_gap_h = float(df_plot6_gap["revisit_gap_hours"].median())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Users", total_users)
    k2.metric("Revisited Users", revisited_users)
    k3.metric("Revisited %", f"{revisit_pct:.1f}%")
    k4.metric("Median Revisit Gap", f"{med_gap_h:.1f} hrs")

    fig_plot6_counts = px.bar(
        df_plot6_revisit_counts,
        x="user_id",
        y="revisit_count",
        color=df_plot6_revisit_counts["user_id"].astype(str),
    )
    fig_plot6_counts.update_layout(
        template="plotly_dark",
        xaxis_title="UserID",
        yaxis_title="Total revisit count",
        legend_title="UserID",
        showlegend=True,
    )
    st.plotly_chart(fig_plot6_counts, use_container_width=True)

    # Distribution buckets: how long users take to revisit.
    gap_bins = [-0.001, 1, 6, 24, 72, 168, float("inf")]
    gap_labels = ["<=1h", "1-6h", "6-24h", "1-3d", "3-7d", ">7d"]
    df_plot6_gap["gap_bucket"] = pd.cut(
        df_plot6_gap["revisit_gap_hours"],
        bins=gap_bins,
        labels=gap_labels,
    )
    bucket_counts = (
        df_plot6_gap.groupby("gap_bucket", observed=False)
        .size()
        .reindex(gap_labels, fill_value=0)
        .reset_index(name="count")
    )
    bucket_counts["pct"] = (
        bucket_counts["count"] / max(bucket_counts["count"].sum(), 1) * 100.0
    ).round(1)

    fig_plot6_gap_dist = px.bar(
        bucket_counts,
        x="gap_bucket",
        y="count",
        text="pct",
        labels={"gap_bucket": "Revisit Gap Bucket", "count": "Revisit Events"},
    )
    fig_plot6_gap_dist.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_plot6_gap_dist.update_layout(
        template="plotly_dark",
        xaxis_title="Time Since Previous Session",
        yaxis_title="Revisit Events",
        showlegend=False,
    )
    st.plotly_chart(fig_plot6_gap_dist, use_container_width=True)

    st.caption(f"Average revisit gap: {avg_gap_h:.1f} hrs")


# ─────────────────────────────────────────────────────────────
# PLOT 7: REPEATED BUTTONS ACROSS PAGES (DYNAMIC)
# ─────────────────────────────────────────────────────────────
st.subheader("Plot 7: Repeated Buttons Across Pages")

df_plot7_buttons = df.copy()
df_plot7_buttons["event_name_str"] = df_plot7_buttons["event_name"].fillna("").astype(str)

# Build raw action text dynamically from whatever action/button-like fields exist.
button_source_cols = [
    c for c in ["button_name", "button_type", "cta_name", "action_name", "event_name"]
    if c in df_plot7_buttons.columns
]
if button_source_cols:
    df_plot7_buttons["raw_button_text"] = (
        df_plot7_buttons[button_source_cols]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
    )
else:
    df_plot7_buttons["raw_button_text"] = df_plot7_buttons["event_name_str"]

# Keep only action-like rows to avoid generic labels like "Product".
action_like_mask = df_plot7_buttons["raw_button_text"].str.contains(
    r"click|clicked|tap|tapped|press|pressed|button|cta|compare|cart|add|buy|try|wishlist",
    case=False,
    regex=True,
)
df_plot7_buttons = df_plot7_buttons[action_like_mask].copy()

normalized = (
    df_plot7_buttons["raw_button_text"]
    .str.lower()
    .str.replace(r"[_\-]+", " ", regex=True)
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
)

# Canonicalize well-known actions first.
df_plot7_buttons["button_type"] = pd.NA
df_plot7_buttons.loc[
    normalized.str.contains(
        r"try\s*&?\s*compare.*toggle|compare.*toggle|product_compare_toggled|trycompare_toggle",
        regex=True,
    ),
    "button_type",
] = "Try&Compare Toggle"
df_plot7_buttons.loc[
    normalized.str.contains(r"add\s*to\s*cart|cart\s*add|add\s*cart", regex=True), "button_type"
] = "Add To Cart"

# Dynamic fallback for future buttons.
fallback = (
    normalized
    .str.replace(r"\b(button|btn|cta)\b", "", regex=True)
    .str.replace(r"\b(click|clicked|tap|tapped|press|pressed)\b", "", regex=True)
    .str.replace(r"\s+", " ", regex=True)
    .str.strip()
    .str.title()
)
df_plot7_buttons["button_type"] = df_plot7_buttons["button_type"].fillna(fallback)

# Remove non-informative generic labels after cleanup.
bad_labels = {
    "", "Product", "Page", "Event", "Click", "Clicked", "Tap", "Pressed",
    "View", "Open", "Load", "Render"
}
df_plot7_buttons = df_plot7_buttons[
    ~df_plot7_buttons["button_type"].isin(bad_labels)
].copy()
df_plot7_buttons = df_plot7_buttons[
    df_plot7_buttons["button_type"] != "Go To Compare"
].copy()

# Keep repeated button types that appear on multiple pages.
repeated_button_types = (
    df_plot7_buttons.groupby("button_type")["page_label"]
    .nunique()
    .loc[lambda s: s > 1]
    .index
)
df_plot7_buttons = df_plot7_buttons[
    df_plot7_buttons["button_type"].isin(repeated_button_types)
].copy()

plot7_button_page_counts = (
    df_plot7_buttons.groupby(["button_type", "page_label"], as_index=False)
    .size()
    .rename(columns={"size": "click_count"})
)

if plot7_button_page_counts.empty:
    st.info("No repeated button click data found across multiple pages.")
else:
    button_order_plot7 = sorted(
        plot7_button_page_counts["button_type"].dropna().unique().tolist()
    )
    page_order_plot7 = [
        p for p in STANDARD_PAGE_FLOW
        if p in plot7_button_page_counts["page_label"].unique()
    ]

    fig_plot7 = px.bar(
        plot7_button_page_counts,
        x="button_type",
        y="click_count",
        color="page_label",
        barmode="group",
        category_orders={
            "button_type": button_order_plot7,
            "page_label": page_order_plot7,
        },
        labels={
            "button_type": "Button Type",
            "click_count": "Count of Clicks",
            "page_label": "Page",
        },
    )
    fig_plot7.update_layout(
        template="plotly_dark",
        xaxis_title="Button Type",
        yaxis_title="Count of Clicks",
        legend_title="Page",
    )
    st.plotly_chart(fig_plot7, use_container_width=True)
