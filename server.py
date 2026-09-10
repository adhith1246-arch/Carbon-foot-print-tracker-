"""
Campus Carbon Footprint Tracker — Full Backend
Flask server with auth, JSON storage, and Excel export
"""
import json, os, io, hashlib, secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file, session
from flask_cors import CORS

app = Flask(__name__, static_folder='frontend', static_url_path='')
app.secret_key = secrets.token_hex(32)
CORS(app, supports_credentials=True)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
EMISSIONS_FILE = os.path.join(DATA_DIR, 'emissions.json')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

# ─── Helpers ───
FACTORS = {
    'electricity_kwh': 0.82, 'diesel_litre': 2.68, 'vehicle_km': 0.21,
    'veg_meal': 0.50, 'nonveg_meal': 3.00, 'food_waste_kg': 2.50, 'water_kl': 0.34,
}

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def calc_co2(d):
    e = d.get('electricity_kwh', 0) * FACTORS['electricity_kwh']
    di = d.get('diesel_litres', 0) * FACTORS['diesel_litre']
    v = d.get('vehicles_entered', 0) * 2 * FACTORS['vehicle_km']
    f = d.get('veg_meals', 0) * FACTORS['veg_meal'] + d.get('nonveg_meals', 0) * FACTORS['nonveg_meal']
    w = d.get('food_waste_kg', 0) * FACTORS['food_waste_kg']
    wa = d.get('water_kl', 0) * FACTORS['water_kl']
    total = e + di + v + f + w + wa
    return {k: round(val, 2) for k, val in
            {'electricity': e, 'diesel': di, 'vehicles': v, 'food': f, 'food_waste': w, 'water': wa, 'total': total}.items()}

def generate_suggestions(co2):
    tips = []
    if co2['electricity'] > 350:
        tips.append({'icon': 'lightbulb', 'type': 'warn', 'title': 'High Electricity Consumption',
                     'message': 'Switch off ACs and lights in unoccupied rooms.',
                     'saving': f"~{((co2['electricity']-350)*0.3):.1f} kg CO2/day"})
    if co2['food_waste'] > 25:
        tips.append({'icon': 'food', 'type': 'warn', 'title': 'Excess Food Waste',
                     'message': 'Reduce preparation by 15-20% or introduce pre-order system.',
                     'saving': f"~{(co2['food_waste']*0.4):.1f} kg CO2/day"})
    if co2['vehicles'] > 50:
        tips.append({'icon': 'bus', 'type': 'info', 'title': 'High Vehicle Entry',
                     'message': 'Encourage carpooling and campus e-shuttles.',
                     'saving': f"~{(co2['vehicles']*0.3):.1f} kg CO2/day"})
    tips.append({'icon': 'sun', 'type': 'info', 'title': 'Switch to Solar Energy',
                 'message': '500 kW solar panels could offset 60% of electricity emissions.',
                 'saving': f"~{(co2['electricity']*0.6):.1f} kg CO2/day"})
    return tips

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'success': False, 'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

# ─── Static Files ───
@app.route('/')
def index():
    if 'user' not in session:
        return send_from_directory('frontend', 'login.html')
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('frontend', path)

# ─── Auth APIs ───
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    department = data.get('department', '')

    if not all([name, email, password]):
        return jsonify({'success': False, 'error': 'All fields required'}), 400

    users = load_json(USERS_FILE)
    if any(u['email'] == email for u in users):
        return jsonify({'success': False, 'error': 'Email already registered'}), 400

    user = {'id': len(users)+1, 'name': name, 'email': email,
            'password': hash_pw(password), 'department': department,
            'role': 'admin' if len(users) == 0 else 'user',
            'created_at': datetime.now().isoformat()}
    users.append(user)
    save_json(USERS_FILE, users)

    session['user'] = {'id': user['id'], 'name': name, 'email': email,
                       'department': department, 'role': user['role']}
    return jsonify({'success': True, 'user': session['user']})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    users = load_json(USERS_FILE)
    user = next((u for u in users if u['email'] == email and u['password'] == hash_pw(password)), None)

    if not user:
        return jsonify({'success': False, 'error': 'Invalid email or password'}), 401

    session['user'] = {'id': user['id'], 'name': user['name'], 'email': user['email'],
                       'department': user['department'], 'role': user['role']}
    return jsonify({'success': True, 'user': session['user']})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/api/auth/me')
def me():
    if 'user' in session:
        return jsonify({'success': True, 'user': session['user']})
    return jsonify({'success': False}), 401

# ─── Emissions APIs ───
@app.route('/api/health')
def health():
    return jsonify({'status': 'OK', 'timestamp': datetime.now().isoformat()})

@app.route('/api/emissions/add', methods=['POST'])
@login_required
def add_emission():
    data = request.json
    co2 = calc_co2(data)
    record = {
        'id': len(load_json(EMISSIONS_FILE)) + 1,
        'department': data.get('department', ''),
        'date': data.get('date', datetime.now().strftime('%Y-%m-%d')),
        'electricity_kwh': data.get('electricity_kwh', 0),
        'diesel_litres': data.get('diesel_litres', 0),
        'vehicles_entered': data.get('vehicles_entered', 0),
        'veg_meals': data.get('veg_meals', 0),
        'nonveg_meals': data.get('nonveg_meals', 0),
        'food_waste_kg': data.get('food_waste_kg', 0),
        'water_kl': data.get('water_kl', 0),
        'co2': co2,
        'submitted_by': session['user']['name'],
        'submitted_at': datetime.now().isoformat(),
    }
    records = load_json(EMISSIONS_FILE)
    records.append(record)
    save_json(EMISSIONS_FILE, records)
    return jsonify({'success': True, 'data': record})

@app.route('/api/emissions/today')
@login_required
def today_emissions():
    today = datetime.now().strftime('%Y-%m-%d')
    records = [r for r in load_json(EMISSIONS_FILE) if r['date'] == today]
    totals = {'total':0,'electricity':0,'diesel':0,'vehicles':0,'food':0,'food_waste':0,'water':0}
    for r in records:
        for k in totals: totals[k] += r['co2'].get(k, 0)
    return jsonify({'success': True, 'date': today, 'totals': {k: round(v,2) for k,v in totals.items()}, 'count': len(records)})

@app.route('/api/emissions/trend')
@login_required
def trend():
    days = int(request.args.get('days', 30))
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    by_date = {}
    for r in load_json(EMISSIONS_FILE):
        if r['date'] >= cutoff:
            by_date[r['date']] = by_date.get(r['date'], 0) + r['co2']['total']
    return jsonify({'success': True, 'trend': [{'date': k, 'co2': round(v,2)} for k,v in sorted(by_date.items())]})

@app.route('/api/emissions/recent')
@login_required
def recent():
    records = sorted(load_json(EMISSIONS_FILE), key=lambda r: r.get('submitted_at',''), reverse=True)[:10]
    return jsonify({'success': True, 'records': records})

@app.route('/api/leaderboard')
@login_required
def leaderboard():
    cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    dept_map = {}
    for r in load_json(EMISSIONS_FILE):
        if r['date'] >= cutoff:
            d = r['department']
            if d not in dept_map: dept_map[d] = {'total':0,'entries':0}
            dept_map[d]['total'] += r['co2']['total']
            dept_map[d]['entries'] += 1
    lb = sorted([{'department':n,'total_co2':round(d['total'],1),
                  'avg_daily':round(d['total']/max(d['entries'],1),1),'entries':d['entries']}
                 for n,d in dept_map.items()], key=lambda x: x['total_co2'])
    return jsonify({'success': True, 'leaderboard': lb})

@app.route('/api/suggestions')
@login_required
def suggestions():
    today = datetime.now().strftime('%Y-%m-%d')
    co2 = {'electricity':0,'diesel':0,'vehicles':0,'food':0,'food_waste':0}
    for r in load_json(EMISSIONS_FILE):
        if r['date'] == today:
            for k in co2: co2[k] += r['co2'].get(k, 0)
    return jsonify({'success': True, 'suggestions': generate_suggestions(co2)})

# ─── Excel Export ───
@app.route('/api/export/excel')
@login_required
def export_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    records = load_json(EMISSIONS_FILE)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Emissions Data'

    # Header styling
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='00875A', end_color='00875A', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'))

    headers = ['ID','Date','Department','Electricity (kWh)','Diesel (L)','Vehicles',
               'Veg Meals','Non-Veg Meals','Food Waste (kg)','Water (kL)',
               'CO2 Electricity','CO2 Diesel','CO2 Vehicles','CO2 Food',
               'CO2 Food Waste','CO2 Water','CO2 Total (kg)','Submitted By','Submitted At']

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    for i, r in enumerate(records, 2):
        co2 = r.get('co2', {})
        row = [r.get('id'), r.get('date'), r.get('department'),
               r.get('electricity_kwh',0), r.get('diesel_litres',0), r.get('vehicles_entered',0),
               r.get('veg_meals',0), r.get('nonveg_meals',0), r.get('food_waste_kg',0), r.get('water_kl',0),
               co2.get('electricity',0), co2.get('diesel',0), co2.get('vehicles',0), co2.get('food',0),
               co2.get('food_waste',0), co2.get('water',0), co2.get('total',0),
               r.get('submitted_by',''), r.get('submitted_at','')]
        for col, val in enumerate(row, 1):
            cell = ws.cell(row=i, column=col, value=val)
            cell.border = thin_border

    # Auto column width
    for col in ws.columns:
        max_len = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 3, 30)

    # Summary sheet
    ws2 = wb.create_sheet('Summary')
    ws2.cell(row=1, column=1, value='Campus Carbon Footprint Report').font = Font(bold=True, size=14)
    ws2.cell(row=2, column=1, value=f'Generated: {datetime.now().strftime("%d %b %Y %H:%M")}')
    ws2.cell(row=3, column=1, value=f'Total Records: {len(records)}')
    total_co2 = sum(r.get('co2',{}).get('total',0) for r in records)
    ws2.cell(row=4, column=1, value=f'Total CO2: {total_co2:.1f} kg')

    # Dept summary
    ws2.cell(row=6, column=1, value='Department').font = Font(bold=True)
    ws2.cell(row=6, column=2, value='Total CO2 (kg)').font = Font(bold=True)
    ws2.cell(row=6, column=3, value='Entries').font = Font(bold=True)
    dept = {}
    for r in records:
        d = r.get('department','')
        if d not in dept: dept[d] = {'co2':0,'n':0}
        dept[d]['co2'] += r.get('co2',{}).get('total',0)
        dept[d]['n'] += 1
    for i,(name,data) in enumerate(sorted(dept.items(), key=lambda x: x[1]['co2']), 7):
        ws2.cell(row=i, column=1, value=name)
        ws2.cell(row=i, column=2, value=round(data['co2'],1))
        ws2.cell(row=i, column=3, value=data['n'])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"campus_carbon_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ─── Sensor API (no login required — uses API key for IoT devices) ───
SENSOR_KEY = 'greencampus2026'

@app.route('/api/sensors/push', methods=['POST'])
def sensor_push():
    data = request.json
    # Optional API key check (skip for demo)
    # if request.headers.get('X-API-Key') != SENSOR_KEY:
    #     return jsonify({'success': False, 'error': 'Invalid API key'}), 403

    co2 = calc_co2(data)
    record = {
        'id': len(load_json(EMISSIONS_FILE)) + 1,
        'department': data.get('department', 'Unknown'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'electricity_kwh': data.get('electricity_kwh', 0),
        'diesel_litres': data.get('diesel_litres', 0),
        'vehicles_entered': data.get('vehicles_entered', 0),
        'veg_meals': data.get('veg_meals', 0),
        'nonveg_meals': data.get('nonveg_meals', 0),
        'food_waste_kg': data.get('food_waste_kg', 0),
        'water_kl': data.get('water_kl', 0),
        'co2': co2,
        'source': 'sensor',
        'sensor_id': data.get('sensor_id', 'unknown'),
        'submitted_by': 'IoT Sensor',
        'submitted_at': datetime.now().isoformat(),
    }
    records = load_json(EMISSIONS_FILE)
    records.append(record)
    save_json(EMISSIONS_FILE, records)
    return jsonify({'success': True, 'data': record})

@app.route('/api/sensors/status')
def sensor_status():
    records = load_json(EMISSIONS_FILE)
    sensors = [r for r in records if r.get('source') == 'sensor']
    last_5 = sorted(sensors, key=lambda r: r.get('submitted_at',''), reverse=True)[:5]
    return jsonify({
        'success': True,
        'total_readings': len(sensors),
        'last_reading': last_5[0]['submitted_at'] if last_5 else None,
        'recent': [{'dept': r['department'], 'co2': r['co2']['total'],
                    'time': r['submitted_at'], 'sensor': r.get('sensor_id')} for r in last_5],
    })

if __name__ == '__main__':
    print('[+] Campus Carbon Tracker Backend')
    print('[*] Dashboard: http://localhost:5000')
    print('[*] API Base:  http://localhost:5000/api/')
    print('[*] Sensor API: POST http://localhost:5000/api/sensors/push')
    app.run(debug=True, port=5000)
