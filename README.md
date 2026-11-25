# pCAM Market Intelligence v3.4 — frequency-aware corrected MVP

This release upgrades v3.3 in place. The financial-market HTML interface and analytical outputs remain; acquisition, availability discovery, cleaning and annual analytics are corrected. Live API requests use the user's own key and network. No key, live production data, or old cache is shipped.

## Upgrade the existing Windows project (recommended)

1. Stop the server (Ctrl+C). Back up the project. Extract this ZIP **into the existing project directory**, replacing matching code files. The ZIP is flat (app.py at its root). Keep your private `.env`, `.venv` and `data/` directories. `.gitignore` is included; review it if you have project-specific rules. No `.env` file is in the ZIP.
2. In the existing activated virtual environment, run:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q test_mvp.py
python app.py
```

If the virtual environment is not activated, substitute `.\.venv\Scripts\python.exe` for `python` in all commands. Or use `start_windows.bat` for a fresh installation. Python 3.11 or 3.12 recommended. macOS/Linux: `sh start_mac_linux.sh`.

3. Open http://127.0.0.1:8765 and refresh (Ctrl+F5). Confirm V3.4 and API key configured. The app binds to localhost only. Old saved runs remain accessible, but are flagged as legacy: do not use their old aggregation for decisions. Re-retrieve into a new run. New raw snapshots are separate in `data/cache_v34/`.

## First live acceptance test: known working annual query

| Field | Value |
|---|---|
| Target codes | `156:28539030` |
| Reporter | China (156) only |
| Reporting frequency | Annual |
| Start / end | 2024 / 2024 |
| Flow | Exports |
| Partner codes | blank (all returned) |
| Budget | 10 |
| Synthetic demo | unchecked |
| Refresh cache | checked |

Preview plan, then Retrieve data. In the supplied independent diagnostic, this query returned 20 records at a deliberately small cap of 20. The new query requests up to 100,000 records with a key; actual response and cleaned partner counts will differ. The three visible sample records for Belgium aggregate to 543 kg, USD 9,500, weighted USD/kg 17.4954; they are only a partial sample, not full Belgian or Chinese exports. The new cleaner must retain their multiplicity. Review Request audit, Raw API snapshots, bilateral table and the current KPIs. Do not expect the full live result to equal that sample. For national tariff lines the interface disables reported world scope. An empty response is not zero trade.

If successful, extend the annual history (e.g. 2020–2025), then add `156:28539050` and imports. Verify each code's historical applicability and actual coverage. Run South Korea separately for monthly availability with its appropriate classification (proxy only until verified). Use the six-digit 850760 control to check the standard API, not as a pCAM product.

## API key and Git

The engine automatically loads `.env` next to engine.py, so app.py and cli.py share the key. Existing environment variables take priority. For a new installation, copy `.env.example` to `.env`, enter `COMTRADE_API_KEY=your_key` locally and never commit it. The API key goes in the Ocp-Apim-Subscription-Key header, not URLs or saved snapshots. Check `git check-ignore -v .env` and `git ls-files -- .env` (the latter should be empty). If already tracked, remove from Git tracking and rotate the exposed key if committed.

## Interactive operation

- HS registry search, official UN six-digit reference lookup, and custom codes. National codes must be reporter-specific (`reporter:code`). China defaults NCM 28539030 and NCA 28539050 (aliases 2853903000/2853905000). Korean 2825902090 and US 2825909000 are optional broad proxies; international 285390/282590 are broad proxies. Registry labels are candidate mappings; confirm country, year and nomenclature before using business conclusions. The diagnostic demonstrated the eight-digit China NCM code for 2024 only. Oxidized precursors and other country-specific mappings are not verified.
- **Annual:** whole completed calendar years; no monthly interpolation. **Monthly:** completed calendar months. **Auto:** check dataset availability, prioritize listed periods and retrieve separate annual and monthly series for the selected range within budget. Whole completed annual years overlapping the range are included, even if only some months were selected. The view defaults to a nonempty monthly series when available for the selected product/flow, otherwise a nonempty annual series. Switch using the view's Frequency selector. Annual and monthly data are never added together. Auto is not a guarantee of completeness; select explicit frequency to minimize requests.
- **Check dataset availability:** independent query for standard/tariff-line dataset metadata (annual and monthly), listed periods, most recent release and code lengths if available. Availability is not commodity-level evidence; empty/unknown metadata does not prove no trade. Auto saves availability summaries and raw metadata snapshots. Budget includes those calls. Explicit annual/monthly mode does not pre-query availability automatically, but the button remains available.
- **Preview plan:** request budget including possible aliases and discovery calls. Run persists independently in `data/runs`. Choose a historical run, product, direction, frequency, time range, scope and partners; Apply filters updates the displayed analysis. No merging of old/new snapshots or unrelated codes.
- Charts: annual/monthly volume and value, weighted unit values, indexed trajectories, partner ranks, shares, concentration, Sankey, maps, heatmaps, growth contribution, matched price-volume bridge, market screening, coverage, conditional mirror check. Monthly mode additionally includes MoM, rolling 12 months, seasonality and a conditional seasonal-naive trade scenario. Annual mode uses YoY and no monthly-specific charts. Chart availability depends on usable data and comparison periods. Maps may need internet for Plotly topology; other charts load locally. No demand forecasts claimed.
- Exports: standalone interactive HTML (browser Print / save PDF), Excel analytical tables, full-run clean CSV, audit CSV and JSON. Raw API snapshots downloadable from Supporting data. Reports/Excel follow the last applied filters. CSV/JSON represent full run, with explicit frequency and contributing source row counts. Data are local.

## Data acquisition and integrity

Authenticated standard API `/data/v1/get/C/{A|M}/HS` uses classic dimensions; tariff-line `/data/v1/getTariffline/C/{A|M}/HS` omits standard total-dimension filters. Public preview equivalents available without a key. Free registered account limits are 100,000 records/call and 500 calls/day; public preview 500 records. Limit is conservative for paid accounts too. Capped or inconsistent responses are withheld, not plotted as complete; narrow by partner if necessary. No pagination/bulk or automated daily quota accounting. Budget counts cache attempts as well as actual requests; three consecutive request errors halt further data retrieval. Connection/read timeouts are 8/75 seconds. No automatic retry loop; rerun after transient errors. Key must have appropriate entitlements.

Raw successful responses (including empty results) are retained as content-addressed snapshots with HTTP code, request parameters, retrieval timestamp and response metadata. Cache index expires after 24 hours; Refresh creates a new snapshot without overwriting historical raw evidence. Request audit reports status, raw/used/clean row counts, exclusions/conflicts, queried alias, response metadata and raw IDs. Aliases are tried only if the previous returned no records; never added together. If aliases are complementary, coverage is not guaranteed; check source codes separately outside family mapping. Do not add standard world totals to bilateral sums.

Tariff-line records can originate from finer-grained datasets, so even identical-looking records can be legitimate. Preserve their multiplicity within the one fetched response. Aggregate by period/reporter/product/flow/partner. Exclude apparent overlapping total/unknown and detailed dimensions or mixed classifications rather than risk double counting. Standard data selects one classic total-dimension aggregate per partner, after exact duplicate removal. Unknown tariff-line partner codes remain separately flagged; their country/region type and geography are not verified. Standard data with unknown partners are excluded and audited. Tariff-line world totals are not inferred; observed partner sums may be partial. Numeric fields are not assumed zero when missing. Net weight kg, primary value USD; weighted unit value sums matched values divided by matched positive net weight. Partial weights/values and estimation flags are exposed. All source fields (quantity units, FOB/CIF, transport/customs dimensions, etc.) remain in raw snapshots; not all are normalized into the business tables. No trade transaction identities exist in these records.

Sources: https://comtrade.un.org/en/api-docs ; https://uncomtrade.org/docs/what-is-tariffline-data/ ; https://uncomtrade.org/docs/data-availability/ ; https://comtrade.un.org/en/subscriptions .

## Command line

```powershell
python cli.py --hs 156:28539030 --reporters 156 --frequency A --start 2024 --end 2024 --flows X --plan
python cli.py --hs 156:28539030 --reporters 156 --frequency A --start 2024 --end 2024 --flows X --refresh
python cli.py --hs 156:28539030 --reporters 156 --frequency A --start 2024 --end 2024 --discover
python cli.py --hs 850760 --reporters 410 --frequency M --start 2025-03 --end 2025-03 --flows X
python cli.py --hs 156:28539030 --reporters 156 --frequency auto --start 2024-01 --end 2025-12 --flows X --budget 100
python cli.py --hs 156:28539030 --reporters 156 --frequency A --start 2020 --end 2025 --flows X --demo
```

CLI saves dashboard runs; nonzero exit (2) flags unusable/incomplete live acquisition. Web UI preserves incomplete runs for inspection.

## Validation and limitations

`python -m pytest -q test_mvp.py` tests the planner, aliases, annual and monthly analytics, real diagnostic sample aggregation, preserved exact tariff-line repeats, overlap rejection, partial weight handling, standard aggregate, mock annual request route, availability parser, auto separation and request budget. The fixture contains ONLY the five supplied visible sample records (three tariff lines, two control records); it is not a full trade dataset and is never loaded automatically into the dashboard. Local HTTP API and HTML/XLSX/CSV/JSON exports were tested with mocked retrieval returning the actual tariff-line sample. JavaScript syntax checked. Live API requests using your key and full browser rendering have not been verified in the build environment. Run the acceptance test above on your machine before using the application for management. Actual 2025/2026 Chinese monthly data may still not be available; annual records cannot substitute for monthly monitoring. Publication and historical comparisons require dataset coverage and nomenclature review. No company-level shipments, customers, contract pricing, tax rules, global pCAM market-size claims, commercial profitability, or full Datamyne replacement. No premium bulk retrieval, automated scheduling, or multi-user authentication. No LME/SMM/Datamyne adapter.
