import unittest,json,tempfile,os
from pathlib import Path
from unittest.mock import patch,Mock
from engine import plan,collect,normalize,targets,request_data,discover
from analytics import analyze
Q=dict(codes='28539030 28539050',reporters=['156'],start='2024-01',end='2025-12',flows=['M','X'],partners=[],budget=100,demo=True,refresh=False)
class MVP(unittest.TestCase):
 def test_default(self):
  t,j=plan(Q);self.assertEqual(len(j),96);self.assertEqual(len(t),2)
 def test_alias(self):self.assertEqual(len(targets('28539030 2853903000',['156'])),1)
 def test_custom(self):self.assertEqual(targets('410:2825902090',['410'])[0]['tier'],'proxy')
 def test_demo(self):
  r=collect(Q);v=analyze(r,'156','28539030','X');self.assertGreaterEqual(len(v['charts']),19);self.assertEqual(v['mode'],'SYNTHETIC DEMO');self.assertEqual(len(v['tables']['monthly']),24);json.dumps(v,allow_nan=False)
 def test_empty(self):
  r=collect(Q);r['rows']=[];v=analyze(r,'156','28539030','X');self.assertFalse(v['kpis']);self.assertEqual(len(v['charts']),1)
 def test_mock_live(self):
  q=Q|dict(codes='28539030',start='2025-01',end='2025-01',flows=['X'],demo=False)
  raw=dict(period=202501,reporterCode=156,partnerCode=410,cmdCode='2853903000',flowCode='X',netWgt=1000,primaryValue=12000,partner2Code=-1,customsCode='-1',motCode=9900)
  with patch('engine.request_data',side_effect=[([], 'empty_not_zero','a'),([raw],'downloaded','b')]) as f:
   r=collect(q);self.assertEqual(f.call_count,2);self.assertEqual(r['rows'][0]['priced_usd'],12000);self.assertEqual(r['rows'][0]['source_hs'],'2853903000');self.assertIn('partial',r['rows'][0]['scope'])
 def test_budget(self):
  with patch('engine.request_data',return_value=([],'empty_not_zero','a')) as f:
   r=collect(Q|dict(demo=False,budget=1));self.assertEqual(f.call_count,1);self.assertFalse(r['rows']);self.assertTrue(any(x['status']=='deferred_budget' for x in r['audit']))
 def test_tariffline_repeated_partner(self):
  t=targets('28539030',['156'])[0];a=dict(period=202501,reporterCode=156,partnerCode=410,cmdCode='28539030',flowCode='X',netWgt=1000,primaryValue=12000,partner2Code=-1,customsCode='-1',motCode=9900);r,e,c=normalize([a,a|{'netWgt':2000}],t,'2025-01','X',[]);self.assertEqual(c,0);self.assertEqual(r[0]['kg'],3000);self.assertEqual(r[0]['source_rows'],2)
 def test_real_fixture(self):
  samples=json.loads((Path(__file__).parent/'tests'/'diagnostic_fixture.json').read_text())['China_NCM_annual_8digit']
  t=targets('28539030',['156'])[0];r,e,c=normalize(samples,t,'2024','X',[])
  self.assertEqual((e,c,len(r)),(0,0,1));self.assertEqual(r[0]['partner_name'],'Belgium');self.assertEqual(r[0]['source_rows'],3);self.assertEqual(r[0]['kg'],543);self.assertEqual(r[0]['usd'],9500)
  self.assertAlmostEqual(r[0]['priced_usd']/r[0]['priced_kg'],9500/543)
 def test_annual_plan(self):
  q=Q|dict(frequency='A',start='2024',end='2025');t,j=plan(q);self.assertEqual(len(j),8);self.assertEqual(j[0][0],'2025')
 def test_annual_dashboard(self):
  q=Q|dict(frequency='A',start='2024',end='2025');v=analyze(collect(q),'156','28539030','X');self.assertEqual(len(v['tables']['annual']),2);self.assertNotIn('MoM',v['kpis'][0][2]);self.assertEqual(v['kpis'][3][0],'Latest observed year');self.assertFalse(any('Seasonality' in x['layout']['title']['text'] for x in v['charts']));json.dumps(v,allow_nan=False)
 def test_auto_separate(self):
  q=Q|dict(frequency='auto',start='2024-01',end='2024-03',codes='28539030',flows=['X']);r=collect(q);a=analyze(r,'156','28539030','X',frequency='A');m=analyze(r,'156','28539030','X',frequency='M');self.assertEqual(len(a['tables']['annual']),1);self.assertEqual(len(m['tables']['monthly']),3)
 def test_exact_repeated_tariffline(self):
  samples=json.loads((Path(__file__).parent/'tests'/'diagnostic_fixture.json').read_text())['China_NCM_annual_8digit'];x=samples[0];r,e,c=normalize([x,x],targets('28539030',['156'])[0],'2024','X',[]);self.assertEqual(r[0]['kg'],500);self.assertEqual(r[0]['source_rows'],2)
 def test_overlap_excluded(self):
  samples=json.loads((Path(__file__).parent/'tests'/'diagnostic_fixture.json').read_text())['China_NCM_annual_8digit'];x=samples[0];r,e,c=normalize([x,x|{'motCode':0}],targets('28539030',['156'])[0],'2024','X',[]);self.assertEqual(c,2);self.assertFalse(r)
 def test_standard_aggregate(self):
  samples=json.loads((Path(__file__).parent/'tests'/'diagnostic_fixture.json').read_text())['China_battery_annual_control'];r,e,c=normalize(samples,targets('850760',['156'])[0],'2024','X',[]);self.assertEqual(r[0]['partner'],'0');self.assertEqual(r[0]['scope'],'total_dimensions');self.assertAlmostEqual(r[0]['usd'],61126922874)
 def test_annual_endpoint(self):
  t=targets('28539030',['156'])[0];snap={'payload':{'data':[],'count':0}};s=Mock()
  with patch('engine._payload',return_value=(snap,'downloaded','x')) as f:
   request_data(s,t,'2024','X','28539030',[],'key',False);args=f.call_args.args;self.assertIn('/getTariffline/C/A/HS',args[1]);self.assertEqual(args[2]['period'],'2024');self.assertNotIn('customsCode',args[2]);self.assertNotIn('partnerCode',args[2])
 def test_discovery(self):
  q=Q|dict(frequency='A',start='2024',end='2024');snap={'payload':{'data':[{'period':2024}]}}
  with patch('engine._payload',return_value=(snap,'downloaded','x')):
   r=discover(q,key='key');self.assertEqual(r[0]['periods'],['2024']);self.assertEqual(r[1]['status'],'empty_or_unrecognized')
 def test_auto_budget(self):
  q=Q|dict(frequency='auto',start='2024-01',end='2024-02',codes='28539030',flows=['X'],demo=False,budget=3)
  with patch('engine.discover',return_value=[{'reporter':'156','dataset':'tariffline','frequency':'A','status':'listed','periods':['2024']}]),patch('engine.request_data',return_value=([],'empty_not_zero','x')) as req:
   r=collect(q);self.assertEqual(r['attempts'],3);self.assertEqual(req.call_count,2)
 def test_partial_weights(self):
  samples=json.loads((Path(__file__).parent/'tests'/'diagnostic_fixture.json').read_text())['China_NCM_annual_8digit'];x=samples[0];r,e,c=normalize([x,x|{'netWgt':None,'primaryValue':200}],targets('28539030',['156'])[0],'2024','X',[]);self.assertEqual(r[0]['kg'],250);self.assertEqual(r[0]['usd'],5199);self.assertEqual(r[0]['priced_usd'],4999);self.assertEqual(r[0]['missing_weight_rows'],1)
if __name__=='__main__':unittest.main()
