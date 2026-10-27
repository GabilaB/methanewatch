"""Auditable methane plume ingestion and publication prototype.

Conservative mapping: never guess that unrecognized numeric fields are methane flux.
Historical records are not presented as live detections.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import truststore
truststore.inject_into_ssl()
import argparse
import hashlib
import json
import logging
import pandas as pd
import requests

LOG = logging.getLogger('methanewatch')
# Explicitly reviewed Carbon Mapper field names; changes must be confirmed in the data dictionary.
ALIASES = {
    'id': ['plume_id', 'plume_name', 'id'],
    'time': ['scene_timestamp', 'observation_timestamp', 'plume_date', 'datetime', 'timestamp', 'observation_date'],
    'lat': ['latitude', 'lat', 'plume_latitude'],
    'lon': ['longitude', 'lon', 'plume_longitude'],
    'flux': ['emission_auto', 'emission', 'flux_tph'],
    'source': ['source_id', 'source_name'],
}
OUTPUT_COLUMNS = ['detection_id','observed_at','latitude','longitude','flux_tph','source_id','provider','quality_status','quality_reason','flux_uncertainty_tph','instrument','platform','gas','sector','plume_quality']

def read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower()=='.csv':
        return pd.read_csv(path, low_memory=False)
    if path.suffix.lower() in ('.json', '.geojson'):
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,dict) and data.get('type')=='FeatureCollection':
            rows=[]
            for feature in data['features']:
                props=dict(feature.get('properties') or {})
                geom=feature.get('geometry') or {}
                if geom.get('type')=='Point' and len(geom.get('coordinates') or [])>=2:
                    props.setdefault('longitude',geom['coordinates'][0]);props.setdefault('latitude',geom['coordinates'][1])
                rows.append(props)
            return pd.DataFrame(rows)
        if isinstance(data,dict) and isinstance(data.get('items'),list):
            rows=[]
            for item in data['items']:
                row=dict(item)
                geom=row.get('geometry_json') or {}
                if isinstance(geom,str):
                    try: geom=json.loads(geom)
                    except json.JSONDecodeError: geom={}
                if isinstance(geom,dict) and geom.get('type')=='Point':
                    coords=geom.get('coordinates')
                    if isinstance(coords,(list,tuple)) and len(coords)>=2:
                        row['longitude']=coords[0]
                        row['latitude']=coords[1]
                rows.append(row)
            return pd.DataFrame(rows)
        if isinstance(data,list):return pd.json_normalize(data,sep='_')
        raise ValueError('Unsupported JSON layout. Inspect the raw schema first.')
    raise ValueError('Supported file types: CSV, JSON and GeoJSON')

def _get(df:pd.DataFrame,key:str):
    col=next((c for c in ALIASES[key] if c in df.columns),None)
    return df[col] if col else pd.Series([None]*len(df),index=df.index)

def normalize(df:pd.DataFrame, provider:str, *, flux_field:str|None=None, flux_unit:str|None=None)->pd.DataFrame:
    if df.empty: return pd.DataFrame(columns=OUTPUT_COLUMNS)
    if flux_field and flux_field not in df.columns: raise ValueError(f'Unknown flux field: {flux_field}')
    if flux_field and flux_unit not in ('kg/h','t/h'):raise ValueError('Explicit flux unit required: kg/h or t/h')
    out=pd.DataFrame(index=df.index)
    ids=_get(df,'id')
    out['detection_id']=[str(v).strip() if pd.notna(v) and str(v).strip() else f'{provider}:{i}' for i,v in zip(df.index,ids)]
    out['observed_at']=pd.to_datetime(_get(df,'time'),utc=True,errors='coerce')
    out['latitude']=pd.to_numeric(_get(df,'lat'),errors='coerce')
    out['longitude']=pd.to_numeric(_get(df,'lon'),errors='coerce')
    # Flux is nullable unless a field and its unit have been EXPLICITLY confirmed.
    out['flux_tph']=pd.to_numeric(df[flux_field],errors='coerce') * (0.001 if flux_unit=='kg/h' else 1.0) if flux_field else float('nan')
    out['source_id']=_get(df,'source').astype('string')
    # Preserve optional sensor and uncertainty metadata; never invent a source ID.
    optional={'instrument':'instrument','platform':'platform','gas':'gas','sector':'sector','plume_quality':'plume_quality'}
    for target,source in optional.items():
        out[target]=df[source].astype('string') if source in df else pd.Series(pd.NA,index=df.index,dtype='string')
    if flux_field=='emission_auto' and 'emission_uncertainty_auto' in df:
        out['flux_uncertainty_tph']=pd.to_numeric(df['emission_uncertainty_auto'],errors='coerce')*(0.001 if flux_unit=='kg/h' else 1.0)
    else:
        out['flux_uncertainty_tph']=float('nan')
    out['provider']=provider
    reasons=[]
    for _,r in out.iterrows():
        errors=[]
        if pd.isna(r['observed_at']):errors.append('invalid_timestamp')
        if pd.isna(r['latitude']) or not -90<=r['latitude']<=90:errors.append('invalid_latitude')
        if pd.isna(r['longitude']) or not -180<=r['longitude']<=180:errors.append('invalid_longitude')
        if pd.notna(r['flux_tph']) and r['flux_tph']<0:errors.append('negative_flux')
        if pd.notna(r['flux_uncertainty_tph']) and r['flux_uncertainty_tph']<0:errors.append('negative_uncertainty')
        reasons.append('|'.join(errors))
    out['quality_reason']=reasons

