import json
import unittest
from datetime import date

import test_app as fixtures
import operations


class LedgerTests(unittest.TestCase):
    setUp = fixtures.MVPTests.setUp
    tearDown = fixtures.MVPTests.tearDown
    seed = fixtures.MVPTests.seed
    quote = fixtures.MVPTests.quote
    def accepted(self, **overrides):
        self.assertEqual(self.quote(**overrides)[0], 200)
        q = self.client.request('state')[1]['quotes'][0]
        self.assertEqual(self.client.request('status', {'id': q['id'], 'status': 'Aceptada'})[0], 200)
        return q

    def consume(self, qid=1, **overrides):
        return self.client.request('consumptions', {'quote_id': qid, 'line_index': 0,
            'quantity': '1', 'date': date.today().isoformat(), 'analyst': 'Analista', **overrides})

    def account(self, qid=1):
        return next(a for a in self.client.request('state')[1]['accounts'] if a['quote_id'] == qid)

    def test_discounted_partial_consumption_and_rounding(self):
        self.seed()
        q = self.accepted(items=[{'service_id': 1, 'quantity': '3'}], discount='15')
        for _ in range(3):
            self.assertEqual(self.consume()[0], 200)
        a = self.account()
        self.assertEqual(a['remaining_amount'], 0)
        self.assertEqual(a['lines'][0]['remaining_quantity'], '0')
        self.assertEqual(sum(r['amount'] for r in a['consumptions']), q['total'])
        self.assertEqual(self.consume()[0], 400)
        self.assertEqual(a['paid'], 0)
        self.assertEqual(a['receivable'], q['total'])

    def test_quantity_and_money_limits_independent(self):
        self.seed()
        self.accepted(items=[{'service_id': 1, 'quantity': 2}], discount=0)
        self.assertEqual(self.consume(quantity=3, price_basis='personalizado', price=1, price_reason='Prueba')[0], 400)
        self.assertEqual(self.consume(quantity=1, price_basis='personalizado', price=300, price_reason='Prueba')[0], 400)
        self.assertEqual(self.account()['consumptions'], [])

    def test_reassignment_transaction_and_void_history(self):
        self.seed()
        self.accepted(discount=0)
        self.accepted(discount=0)
        self.assertEqual(self.consume()[0], 200)
        # A failed replacement must undo the old row's tentative cancellation.
        self.assertEqual(self.consume(qid=2, replaces=1, reason='Cuenta equivocada', quantity=100)[0], 400)
        self.assertEqual(self.account(1)['consumptions'][0]['void_reason'], '')
        self.assertEqual(self.consume(qid=2, replaces=1, reason='Cuenta equivocada')[0], 200)
        self.assertEqual(self.account(1)['remaining_amount'], 30863)
        self.assertEqual(self.account(1)['lines'][0]['remaining_quantity'], '2.5')
        self.assertEqual(self.account(2)['consumptions'][0]['replaces'], 1)
        self.assertEqual(self.consume(qid=2, replaces=1, reason='De nuevo')[0], 400)
        self.assertEqual(self.client.request('void-consumption', {'id': 2, 'reason': 'Duplicado'})[0], 200)
        self.assertEqual(self.account(2)['remaining_amount'], 30863)

    def test_requirements_documents_and_payment_balance(self):
        self.seed()
        self.accepted(items=[{'service_id':1, 'quantity':2, 'requirement':'pago'}], discount=0)
        self.assertEqual(self.consume()[0], 400)
        document = {'quote_id':1,'kind':'orden','date':date.today().isoformat(),'reference':'OC-1','amount':246.90}
        self.assertEqual(self.client.request('administration', document)[0], 200)
        self.assertEqual(self.consume()[0], 400)
        self.assertEqual(self.account()['paid'], 0)
        self.assertEqual(self.client.request('administration', {**document, 'kind':'pago', 'amount':300})[0], 400)
        self.assertEqual(self.client.request('administration', {**document, 'kind':'pago'})[0], 200)
        self.assertEqual(self.consume()[0], 200)
        self.assertEqual(self.account()['receivable'], 0)
        self.assertEqual(self.client.request('void-document', {'id':2,'reason':'Pago mal registrado'})[0], 200)
        self.assertEqual(self.account()['receivable'], 24690)
        self.assertEqual(self.consume()[0], 400)

    def test_manual_price_line_discount_permissions_and_unique_names(self):
        self.seed()
        self.assertEqual(self.client.request('services', {'code':'S2','name':'  ANÁLISIS  ','unit':'hora','category':'Externo','price':1})[0], 400)
        q = self.accepted(items=[{'service_id':1,'quantity':1,'price':1752500,'price_reason':'Presupuesto multitécnica', 'discount':10}], discount=15)
        self.assertEqual(q['total'], 134066250)
        roles = json.loads(self.client.request('state')[1]['settings']['permissions'])
        roles['cotizador']['quotes'] = False
        roles['cotizador']['consumptions'] = True
        roles['cotizador']['approve_prices'] = False
        self.assertEqual(self.client.request('permissions', {'permissions': roles})[0], 200)
        other = fixtures.Client(self.server.server_port)
        self.assertEqual(other.open('cotizador')[0], 200)
        self.assertEqual(other.request('quotes', {'client_id':1})[0], 403)
        self.assertEqual(other.request('consumptions', {'quote_id':1,'line_index':0,'quantity':'.1',
            'date':date.today().isoformat(),'analyst':'Analista','price_basis':'personalizado','price':1,'price_reason':'Prueba'})[0], 400)
        self.assertEqual(other.request('consumptions', {'quote_id':1,'line_index':0,'quantity':'.1',
            'date':date.today().isoformat(),'analyst':'Analista'})[0], 200)
        self.assertEqual(other.request('permissions', {'permissions': roles})[0], 403)

    def test_actual_price_and_separate_package_quantity(self):
        self.seed()
        self.accepted(items=[{'service_id':1,'quantity':1,'price':1750000,'price_reason':'Paquete'}], discount=0)
        self.assertEqual(self.consume(quantity='.1', executed_quantity=2, price_basis='actual')[0], 200)
        a = self.account()
        self.assertEqual(a['lines'][0]['remaining_quantity'], '0.9')
        self.assertEqual(a['remaining_amount'], 175000000-24690)
        self.assertEqual(json.loads(a['consumptions'][0]['payload'])['executed_quantity'], '2')

    def test_review_preserves_original_and_migration_preserves_snapshots(self):
        self.seed()
        q = self.accepted()
        with operations_db(self.path) as db:
            db.execute('INSERT INTO source_records(kind,sheet,row_number,reference,payload) VALUES (?,?,?,?,?)',
                       ('cotizacion','Original',2,'Duplicada','{"Cantidad":44378}'))
            db.execute('INSERT INTO services(code,name,unit,category,price) VALUES (?,?,?,?,?)', ('S2','Análisis','hora','Externo',100))
        import app
        app.initialize(self.path, 'MetCore')
        state = self.client.request('state')[1]
        self.assertEqual(len({s['name'] for s in state['services']}), 2)
        self.assertEqual(state['quotes'][0], self.client.request('state')[1]['quotes'][0])
        self.assertEqual(json.loads(q['items'])[0]['name'], 'Análisis')
        self.assertEqual(self.client.request('source-review', {'id':1,'payload':{'Cantidad':2},'reason':'Confirmado en documento original'})[0], 200)
        original = self.client.request('source')[1][0]
        self.assertEqual(json.loads(original['payload'])['Cantidad'], 44378)
        self.assertEqual(json.loads(self.client.request('state')[1]['reviews'][0]['payload'])['Cantidad'], 2)

    def test_reviewed_quote_migration_is_explicit_and_idempotent(self):
        self.seed()
        with operations_db(self.path) as db:
            db.execute('INSERT INTO source_records(kind,sheet,row_number,reference,payload) VALUES (?,?,?,?,?)',
                       ('cotizacion','Original',3,'U0621-0001','{"Cantidad":4}'))
        data = {'source_id':1,'created_date':'2021-06-01','confirmed_total':'493.80','initial_status':'Aceptada',
                'items':[{'service_id':1,'quantity':4}], 'discount':0,'valid_until':'2021-07-01'}
        self.assertEqual(self.quote(**data)[0], 400)
        self.assertEqual(self.client.request('source-review', {'id':1,'payload':{'Cantidad':4},'reason':'Confirmado'})[0], 200)
        self.assertEqual(self.quote(**{**data,'confirmed_total':400})[0], 400)
        self.assertEqual(self.quote(**data)[0], 200)
        q = self.client.request('state')[1]['quotes'][0]
        self.assertEqual((q['created'], q['status'], json.loads(q['context'])['source_reference']), ('2021-06-01','Aceptada','U0621-0001'))
        self.assertEqual(self.quote(**data)[0], 400)
        self.assertEqual(len(self.client.request('state')[1]['quotes']), 1)

    def test_concurrent_spending_cannot_exceed_budget(self):
        import concurrent.futures
        self.seed()
        self.accepted(items=[{'service_id':1,'quantity':1}], discount=0)
        clients = [fixtures.Client(self.server.server_port) for _ in range(2)]
        for client in clients:
            client.open()
        payload = {'quote_id':1,'line_index':0,'quantity':1,'date':date.today().isoformat(),'analyst':'Analista'}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda client: client.request('consumptions', payload)[0], clients))
        self.assertEqual(sorted(statuses), [200,400])
        self.assertEqual(self.account()['remaining_amount'], 0)

    def test_backup_restore_keeps_accounts_and_original_space(self):
        import base64
        self.seed()
        self.accepted(discount=0)
        self.consume()
        with self.client.opener.open(self.client.base+'/api/backup') as response:
            raw = response.read()
        self.assertTrue(raw.startswith(b'SQLite format 3'))
        self.assertEqual(self.client.request('restore', {'name':'Recuperado','file':base64.b64encode(raw).decode()})[0],200)
        cores = self.client.request('cores')[1]
        core = next(c for c in cores if c['name']=='Recuperado')
        expected = self.account()
        self.client.open(core=core['id'])
        self.assertEqual(self.account(),expected)
        self.client.open()
        self.assertEqual(self.account(),expected)
        self.assertEqual(self.client.request('restore', {'name':'Corrupto','file':base64.b64encode(b'Invalid').decode()})[0],400)
        self.assertEqual(len(self.client.request('cores')[1]),2)


from app import connect as operations_db
