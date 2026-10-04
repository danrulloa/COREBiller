import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer

import app


class Client:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}'
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ''

    def request(self, path, data=None, csrf=True):
        headers = {'Content-Type': 'application/json'}
        if csrf:
            headers['X-CSRF-Token'] = self.csrf
        req = urllib.request.Request(self.base+'/api/'+path,
                                     data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with self.opener.open(req) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def open(self, role='admin', core='metcore', **extra):
        status, body = self.request('start', {'core':core,'role':role, **extra})
        if status == 200:
            status, body = self.request('state')
            self.csrf = body['csrf']
        return status, body


class MVPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'metcore.sqlite3'
        app.initialize(self.path, 'MetCore')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.server.db_path, self.server.data_dir = self.path, Path(self.temp.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.server.server_port)
        self.assertEqual(self.client.open()[0], 200)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.SESSIONS.clear()
        self.temp.cleanup()

    def seed(self):
        self.assertEqual(self.client.request('services', {'code':'S1','name':'Análisis','unit':'muestra','category':'General','price':'123.45'})[0], 200)
        self.assertEqual(self.client.request('clients', {'name':'Persona','institution':'Institución','email':'test@example.org'})[0], 200)

    def quote(self, **overrides):
        return self.client.request('quotes', {'client_id':1, 'items':[{'service_id':1,'quantity':'2.5'}],
            'discount':'10', 'valid_until':(date.today()+timedelta(days=30)).isoformat(), **overrides})

    def test_snapshot_money_and_status(self):
        self.seed()
        self.assertEqual(self.quote()[0], 200)
        quote = self.client.request('state')[1]['quotes'][0]
        self.assertEqual((quote['subtotal'], quote['discount'], quote['total']), (30863,3086,27777))
        self.assertEqual(quote['number'], f'METCORE-{date.today().year}-0001')
        self.client.request('services', {'id':1,'code':'S1','name':'Nuevo nombre','unit':'muestra','category':'General','price':999})
        self.client.request('settings', {'name':'Otro Core','contact':'nuevo','terms':'Nuevas condiciones'})
        quote2 = self.client.request('state')[1]['quotes'][0]
        self.assertEqual(quote, quote2)
        self.assertEqual(json.loads(quote2['items'])[0]['name'], 'Análisis')
        self.assertEqual(self.client.request('status', {'id':1,'status':'Aceptada'})[0], 200)
        self.assertEqual(self.client.request('status', {'id':1,'status':'Rechazada'})[0], 400)

    def test_roles_and_csrf(self):
        self.seed()
        for role in ('consulta','cotizador'):
            other = Client(self.server.server_port)
            self.assertEqual(other.open(role)[0],200)
            self.assertEqual(other.request('services', {'code':'S2','name':'X','unit':'hora','category':'General','price':1})[0],403)
            status = other.request('clients', {'name':'Cliente','institution':'Empresa'})[0]
            self.assertEqual(status,403 if role=='consulta' else 200)
        self.assertEqual(self.client.request('clients', {'name':'X','institution':'Y'}, csrf=False)[0],403)
        self.assertEqual(Client(self.server.server_port).request('state')[0],401)

    def test_import_rollback_and_upsert(self):
        self.seed()
        bad = 'code,name,unit,category,price\nS1,Changed,hour,General,42\nS2,Invalid,hour,General,nope\n'
        self.assertEqual(self.client.request('import', {'csv':bad})[0],400)
        self.assertEqual(self.client.request('state')[1]['services'][0]['price'],12345)
        good = 'code,name,unit,category,price\nS1,Changed,hour,General,42\nS2,Valid,hour,General,15.50\n'
        self.assertEqual(self.client.request('import', {'csv':good})[0],200)
        self.assertEqual(len(self.client.request('state')[1]['services']),2)
        duplicate = 'code,name,unit,category,price\nS1,Changed,hour,General,2\nS1,Changed,hour,General,3\n'
        self.assertEqual(self.client.request('import', {'csv':duplicate})[0],400)

    def test_invalid_quote_and_core_isolation(self):
        self.seed()
        for overrides in ({'discount':101}, {'items':[{'service_id':1,'quantity':0}]},
                          {'items':[{'service_id':99,'quantity':1}]}, {'client_id':99},
                          {'items':[{'service_id':1,'quantity':'NaN'}]}, {'valid_until':'2000-01-01'}):
            self.assertEqual(self.quote(**overrides)[0],400)
        self.assertEqual(self.client.request('state')[1]['quotes'],[])
        other_path = Path(self.temp.name)/'microcore.sqlite3'
        app.initialize(other_path,'MicroCore')
        with app.connect(other_path) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM clients').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT value FROM settings WHERE key='name'").fetchone()[0],'MicroCore')

    def test_generic_core_creation_and_switch_without_credentials(self):
        self.seed()
        self.assertEqual(self.client.open(new_core='AnimalCore')[0],200)
        self.assertEqual(self.client.request('state')[1]['services'],[])
        self.assertEqual(self.client.request('state')[1]['settings']['name'],'AnimalCore')
        cores=self.client.request('cores')[1]
        self.assertEqual(len(cores),2)
        self.assertEqual(self.client.open(new_core='AnimalCore')[0],400)
        self.assertEqual(self.client.open(core='../../outside')[0],400)
        self.assertEqual(self.client.open(role='unknown')[0],400)
        self.assertEqual(self.client.open()[0],200)
        self.assertEqual(len(self.client.request('state')[1]['services']),1)
        self.assertEqual(self.client.open('consulta')[0],200)
        self.assertEqual(self.client.request('state')[1]['user']['role'],'consulta')
        self.assertEqual(self.client.request('logout',{})[0],200)
        self.assertEqual(self.client.request('state')[0],401)


if __name__ == '__main__':
    unittest.main()
