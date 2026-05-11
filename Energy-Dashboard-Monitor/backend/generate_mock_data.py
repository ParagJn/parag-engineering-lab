import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration
NUM_CUSTOMERS = 5000
NUM_METERS_PER_CUSTOMER = 1  # Each customer has 1 smart meter
NUM_METER_READINGS = 10000  # Total meter readings across all meters
NUM_GRID_SENSORS = 50  # Physical grid sensors
NUM_SENSOR_READINGS = 8000  # Total sensor readings
NUM_BILLING_RECORDS = 5000  # One per customer per month
NUM_WEATHER_RECORDS = 2000  # Weather data points

# Data quality issue rates (targeting 10-12% overall)
CUSTOMER_NULL_RATE = 0.08
CUSTOMER_INVALID_RATE = 0.04
METER_NULL_RATE = 0.06
METER_OUTLIER_RATE = 0.05
SENSOR_NULL_RATE = 0.07
SENSOR_INVALID_RATE = 0.04
BILLING_INVALID_RATE = 0.10
WEATHER_INVALID_RATE = 0.08

def generate_timestamp(base_date: datetime, offset_minutes: int) -> str:
    """Generate ISO format timestamp"""
    return (base_date + timedelta(minutes=offset_minutes)).isoformat()

def inject_null(value: Any, rate: float) -> Any:
    """Randomly inject null values based on rate"""
    return None if random.random() < rate else value

def generate_customers(num_records: int) -> List[Dict[str, Any]]:
    """Generate customer master data with quality issues"""
    print(f"Generating {num_records} customer records...")
    
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", 
                   "James", "Mary", "William", "Patricia", "Richard", "Jennifer", "Thomas"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                  "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson"]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", 
              "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville"]
    states = ["NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX", "CA", "TX", "FL"]
    
    data = []
    for i in range(num_records):
        customer_id = f"CUST-{10000 + i}"
        
        # Base record
        record = {
            "customer_id": customer_id,
            "first_name": random.choice(first_names),
            "last_name": random.choice(last_names),
            "email": f"customer{i}@example.com",
            "phone": f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
            "address": f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Maple', 'Cedar', 'Elm'])} St",
            "city": random.choice(cities),
            "state": random.choice(states),
            "zip_code": f"{random.randint(10000, 99999)}",
            "account_status": random.choice(["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "SUSPENDED", "INACTIVE"]),
            "registration_date": generate_timestamp(datetime.now() - timedelta(days=random.randint(30, 1095)), 0),
            "customer_type": random.choice(["RESIDENTIAL", "RESIDENTIAL", "RESIDENTIAL", "COMMERCIAL", "INDUSTRIAL"])
        }
        
        # Inject quality issues - NULL values
        if random.random() < CUSTOMER_NULL_RATE:
            null_field = random.choice(["email", "phone", "address", "city", "zip_code"])
            record[null_field] = None
        
        # Inject quality issues - Invalid data
        if random.random() < CUSTOMER_INVALID_RATE:
            issue_type = random.choice(["invalid_email", "invalid_phone", "invalid_zip", "invalid_state"])
            if issue_type == "invalid_email":
                record["email"] = "invalid.email.format"
            elif issue_type == "invalid_phone":
                record["phone"] = "123-INVALID"
            elif issue_type == "invalid_zip":
                record["zip_code"] = "ABCDE"
            elif issue_type == "invalid_state":
                record["state"] = "XX"
        
        data.append(record)
    
    return data

def generate_smart_meters(customers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate smart meter master data linked to customers"""
    print(f"Generating {len(customers)} smart meter records...")
    
    manufacturers = ["Siemens", "GE", "Schneider", "Honeywell", "Landis+Gyr"]
    models = ["SM-2000", "SM-3000", "SM-4000", "SM-5000"]
    
    data = []
    for i, customer in enumerate(customers):
        meter_id = f"MTR-{20000 + i}"
        
        record = {
            "meter_id": meter_id,
            "customer_id": customer["customer_id"],
            "manufacturer": random.choice(manufacturers),
            "model": random.choice(models),
            "installation_date": generate_timestamp(
                datetime.fromisoformat(customer["registration_date"]) + timedelta(days=random.randint(1, 30)), 
                0
            ),
            "last_calibration": generate_timestamp(datetime.now() - timedelta(days=random.randint(1, 365)), 0),
            "status": random.choice(["ACTIVE", "ACTIVE", "ACTIVE", "MAINTENANCE", "FAULTY"]),
            "firmware_version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 20)}"
        }
        
        # Inject quality issues
        if random.random() < METER_NULL_RATE:
            null_field = random.choice(["last_calibration", "firmware_version"])
            record[null_field] = None
        
        data.append(record)
    
    return data

def generate_meter_readings(meters: List[Dict[str, Any]], num_records: int) -> List[Dict[str, Any]]:
    """Generate smart meter reading data with quality issues"""
    print(f"Generating {num_records} meter reading records...")
    
    base_date = datetime.now() - timedelta(days=30)
    data = []
    
    for i in range(num_records):
        meter = random.choice(meters)
        
        record = {
            "reading_id": f"READ-{100000 + i}",
            "meter_id": meter["meter_id"],
            "customer_id": meter["customer_id"],
            "timestamp": generate_timestamp(base_date, i * 5),
            "power_usage_kwh": round(random.uniform(0.5, 5.0), 2),
            "voltage": round(random.uniform(220.0, 240.0), 1),
            "current_ampere": round(random.uniform(5.0, 30.0), 2),
            "power_factor": round(random.uniform(0.85, 1.0), 3),
            "frequency_hz": round(random.uniform(59.5, 60.5), 2)
        }
        
        # Inject quality issues - NULL values
        if random.random() < METER_NULL_RATE:
            null_field = random.choice(["power_usage_kwh", "voltage", "current_ampere"])
            record[null_field] = None
        
        # Inject quality issues - Outliers
        if random.random() < METER_OUTLIER_RATE:
            outlier_type = random.choice(["voltage_spike", "negative_usage", "extreme_current", "invalid_frequency"])
            if outlier_type == "voltage_spike":
                record["voltage"] = round(random.uniform(300.0, 999.9), 1)
            elif outlier_type == "negative_usage":
                record["power_usage_kwh"] = round(random.uniform(-5.0, -0.1), 2)
            elif outlier_type == "extreme_current":
                record["current_ampere"] = round(random.uniform(100.0, 500.0), 2)
            elif outlier_type == "invalid_frequency":
                record["frequency_hz"] = round(random.uniform(40.0, 80.0), 2)
        
        data.append(record)
    
    return data

def generate_grid_sensors(num_sensors: int) -> List[Dict[str, Any]]:
    """Generate grid sensor master data"""
    print(f"Generating {num_sensors} grid sensor records...")
    
    locations = ["Substation-A", "Substation-B", "Substation-C", "Substation-D", 
                 "Transformer-1", "Transformer-2", "Transformer-3", "Distribution-Hub-1"]
    sensor_types = ["TEMPERATURE", "VOLTAGE", "CURRENT", "TENSION", "VIBRATION"]
    
    data = []
    for i in range(num_sensors):
        record = {
            "sensor_id": f"GS-{1000 + i}",
            "location": random.choice(locations),
            "sensor_type": random.choice(sensor_types),
            "installation_date": generate_timestamp(datetime.now() - timedelta(days=random.randint(365, 1825)), 0),
            "last_maintenance": generate_timestamp(datetime.now() - timedelta(days=random.randint(1, 180)), 0),
            "status": random.choice(["OPERATIONAL", "OPERATIONAL", "OPERATIONAL", "CALIBRATION", "OFFLINE"])
        }
        data.append(record)
    
    return data

def generate_sensor_readings(sensors: List[Dict[str, Any]], num_records: int) -> List[Dict[str, Any]]:
    """Generate grid sensor reading data with quality issues"""
    print(f"Generating {num_records} sensor reading records...")
    
    base_date = datetime.now() - timedelta(days=30)
    data = []
    
    for i in range(num_records):
        sensor = random.choice(sensors)
        
        record = {
            "reading_id": f"SREAD-{200000 + i}",
            "sensor_id": sensor["sensor_id"],
            "timestamp": generate_timestamp(base_date, i * 6),
            "temperature_c": round(random.uniform(-10.0, 45.0), 1),
            "line_tension_kg": round(random.uniform(500, 1500), 0),
            "vibration_level": round(random.uniform(0.0, 10.0), 2),
            "humidity_percent": random.randint(10, 90)
        }
        
        # Inject quality issues - NULL values
        if random.random() < SENSOR_NULL_RATE:
            null_field = random.choice(["temperature_c", "line_tension_kg", "vibration_level"])
            record[null_field] = None
        
        # Inject quality issues - Invalid data
        if random.random() < SENSOR_INVALID_RATE:
            issue_type = random.choice(["negative_tension", "extreme_temp", "invalid_humidity", "empty_timestamp"])
            if issue_type == "negative_tension":
                record["line_tension_kg"] = round(random.uniform(-500, -10), 0)
            elif issue_type == "extreme_temp":
                record["temperature_c"] = round(random.uniform(100.0, 200.0), 1)
            elif issue_type == "invalid_humidity":
                record["humidity_percent"] = random.randint(101, 200)
            elif issue_type == "empty_timestamp":
                record["timestamp"] = ""
        
        data.append(record)
    
    return data

def generate_billing_records(customers: List[Dict[str, Any]], num_records: int) -> List[Dict[str, Any]]:
    """Generate billing data linked to customers"""
    print(f"Generating {num_records} billing records...")
    
    base_date = datetime.now() - timedelta(days=90)
    data = []
    
    for i in range(num_records):
        customer = customers[i % len(customers)]
        
        record = {
            "billing_id": f"BILL-{300000 + i}",
            "customer_id": customer["customer_id"],
            "billing_period_start": generate_timestamp(base_date + timedelta(days=(i // len(customers)) * 30), 0),
            "billing_period_end": generate_timestamp(base_date + timedelta(days=(i // len(customers)) * 30 + 30), 0),
            "total_kwh_used": round(random.uniform(100.0, 1500.0), 2),
            "amount_due": round(random.uniform(50.0, 500.0), 2),
            "amount_paid": 0.0,
            "due_date": generate_timestamp(base_date + timedelta(days=(i // len(customers)) * 30 + 45), 0),
            "payment_date": None,
            "status": random.choice(["PENDING", "PENDING", "PAID", "OVERDUE"])
        }
        
        # Set payment details for PAID status
        if record["status"] == "PAID":
            record["amount_paid"] = record["amount_due"]
            record["payment_date"] = generate_timestamp(
                datetime.fromisoformat(record["due_date"]) - timedelta(days=random.randint(1, 15)), 
                0
            )
        
        # Inject quality issues
        if random.random() < BILLING_INVALID_RATE:
            issue_type = random.choice(["negative_amount", "invalid_status", "missing_period", "future_date"])
            if issue_type == "negative_amount":
                record["amount_due"] = round(random.uniform(-100.0, -10.0), 2)
            elif issue_type == "invalid_status":
                record["status"] = random.choice(["TRUE", "FALSE", "UNKNOWN", "123"])
            elif issue_type == "missing_period":
                record["billing_period_start"] = None
            elif issue_type == "future_date":
                record["billing_period_start"] = generate_timestamp(datetime.now() + timedelta(days=30), 0)
        
        data.append(record)
    
    return data

def generate_weather_data(num_records: int) -> List[Dict[str, Any]]:
    """Generate weather data"""
    print(f"Generating {num_records} weather records...")
    
    base_date = datetime.now() - timedelta(days=30)
    locations = ["US-East", "US-West", "US-Central", "US-South"]
    
    data = []
    for i in range(num_records):
        record = {
            "weather_id": f"WTH-{400000 + i}",
            "location": random.choice(locations),
            "timestamp": generate_timestamp(base_date, i * 30),
            "temperature_c": round(random.uniform(-20.0, 45.0), 1),
            "humidity_percent": random.randint(10, 100),
            "wind_speed_mph": round(random.uniform(0.0, 50.0), 1),
            "precipitation_mm": round(random.uniform(0.0, 25.0), 1),
            "cloud_cover_percent": random.randint(0, 100)
        }
        
        # Inject quality issues
        if random.random() < WEATHER_INVALID_RATE:
            issue_type = random.choice(["invalid_humidity", "string_wind", "negative_precip", "extreme_temp"])
            if issue_type == "invalid_humidity":
                record["humidity_percent"] = random.randint(101, 200)
            elif issue_type == "string_wind":
                record["wind_speed_mph"] = random.choice(["Fast", "Slow", "N/A", "ERROR"])
            elif issue_type == "negative_precip":
                record["precipitation_mm"] = round(random.uniform(-10.0, -0.1), 1)
            elif issue_type == "extreme_temp":
                record["temperature_c"] = round(random.uniform(60.0, 100.0), 1)
        
        data.append(record)
    
    return data

def save_to_json(filename: str, data: List[Dict[str, Any]]):
    """Save data to JSON file"""
    filepath = f"../data/raw/{filename}"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved {len(data)} records to {filepath}")

def calculate_quality_stats(data: List[Dict[str, Any]], dataset_name: str):
    """Calculate and display data quality statistics"""
    total_records = len(data)
    issues = 0
    
    for record in data:
        for value in record.values():
            if value is None:
                issues += 1
                break
            if isinstance(value, (int, float)) and value < 0 and "id" not in str(value):
                issues += 1
                break
            if isinstance(value, str) and value in ["", "UNKNOWN", "ERROR", "N/A", "TRUE", "FALSE", "XX"]:
                issues += 1
                break
    
    quality_rate = ((total_records - issues) / total_records * 100) if total_records > 0 else 100
    issue_rate = (issues / total_records * 100) if total_records > 0 else 0
    
    print(f"  {dataset_name}: {quality_rate:.1f}% clean, {issue_rate:.1f}% issues ({issues}/{total_records} records)")

if __name__ == "__main__":
    print("=" * 60)
    print("ENERGY DASHBOARD - MOCK DATA GENERATOR")
    print("=" * 60)
    print()
    
    # Generate master data first (entities)
    customers = generate_customers(NUM_CUSTOMERS)
    smart_meters = generate_smart_meters(customers)
    grid_sensors = generate_grid_sensors(NUM_GRID_SENSORS)
    
    # Generate transactional data (linked via foreign keys)
    meter_readings = generate_meter_readings(smart_meters, NUM_METER_READINGS)
    sensor_readings = generate_sensor_readings(grid_sensors, NUM_SENSOR_READINGS)
    billing_records = generate_billing_records(customers, NUM_BILLING_RECORDS)
    weather_data = generate_weather_data(NUM_WEATHER_RECORDS)
    
    print()
    print("Saving data files...")
    print("-" * 60)
    
    # Save all datasets
    save_to_json("customers.json", customers)
    save_to_json("smart_meters.json", smart_meters)
    save_to_json("meter_readings.json", meter_readings)
    save_to_json("grid_sensors.json", grid_sensors)
    save_to_json("sensor_readings.json", sensor_readings)
    save_to_json("billing_records.json", billing_records)
    save_to_json("weather_data.json", weather_data)
    
    print()
    print("Data Quality Summary:")
    print("-" * 60)
    calculate_quality_stats(customers, "Customers")
    calculate_quality_stats(smart_meters, "Smart Meters")
    calculate_quality_stats(meter_readings, "Meter Readings")
    calculate_quality_stats(grid_sensors, "Grid Sensors")
    calculate_quality_stats(sensor_readings, "Sensor Readings")
    calculate_quality_stats(billing_records, "Billing Records")
    calculate_quality_stats(weather_data, "Weather Data")
    
    print()
    print("=" * 60)
    print("✓ Mock data generation complete!")
    print(f"✓ Total records generated: {len(customers) + len(smart_meters) + len(meter_readings) + len(grid_sensors) + len(sensor_readings) + len(billing_records) + len(weather_data):,}")
    print("=" * 60)

# Made with Bob
