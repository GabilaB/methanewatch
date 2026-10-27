"""MethaneWatch public observation explorer. Run: python -m streamlit run app.py"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="MethaneWatch | Satellite methane observations", layout="wide", initial_sidebar_state="expanded")

# Restrained styling. No external images, fonts, scripts or decorative logo.
st.markdown("""<style>
:root {--navy:#14283b;--ink:#172b3c;--soft:#f5f7f7;--line:#e0e6e8;--accent:#317b68;}
.stApp {background:#f7f8f8;color:#172b3c;}
[data-testid="stSidebar"] {background:#14283b;}
[data-testid="stSidebar"] * {color:#edf3f4;}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] small {color:#d7e1e6!important;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#172b3c!important;}
[data-testid="stSidebar"] .stRadio label {padding:5px 0;}
[data-testid="stSidebar"] .stMarkdown h2 {color:#fff;font-family:Georgia,serif;font-size:1.55rem;margin-bottom:.8rem;}
.block-container {padding-top:2rem;max-width:1570px;}
h1,h2,h3 {color:#172b3c;letter-spacing:-.02em;}
h1 {font-family:Georgia,serif;font-size:2.8rem!important;margin-bottom:0!important;}
h2 {font-size:1.35rem!important;}
h3 {font-size:1.03rem!important;}
[data-testid="stMetric"] {border:1px solid var(--line);border-radius:9px;background:#fff;padding:15px 16px;min-height:125px;}
[data-testid="stMetricValue"] {font-size:1.65rem;color:#172b3c;}
[data-testid="stMetricLabel"] {color:#526576;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:#e0e6e8!important;}
.stButton button[kind="primary"], .stDownloadButton button {border-color:#317b68;color:#245d50;}
.stCaption {color:#617180;}
hr {border-color:#e0e6e8;}
</style>""", unsafe_allow_html=True)

processed = Path("data/processed")
demo = Path("data/demo")
root = processed if (processed / "plumes.csv").exists() else demo
file = root / "plumes.csv"
manifest = root / "run_manifest.json"

@st.cache_data(show_spinner=False)
def read_data(path: str, stamp: float):
    return pd.read_csv(path)

meta = {}
if manifest.exists():
    try:
        meta = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        st.warning("Processing metadata could not be read.")

with st.sidebar:
    st.markdown("## MethaneWatch")
    section = st.radio("Sections", ["Overview", "Explore map", "Observations", "Analytics", "Data and methods", "About"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Filter observations**")

st.title("MethaneWatch")
st.markdown("**Satellite methane observations, from detection to usable data.**")
st.caption("An independent data engineering demonstration using public Carbon Mapper observations. Historical sample, not a live alert service.")

if not file.exists():
    st.info("No observation dataset is available. Run the ingestion pipeline locally or add a licensed demo release in data/demo/.")
    st.stop()

try:
    df = read_data(str(file), file.stat().st_mtime).copy()
except (pd.errors.EmptyDataError, ValueError, OSError) as exc:
    st.error(f"Could not load observation data: {exc}")
    st.stop()

for key in ["latitude", "longitude", "flux_tph", "flux_uncertainty_tph"]:
    if key not in df.columns:
        df[key] = np.nan
    df[key] = pd.to_numeric(df[key], errors="coerce")
for key in ["detection_id", "platform", "instrument", "sector", "provider"]:
    if key not in df.columns:
        df[key] = ""
df["observed_at"] = pd.to_datetime(df.get("observed_at", pd.Series(dtype=str)), errors="coerce", utc=True)
df["sector"] = df["sector"].fillna("Unspecified").astype(str).replace({"": "Unspecified", "nan": "Unspecified"})
df["platform"] = df["platform"].fillna("Unspecified").astype(str).replace({"": "Unspecified", "nan": "Unspecified"})

with st.sidebar:
    platforms = sorted(df["platform"].unique().tolist())
    sectors = sorted(df["sector"].unique().tolist())
    selected_platforms = st.multiselect("Satellite platform", platforms, default=platforms)
    selected_sectors = st.multiselect("Reported sector code", sectors, default=sectors)
    flux_max = float(max(0, df["flux_tph"].max())) if df["flux_tph"].notna().any() else 0.0
    minimum_flux = st.slider("Minimum observed flux (t/h)", min_value=0.0, max_value=max(0.1, round(flux_max, 1)), value=0.0, step=0.1)
    valid_dates = df["observed_at"].dropna()
    if len(valid_dates):
        start_date, end_date = valid_dates.min().date(), valid_dates.max().date()
        if start_date < end_date:
            chosen_dates = st.date_input("Observation period", value=(start_date, end_date), min_value=start_date, max_value=end_date)
        else:
            st.caption(f"Observation date: {start_date}")
            chosen_dates = (start_date, end_date)
    else:
        chosen_dates = ()
    st.divider()
    st.caption("Data: Carbon Mapper. This sample does not represent complete global coverage.")

filtered = df[df["platform"].isin(selected_platforms) & df["sector"].isin(selected_sectors)].copy()
filtered = filtered[filtered["flux_tph"].ge(minimum_flux) & filtered["flux_tph"].notna()]
if len(chosen_dates) == 2:
    low, high = pd.Timestamp(chosen_dates[0], tz="UTC"), pd.Timestamp(chosen_dates[1], tz="UTC")
    filtered = filtered[filtered["observed_at"].between(low, high + pd.Timedelta(days=1), inclusive="left")]

count = len(filtered)
flux = filtered["flux_tph"].dropna()
flux_unc = filtered["flux_uncertainty_tph"].dropna()
period = "Not available"
if filtered["observed_at"].notna().any():
    dates = filtered["observed_at"].dropna()
    period = dates.min().strftime("%d %b %Y") if dates.min().date() == dates.max().date() else f"{dates.min():%d %b %Y} to {dates.max():%d %b %Y}"


def cards():
    cols = st.columns(4)
    cols[0].metric("Selected detections", f"{count:,}")
    cols[1].metric("Median observed flux", f"{flux.median():,.2f} t/h" if len(flux) else "N/A")
    cols[2].metric("Largest observed flux", f"{flux.max():,.2f} t/h" if len(flux) else "N/A")
    cols[3].metric("Excluded by validation", str(meta.get("rejected_rows", "N/A")))


def map_panel():
    mapped = filtered.dropna(subset=["latitude", "longitude"]).copy()
    mapped = mapped[mapped["latitude"].between(-90, 90) & mapped["longitude"].between(-180, 180)]
    if mapped.empty:
        st.info("No mapped observations match the filters.")
        return
    mapped["flux_label"] = mapped["flux_tph"].map(lambda x: f"{x:,.3f} t/h" if pd.notna(x) else "Not reported")
    mapped["unc_label"] = mapped["flux_uncertainty_tph"].map(lambda x: f"±{x:,.3f} t/h" if pd.notna(x) else "Not reported")
    mapped["date_label"] = mapped["observed_at"].dt.strftime("%d %b %Y, %H:%M UTC").fillna("Unknown")
    layer = pdk.Layer("ScatterplotLayer", data=mapped, get_position="[longitude, latitude]", get_radius=16000,
                      radius_min_pixels=5, radius_max_pixels=11, get_fill_color=[213, 88, 58, 205],
                      get_line_color=[255, 255, 255, 180], line_width_min_pixels=1, stroked=True,
                      pickable=True, auto_highlight=True)
    view = pdk.ViewState(latitude=12, longitude=0, zoom=1.1)
    tip = {"html":"<b>Methane plume observation</b><br/>ID: {detection_id}<br/>Observed: {date_label}<br/>Flux: {flux_label}<br/>Reported uncertainty: {unc_label}<br/>Satellite: {platform}<br/>Sector code: {sector}",
           "style":{"backgroundColor":"#14283b","color":"#fff","fontSize":"12px"}}
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view, map_style=None, tooltip=tip), use_container_width=True)
    st.caption("Dots represent reported observation locations, not plume footprints. Hover over a marker for details.")


def chart_row():
    a,b,c = st.columns([1.3,1,1])
    with a:
        st.markdown("#### Observed methane flux")
        if len(flux):
            counts, edges = np.histogram(flux.to_numpy(), bins=min(12, max(2, int(np.sqrt(len(flux))))))
            hist = pd.DataFrame({"Flux range (t/h)": [f"{edges[i]:.2f}–{edges[i+1]:.2f}" for i in range(len(counts))], "Detections":counts})
            st.bar_chart(hist, x="Flux range (t/h)", y="Detections", color="#468875", use_container_width=True)
        else:
            st.caption("No flux values in the current selection.")
    with b:
        st.markdown("#### Detections by sector")
        if count:
            sectors_count = filtered["sector"].value_counts().head(8).rename_axis("Sector code").reset_index(name="Detections")
            st.bar_chart(sectors_count, x="Sector code", y="Detections", color="#468875", horizontal=True, use_container_width=True)
    with c:
        st.markdown("#### Detections by satellite")
        if count:
            sat = filtered["platform"].value_counts().rename_axis("Platform").reset_index(name="Detections")
            st.bar_chart(sat, x="Platform", y="Detections", color="#597c98", use_container_width=True)
    st.caption("Sector values are original provider codes. Counts reflect only the selected sample and should not be interpreted as sector-wide emissions.")


def top_table():
    st.markdown("#### Largest observed plumes in this sample")
    st.caption("Ranked by observed methane flux. These are individual detections, not persistent sources or annual emitters.")
    cols = [k for k in ["detection_id","observed_at","platform","sector","flux_tph","flux_uncertainty_tph"] if k in filtered]
    st.dataframe(filtered.nlargest(min(10,count),"flux_tph")[cols], use_container_width=True, hide_index=True,
                 column_config={"flux_tph":st.column_config.NumberColumn("Flux (t/h)",format="%.3f"),"flux_uncertainty_tph":st.column_config.NumberColumn("Uncertainty (t/h)",format="%.3f")})


def methods():
    st.markdown("### Data and methods")
    st.markdown("""**Original observations.** Carbon Mapper provides the historical satellite methane plume records used in this demonstration. The dashboard displays a small sample rather than a global inventory.\n\n**Processing.** A Python workflow normalizes source identifiers, coordinates, timestamps and methane flux measurements. It validates required fields, separates rejected records and writes CSV, GeoJSON and processing metadata.\n\n**Units.** Observed flux and its reported uncertainty are converted from kilograms per hour to tonnes per hour.\n\n**Interpretation.** Each record is a point-in-time plume observation. A detected plume does not establish that its source emits continuously. The data shown here are not sufficient to calculate source persistence or verified annual emissions.\n\n**Scope.** This independent demonstration is not affiliated with or endorsed by UNEP, IMEO or Carbon Mapper.""")
    st.markdown("**Source:** [Carbon Mapper](https://data.carbonmapper.org/)  |  **Terms:** [Carbon Mapper Terms of Use](https://carbonmapper.org/terms)")
    with st.expander("Processing record and validation"):
        st.json(meta)
        quarantine = root / "quarantine.csv"
        if quarantine.exists():
            st.dataframe(pd.read_csv(quarantine), use_container_width=True, hide_index=True)
        else:
            st.caption("Quarantine records are not included in the public demonstration release.")


def downloads():
    st.markdown("### Download data")
    st.caption("Data by Carbon Mapper®. Normalized for this independent demonstration. Original data restrictions continue to apply.")
    items = [("plumes.csv","CSV","text/csv"),("plumes.geojson","GeoJSON","application/geo+json"),("run_manifest.json","Run metadata","application/json")]
    buttons = st.columns(3)
    for col, (name, label, mime) in zip(buttons,items):
        path = root / name
        if path.exists():
            col.download_button(f"Download {label}", path.read_bytes(), file_name=name, mime=mime, use_container_width=True)
    st.markdown("[Data terms](https://carbonmapper.org/terms)  |  [Source dataset](https://data.carbonmapper.org/)")

if section == "Overview":
    st.caption(f"{count:,} of {len(df):,} validated observations selected  |  {period}  |  Satellite observations, not live monitoring")
    cards()
    st.markdown("### Observation map")
    map_panel()
    chart_row()
    top_table()
    downloads()
elif section == "Explore map":
    st.markdown("### Observation map")
    st.caption(f"{count:,} locations in the current selection. Filters are available in the sidebar.")
    map_panel()
    top_table()
elif section == "Observations":
    st.markdown("### Validated observations")
    st.caption(f"{count:,} records selected from {len(df):,} validated observations.")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    downloads()
elif section == "Analytics":
    st.markdown("### Sample statistics")
    cards()
    chart_row()
    top_table()
elif section == "Data and methods":
    methods()
    downloads()
else:
    st.markdown("### About MethaneWatch")
    st.write("MethaneWatch is an independent portfolio project showing how public satellite methane observations can be ingested, validated, explored and published through a reproducible Python workflow.")
    st.write("The current release is a demonstration dataset and viewer. It does not operate an alerting service or a validated annual emissions inventory.")
    st.write("Data by Carbon Mapper®. This project is not affiliated with UNEP, IMEO or Carbon Mapper.")
    methods()
