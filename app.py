"""MethaneWatch public exploration interface for reproducible snapshot releases."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import pydeck as pdk

st.set_page_config(page_title='MethaneWatch | Satellite Methane Data Engineering',layout='wide')
st.title('MethaneWatch')
st.caption('Independent scientific data engineering demonstration. Not affiliated with UNEP or Carbon Mapper. Historical records, not a live methane alert service.')
root = (
    Path('data/processed')
    if Path('data/processed/plumes.csv').exists()
    else Path('data/demo')
)
file=root/'plumes.csv'
manifest=root/'run_manifest.json'
if not file.exists():
    st.info('No processed dataset yet. Run `python -m methanewatch.pipeline --fetch-carbonmapper` in your terminal, or use `--input data/raw/yourfile.csv --provider imeo`.')
    st.stop()
meta=json.loads(manifest.read_text()) if manifest.exists() else {}
try:df=pd.read_csv(file)
except pd.errors.EmptyDataError:df=pd.DataFrame()
a,b,c,d=st.columns(4)
a.metric('Accepted detections',meta.get('accepted_rows',len(df)))
b.metric('Quarantined',meta.get('rejected_rows','N/A'))
c.metric('Duplicates identified',meta.get('duplicate_rows','N/A'))
d.metric('Data provider',meta.get('provider','Unknown'))
st.caption(f"Processed: {meta.get('run_utc','unknown')} | Input SHA256: {meta.get('sha256','unknown')} | Not real-time")
if not df.empty:
    if {'latitude','longitude'}.issubset(df.columns):
        st.subheader('Satellite detections')
        map_df = df.dropna(subset=["latitude", "longitude"]).copy()

        map_df["flux_display"] = map_df["flux_tph"].apply(
            lambda x: f"{x:.3f} t/h" if pd.notna(x) else "Not available"
        )
        map_df["uncertainty_display"] = map_df["flux_uncertainty_tph"].apply(
            lambda x: f"±{x:.3f} t/h" if pd.notna(x) else "Not available"
        )
        map_df["observed_display"] = map_df["observed_at"].astype(str)

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_df,
            get_position="[longitude, latitude]",
            get_radius=18000,
            radius_min_pixels=5,
            radius_max_pixels=12,
            get_fill_color=[206, 69, 48, 190],
            pickable=True,
            auto_highlight=True,
            id="methane-plumes",
        )

        deck = pdk.Deck(
            map_style=None,
            initial_view_state=pdk.ViewState(
                latitude=15,
                longitude=0,
                zoom=1.2,
                pitch=0,
            ),
            layers=[layer],
            tooltip={
                "html": """
                    <b>Satellite methane detection</b><br/>
                    <b>Plume:</b> {detection_id}<br/>
                    <b>Observed:</b> {observed_display}<br/>
                    <b>Flux:</b> {flux_display}<br/>
                    <b>Uncertainty:</b> {uncertainty_display}<br/>
                    <b>Satellite:</b> {platform}<br/>
                    <b>Sector:</b> {sector}
                """,
                "style": {
                    "backgroundColor": "#17283A",
                    "color": "white",
                    "fontSize": "12px",
                },
            },
        )

        st.pydeck_chart(deck, use_container_width=True)
    st.subheader('Validated observations')
    st.dataframe(df, use_container_width=True)
else:
    st.warning('No valid detections were ingested; inspect quarantine and confirm field mapping.')
st.subheader('Pipeline observability')
st.json(meta)
q=root/'quarantine.csv'
if q.exists():
    with st.expander('Quarantined records and failure reasons'):
        st.dataframe(pd.read_csv(q),use_container_width=True)
st.subheader('Reproducible public products')
for name,mime in [('plumes.csv','text/csv'),('plumes.geojson','application/geo+json'),('run_manifest.json','application/json')]:
    f=root/name
    if f.exists():st.download_button('Download '+name,f.read_bytes(),file_name=name,mime=mime)
st.caption('Source attribution and licensing must be preserved before publication of downloaded records. Flux is intentionally blank unless the field and unit are verified.')
