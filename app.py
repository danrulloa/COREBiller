"""COREBiller local: Python 3.10+, standard library only."""
import argparse
import base64
import csv
import hmac
import io
import json
import secrets
import sqlite3
import socket
import errno
import hashlib
import os
import sys
import urllib.request
import time
import operations
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SESSIONS = {}
ROLES = ('admin', 'cotizador', 'consulta')


def money(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n > Decimal('1000000000000'):
            raise ValueError('Valor fuera del rango permitido.')
        return int((n * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError('Ingresa un valor numérico válido.')


def required(data, key, limit=500):
    value = str(data.get(key, '')).strip()
    if not value or len(value) > limit:
        raise ValueError(f'El campo {key} es obligatorio (máximo {limit} caracteres).')
    return value


def clean_logo(value):
    """Accept a small PNG data URL for local Core branding."""
    if value == '':
        return ''
    prefix = 'data:image/png;base64,'
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) > 410000:
        raise ValueError('El logo debe ser un PNG de máximo 300 KB.')
    try:
        raw = base64.b64decode(value[len(prefix):], validate=True)
    except (ValueError, base64.binascii.Error):
        raise ValueError('El archivo del logo no es un PNG válido.')
    if (len(raw) > 300000 or len(raw) < 24 or raw[:8] != b'\x89PNG\r\n\x1a\n'
            or raw[12:16] != b'IHDR'):
        raise ValueError('El archivo del logo no es un PNG válido o supera 300 KB.')
    width = int.from_bytes(raw[16:20], 'big')
    height = int.from_bytes(raw[20:24], 'big')
    if not width or not height or width > 4000 or height > 1500:
        raise ValueError('El logo debe tener máximo 4000 × 1500 píxeles.')
    return value


@contextmanager
def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path, core):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with connect(path) as existing:
            version = existing.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
            if not version or version[0] != '2':
                backup_dir = path.parent / 'backups'
                backup_dir.mkdir(exist_ok=True)
                destination = sqlite3.connect(backup_dir / f'{path.stem}-before-v2-{time.time_ns()}.sqlite3')
                try:
                    existing.backup(destination)
                finally:
                    destination.close()
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL,
          name TEXT NOT NULL, unit TEXT NOT NULL, category TEXT NOT NULL,
          price INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          institution TEXT NOT NULL, email TEXT NOT NULL, identification TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS quotes(id INTEGER PRIMARY KEY, number TEXT UNIQUE,
          client TEXT NOT NULL, items TEXT NOT NULL, subtotal INTEGER NOT NULL,
          discount INTEGER NOT NULL, total INTEGER NOT NULL, notes TEXT NOT NULL,
          terms TEXT NOT NULL, core_name TEXT NOT NULL, contact TEXT NOT NULL,
          created TEXT NOT NULL, valid_until TEXT NOT NULL, status TEXT NOT NULL,
          author TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL,
          actor TEXT NOT NULL, action TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_records(id INTEGER PRIMARY KEY,
          kind TEXT NOT NULL, sheet TEXT NOT NULL, row_number INTEGER NOT NULL,
          reference TEXT NOT NULL, payload TEXT NOT NULL);
        ''')
        defaults = {'name': core, 'contact': '', 'logo_data': '', 'terms': 'Cotización sujeta a confirmación de disponibilidad. Precios expresados en COP. Definir las condiciones comerciales oficiales antes de emitir propuestas reales.'}
        for key, value in defaults.items():
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (key, value))
        operations.migrate(db)
        db.execute("INSERT OR REPLACE INTO settings VALUES ('schema_version','2')")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Do not log credentials or request bodies.
        pass

    def respond(self, status, data, content_type='application/json; charset=utf-8', headers=None):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def user(self, db=None):
        cookie = SimpleCookie()
        cookie.load(self.headers.get('Cookie', ''))
        token = cookie.get('session')
        session = SESSIONS.get(token.value) if token else None
        if not session or session['expires'] < time.time():
            return None, None
        return {'name': session['name'], 'username': session['name'], 'role': session['role']}, session

    def database_path(self):
        _, session = self.user()
        return self.server.data_dir / f"{session['core']}.sqlite3" if session else self.server.db_path

    def cores(self):
        result = []
        for path in sorted(self.server.data_dir.glob('*.sqlite3')):
            with connect(path) as db:
                row = db.execute("SELECT value FROM settings WHERE key='name'").fetchone()
                result.append({'id': path.stem, 'name': row[0]})
        return result

    def do_GET(self):
        if self.path == '/api/health':
            return self.respond(200, {'application':'COREBiller', 'data_directory_id':directory_id(self.server.data_dir)})
        if self.path in ('/', '/app.js', '/operations.js', '/lifecycle.js', '/style.css'):
            filename = {'/': 'index.html', '/app.js': 'app.js', '/operations.js': 'operations.js', '/lifecycle.js': 'lifecycle.js', '/style.css': 'style.css'}[self.path]
            kind = {'/': 'text/html', '/app.js': 'text/javascript', '/operations.js': 'text/javascript', '/lifecycle.js': 'text/javascript', '/style.css': 'text/css'}[self.path]
            return self.respond(200, (ROOT / 'static' / filename).read_bytes(), kind + '; charset=utf-8')
        if self.path == '/api/cores':
            return self.respond(200, self.cores())
        if not self.user()[0]:
            return self.respond(401, {'error': 'Crea un Core o selecciona uno para continuar.'})
        with connect(self.database_path()) as db:
            user, session = self.user(db)
            if not user:
                return self.respond(401, {'error': 'Selecciona un Core y un rol para continuar.'})
            if self.path == '/api/state':
                settings = dict(db.execute('SELECT key,value FROM settings').fetchall())
                return self.respond(200, {'user': dict(user), 'csrf': session['csrf'], 'settings': settings,
                    'permissions': operations.permissions(db, user['role']),
                    'accounts': [operations.account(db, r) for r in db.execute("SELECT * FROM quotes WHERE status<>'Eliminada' ORDER BY id DESC")],
                    'reviews': [dict(r) for r in db.execute('SELECT * FROM source_reviews')],
                    'services': [dict(r) for r in db.execute('SELECT * FROM services ORDER BY name')],
                    'clients': [dict(r) for r in db.execute('SELECT * FROM clients ORDER BY name')],
                    'quotes': [dict(r) for r in db.execute("SELECT * FROM quotes WHERE status<>'Eliminada' ORDER BY id DESC")],
                    'audit': [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50')] if user['role'] == 'admin' else []})
            if self.path == '/api/backup':
                import tempfile
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / 'backup.sqlite3'
                    destination = sqlite3.connect(path)
                    try:
                        db.backup(destination)
                    finally:
                        destination.close()
                    return self.respond(200, path.read_bytes(), 'application/octet-stream',
                                        {'Content-Disposition': f'attachment; filename="{session["core"]}-{date.today()}.sqlite3"'})
            if self.path == '/api/source':
                exists = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='source_records'").fetchone()
                records = [dict(r) for r in db.execute('SELECT * FROM source_records ORDER BY id')] if exists else []
                return self.respond(200, records)
            if self.path == '/api/services.csv':
                out = io.StringIO(newline='')
                writer = csv.writer(out)
                writer.writerow(['code', 'name', 'unit', 'category', 'price'])
                for r in db.execute('SELECT * FROM services WHERE active=1 ORDER BY code'):
                    writer.writerow([r['code'], r['name'], r['unit'], r['category'], f"{r['price']/100:.2f}"])
                return self.respond(200, out.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8',
                                    {'Content-Disposition': 'attachment; filename="servicios.csv"'})
        self.respond(404, {'error': 'Ruta inexistente.'})

    def do_POST(self):
        try:
            self.post()
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.respond(400, {'error': str(error) or 'Datos inválidos.'})
        except sqlite3.IntegrityError:
            self.respond(400, {'error': 'El código o usuario ya existe, o la referencia es inválida.'})
        except Exception:
            self.respond(500, {'error': 'No se pudo completar la operación.'})

    def post(self):
        # Reject requests from other websites, including DNS rebinding hosts.
        expected = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') not in (expected, f'localhost:{self.server.server_port}'):
            return self.respond(403, {'error': 'Host no permitido.'})
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://{expected}', f'http://localhost:{self.server.server_port}'):
            return self.respond(403, {'error': 'Origen no permitido.'})
        length = int(self.headers.get('Content-Length', '0'))
        maximum = 20000000 if self.path == '/api/restore' else 1000000
        if length < 0 or length > maximum:
            raise ValueError('La solicitud supera el tamaño permitido.')
        data = json.loads(self.rfile.read(length) or b'{}')
        if not isinstance(data, dict):
            raise ValueError('Se esperaba un objeto JSON.')
        if self.path == '/api/start':
            role = required(data, 'role')
            if role not in ROLES:
                raise ValueError('Rol inválido.')
            cores = self.cores()
            core = str(data.get('core', ''))
            if data.get('new_core'):
                role = 'admin'
                name = required(data, 'new_core', 100)
                if any(c['name'].casefold() == name.casefold() for c in cores):
                    raise ValueError('Ese Core ya existe. Selecciónalo en la lista.')
                core = 'core-' + secrets.token_hex(6)
                initialize(self.server.data_dir / f'{core}.sqlite3', name)
            elif core not in {c['id'] for c in cores}:
                raise ValueError('Selecciona un Core válido.')
            name = str(data.get('name', '')).strip()[:100] or {'admin':'Administrador local','cotizador':'Cotizador local','consulta':'Consulta local'}[role]
            old_user, old_session = self.user()
            if old_session:
                for token in list(SESSIONS):
                    if SESSIONS[token] is old_session:
                        del SESSIONS[token]
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {'core':core,'role':role,'name':name,'csrf':secrets.token_urlsafe(24),'expires':time.time()+8*3600}
            return self.respond(200, {'ok':True}, headers={'Set-Cookie':f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
        if not self.user()[0]:
            return self.respond(401, {'error': 'Crea un Core o selecciona uno para continuar.'})
        with connect(self.database_path()) as db:
            user, session = self.user(db)
            if not user:
                return self.respond(401, {'error': 'Selecciona un Core y un rol para continuar.'})
            if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
                return self.respond(403, {'error': 'Sesión inválida. Recarga la página.'})
            if self.path == '/api/logout':
                for token in list(SESSIONS):
                    if SESSIONS[token] is session:
                        del SESSIONS[token]
                return self.respond(200, {'ok': True}, headers={'Set-Cookie': 'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            # Serialize validation + mutation so simultaneous requests cannot spend the same balance.
            db.execute('BEGIN IMMEDIATE')
            route_permissions = {'/api/settings':'catalogue', '/api/services':'catalogue', '/api/import':'catalogue',
                '/api/clients':'clients', '/api/quotes':'quotes', '/api/status':'quotes', '/api/delete-draft':'quotes',
                '/api/consumptions':'consumptions', '/api/void-consumption':'consumptions',
                '/api/administration':'administration', '/api/void-document':'administration', '/api/source-review':'review_source'}
            allowed = operations.permissions(db, user['role'])
            if (self.path in ('/api/permissions', '/api/restore') and user['role'] != 'admin') or (self.path in route_permissions and not allowed[route_permissions[self.path]]):
                return self.respond(403, {'error': 'Tu rol no permite esta operación.'})
            previous = None
            if self.path in ('/api/services', '/api/clients') and data.get('id'):
                table = 'services' if self.path == '/api/services' else 'clients'
                row = db.execute(f'SELECT * FROM {table} WHERE id=?', (int(data['id']),)).fetchone()
                previous = dict(row) if row else None
            elif self.path in ('/api/settings', '/api/permissions'):
                previous = dict(db.execute('SELECT key,value FROM settings').fetchall())
                if self.path == '/api/settings':
                    previous['logo_configured'] = bool(previous.pop('logo_data', ''))
            if self.path == '/api/restore':
                name = required(data, 'name', 100)
                if any(c['name'].casefold() == name.casefold() for c in self.cores()):
                    raise ValueError('Usa un nombre diferente para el Core recuperado.')
                try:
                    raw = base64.b64decode(required(data, 'file', 19000000), validate=True)
                except (ValueError, base64.binascii.Error):
                    raise ValueError('La copia no es válida.')
                if not raw.startswith(b'SQLite format 3\x00'):
                    raise ValueError('Selecciona una copia SQLite de COREBiller.')
                restored = self.server.data_dir / ('core-' + secrets.token_hex(6) + '.sqlite3')
                try:
                    restored.write_bytes(raw)
                    with connect(restored) as candidate:
                        if candidate.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                            raise ValueError('La copia está dañada.')
                        version = candidate.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
                        if not version or version[0] != '2':
                            raise ValueError('La copia debe corresponder a COREBiller versión 2.')
                        for table in ('quotes','services','clients','consumptions','administration','source_reviews','audit','source_records'):
                            candidate.execute(f'SELECT * FROM {table} LIMIT 1')
                    initialize(restored, name)
                    with connect(restored) as candidate:
                        candidate.execute("UPDATE settings SET value=? WHERE key='name'", (name,))
                except Exception:
                    restored.unlink(missing_ok=True)
                    raise ValueError('No se pudo recuperar la copia. Verifica que sea una base completa de COREBiller v2.')
            elif operations.mutate(db, self.path, data, user, money, required):
                pass
            elif self.path == '/api/settings':
                for key in ('name', 'contact', 'terms'):
                    value = required(data, key, 4000) if key != 'contact' else str(data.get(key, ''))[:500]
                    db.execute('UPDATE settings SET value=? WHERE key=?', (value, key))
                if 'logo_data' in data:
                    db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)',
                               ('logo_data', clean_logo(data['logo_data'])))
            elif self.path == '/api/clients':
                values = (required(data, 'name', 150), required(data, 'institution', 200),
                          str(data.get('email', '')).strip()[:200], str(data.get('identification', '')).strip()[:100],
                          str(data.get('address', ''))[:300], str(data.get('phone', ''))[:100], str(data.get('city', ''))[:100],
                          str(data.get('tariff', ''))[:100], operations.check_requirement(str(data.get('requirement', '')), True))
                if data.get('id'):
                    cur = db.execute('UPDATE clients SET name=?,institution=?,email=?,identification=?,address=?,phone=?,city=?,tariff=?,requirement=? WHERE id=?', (*values, int(data['id'])))
                    if not cur.rowcount:
                        raise ValueError('Cliente inexistente.')
                else:
                    db.execute('INSERT INTO clients(name,institution,email,identification,address,phone,city,tariff,requirement) VALUES (?,?,?,?,?,?,?,?,?)', values)
            elif self.path == '/api/services':
                operations.validate_name(db, required(data, 'name', 200), int(data.get('id', 0)))
                values = (required(data, 'code', 50), required(data, 'name', 200), required(data, 'unit', 80),
                          required(data, 'category', 100), money(data.get('price')),
                          operations.check_requirement(data.get('requirement', 'ninguno')), str(data.get('description', ''))[:2000])
                if data.get('id'):
                    cur = db.execute('UPDATE services SET code=?,name=?,unit=?,category=?,price=?,requirement=?,description=? WHERE id=?', (*values, int(data['id'])))
                    if not cur.rowcount:
                        raise ValueError('Servicio inexistente.')
                else:
                    db.execute('INSERT INTO services(code,name,unit,category,price,requirement,description) VALUES (?,?,?,?,?,?,?)', values)
            elif self.path == '/api/import':
                reader = csv.DictReader(io.StringIO(required(data, 'csv', 900000).lstrip('\ufeff')))
                if not reader.fieldnames or not {'code','name','unit','category','price'}.issubset(reader.fieldnames):
                    raise ValueError('Encabezados requeridos: code,name,unit,category,price. Separador: coma.')
                seen = set()
                count = 0
                for row in reader:
                    code = required(row, 'code', 50)
                    if code in seen:
                        raise ValueError(f'Código duplicado en el archivo: {code}. No se importó ningún cambio.')
                    seen.add(code)
                    old = db.execute('SELECT id FROM services WHERE code=?', (code,)).fetchone()
                    operations.validate_name(db, required(row, 'name', 200), old['id'] if old else 0)
                    values = (code, required(row, 'name', 200), required(row, 'unit', 80), required(row, 'category', 100), money(row['price']))
                    db.execute('INSERT INTO services(code,name,unit,category,price) VALUES (?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name,unit=excluded.unit,category=excluded.category,price=excluded.price', values)
                    count += 1
                if not count:
                    raise ValueError('El archivo no contiene servicios.')
            elif self.path == '/api/quotes':
                draft = None
                if data.get('id'):
                    draft = db.execute('SELECT * FROM quotes WHERE id=?', (int(data['id']),)).fetchone()
                    if not draft or draft['status'] != 'Borrador':
                        raise ValueError('Solo se pueden editar borradores.')
                    previous = dict(draft)
                source = None
                if data.get('source_id'):
                    if not allowed['review_source']:
                        return self.respond(403, {'error':'Tu rol no migra registros históricos.'})
                    source = db.execute("SELECT r.*,v.reason FROM source_records r JOIN source_reviews v ON v.source_id=r.id WHERE r.id=? AND r.kind='cotizacion'", (int(data['source_id']),)).fetchone()
                    if not source:
                        raise ValueError('Revisa el registro de origen antes de migrarlo.')
                    if any(json.loads(r['context']).get('source_id') == source['id'] for r in db.execute('SELECT context FROM quotes')):
                        raise ValueError('Esta fila ya fue migrada. El consecutivo original repetido no identifica una fila única.')
                client = db.execute('SELECT * FROM clients WHERE id=?', (int(data['client_id']),)).fetchone()
                if not client:
                    raise ValueError('Selecciona un cliente válido.')
                source_items = data.get('items')
                if not isinstance(source_items, list) or not 1 <= len(source_items) <= 100:
                    raise ValueError('Agrega entre 1 y 100 ítems.')
                items = []
                for item in source_items:
                    service = db.execute('SELECT * FROM services WHERE id=? AND active=1', (int(item['service_id']),)).fetchone()
                    if not service:
                        raise ValueError('Servicio inexistente.')
                    try:
                        qty = Decimal(str(item['quantity']))
                    except InvalidOperation:
                        raise ValueError('Cantidad inválida.')
                    if not qty.is_finite() or qty <= 0 or qty > 1000000:
                        raise ValueError('La cantidad debe ser mayor que cero y no superar un millón.')
                    amount = int((qty*service['price']).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                    price = service['price']
                    if item.get('price') is not None and str(item['price']) != '':
                        price = money(item['price'])
                        if price != service['price']:
                            if not allowed['approve_prices']:
                                raise ValueError('Tu rol no aprueba precios personalizados.')
                            required(item, 'price_reason', 1000)
                    pct = money(item.get('discount', 0))
                    if pct > 10000 or (pct and not allowed['approve_prices']):
                        raise ValueError('Descuento por ítem inválido o sin permiso.')
                    amount = operations.cents(qty * price)
                    if amount > 100000000000000:
                        raise ValueError('El importe del ítem supera el máximo permitido de un billón de COP.')
                    net = amount - operations.cents(Decimal(amount)*pct/10000)
                    requirement = item.get('requirement') or client['requirement'] or service['requirement']
                    operations.check_requirement(requirement)
                    items.append({**dict(service), 'price': price, 'quantity': str(qty), 'amount': amount,
                                  'net_amount': net, 'line_discount': amount-net, 'requirement': requirement,
                                  'price_reason': str(item.get('price_reason', ''))[:1000]})
                subtotal = sum(i['amount'] for i in items)
                line_discount = sum(i['line_discount'] for i in items)
                discount_pct = money(data.get('discount', 0))
                if discount_pct > 10000:
                    raise ValueError('El descuento debe estar entre 0 y 100 %.')
                if discount_pct and not allowed['approve_prices']:
                    raise ValueError('Tu rol no aprueba descuentos.')
                discount = line_discount + operations.cents(Decimal(subtotal-line_discount)*discount_pct/10000)
                valid = date.fromisoformat(required(data, 'valid_until'))
                created = date.fromisoformat(data.get('created_date', date.today().isoformat())) if source else date.today()
                if source and created > date.today():
                    raise ValueError('La fecha histórica no puede estar en el futuro.')
                if valid < (created if source else date.today()):
                    raise ValueError('La vigencia no puede estar en el pasado.')
                if source and subtotal-discount != money(data['confirmed_total']):
                    raise ValueError('El total calculado no coincide con el total revisado. Confirma cantidad, precio y descuentos antes de migrar.')
                status = data.get('initial_status', 'Emitida') if source else data.get('save_as', 'Emitida')
                if status not in (('Emitida', 'Aceptada', 'Rechazada') if source else ('Borrador', 'Emitida')):
                    raise ValueError('Estado inicial inválido.')
                settings = dict(db.execute('SELECT key,value FROM settings').fetchall())
                values = (json.dumps(dict(client), ensure_ascii=False), json.dumps(items, ensure_ascii=False), subtotal, discount,
                     subtotal-discount, str(data.get('notes', ''))[:4000], settings['terms'], settings['name'], settings['contact'],
                     created.isoformat(), valid.isoformat(), status, user['name'])
                if draft:
                    quote_id = draft['id']
                    db.execute('UPDATE quotes SET client=?,items=?,subtotal=?,discount=?,total=?,notes=?,terms=?,core_name=?,contact=?,created=?,valid_until=?,status=?,author=? WHERE id=?', (*values, quote_id))
                else:
                    cur = db.execute('INSERT INTO quotes(client,items,subtotal,discount,total,notes,terms,core_name,contact,created,valid_until,status,author) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', values)
                    quote_id = cur.lastrowid
                number = f"BORRADOR-{quote_id:04d}" if status == 'Borrador' else f"{session['core'].upper()}-{date.today().year}-{quote_id:04d}"
                db.execute('UPDATE quotes SET number=? WHERE id=?', (number, quote_id))
                context = {key: str(data.get(key, ''))[:2000] for key in ('project', 'project_code', 'responsible', 'samples', 'email_notes', 'discount_reason')}
                context['core_logo'] = settings.get('logo_data', '')
                context['discount_percent'] = str(Decimal(discount_pct)/100)
                context['line_discount_percents'] = [str(i.get('discount', 0)) for i in source_items]
                if source:
                    context.update({'source_id':source['id'], 'source_reference':source['reference'], 'source_sheet':source['sheet'], 'source_row':source['row_number']})
                db.execute('UPDATE quotes SET context=? WHERE id=?', (json.dumps(context, ensure_ascii=False), quote_id))
            elif self.path == '/api/delete-draft':
                row = db.execute('SELECT * FROM quotes WHERE id=?', (int(data['id']),)).fetchone()
                if not row or row['status'] != 'Borrador':
                    raise ValueError('Solo se pueden borrar borradores. Cancela las cotizaciones emitidas.')
                if any(db.execute(f'SELECT 1 FROM {table} WHERE quote_id=?', (row['id'],)).fetchone() for table in ('consumptions', 'administration')):
                    raise ValueError('Este registro tiene movimientos y no puede borrarse.')
                previous = dict(row)
                # Tombstone preserves audit evidence and prevents reuse of identifiers.
                db.execute("UPDATE quotes SET status='Eliminada' WHERE id=?", (row['id'],))
            elif self.path == '/api/status':
                status = required(data, 'status')
                if status not in ('Aceptada', 'Rechazada', 'Emitida', 'Cancelada'):
                    raise ValueError('Estado inválido.')
                row = db.execute('SELECT * FROM quotes WHERE id=?', (int(data['id']),)).fetchone()
                permitted = {'Emitida':('Borrador',), 'Aceptada':('Emitida',), 'Rechazada':('Emitida',), 'Cancelada':('Emitida','Aceptada','Rechazada')}
                if not row or row['status'] not in permitted[status]:
                    raise ValueError('Ese cambio de estado no está permitido.')
                previous = dict(row)
                if status == 'Emitida':
                    if date.fromisoformat(row['valid_until']) < date.today():
                        raise ValueError('Actualiza la vigencia del borrador antes de emitir.')
                    number = f"{session['core'].upper()}-{date.today().year}-{row['id']:04d}"
                    db.execute('UPDATE quotes SET number=?,created=? WHERE id=?', (number,date.today().isoformat(),row['id']))
                if status == 'Cancelada':
                    context = json.loads(row['context'])
                    context.update({'cancel_reason': required(data,'reason',1000), 'cancelled_at':date.today().isoformat(), 'cancelled_by':user['name']})
                    db.execute('UPDATE quotes SET context=? WHERE id=?', (json.dumps(context,ensure_ascii=False),row['id']))
                db.execute('UPDATE quotes SET status=? WHERE id=?', (status, int(data['id'])))
            else:
                return self.respond(404, {'error': 'Ruta inexistente.'})
            audit_data = {k:v for k,v in data.items() if k not in ('file','csv','logo_data')}
            if 'logo_data' in data:
                audit_data['logo_configured'] = bool(data['logo_data'])
            detail = json.dumps({'route':self.path, 'data':audit_data,
                                 'previous':previous}, ensure_ascii=False)
            db.execute('INSERT INTO audit(at,actor,action) VALUES (?,?,?)',
                       (time.strftime('%Y-%m-%d %H:%M:%S'), user['username'], detail))
        self.respond(200, {'ok': True})


def seed_example_quote(db):
    """Make the example Core demonstrate the quote-to-service-and-payment flow."""
    is_demo = db.execute("SELECT value FROM settings WHERE key='is_demo'").fetchone()
    marker = 'Ejemplo ficticio para demostrar el seguimiento.'
    if (not is_demo or is_demo[0] != 'true'
            or db.execute('SELECT 1 FROM quotes WHERE notes LIKE ?', (marker + '%',)).fetchone()):
        return
    client = db.execute("SELECT * FROM clients WHERE identification='DEMO-001'").fetchone()
    service = db.execute("SELECT * FROM services WHERE code='DEMO-01'").fetchone()
    if not client or not service:
        return
    now = date.today()
    quantity = Decimal('4')
    amount = int(quantity * service['price'])
    item = {**dict(service), 'quantity': str(quantity), 'amount': amount,
            'net_amount': amount, 'line_discount': 0, 'price_reason': ''}
    context = {'project': 'Caracterización de muestras de ejemplo',
               'project_code': f'DEMO-{now.year}-01', 'responsible': 'Dr. Andrés Gómez',
               'samples': '4 muestras ficticias', 'email_notes': '',
               'discount_reason': '', 'discount_percent': '0',
               'line_discount_percents': ['0'], 'core_logo': '',
               'demo_walkthrough': True}
    cur = db.execute('''INSERT INTO quotes(client,items,subtotal,discount,total,notes,terms,core_name,
        contact,created,valid_until,status,author,context) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (json.dumps(dict(client), ensure_ascii=False), json.dumps([item], ensure_ascii=False),
         amount, 0, amount, marker + ' Sin validez comercial.',
         db.execute("SELECT value FROM settings WHERE key='terms'").fetchone()[0],
         'EjemploCORE', 'EjemploCORE · contacto@example.org', now.isoformat(),
         (now + timedelta(days=30)).isoformat(), 'Aceptada', 'Administrador EjemploCORE',
         json.dumps(context, ensure_ascii=False)))
    quote_id = cur.lastrowid
    db.execute('UPDATE quotes SET number=? WHERE id=?',
               (f'EJEMPLOCORE-{now.year}-{quote_id:04d}', quote_id))
    execution = {'date': now.isoformat(), 'analyst': 'Dra. Laura Pérez',
                 'author': 'Administrador EjemploCORE', 'service_id': service['id'],
                 'service_name': service['name'], 'executed_quantity': '1',
                 'executed_unit': service['unit'], 'samples': 'Muestra de demostración 01',
                 'duration': '1 hora', 'notes': 'Registro ficticio de ejemplo.',
                 'price_basis': 'acordado', 'requirement': 'ninguno'}
    db.execute('INSERT INTO consumptions(quote_id,line_index,quantity,amount,payload) VALUES (?,?,?,?,?)',
               (quote_id, 0, '1', service['price'], json.dumps(execution, ensure_ascii=False)))
    db.execute('''INSERT INTO administration(quote_id,kind,amount,date,reference,notes)
        VALUES (?,?,?,?,?,?)''', (quote_id, 'pago', 8000000, now.isoformat(), 'DEMO-PAGO-01',
        'Pago parcial ficticio de demostración.'))


def bootstrap(data_dir):
    """Keep the example walkthrough available; user-created Core databases stay empty."""
    data_dir.mkdir(parents=True, exist_ok=True)
    if not any(data_dir.glob('*.sqlite3')):
        path = data_dir / 'ejemplocore.sqlite3'
        initialize(path, 'EjemploCORE')
        with connect(path) as db:
            db.execute("UPDATE settings SET value='Datos ficticios para explorar COREBiller. Sin validez comercial.' WHERE key='terms'")
            db.execute("INSERT INTO settings VALUES ('is_demo','true')")
            db.execute("INSERT INTO services(code,name,unit,category,price) VALUES ('DEMO-01','Análisis de ejemplo','muestra','General',5000000)")
            db.execute("INSERT INTO services(code,name,unit,category,price) VALUES ('DEMO-02','Uso de equipo de ejemplo','hora','General',10000000)")
            db.execute("INSERT INTO clients(name,institution,email,identification) VALUES ('Cliente de ejemplo','Institución ficticia','cliente@example.org','DEMO-001')")
    for path in data_dir.glob('*.sqlite3'):
        initialize(path, path.stem)
        with connect(path) as db:
            seed_example_quote(db)


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def directory_id(path):
    return hashlib.sha256(os.path.normcase(str(path.resolve())).encode('utf-8')).hexdigest()


def occupied_port_message(port, data_dir):
    url = f'http://127.0.0.1:{port}'
    try:
        # A loopback health check must not use external proxy settings or follow redirects.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(url+'/api/health', timeout=2) as response:
            health = json.loads(response.read(4096))
        if isinstance(health, dict) and health.get('application') == 'COREBiller':
            if health.get('data_directory_id') == directory_id(data_dir):
                print(f'COREBiller ya está funcionando.\nAbre {url}\nPuedes usar la instancia existente; no necesitas iniciarla otra vez.', flush=True)
                return 0
            print(f'El puerto {port} está ocupado por COREBiller de otra carpeta.', file=sys.stderr)
        else:
            print(f'El puerto {port} está ocupado por otra aplicación.', file=sys.stderr)
    except (OSError, ValueError):
        print(f'El puerto {port} está ocupado. No se pudo identificar la aplicación que lo utiliza.', file=sys.stderr)
    alternative = port+1 if port<65535 else port-1
    print(f'Para usar esta copia, detén la instancia anterior con Ctrl+C en su terminal o elige otro puerto:\n.\\Start-COREBiller.ps1 -Port {alternative}', file=sys.stderr)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description='COREBiller local')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('El puerto debe estar entre 1 y 65535.')
    data_dir = ROOT / 'data'
    try:
        server = LocalServer(('127.0.0.1', args.port), Handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE or getattr(error, 'winerror', None) == 10048:
            return occupied_port_message(args.port, data_dir)
        print(f'No se pudo iniciar COREBiller en el puerto {args.port}: {error}', file=sys.stderr)
        return 1
    try:
        bootstrap(data_dir)
        server.data_dir = data_dir
        server.db_path = next(data_dir.glob('*.sqlite3'))
        print(f'COREBiller local · http://127.0.0.1:{args.port}\nDatos: {data_dir}\nSin credenciales. Selecciona o crea un Core y elige un rol.\nCtrl+C para detener.', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
