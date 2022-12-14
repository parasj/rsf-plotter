from functools import lru_cache
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import json
import pandas as pd
import urllib
import time
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.style.use("ggplot")

st.write(f"### RSF occupancy")
truncate_weeks = st.slider("Truncate weeks", 0, 12, 3)


@st.cache(ttl=120, suppress_st_warning=True)
def load_data():
    with st.spinner("Loading data..."):
        start = time.time()
        data_url = "https://people.eecs.berkeley.edu/~paras/rsf_occupancy.jsonl"
        with urllib.request.urlopen(data_url) as f:
            jsonl = f.read().decode("utf-8").strip().split("\n")
            if truncate_weeks > 0:
                n_records = 60 * 24 * 7 * truncate_weeks
                records = [json.loads(line) for line in jsonl[-n_records:]]
            else:
                records = [json.loads(line) for line in jsonl]
            df = pd.DataFrame(records)
        end = time.time()
    print(f"loaded in {end - start:.2f} seconds")
    st.write(f"Loaded {len(df)} records")
    return df


df = load_data().copy()
last_rec = df.iloc[-1]
st.write(
    f"**{int(last_rec['count'])}** people in RSF, **{int(last_rec['count'] / 150 * 100):d}**% of capacity (updated at {last_rec['datetime']})"
)


@lru_cache(maxsize=4096)
def map_date(date):
    return pd.to_datetime(date, format="%Y-%b-%d %H:%M:%S", cache=True)


@st.cache(ttl=120, suppress_st_warning=True)
def map_dates(df):
    start = time.time()
    parser = re.compile(
        r"(?P<day_of_week>\w+) (?P<month>\w+) (?P<day>\d+) (?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+) (?P<timezone>\w+) (?P<year>\d+)"
    )
    parsed = df["datetime"].apply(lambda x: parser.match(x).groupdict())
    df["datetime_str"] = parsed.apply(lambda x: f"{x['year']}-{x['month']}-{x['day']} {x['hour']}:{x['minute']}:{x['second']}")
    with st.spinner("Mapping dates..."):
        df["datetime"] = df["datetime_str"].apply(map_date)
    df = df.drop(columns=["datetime_str"])
    df["date"] = df["datetime"].dt.date
    end = time.time()
    print(f"parsed in {end - start:.2f} seconds")
    return df


st_autorefresh(interval=10000)
df = map_dates(df).copy()

# ask for plot options
col1, col2 = st.columns(2)
with col1:
    apply_ema = st.checkbox("Apply EMA", value=True)
with col2:
    if apply_ema:
        ema_span = st.slider("EMA span", 1, 60, 10)


def ema(df):
    return df.ewm(span=ema_span).mean() if apply_ema else df


# show detailed data for today since 7am
df_today = df[df["date"] == df["date"].max()]
df_today = df_today.sort_values("datetime")
df_today = df_today.set_index("datetime")
opening_time = pd.Timestamp(df_today[df_today["count"] > 20].index.min())
df_today = df_today[df_today.index >= opening_time]

# same plot as above but instead, show last 7 historical lines for the same day of the week
today = pd.Timestamp(df["datetime"].max())
df_last = df.copy()
df_last = df_last.sort_values("datetime")
df_last = df_last.set_index("datetime")
fig, ax = plt.subplots(figsize=(7, 3))

# Set time on day to be same time but replace year/month/day with today's
df_today["time_on_day"] = df_today.index.time
df_today["time_on_day"] = df_today["time_on_day"].apply(lambda x: today.replace(hour=x.hour, minute=x.minute, second=x.second))

for date, df_date in df_last.groupby("date"):
    # if same day of the week
    date_dow = date.strftime("%a")
    today_dow = today.strftime("%a")
    if date_dow == today_dow:
        df_date = df_date.resample("5min").max()
        opening_time = pd.Timestamp(df_date[df_date["count"] > 20].index.min())
        df_date = df_date[df_date.index >= opening_time]
        df_date["time_on_day"] = df_date.index.time
        df_date["time_on_day"] = df_date["time_on_day"].apply(lambda x: today.replace(hour=x.hour, minute=x.minute, second=x.second))
        label = f"{date.strftime('%a %m/%d')}"
        ax.plot(df_date["time_on_day"], ema(df_date["count"]), linewidth=1, label=label)

# show today in a thick black line
ax.plot(df_today["time_on_day"], ema(df_today["count"]), linewidth=2, color="black", label="today")
ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
ax.set_title(f"RSF occupancy by hour (last {truncate_weeks} weeks)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

# show line at 150
ax.axhline(150, color="red", linestyle="--", linewidth=1)

fig.tight_layout()
st.pyplot(fig)

if st.button("Show historical data"):
    # aggregate max count by date, and then show bar chart
    df_max = df.groupby("date").max()
    df_max = df_max.sort_values("datetime")
    df_max = df_max.set_index("datetime")
    fig, ax = plt.subplots(figsize=(7, 2))
    ax.plot(df_max.index, df_max["count"], marker="o", markersize=2, linewidth=1)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_title("Peak RSF occupancy by day")
    st.plotly_chart(fig)
