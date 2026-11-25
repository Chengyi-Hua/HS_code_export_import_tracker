"""Shared management-report presentation; no changes to numerical analysis."""
import html,json
import pandas as pd
import plotly.io as pio
from plotly.offline import get_plotlyjs

# Order by commercial question, not the order in which calculations run.
CHAPTERS=[
 ('trajectory','Market trajectory','Is trade activity expanding, and is value keeping pace?',[
 ('Monthly volume','Monthly trade volume and 12-month average, where enough data exist.',True),
 ('Annual volume','Full-year trade volume; no monthly interpolation.',True),
 ('Annual trade value','Customs trade value for whole calendar years.',False),
 ('Year-on-year','Growth against the preceding calendar year.',False),
 ('Monthly trade value','Customs trade value in US dollars.',False),
 ('Weighted customs','Weighted unit value from matched customs value and net weight; not contract pricing.',False),
 ('Volume, value','Common starting point makes changes across different units comparable.',True),
 ('Rolling 12','Trailing annual volume; requires 12 consecutive observations.',False),
 ('Month-on-month','Growth against the preceding month and the same month last year.',False),
 ('Seasonality','Monthly pattern across years; blanks indicate unavailable observations.',True)]),
 ('markets','Market footprint','Which trading partners matter most?',[
 ('Leading observed','Largest observed partners in the latest usable period; not global market shares.',False),
 ('Geographic footprint','Geographic footprint of the displayed observed trading partners.',False),
 ('Trade routes','Flow width represents observed tonnes on the displayed routes.',True),
 ('Partner heatmap','Track changes in bilateral trade activity across reporting periods.',True),
 ('Destination / origin','Partner shares within the observed trade universe.',False),
 ('Partner ranking','Changes in relative observed partner volume rank.',False),
 ('Market concentration','HHI and top-three share; higher concentration indicates a less diversified observed partner mix.',True)]),
 ('commercial','Commercial signals','Where should the commercial team investigate further?',[
 ('YoY growth contribution','Volume changes among matched partners only; unmatched routes are not treated as zero.',True),
 ('Market screening','Growth, unit value and bubble size (volume) are screening signals, not profitability estimates.',True),
 ('Partner unit values','Latest weighted customs unit values; product mix and valuation can differ.',False),
 ('Unit value dispersion','Distribution of observed partner unit values.',False),
 ('Unit value trends','Changes in weighted unit values across leading observed partners.',True),
 ('YoY matched','Matched price–volume decomposition; not a causal estimate.',True)]),
 ('risk','Risk & forward signals','Which changes merit attention, and what could a simple scenario look like?',[
 ('Unusual volume','Historical rolling z-score; thresholds flag unusual observations, not confirmed events.',False),
 ('Seasonal-naive','Prior-year seasonal pattern; illustrative trade-volume scenario, not a demand forecast.',False),
 ('Mirror trade','Same six-digit code only; differences may reflect reporting definitions and timing.',True)]),
 ('quality','Data reliability','What can be trusted, and what still needs checking?',[
 ('01 / Retrieval','Request-level availability by reporting period. Empty or failed requests are not zero trade.',True)])]

def sections(charts):
    out=[]; seen=set()
    for key,title,question,rules in CHAPTERS:
        cards=[]
        for prefix,caption,wide in rules:
            for i,f in enumerate(charts):
                if i not in seen and f['layout']['title']['text'].startswith(prefix):
                    cards.append(dict(index=i,caption=caption,wide=wide));seen.add(i)
        if cards:out.append(dict(id=key,title=title,question=question,cards=cards))
    extra=[dict(index=i,caption='Explore the underlying observations.',wide=False) for i in range(len(charts)) if i not in seen]
    if extra:out.append(dict(id='additional',title='Additional analysis',question='Further detail on the selected trade series.',cards=extra))
    return out

REPORT_CSS='''
:root{--navy:#14171B;--ink:#20242A;--muted:#58616C;--teal:#145A91;--line:#D6DBE0;--bg:#F2F4F6;--paper:#FFF;--canvas:#F2F4F6;--accent:#E7A126}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--canvas);color:var(--ink);font:13px/1.5 Arial,Helvetica,sans-serif;font-variant-numeric:tabular-nums}a{color:var(--teal)}h1,h2,h3{margin:0;font-weight:700}button,input,select,textarea{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus,select:focus,textarea:focus{outline:2px solid #2E78AD;outline-offset:2px}.eyebrow,.num,.number{font-size:10px;font-weight:700;letter-spacing:.65px;text-transform:uppercase;color:#646E78}.chapter{margin-top:24px;scroll-margin-top:55px}.chapter-head{display:grid;grid-template-columns:auto 1fr;align-items:baseline;column-gap:10px;border-top:2px solid #343A41;border-bottom:1px solid var(--line);padding:10px 0;margin-bottom:10px}.chapter-head .num,.chapter-head .number{color:#646E78;font-size:10px}.chapter-head h2{font-size:19px;line-height:1.3;letter-spacing:-.25px}.chapter-head p{grid-column:2;color:var(--muted);font-size:12px;margin:3px 0 0}.chartgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.chartcard{min-width:0;background:white;border:1px solid var(--line);border-radius:0;padding:3px 8px 10px;overflow:hidden}.wide{grid-column:1/-1}.chart-caption{margin:3px 10px 0;padding:7px 0 0;border-top:1px solid #E7EAED;color:var(--muted);font-size:11px;line-height:1.45}.nav{display:flex;gap:0;flex-wrap:wrap;border-bottom:1px solid #ADB5BE;background:white}.nav a{font-size:12px;font-weight:600;text-decoration:none;color:#343A41;padding:10px 12px;border-bottom:2px solid transparent}.nav a:hover,.nav a:focus{border-bottom-color:var(--accent);color:#145A91;background:#F4F6F8}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:12px 0}.tile,.k{min-width:0;background:white;padding:14px 15px}.tile span,.k small{display:block;color:#4C5661;font-size:11px;font-weight:600}.tile strong,.k strong{display:block;color:#15191E;font-size:25px;letter-spacing:-.65px;line-height:1.2;margin:7px 0;font-weight:700;overflow-wrap:anywhere}.tile small,.k div{font-size:11px;color:var(--muted)}.insights{background:white;border:1px solid var(--line);border-top:2px solid #343A41;padding:13px 16px;margin:0 0 12px}.insights h2{font-size:15px;margin:0 0 7px}.insights ul{margin:0;padding-left:17px;line-height:1.5}.insights li{padding:2px 0}.warning{background:#FFF4D9;border:1px solid #E7C67F;border-left:3px solid var(--accent);color:#5E4519;padding:8px 12px;margin:10px 0;font-size:12px;font-weight:600}.warning[hidden]{display:none}.tag,.pill{font-size:10px;letter-spacing:.25px;font-weight:700;padding:4px 7px;border:1px solid #ADB5BE;color:#38434E;background:#F2F4F6;white-space:nowrap}.tag.demo,.pill.demo{background:#FFF0CD;color:#61420C;border-color:#E7C67F}table{border-collapse:collapse;width:100%;font-size:11px;text-align:left}th,td{padding:6px 9px;border-bottom:1px solid #E1E5E9;white-space:nowrap}th{position:sticky;top:0;background:#E9EDF0;color:#24292E;font-weight:700}tr:nth-child(even){background:#F6F8F9}footer{font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding:10px 0;margin-top:20px}.modebar{opacity:.8}@media(max-width:850px){.chartgrid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.chapter-head h2{font-size:17px}}@page{size:A4 landscape;margin:10mm}@media print{body{background:white;font-size:10pt;-webkit-print-color-adjust:exact;print-color-adjust:exact}.chartcard,.insights,.k,.tile{break-inside:avoid}.chapter-head{break-after:avoid}.chapter{break-before:page}.chartgrid{display:block}.chartcard{margin-bottom:8px}.modebar{display:none!important}.nav{display:none}.kpis{grid-template-columns:repeat(5,minmax(0,1fr))}.k strong,.tile strong{font-size:16pt}th{position:static}th,td{white-space:normal;overflow-wrap:anywhere;font-size:7pt}}

.shell{max-width:1540px;margin:auto;padding:0 24px 28px}.hero{background:var(--navy);color:white;border-bottom:3px solid var(--accent);margin:0 -24px;padding:20px 24px;position:relative}.hero .eyebrow{color:#E7A126}.hero h1{font-size:30px;line-height:1.2;letter-spacing:-.55px;margin:4px 0}.hero p{margin:4px 0;color:#D7DDE3;font-size:13px}.hero .metadata{font-size:11px;color:#B9C3CD}.hero .pill{display:inline-block;margin-top:8px}.actions{display:flex;justify-content:space-between;align-items:center;gap:10px;background:white;border-bottom:1px solid var(--line);margin:10px 0 15px;padding-right:8px;position:sticky;top:0;z-index:5}.actions .nav{flex:1;border:0}.actions button{background:white;border:1px solid #ADB5BE;padding:7px 10px;color:var(--ink);font-size:11px;font-weight:700;white-space:nowrap}.actions button:hover{background:#E9EDF0}.tablewrap{overflow:auto;max-height:460px;border:1px solid var(--line);background:white}.empty{color:var(--muted)}@media(max-width:850px){.shell{padding:0 12px 20px}.hero{margin:0 -12px;padding:16px 12px}.hero h1{font-size:24px}.actions{position:static;flex-wrap:wrap}.actions .nav{flex-basis:100%}}@media print{.shell{max-width:none;padding:0}.hero{margin:0;padding:14px 18px}.hero h1{font-size:22pt}.actions{display:none}.tablewrap{max-height:none;overflow:visible}.hero{break-inside:avoid}}
'''

def report_html(v,run,scope):
    e=lambda s:html.escape(str(s))
    groups=sections(v['charts'])
    demo=v['mode']=='SYNTHETIC DEMO'
    nav=''.join(f'<a href="#{g["id"]}">{e(g["title"])}</a>' for g in groups)
    cards=''.join(f'<div class="k"><small>{e(x[0])}</small><strong>{e(x[1])}</strong><div>{e(x[2])}</div></div>' for x in v['kpis'])
    notes=''.join(f'<li>{e(x)}</li>' for x in v['notes'])
    chapters=[]
    for j,g in enumerate(groups,1):
        figures=[]
        for c in g['cards']:
            f=v['charts'][c['index']]
            plot=pio.to_html(pio.from_json(json.dumps(f)),full_html=False,include_plotlyjs=False,config={'displaylogo':False,'responsive':True,'toImageButtonOptions':{'format':'png','scale':2}})
            figures.append(f'<div class="chartcard{" wide" if c["wide"] else ""}">{plot}<p class="chart-caption">{e(c["caption"])}</p></div>')
        chapters.append(f'<section class="chapter" id="{g["id"]}"><div class="chapter-head"><div class="num">{j:02}</div><h2>{e(g["title"])}</h2><p>{e(g["question"])}</p></div><div class="chartgrid">{"".join(figures)}</div></section>')
    warning='<div class="warning">Synthetic demonstration — not real trade statistics and not for commercial decisions.</div>' if demo else '<div class="warning">Broad or custom classification — not verified pCAM-specific trade.</div>' if v['tier']!='specific' else ''
    audit=pd.DataFrame(v['audit']).to_html(index=False,escape=True,border=0) if v['audit'] else '<p>No request audit rows in the selected period.</p>'
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>pCAM | Executive market intelligence</title><style>{REPORT_CSS}</style><script>{get_plotlyjs()}</script></head><body><main class="shell"><header class="hero"><div class="eyebrow">MARKET DATA / COMMODITIES</div><h1>pCAM trade monitor</h1><p>{e(v['title'])}</p><p class="metadata">Tool developed by <strong style="color:#FFFFFF">Chengyi Hua</strong> &nbsp;·&nbsp; Market Intelligence</p><p class="metadata">Retrieved {e(run['created'])} · Analysis scope: {e('Observed partners' if scope=='partners' else 'Reported world')}</p><span class="pill{' demo' if demo else ''}">{e(v['mode'])}</span></header>{warning}<div class="actions"><nav class="nav" aria-label="Report chapters"><a href="#overview">Overview</a>{nav}<a href="#audit">Request audit</a></nav><button onclick="window.print()">Print / save PDF</button></div><section id="overview"><div class="chapter-head"><div class="num">SUMMARY</div><h2>Trade overview</h2><p>Latest usable observation in the selected time window.</p></div><div class="kpis">{cards or '<p class="empty">No usable KPI observations.</p>'}</div><div class="insights"><h2>Key observations</h2><ul>{notes}</ul></div></section>{''.join(chapters)}<section class="chapter" id="audit"><div class="chapter-head"><h2>Request audit</h2><p>Extraction and cleaning status for the selected trade series.</p></div><div class="tablewrap">{audit}</div></section><footer>Source: {'Deterministic synthetic demonstration dataset' if demo else 'UN Comtrade'} · <a href="https://comtrade.un.org/en/api-docs">UN Comtrade API documentation</a> · Unit values are derived customs statistics, not contract prices. · pCAM Market Intelligence v3.4</footer></main></body></html>'''
