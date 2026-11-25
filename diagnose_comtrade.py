"""Run from tracker root with its existing virtualenv. No API key printed."""
import os
import json
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
key = os.getenv('COMTRADE_API_KEY', '').strip()
if not key:
    raise SystemExit('COMTRADE_API_KEY not found. Put diagnose_comtrade.py beside app.py and .env.')
BASE = 'https://comtradeapi.un.org/data/v1/'
base = dict(reporterCode='156', period='202503', flowCode='X')
world = dict(partnerCode='0', partner2Code='0', customsCode='C00', motCode='0')
checks = [
 ('China_monthly_availability', 'getDa/C/M/HS', dict(reporterCode='156', period='202501,202502,202503')),
 ('China_tariffline_availability', 'getDaTariffline/C/M/HS', dict(reporterCode='156', period='202501,202502,202503')),
 ('China_battery_monthly_control', 'get/C/M/HS', dict(base, **world, cmdCode='850760', breakdownMode='classic', maxRecords=20)),
 ('China_battery_annual_control', 'get/C/A/HS', dict(base, **world, period='2024', cmdCode='850760', breakdownMode='classic', maxRecords=20)),
 ('Korea_battery_monthly_control', 'get/C/M/HS', dict(base, **world, reporterCode='410', cmdCode='850760', breakdownMode='classic', maxRecords=20)),
 ('China_parent_tracker_filters', 'get/C/M/HS', dict(base, cmdCode='285390', partner2Code='0', customsCode='C00', motCode='0', maxRecords=250000)),
 ('China_parent_classic_world', 'get/C/M/HS', dict(base, **world, cmdCode='285390', breakdownMode='classic', maxRecords=20)),
 ('China_parent_no_dimension_filters', 'get/C/M/HS', dict(base, cmdCode='285390', maxRecords=20)),
 ('China_NCM_8digit', 'getTariffline/C/M/HS', dict(base, cmdCode='28539030', maxRecords=20)),
 ('China_NCM_10digit', 'getTariffline/C/M/HS', dict(base, cmdCode='2853903000', maxRecords=20)),
 ('China_NCM_annual_8digit', 'getTariffline/C/A/HS', dict(base, period='2024', cmdCode='28539030', maxRecords=20)),
 ('China_NCM_annual_10digit', 'getTariffline/C/A/HS', dict(base, period='2024', cmdCode='2853903000', maxRecords=20)),
]
# These are diagnostic samples, not complete trade extracts.
results = []
with requests.Session() as session:
    for name, endpoint, params in checks:
        result = dict(test=name, endpoint=BASE+endpoint, params=params)
        try:
            r = session.get(BASE+endpoint, params=params, headers={'Ocp-Apim-Subscription-Key': key}, timeout=(10, 60))
            result['http'] = r.status_code
            try:
                body = r.json()
            except ValueError:
                body = {'non_json_response': r.text[:800]}
            if isinstance(body, dict):
                data = body.get('data')
                result['count'] = body.get('count')
                result['rows'] = len(data) if isinstance(data, list) else None
                result['response_metadata'] = {k:v for k,v in body.items() if k != 'data'}
                result['sample_rows'] = data[:3] if isinstance(data, list) else []
            else:
                result['unexpected_response'] = str(body)[:800]
        except requests.RequestException as e:
            result['exception'] = str(e)
        # Strip credential even if an unusual server response echoes it.
        result = json.loads(json.dumps(result, default=str).replace(key, '[REDACTED]'))
        results.append(result)
        print(f"{name}: HTTP {result.get('http', 'failed')} | count={result.get('count')} | rows={result.get('rows')}" , flush=True)
        if result.get('exception'):
            print('  ', result['exception'], flush=True)
        if result.get('http') in (401, 403, 429):
            print('Stopping: authentication/permission/quota response. Check saved diagnostic.', flush=True)
            break
        time.sleep(1.2)
out = ROOT / 'data' / 'comtrade_diagnostics.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'\nSaved {len(results)} diagnostic results to {out}')
