import json
import tempfile
import unittest
from pathlib import Path

import app
import test_app as fixtures


class LifecycleTests(unittest.TestCase):
    setUp = fixtures.MVPTests.setUp
    tearDown = fixtures.MVPTests.tearDown
    seed = fixtures.MVPTests.seed
    quote = fixtures.MVPTests.quote

    def test_create_first_core_without_any_existing_database(self):
        root=Path(self.temp.name)/'empty-installation'
        root.mkdir()
        self.server.data_dir=root
        self.server.db_path=root/'unused.sqlite3'
        client=fixtures.Client(self.server.server_port)
        self.assertEqual(client.request('cores'),(200,[]))
        self.assertEqual(client.request('state')[0],401)
        self.assertEqual(list(root.iterdir()),[])
        status,state=client.open(role='consulta',core='',new_core='Mi primer Core')
        self.assertEqual(status,200)
        self.assertEqual(state['user']['role'],'admin')
        self.assertEqual(state['settings']['name'],'Mi primer Core')
        self.assertEqual((state['clients'],state['services'],state['quotes']),([],[],[]))

    def test_server_rejects_a_second_listener(self):
        first = app.LocalServer(('127.0.0.1',0),app.Handler)
        try:
            with self.assertRaises(OSError):
                app.LocalServer(('127.0.0.1',first.server_port),app.Handler)
        finally:
            first.server_close()

    def test_new_installation_only_example_and_new_cores_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app.bootstrap(root)
            self.assertEqual([p.name for p in root.glob('*.sqlite3')], ['ejemplocore.sqlite3'])
            with app.connect(root/'ejemplocore.sqlite3') as db:
                self.assertEqual(db.execute("SELECT value FROM settings WHERE key='name'").fetchone()[0], 'EjemploCORE')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM quotes').fetchone()[0],0)
            app.bootstrap(root)
            with app.connect(root/'ejemplocore.sqlite3') as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM services').fetchone()[0],2)
        self.client.open(new_core='Mi Core')
        state=self.client.request('state')[1]
        self.assertEqual((state['clients'],state['services'],state['quotes']),([],[],[]))
        self.assertNotIn('is_demo',state['settings'])

    def test_draft_edit_emit_and_protect_issued(self):
        self.seed()
        self.assertEqual(self.quote(save_as='Borrador')[0],200)
        self.assertEqual(self.quote(id=1,save_as='Borrador',notes='Editado',discount=0)[0],200)
        state=self.client.request('state')[1]
        self.assertEqual(len(state['quotes']),1)
        self.assertEqual((state['quotes'][0]['status'],state['quotes'][0]['notes']),('Borrador','Editado'))
        self.assertEqual(self.client.request('status',{'id':1,'status':'Aceptada'})[0],400)
        self.assertEqual(self.client.request('status',{'id':1,'status':'Emitida'})[0],200)
        self.assertEqual(self.quote(id=1,save_as='Borrador')[0],400)
        self.assertEqual(self.client.request('delete-draft',{'id':1})[0],400)
        self.assertEqual(self.client.request('status',{'id':1,'status':'Emitida'})[0],400)

    def test_delete_draft_hides_and_audits_without_reusing_id(self):
        self.seed()
        self.quote(save_as='Borrador')
        self.assertEqual(self.client.request('delete-draft',{'id':1})[0],200)
        state=self.client.request('state')[1]
        self.assertEqual(state['quotes'],[])
        self.assertEqual(state['accounts'],[])
        audit=json.loads(state['audit'][0]['action'])
        self.assertEqual(audit['previous']['status'],'Borrador')
        self.quote(save_as='Borrador')
        self.assertEqual(self.client.request('state')[1]['quotes'][0]['id'],2)
        self.assertEqual(self.client.request('delete-draft',{'id':1})[0],400)

    def test_cancellation_preserves_movements_and_allows_settlement(self):
        from datetime import date
        self.seed()
        self.quote(discount=0)
        self.client.request('status',{'id':1,'status':'Aceptada'})
        payload={'quote_id':1,'line_index':0,'quantity':1,'date':date.today().isoformat(),'analyst':'Prueba'}
        self.assertEqual(self.client.request('consumptions',payload)[0],200)
        before=self.client.request('state')[1]['accounts'][0]
        self.assertEqual(self.client.request('status',{'id':1,'status':'Cancelada'})[0],400)
        self.assertEqual(self.client.request('status',{'id':1,'status':'Cancelada','reason':'Cliente cancela el resto'})[0],200)
        state=self.client.request('state')[1]
        self.assertEqual(state['accounts'][0],before)
        self.assertEqual(state['quotes'][0]['status'],'Cancelada')
        self.assertEqual(self.client.request('consumptions',payload)[0],400)
        self.assertEqual(self.client.request('delete-draft',{'id':1})[0],400)
        self.assertEqual(self.client.request('administration',{'quote_id':1,'kind':'pago','date':date.today().isoformat(),'reference':'Pago final','amount':100})[0],200)
        self.assertEqual(self.client.request('state')[1]['accounts'][0]['paid'],10000)

    def test_read_only_role_cannot_delete_or_cancel(self):
        self.seed()
        self.quote(save_as='Borrador')
        self.client.open('consulta')
        self.assertEqual(self.client.request('delete-draft',{'id':1})[0],403)
        self.assertEqual(self.client.request('status',{'id':1,'status':'Cancelada','reason':'Prueba'})[0],403)
