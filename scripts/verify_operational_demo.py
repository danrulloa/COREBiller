"""Repeatable local demonstration; uses source prices, keeps source records intact."""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_app import Client

client = Client(8765)
assert client.open(core='microcore-excel', name='Demostración operativa')[0] == 200


def state():
    return client.request('state')[1]


def post(route, data):
    status, result = client.request(route, data)
    assert status == 200, (route, status, result)


current = state()
by_code = {s['code']:s for s in current['services']}
source_rows = client.request('source')[1]
historical = next(json.loads(r['payload']) for r in source_rows if r['kind']=='cotizacion' and r['row_number']==3)
person = next(c for c in current['clients'] if c['name']==historical['Usuario'] and c['institution']==historical['Institución'])
marker = 'DEMOSTRACIÓN OPERATIVA · presupuesto multitécnica'
q = next((q for q in current['quotes'] if q['notes'].startswith(marker)), None)
if not q:
    post('quotes', {'client_id':person['id'], 'items':[{'service_id':by_code['XLS-33-3-2025']['id'],
         'quantity':1,'price':1752500,'price_reason':'Presupuesto exacto acordado de prueba','requirement':'orden'}],
         'valid_until':(date.today()+timedelta(days=30)).isoformat(), 'discount':0,
         'project':'Demostración de múltiples servicios', 'samples':'Muestras ficticias de prueba',
         'notes':marker+'\nBasado en Tarifas!D33; precio personalizado. Cantidad 1 representa el paquete completo de prueba. Sin validez comercial.',
         'email_notes':'Adjuntar PDF y formato oficial manualmente.'})
    q = state()['quotes'][0]
assert q['total'] == 175250000
if q['status'] == 'Emitida':
    post('status', {'id':q['id'],'status':'Aceptada'})
account = next(a for a in state()['accounts'] if a['quote_id']==q['id'])
payload = {'quote_id':q['id'],'line_index':0,'quantity':'.2','executed_quantity':1,
           'service_id':by_code['XLS-03-3-2025']['id'],'price_basis':'actual',
           'date':date.today().isoformat(),'analyst':'Analista · demostración','duration':'1 unidad por confirmar',
           'samples':'Muestra ficticia 02','notes':'Consumo de SEM en presupuesto multitécnica; fracción contractual confirmada solo para esta prueba.'}
if not account['documents']:
    status, _ = client.request('consumptions', payload)
    assert status == 400, 'Must require purchase order before starting'
    post('administration', {'quote_id':q['id'],'kind':'orden','date':date.today().isoformat(),
         'reference':'DEMO-OC-01 · referencia ficticia','amount':1752500,'notes':'No equivale a pago recibido.'})
if not account['consumptions']:
    post('consumptions', payload)
account = next(a for a in state()['accounts'] if a['quote_id']==q['id'])
assert account['remaining_amount'] == 141850000
assert account['lines'][0]['remaining_quantity'] == '0.8'
assert account['paid'] == 0 and account['receivable'] == 175250000
source = client.request('source')[1]
assert sum(r['kind']=='cotizacion' for r in source) == 234
assert sum(r['kind']=='servicio' for r in source) == 115
report = {'date':date.today().isoformat(), 'quote':q['number'], 'contracted_cop':q['total']/100,
          'consumed_cop':account['consumed_amount']/100,'available_cop':account['remaining_amount']/100,
          'remaining_contract_quantity':account['lines'][0]['remaining_quantity'], 'paid_cop':account['paid']/100,
          'source_sha256':hashlib.sha256((ROOT/'MicroAccounts.xlsx').read_bytes()).hexdigest(),
          'checks':['custom exact price','configurable purchase-order requirement','separate executed and contracted quantity',
                    'current source price','dual balance','purchase order does not count as payment','source remains intact']}
(ROOT/'outputs').mkdir(exist_ok=True)
(ROOT/'outputs'/'operational-demo-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
