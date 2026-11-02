# Flood & Wetland Change Map

A Streamlit MVP for emergency-management analysts to explore NISAR Level 2 GCOV
observations and compare radar backscatter before and after an event.

The app can search ASF for provisional NISAR GCOV products, download a selected
before-and-after pair, or analyze two GCOV HDF5 files already on disk. It subsets
the scenes to the chosen bounding box, compares a selected polarization in
decibels, displays before/after views and a color-coded change map, and exports
GeoTIFF layers, a PNG map, and a text summary.

> **Interpretation:** A backscatter difference is a potential surface-change
> indicator, not a confirmed flood boundary, wetland change, or damage assessment.
> Validate findings with independent reference data and domain expertise.

## Run locally

Use Python 3.11 or newer. From this project directory:

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

### Linux, macOS, or WSL

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) to open in
your browser.

## Workflow

1. Set the study-area bounding box in the sidebar. The initial values are an
   example from the NISAR Cookbook; replace them with the event location.
2. In **Search & download from ASF**, enter your Earthdata Login credentials,
   choose before/after date windows, and search. Credentials are passed to the
   local Streamlit process for ASF requests and are not saved to project files.
   Run this app only on a trusted machine; never enter credentials into a
   publicly hosted or untrusted deployment.
3. Choose one scene from each period and download the pair. GCOV products can
   be large, so allow time and disk space for both downloads.
4. In **Analyze local scenes**, choose the downloaded files and a polarization,
   then analyze potential change. The analysis view shows before/after
   backscatter side by side and a color-coded change map. Alternatively, put
   two `.h5` GCOV files in `data/scenes` and analyze them without using the ASF
   search.
5. Download the before, after, and change GeoTIFFs for GIS use, or download the
   displayed PNG map and text summary for sharing.

The search defaults match the Cookbook’s example acquisition window. Change the
dates and bounds to suit your event; a search may return no suitable scenes.

## Data and method notes

- ASF search is limited to provisional NISAR GCOV products, production
  configuration `PR`, and excludes `QA_STATS` companion files.
- ASF returns radar scenes, not flood- or wetland-labeled products. The
  exploratory SAR-only screening uses a user-adjustable low-backscatter cutoff:
  a strong decrease ending below that cutoff is marked as a possible new
  inundation candidate, while low backscatter in both scenes is shown as a
  persistent water-like proxy. These simple rules are not a validated flood
  detector or wetland map; they can miss flooded vegetation and confuse water
  with shadows or other dark surfaces.
- The app reads the GCOV HDF5 grid and polarization dataset, crops to the
  selected bounding box, and calculates `after - before` backscatter change in
  dB. It highlights pixels whose absolute change meets the selected threshold.
- The estimate is based on the product grid pixel spacing. It is a screening
  aid, not an accuracy or uncertainty estimate.
- The exported PNG uses grid row/column axes; the interactive map is located
  geographically. For operational use, add independent flood/wetland reference
  layers, quality checks, acquisition-time review, and validation.
- GeoTIFF exports contain backscatter in dB for the aligned before/after scenes
  and the after-minus-before difference, with the map grid's CRS and transform.

## References

- [NISAR Cookbook](https://asfopensarlab.github.io/NISAR_Cookbook/)
- [ASF `asf_search`](https://github.com/asfadmin/Discovery-asf_search)
- [NISAR GCOV Product Specification](https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102274_RevE_NASA_SDS_Product_Specification_L2_GCOV_Nov8_2024_w-sigs.pdf)
