import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import app


@unittest.skipUnless((app.ROOT/'MicroAccounts.xlsx').is_file(), 'Prueba privada: MicroAccounts.xlsx no se distribuye con el proyecto.')
class ExcelImportTests(unittest.TestCase):
    def test_source_prices_and_history_are_preserved(self):
        from scripts.import_microaccounts import import_workbook
        source=app.ROOT/'MicroAccounts.xlsx'
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'demo.sqlite3'
            meta=import_workbook(source,path)
            self.assertEqual(meta['conteos']['precios_catalogo'],96)
            self.assertEqual(meta['conteos']['servicios_catalogo'],24)
            self.assertEqual(meta['conteos']['clientes'],122)
            with app.connect(path) as db:
                records=[dict(r) for r in db.execute('SELECT * FROM source_records')]
                for record in records:
                    if record['kind']=='tarifa':
                        payload=json.loads(record['payload'])
                        if payload['Año']==2025 and isinstance(payload['Valor original'],(int,float)):
                            col=payload['Celda precio'][0]
                            offset={'B':1,'C':2,'D':3,'E':4}[col]
                            row=db.execute('SELECT price FROM services WHERE code=?',
                                (f"XLS-{record['row_number']:02d}-{offset}-2025",)).fetchone()
                            self.assertEqual(row['price'],app.money(payload['Valor original']))
                history=[r for r in records if r['kind']=='cotizacion']
                self.assertEqual(len(history),234)
                self.assertEqual(sum(r['reference']=='U0621-0001' for r in history),2)
                atypical=json.loads(next(r['payload'] for r in history if r['row_number']==2))
                self.assertEqual(atypical['Valor Cotización'],149940)
                self.assertEqual(atypical['Valor Descuento'],'Valor Extraño')
                self.assertIn('Dirección',atypical)
                self.assertIn('Nombre Proyecto',atypical)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM quotes').fetchone()[0],0)
            with self.assertRaises(ValueError):
                import_workbook(source,path)
            with app.connect(path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM services').fetchone()[0],97)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)


if __name__=='__main__':
    unittest.main()
