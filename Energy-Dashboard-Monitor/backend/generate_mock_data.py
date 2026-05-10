import csv
import json
import random
from datetime import datetime, timedelta

def generate_timestamp(base_date, offset_minutes):
    return (base_date + timedelta(minutes=offset_minutes)).isoformat()

def generate_smart_meter_data(num_records):
    base_date = datetime.now() - timedelta(days=30)
    data = []
    for i in range(num_records):
        record = {
            "meter_id": f"MTR-{random.randint(1000, 9999)}",
            "timestamp": generate_timestamp(base_date, i * 15),
            "power_usage_kwh": round(random.uniform(0.5, 5.0), 2),
            "voltage": round(random.uniform(220.0, 240.0), 1)
        }
        # Inject quality issues
        if random.random() < 0.05:  # 5% chance of null usage
            record["power_usage_kwh"] = None
        if random.random() < 0.01:  # 1% chance of extreme outlier
            record["voltage"] = 999.9
        data.append(record)
    return data

def generate_grid_sensor_data(num_records):
    base_date = datetime.now() - timedelta(days=30)
    data = []
    for i in range(num_records):
        record = {
            "sensor_id": f"GS-{random.randint(100, 999)}",
            "timestamp": generate_timestamp(base_date, i * 5),
            "temperature_c": round(random.uniform(-10.0, 45.0), 1),
            "line_tension_kg": round(random.uniform(500, 1500), 0)
        }
        # Inject quality issues
        if random.random() < 0.02:  # 2% chance of missing timestamp
            record["timestamp"] = ""
        if random.random() < 0.03:  # 3% chance of negative tension (impossible)
            record["line_tension_kg"] = -100
        data.append(record)
    return data

def generate_billing_data(num_records):
    base_date = datetime.now() - timedelta(days=30)
    statuses = ["PAID", "PENDING", "OVERDUE"]
    data = []
    for i in range(num_records):
        record = {
            "account_id": f"ACC-{random.randint(10000, 99999)}",
            "timestamp": generate_timestamp(base_date, i * 60 * 24), # Daily
            "amount_due": round(random.uniform(50.0, 300.0), 2),
            "status": random.choice(statuses)
        }
        # Inject quality issues
        if random.random() < 0.04:  # 4% chance of wrong type status
            record["status"] = "TRUE"
        if random.random() < 0.01:  # 1% chance of negative amount
            record["amount_due"] = -50.0
        data.append(record)
    return data

def generate_weather_data(num_records):
    base_date = datetime.now() - timedelta(days=30)
    locations = ["US-East", "US-West", "EU-Central", "APAC"]
    data = []
    for i in range(num_records):
        record = {
            "location": random.choice(locations),
            "timestamp": generate_timestamp(base_date, i * 60), # Hourly
            "temperature_c": round(random.uniform(-20.0, 50.0), 1),
            "humidity": random.randint(10, 100),
            "wind_speed_mph": round(random.uniform(0.0, 100.0), 1)
        }
        # Inject quality issues
        if random.random() < 0.02:  # 2% chance of impossible humidity
            record["humidity"] = 150
        if random.random() < 0.02:  # 2% chance of string instead of float for wind
            record["wind_speed_mph"] = "Fast"
        data.append(record)
    return data

def save_to_json(filename, data):
    with open(f"../data/raw/{filename}", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    print("Generating Smart Meter Data...")
    save_to_json("smart_meter_data.json", generate_smart_meter_data(5000))
    print("Generating Grid Sensor Data...")
    save_to_json("grid_sensor_data.json", generate_grid_sensor_data(5000))
    print("Generating Billing Data...")
    save_to_json("billing_data.json", generate_billing_data(5000))
    print("Generating Weather Data...")
    save_to_json("weather_data.json", generate_weather_data(5000))
    print("Mock data generation complete. Saved to ../data/raw/")
