"""
sensor_simulator.py — Simulates IoT sensors pushing data to the backend
Generates realistic campus emission data every 30 seconds.

For hackathon demo: Run this alongside server.py to show live data flowing in.
For production: Replace this with real ESP32/Arduino sensors hitting the same API.
"""
import requests, random, time, math
from datetime import datetime

API_URL = 'http://localhost:5000/api/sensors/push'

DEPARTMENTS = [
    'H1 Hostel', 'H4 Hostel', 'H5 Hostel', 'H7 Hostel', 'H10 Hostel',
    'Main Building', 'Lecture Hall Complex', 'Library', 'Sports Complex', 'Canteen',
]

# Base values per department (realistic daily ranges)
BASE = {
    'H1 Hostel':         {'elec': (150,250), 'diesel': (0,10), 'vehicle': (5,20),  'veg': (250,400), 'nonveg': (60,120), 'waste': (3,10), 'water': (30,60)},
    'H4 Hostel':         {'elec': (180,280), 'diesel': (0,12), 'vehicle': (8,25),  'veg': (300,450), 'nonveg': (80,140), 'waste': (5,12), 'water': (35,65)},
    'H5 Hostel':         {'elec': (140,220), 'diesel': (0,8),  'vehicle': (5,18),  'veg': (220,350), 'nonveg': (50,100), 'waste': (3,8),  'water': (25,50)},
    'H7 Hostel':         {'elec': (200,300), 'diesel': (5,15), 'vehicle': (10,30), 'veg': (320,480), 'nonveg': (90,150), 'waste': (6,14), 'water': (40,70)},
    'H10 Hostel':        {'elec': (220,320), 'diesel': (5,18), 'vehicle': (12,35), 'veg': (340,500), 'nonveg': (100,160),'waste': (7,15), 'water': (45,75)},
    'Main Building':     {'elec': (350,500), 'diesel': (15,30),'vehicle': (30,60), 'veg': (30,80),   'nonveg': (10,40),  'waste': (5,12), 'water': (15,35)},
    'Lecture Hall Complex':{'elec':(300,450), 'diesel': (10,25),'vehicle': (25,50), 'veg': (60,120),  'nonveg': (20,60),  'waste': (8,18), 'water': (20,40)},
    'Library':           {'elec': (70,130),  'diesel': (0,5),  'vehicle': (2,8),   'veg': (0,0),     'nonveg': (0,0),    'waste': (0,2),  'water': (5,15)},
    'Sports Complex':    {'elec': (150,250), 'diesel': (5,15), 'vehicle': (10,25), 'veg': (30,60),   'nonveg': (10,30),  'waste': (5,10), 'water': (60,120)},
    'Canteen':           {'elec': (250,380), 'diesel': (15,35),'vehicle': (20,40), 'veg': (700,1000),'nonveg': (300,500),'waste': (25,55),'water': (100,200)},
}

def generate_reading(dept):
    """Generate one realistic sensor reading for a department."""
    hour = datetime.now().hour
    
    # Time-based multiplier (lower at night, peak during day)
    if 0 <= hour < 6:
        mult = 0.3
    elif 6 <= hour < 9:
        mult = 0.7
    elif 9 <= hour < 17:
        mult = 1.0
    elif 17 <= hour < 21:
        mult = 0.8
    else:
        mult = 0.5
    
    # Add some noise
    b = BASE[dept]
    return {
        'department': dept,
        'sensor_id': f'SEN-{DEPARTMENTS.index(dept)+1:03d}',
        'electricity_kwh':  round(random.uniform(*b['elec']) * mult, 1),
        'diesel_litres':    round(random.uniform(*b['diesel']) * mult, 1),
        'vehicles_entered': round(random.uniform(*b['vehicle']) * mult),
        'veg_meals':        round(random.uniform(*b['veg']) * mult),
        'nonveg_meals':     round(random.uniform(*b['nonveg']) * mult),
        'food_waste_kg':    round(random.uniform(*b['waste']) * mult, 1),
        'water_kl':         round(random.uniform(*b['water']) * mult, 1),
    }

def main():
    print('[+] Sensor Simulator Started')
    print(f'[*] Pushing data to {API_URL}')
    print(f'[*] Simulating {len(DEPARTMENTS)} departments')
    print('[*] Interval: 30 seconds')
    print('-' * 50)
    
    cycle = 0
    while True:
        cycle += 1
        # Pick 2-4 random departments per cycle (not all at once)
        depts = random.sample(DEPARTMENTS, random.randint(2, 4))
        
        for dept in depts:
            reading = generate_reading(dept)
            try:
                res = requests.post(API_URL, json=reading, timeout=5)
                data = res.json()
                co2 = data.get('data', {}).get('co2', {}).get('total', '?')
                print(f'[Cycle {cycle}] {dept:<25} -> {co2} kg CO2')
            except Exception as e:
                print(f'[!] Error sending to {dept}: {e}')
        
        print(f'--- Waiting 30s (next cycle: {cycle+1}) ---')
        time.sleep(30)

if __name__ == '__main__':
    main()
