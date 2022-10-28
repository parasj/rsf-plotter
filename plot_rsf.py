import streamlit as st
import json
import pandas as pd
import urllib
import time
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

plt.style.use('ggplot')

start = time.time()
data_url = "https://people.eecs.berkeley.edu/~paras/rsf_occupancy.jsonl"
with urllib.request.urlopen(data_url) as f:
    jsonl = f.read().decode("utf-8").strip().split("\n")
    records = [json.loads(line) for line in jsonl]
    df = pd.DataFrame(records)
end = time.time()
print(f"loaded in {end - start:.2f} seconds")

start = time.time()
parser = re.compile(r"(?P<day_of_week>\w+) (?P<month>\w+) (?P<day>\d+) (?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+) (?P<timezone>\w+) (?P<year>\d+)")
parsed = df["datetime"].apply(lambda x: parser.match(x).groupdict())
# filter date to current year and month or last month
current_year = time.strftime("%Y")
current_month = time.strftime("%m")
last_month = str(int(current_month) - 1).zfill(2)
df = df[(parsed["year"] == current_year) & ((parsed["month"] == current_month) | (parsed["month"] == last_month))]
df["datetime_str"] = parsed.apply(lambda x: f"{x['year']}-{x['month']}-{x['day']} {x['hour']}:{x['minute']}:{x['second']}")
df["datetime"] = pd.to_datetime(df["datetime_str"], format="%Y-%b-%d %H:%M:%S")
df = df.drop(columns=["datetime_str"])
df["date"] = df["datetime"].dt.date
end = time.time()
print(f"parsed in {end - start:.2f} seconds")

# show detailed data for today since 7am
today = pd.Timestamp.today()
df_today = df[df["date"] == today]
df_today = df_today.sort_values("datetime")
df_today = df_today.set_index("datetime")
opening_time = df_today[df_today["count"] > 20].index.min()
df_today = df_today[df_today.index >= opening_time]

# same plot as above but instead, show last 7 historical lines for the same day of the week
historical_weeks = st.slider("Historical weeks", 1, 7, 3)
today = pd.Timestamp.today()
df_last = df[df["date"] >= today - pd.Timedelta(weeks=historical_weeks)]
df_last = df_last.sort_values("datetime")
df_last = df_last.set_index("datetime")
fig, ax = plt.subplots(figsize=(7, 3))

# today data
df_today = df[df["date"] == today]
df_today = df_today.sort_values("datetime")
df_today = df_today.set_index("datetime")
today_opening_time = df_today[df_today["count"] > 20].index.min()
df_today = df_today[df_today.index >= today_opening_time]
today_midnight_time = today.replace(hour=0, minute=0, second=0)
df_today["time_on_day"] = (df_today.index - today_midnight_time) / pd.Timedelta(minutes=1)
df_today["time_on_day"] = df_today["time_on_day"].apply(lambda x: pd.Timestamp.today().replace(hour=int(x // 60), minute=int(x) % 60))

for date, df_date in df_last.groupby("date"):
    # if same day of the week
    date_dow = date.strftime("%a")
    today_dow = today.strftime("%a")
    if date_dow == today_dow:
        df_date = df_date.resample("5min").max()
        opening_time = df_date[df_date["count"] > 20].index.min()
        df_date = df_date[df_date.index >= opening_time]
        midnight_time = pd.Timestamp(date).replace(hour=0, minute=0, second=0)
        df_date["time_on_day"] = (df_date.index - midnight_time) / pd.Timedelta(minutes=1)
        # convert to format for DateFormatter
        df_date["time_on_day"] = df_date["time_on_day"].apply(lambda x: pd.Timestamp.today().replace(hour=int(x // 60), minute=int(x) % 60))
        label = f"{date.strftime('%a %m/%d')}"
        ax.plot(df_date["time_on_day"], df_date["count"], linewidth=1, label=label)
# show today in a thick black line
ax.plot(df_today["time_on_day"], df_today["count"], linewidth=2, color="black", label="today")
ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
ax.set_title(f"RSF occupancy by hour (last {historical_weeks} weeks)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
fig.tight_layout()
st.pyplot(fig)

# # aggregate max count by date, and then show bar chart
# df_max = df.groupby("date").max()
# df_max = df_max.sort_values("datetime")
# df_max = df_max.set_index("datetime")
# fig, ax = plt.subplots(figsize=(7, 2))
# ax.plot(df_max.index, df_max["count"], marker="o", markersize=2, linewidth=1)
# ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
# ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
# ax.set_title("Peak RSF occupancy by day")
# st.plotly_chart(fig)