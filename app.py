"""MethaneWatch public exploration interface for reproducible snapshot releases."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title='MethaneWatch | Satellite Methane Data Engineering',layout='wide')
st.title('MethaneWatch')
st.caption('Independent scientific data engineering demonstration. Not affiliated with UNEP or Carbon Mapper. Historical records, not a live methane alert service.')
root=Path('data/processed')
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
        st.map(df.dropna(subset=['latitude','longitude']),latitude='latitude',longitude='longitude')
    st.subheader('Validated observations')
    st.dataframe(df,use_container_width=True)
else:st.warning('No valid detections were ingested; inspect quarantine and confirm field mapping.')
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
