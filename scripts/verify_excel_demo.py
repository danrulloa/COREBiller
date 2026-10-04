"""Exercise the local API with source-backed examples, without emailing clients."""
import http.cookiejar
import json
from datetime import date, timedelta
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
csrf=''


def request(path,data=None):
    req=urllib.request.Request('http://127.0.0.1:8765/api/'+path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type':'application/json','X-CSRF-Token':csrf})
    with opener.open(req) as response:
        return json.loads(response.read())


request('start',{'core':'microcore-excel','role':'admin','name':'Demostración Excel'})
state=request('state')
csrf=state['csrf']
source=request('source')
meta=json.loads(state['settings']['source_metadata'])
historical=next(json.loads(r['payload']) for r in source if r['kind']=='cotizacion' and r['row_number']==3)
client=next(c for c in state['clients'] if c['name']==historical['Usuario'] and c['institution']==historical['Institución'])
by_code={s['code']:s for s in state['services']}
cases=[
    ('Reproducción fila 3 de 2021',[('REPLAY-2021-R3',4)],0,133200000,
     'Copia de BDcotizaciones!S3:U3. Conserva servicio y precio histórico. Consecutivo nuevo de demostración; no reemplaza U0621-0001.'),
    ('SEM externo con tarifa 2025',[('XLS-03-3-2025',2)],0,66800000,
     'Tarifas!D3: 334000 por unidad. Cantidad elegida para la demostración: 2.'),
    ('Descuento de volumen 15 %',[('XLS-03-3-2025',2)],15,56780000,
     'Tarifas!D3 y Descuentos!B4. Cálculo global de 15 %; modalidad y elegibilidad aún no implementadas.'),
    ('Dos servicios en una propuesta',[('XLS-03-3-2025',2),('XLS-25-3-2025',1)],0,77800000,
     'Tarifas!D3 (SEM: 334000) y D25 (oro: 110000). Cantidades de demostración: 2 y 1. El MVP agrupa ambos en una propuesta; el sistema original genera documentos por ítem.'),
]
results=[]
for title,entries,discount,expected,note in cases:
    marker='DEMOSTRACIÓN EXCEL · '+title
    quote=next((q for q in request('state')['quotes'] if q['notes'].startswith(marker)),None)
    if quote is None:
        request('quotes',{'client_id':client['id'],
            'items':[{'service_id':by_code[code]['id'],'quantity':qty} for code,qty in entries],
            'discount':discount,'valid_until':(date.today()+timedelta(days=30)).isoformat(),
            'notes':marker+'\n'+note+'\nSin validez comercial. Las unidades deben confirmarse antes de uso real.'})
        quote=request('state')['quotes'][0]
    assert quote['total']==expected,(title,quote['total'],expected)
    results.append({'caso':title,'numero':quote['number'],'subtotal_cop':quote['subtotal']/100,
                    'descuento_cop':quote['discount']/100,'total_cop':quote['total']/100,'origen':note})
assert sum(r['kind']=='cotizacion' for r in source)==234
assert sum(r['kind']=='servicio' for r in source)==115
assert sum(r['kind']=='tarifa' for r in source)==836
assert historical['Valor Cotización']==1332000
# Check a differently priced historical row is preserved, rather than recomputed.
unusual=next(json.loads(r['payload']) for r in source if r['kind']=='cotizacion' and r['row_number']==2)
assert unusual['Valor Cotización']==149940 and unusual['Valor Unidad']==77084
report={'fecha':date.today().isoformat(),'fuente':meta['archivo'],'casos_ejecutados':results,
        'historico_conservado':{'cotizaciones':234,'servicios':115,'tarifas':836},
        'archivo_original_sha256':meta['sha256']}
(ROOT/'outputs').mkdir(exist_ok=True)
(ROOT/'outputs'/'excel-demo-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
