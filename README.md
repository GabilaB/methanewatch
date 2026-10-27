# MethaneWatch
Independent engineering prototype for ingesting, validating and publishing public satellite methane detection records. **Not affiliated with UNEP, IMEO or Carbon Mapper.** Historical data, not live alerts.

## Quick start (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python -m methanewatch.pipeline --fetch-carbonmapper --limit 100
streamlit run app.py
```
If PowerShell blocks activation: use `.venv\Scripts\python.exe -m pip install -r requirements.txt` and substitute that executable in subsequent commands.

If the Carbon Mapper API rejects the request or its schema has changed, inspect `https://api.carbonmapper.org/api/v1/docs`, download UNEP's CSV or GeoJSON from `https://methanedata.unep.org/download-dataset` into `data/raw/`, and run:
```powershell
python -m methanewatch.pipeline --input data/raw/your_download.csv --provider imeo
```
**Important:** Different providers use different field names. The prototype deliberately rejects invalid/missing key geolocation and date columns. Inspect the CSV headers before extending `ALIASES` in `methanewatch/pipeline.py`. Flux output stays null until its column and units are verified. Example after verification: `--flux-field emission --flux-unit kg/h`.

For JupyterLab: `jupyter lab`, then open `notebooks/01_data_reconnaissance.ipynb`.

## What works in this initial starter
- CSV, point GeoJSON and JSON API ingestion
- Source snapshot checksum, UTC processing time and metadata manifest
- Validation of time, latitude, longitude and nonnegative explicitly mapped flux
- Provider-scoped identifier deduplication and rejected-record quarantine
- Validated CSV/GeoJSON products and simple Streamlit map/monitor
- pytest unit/integration tests and GitHub Actions CI
- A draft PostGIS schema for the next stage

## Not yet implemented
The starter does **not** claim operational PostGIS integration, automated persistent event grouping, observed persistence estimation, annual emissions estimation, or continuously scheduled production ingestion. These are the next modules, contingent on verifying schema and observation opportunities. Do not describe them as completed in an application.

## Methodological caution
Detection frequency is not equivalent to emissions persistence, and annualization requires defensible exposure/opportunity information and uncertainty assumptions. Do not calculate annual emissions from repeat detections alone. Do not describe the public release as an official MARS product.

## Licensing and citations
- UNEP IMEO Eye on Methane: https://methanedata.unep.org/download-dataset . Source materials are generally CC BY-NC-SA 4.0. Preserve attribution, license and share-alike obligations and verify terms for each dataset.
- Carbon Mapper: https://api.carbonmapper.org/api/v1/docs . Follow its attribution and access requirements, respect rate limits and verify rights before public redistribution.

Do not commit private data, credentials or large datasets. Public hosting of derived data requires license review.
