"""Local account ledger. Amounts are integer COP cents; quantities are decimal strings."""
import json
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

PERMISSIONS = ('catalogue', 'clients', 'quotes', 'consumptions', 'administration', 'approve_prices', 'review_source')
DEFAULT_PERMISSIONS = {
    'admin': dict.fromkeys(PERMISSIONS, True),
    'cotizador': {p: p in ('clients', 'quotes', 'consumptions', 'administration', 'approve_prices') for p in PERMISSIONS},
    'consulta': {p: p == 'approve_prices' for p in PERMISSIONS},
}
REQUIREMENTS = ('ninguno', 'pago', 'anticipo', 'orden', 'traslado', 'autorizacion')


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def migrate(db):
    additions = {
        'services': {'requirement': "TEXT NOT NULL DEFAULT 'ninguno'", 'description': "TEXT NOT NULL DEFAULT ''"},
        'clients': {'address': "TEXT NOT NULL DEFAULT ''", 'phone': "TEXT NOT NULL DEFAULT ''", 'city': "TEXT NOT NULL DEFAULT ''", 'tariff': "TEXT NOT NULL DEFAULT ''", 'requirement': "TEXT NOT NULL DEFAULT ''"},
        'quotes': {'context': "TEXT NOT NULL DEFAULT '{}'"},
    }
    for table, columns in additions.items():
        existing = {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}
        for column, definition in columns.items():
            if column not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS consumptions(id INTEGER PRIMARY KEY, quote_id INTEGER NOT NULL REFERENCES quotes(id),
        line_index INTEGER NOT NULL, quantity TEXT NOT NULL, amount INTEGER NOT NULL,
        payload TEXT NOT NULL, void_reason TEXT NOT NULL DEFAULT '', replaces INTEGER REFERENCES consumptions(id));
      CREATE TABLE IF NOT EXISTS administration(id INTEGER PRIMARY KEY, quote_id INTEGER NOT NULL REFERENCES quotes(id),
        kind TEXT NOT NULL, amount INTEGER NOT NULL, date TEXT NOT NULL, reference TEXT NOT NULL,
        notes TEXT NOT NULL, void_reason TEXT NOT NULL DEFAULT '');
      CREATE TABLE IF NOT EXISTS source_reviews(source_id INTEGER PRIMARY KEY REFERENCES source_records(id),
        payload TEXT NOT NULL, reason TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL);
    ''')
    db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('permissions', json.dumps(DEFAULT_PERMISSIONS)))
    names = [dict(r) for r in db.execute('SELECT id,name,category,code FROM services ORDER BY id')]
    counts = {}
    for row in names:
        key = normalized(row['name'])
        counts[key] = counts.get(key, 0) + 1
    occupied = {normalized(row['name']) for row in names if counts[normalized(row['name'])] == 1}
    for row in names:
        if counts[normalized(row['name'])] > 1:
            name = f"{row['name']} · {row['category']}"
            if normalized(name) in occupied:
                name += f" · {row['code']}"
            occupied.add(normalized(name))
            db.execute('UPDATE services SET name=? WHERE id=?', (name, row['id']))


def permissions(db, role):
    return json.loads(db.execute("SELECT value FROM settings WHERE key='permissions'").fetchone()[0])[role]


def number(value, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError('Cantidad inválida.')
    if not result.is_finite() or result < 0 or result > 1000000 or (positive and result == 0):
        raise ValueError('Cantidad fuera del rango permitido.')
    return result


def cents(value):
    return int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def budgets(q):
    items = json.loads(q['items'])
    # Allocate global discount to lines, preserving every cent (largest remainders).
    amounts = [i.get('net_amount', i['amount']) for i in items]
    subtotal = sum(amounts)
    if not subtotal:
        return [0] * len(items)
    raw = [Decimal(a) * q['total'] / subtotal for a in amounts]
    allocated = [int(a) for a in raw]
    for index in sorted(range(len(raw)), key=lambda i: raw[i]-allocated[i], reverse=True)[:q['total']-sum(allocated)]:
        allocated[index] += 1
    return allocated


def account(db, q):
    limits = budgets(q)
    rows = [dict(r) for r in db.execute('SELECT * FROM consumptions WHERE quote_id=? ORDER BY id', (q['id'],))]
    documents = [dict(r) for r in db.execute('SELECT * FROM administration WHERE quote_id=? ORDER BY id', (q['id'],))]
    lines = []
    for index, item in enumerate(json.loads(q['items'])):
        active = [r for r in rows if r['line_index'] == index and not r['void_reason']]
        qty = sum((Decimal(r['quantity']) for r in active), Decimal(0))
        used = sum(r['amount'] for r in active)
        lines.append({'index': index, 'name': item['name'], 'unit': item['unit'], 'contracted': item['quantity'],
                      'consumed': str(qty), 'remaining_quantity': str(Decimal(item['quantity'])-qty),
                      'budget': limits[index], 'consumed_amount': used, 'remaining_amount': limits[index]-used})
    paid = sum(r['amount'] for r in documents if r['kind'] == 'pago' and not r['void_reason'])
    return {'quote_id': q['id'], 'lines': lines, 'consumptions': rows, 'documents': documents,
            'consumed_amount': sum(l['consumed_amount'] for l in lines),
            'remaining_amount': q['total']-sum(l['consumed_amount'] for l in lines),
            'paid': paid, 'receivable': q['total']-paid}


def validate_name(db, name, service_id=0):
    key = normalized(name)
    if any(normalized(r['name']) == key for r in db.execute('SELECT id,name FROM services WHERE id<>?', (service_id,))):
        raise ValueError('Ya existe un servicio con ese nombre. Describe la variante en el nombre; para otro tipo de tarifa utiliza un nombre que lo identifique.')


def check_requirement(value, allow_empty=False):
    if value not in REQUIREMENTS and not (allow_empty and value == ''):
        raise ValueError('Requisito de inicio inválido.')
    return value


def mutate(db, route, data, user, money, required):
    """Return True for routes handled here. Caller commits audit and transaction."""
    if route == '/api/permissions':
        if user['role'] != 'admin':
            raise ValueError('Solo Administración puede configurar permisos.')
        roles = data.get('permissions')
        if not isinstance(roles, dict) or set(roles) != set(DEFAULT_PERMISSIONS):
            raise ValueError('Configura los tres roles.')
        for values in roles.values():
            if not isinstance(values, dict) or set(values) != set(PERMISSIONS) or any(type(v) is not bool for v in values.values()):
                raise ValueError('Configuración de permisos inválida.')
        db.execute("UPDATE settings SET value=? WHERE key='permissions'", (json.dumps(roles),))
    elif route == '/api/consumptions':
        source_id = data.get('source_id')
        if source_id:
            if not permissions(db, user['role'])['review_source']:
                raise ValueError('Tu rol no migra movimientos históricos.')
            source = db.execute("SELECT r.id FROM source_records r JOIN source_reviews v ON v.source_id=r.id WHERE r.id=? AND r.kind='servicio'", (int(source_id),)).fetchone()
            if not source:
                raise ValueError('Revisa la fila de servicio antes de migrarla.')
            if any(json.loads(r['payload']).get('source_id') == int(source_id) and not r['void_reason'] for r in db.execute('SELECT payload,void_reason FROM consumptions')):
                raise ValueError('Esta fila ya tiene un consumo activo migrado.')
        q = db.execute('SELECT * FROM quotes WHERE id=?', (int(data['quote_id']),)).fetchone()
        if not q or q['status'] != 'Aceptada':
            raise ValueError('Selecciona una cotización aceptada.')
        index = int(data['line_index'])
        items = json.loads(q['items'])
        if not 0 <= index < len(items):
            raise ValueError('Ítem contratado inexistente.')
        item = items[index]
        qty = number(data['quantity'], True)
        executed_qty = number(data.get('executed_quantity') or qty, True)
        day = date.fromisoformat(required(data, 'date'))
        if day > date.today():
            raise ValueError('El consumo no puede tener fecha futura.')
        actor = required(data, 'analyst', 150)
        replaces = data.get('replaces')
        reason = ''
        if replaces:
            reason = required(data, 'reason', 1000)
            old = db.execute('SELECT * FROM consumptions WHERE id=?', (int(replaces),)).fetchone()
            if not old or old['void_reason']:
                raise ValueError('El consumo a corregir no existe o está anulado.')
            db.execute('UPDATE consumptions SET void_reason=? WHERE id=?', (reason, int(replaces)))
        current = account(db, q)
        requirement = item.get('requirement', 'ninguno')
        docs = [d for d in current['documents'] if not d['void_reason']]
        allowed = requirement == 'ninguno' or any(d['kind'] == requirement for d in docs)
        if requirement == 'pago':
            allowed = current['paid'] >= q['total']
        if requirement == 'anticipo':
            allowed = current['paid'] > 0
        if not allowed:
            raise ValueError(f'Falta registrar el requisito de inicio: {requirement}.')
        balance = current['lines'][index]
        basis = data.get('price_basis', 'acordado')
        actual_service = db.execute('SELECT * FROM services WHERE id=?', (int(data.get('service_id', item['id'])),)).fetchone()
        if not actual_service:
            raise ValueError('Servicio ejecutado inexistente.')
        if basis == 'acordado':
            # Difference of cumulative rounded values avoids drift for fractional units.
            rate = Decimal(balance['budget']) / Decimal(item['quantity'])
            amount = cents((Decimal(balance['consumed']) + qty) * rate)-cents(Decimal(balance['consumed'])*rate)
        elif basis == 'actual':
            amount = cents(executed_qty * actual_service['price'])
        elif basis == 'personalizado':
            if not permissions(db, user['role'])['approve_prices']:
                raise ValueError('Tu rol no aprueba precios personalizados.')
            required(data, 'price_reason', 1000)
            amount = cents(executed_qty * money(data['price']))
        else:
            raise ValueError('Selecciona precio acordado, actual o personalizado.')
        if qty > Decimal(balance['remaining_quantity']) or amount > balance['remaining_amount']:
            raise ValueError('El consumo supera las cantidades o el dinero contratado. Amplía la contratación con una nueva cotización.')
        payload = {'service_id': actual_service['id'], 'service_name': actual_service['name'], 'date': day.isoformat(),
                   'analyst': actor, 'samples': str(data.get('samples', ''))[:2000], 'duration': str(data.get('duration', ''))[:200],
                   'notes': str(data.get('notes', ''))[:2000], 'price_basis': basis, 'price_reason': str(data.get('price_reason', ''))[:1000],
                   'executed_quantity': str(executed_qty), 'executed_unit': actual_service['unit'],
                   'source_id': int(source_id) if source_id else None,
                   'author': user['name'], 'correction_reason': reason}
        db.execute('INSERT INTO consumptions(quote_id,line_index,quantity,amount,payload,replaces) VALUES (?,?,?,?,?,?)',
                   (q['id'], index, str(qty), amount, json.dumps(payload, ensure_ascii=False), replaces))
    elif route == '/api/void-consumption':
        cur = db.execute("UPDATE consumptions SET void_reason=? WHERE id=? AND void_reason=''", (required(data, 'reason', 1000), int(data['id'])))
        if not cur.rowcount:
            raise ValueError('Consumo inexistente o ya anulado.')
    elif route == '/api/administration':
        q = db.execute('SELECT * FROM quotes WHERE id=?', (int(data['quote_id']),)).fetchone()
        if not q or q['status'] not in ('Aceptada', 'Cancelada'):
            raise ValueError('Selecciona una cuenta aceptada o cancelada para registrar su seguimiento.')
        kind = required(data, 'kind')
        if kind not in ('pago', 'orden', 'traslado', 'autorizacion', 'factura', 'recibo'):
            raise ValueError('Tipo de documento inválido.')
        day = date.fromisoformat(required(data, 'date')).isoformat()
        if day > date.today().isoformat():
            raise ValueError('El registro recibido no puede tener fecha futura.')
        amount = money(data.get('amount', 0))
        if kind == 'pago' and (not amount or amount > account(db, q)['receivable']):
            raise ValueError('El pago debe ser positivo y no superar el saldo por cobrar.')
        db.execute('INSERT INTO administration(quote_id,kind,amount,date,reference,notes) VALUES (?,?,?,?,?,?)',
                   (q['id'], kind, amount, day, required(data, 'reference', 300), str(data.get('notes', ''))[:2000]))
    elif route == '/api/void-document':
        cur = db.execute("UPDATE administration SET void_reason=? WHERE id=? AND void_reason=''", (required(data, 'reason', 1000), int(data['id'])))
        if not cur.rowcount:
            raise ValueError('Documento inexistente o ya anulado.')
    elif route == '/api/source-review':
        if not db.execute('SELECT id FROM source_records WHERE id=?', (int(data['id']),)).fetchone():
            raise ValueError('Registro original inexistente.')
        payload = data.get('payload')
        if not isinstance(payload, dict):
            raise ValueError('La corrección debe ser un objeto JSON.')
        db.execute('INSERT INTO source_reviews VALUES (?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET payload=excluded.payload,reason=excluded.reason,reviewer=excluded.reviewer,reviewed_at=excluded.reviewed_at',
                   (int(data['id']), json.dumps(payload, ensure_ascii=False), required(data, 'reason', 2000), user['name'], date.today().isoformat()))
    else:
        return False
    return True
