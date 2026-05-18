import json
import os
import random
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="Energy Dashboard API")

# Setup CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE_DIR, "..", "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "..", "data", "processed")

# Ensure processed directory exists
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Pipeline run history file (rolling snapshot log)
HISTORY_FILE = os.path.join(PROCESSED_DIR, "run_history.json")
MAX_HISTORY_RUNS = 20

# Global variables to simulate dynamic system changes over time
system_state = {
    "runs": 0,
    "last_run_time": None
}

def load_run_history():
    """Load pipeline run history snapshots"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def append_run_snapshot(snapshot: dict):
    """Append a run snapshot and keep rolling window of MAX_HISTORY_RUNS"""
    history = load_run_history()
    history.append(snapshot)
    if len(history) > MAX_HISTORY_RUNS:
        history = history[-MAX_HISTORY_RUNS:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def load_data(filename):
    """Load data from processed directory first, fallback to raw"""
    processed_path = os.path.join(PROCESSED_DIR, filename)
    raw_path = os.path.join(RAW_DIR, filename)
    
    file_path = processed_path if os.path.exists(processed_path) else raw_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Data file not found: {filename}")
        
    with open(file_path, "r") as f:
        return json.load(f)

def save_processed(filename, data):
    """Save processed data"""
    processed_path = os.path.join(PROCESSED_DIR, filename)
    with open(processed_path, "w") as f:
        json.dump(data, f, indent=2)

@app.post("/api/simulate")
def run_simulation():
    """Run data simulation - adds variance and fixes/introduces quality issues"""
    # Load all datasets
    customers = load_data("customers.json")
    smart_meters = load_data("smart_meters.json")
    meter_readings = load_data("meter_readings.json")
    grid_sensors = load_data("grid_sensors.json")
    sensor_readings = load_data("sensor_readings.json")
    billing_records = load_data("billing_records.json")
    weather_data = load_data("weather_data.json")
    
    # Add variance to meter readings
    for record in meter_readings:
        if record.get("power_usage_kwh") is not None:
            variance = random.uniform(0.95, 1.05)
            record["power_usage_kwh"] = round(record["power_usage_kwh"] * variance, 2)
        
        # Occasionally fix or introduce issues
        if random.random() < 0.01:
            record["power_usage_kwh"] = round(random.uniform(0.5, 5.0), 2)
        elif random.random() < 0.005:
            record["power_usage_kwh"] = None
    
    # Add variance to sensor readings
    for record in sensor_readings:
        if record.get("line_tension_kg") is not None and record["line_tension_kg"] > 0:
            variance = random.uniform(0.98, 1.02)
            record["line_tension_kg"] = round(record["line_tension_kg"] * variance, 0)
    
    # Save all processed data
    save_processed("customers.json", customers)
    save_processed("smart_meters.json", smart_meters)
    save_processed("meter_readings.json", meter_readings)
    save_processed("grid_sensors.json", grid_sensors)
    save_processed("sensor_readings.json", sensor_readings)
    save_processed("billing_records.json", billing_records)
    save_processed("weather_data.json", weather_data)
    
    system_state["runs"] += 1
    system_state["last_run_time"] = datetime.now().isoformat()

    # Quick quality metrics for the snapshot
    total_records = (len(customers) + len(smart_meters) + len(meter_readings) +
                     len(grid_sensors) + len(sensor_readings) + len(billing_records) + len(weather_data))
    null_issues = (sum(1 for r in meter_readings if r.get("power_usage_kwh") is None) +
                   sum(1 for r in sensor_readings if r.get("line_tension_kg") is None))
    outlier_issues = (sum(1 for r in meter_readings if r.get("voltage") and r["voltage"] > 250) +
                      sum(1 for r in billing_records if r.get("amount_due") and r["amount_due"] < 0))
    total_issues = null_issues + outlier_issues
    quality_score = round(max(0, 100 - (total_issues / total_records * 100)), 1) if total_records > 0 else 100

    # Generate varied, realistic data for meaningful trends
    # Simulate different processing volumes (70-100% of total records)
    processing_efficiency = random.uniform(0.70, 1.0)
    records_processed = int(total_records * processing_efficiency)
    
    # Add some variation to quality score (±5%)
    quality_variation = random.uniform(-5, 5)
    varied_quality = max(65, min(100, quality_score + quality_variation))
    
    # Record snapshot for chart history with varied data
    append_run_snapshot({
        "run_id": f"RUN-{system_state['runs']}",
        "timestamp": system_state["last_run_time"],
        "records_processed": records_processed,
        "quality_score": round(varied_quality, 1),
        "issues_found": total_issues,
        "duration_s": random.randint(45, 180)
    })

    # Small delay to simulate processing time
    time.sleep(1)
    
    return {
        "status": "success", 
        "message": "Simulation run complete", 
        "runs": system_state["runs"],
        "timestamp": system_state["last_run_time"]
    }

# ============================================================================
# CUSTOMER ENDPOINTS
# ============================================================================

@app.get("/api/customers")
def get_customers(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None
):
    """Get customer data with optional filtering"""
    data = load_data("customers.json")
    
    # Filter by status if provided
    if status:
        data = [r for r in data if r.get("account_status") == status]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    """Get specific customer by ID"""
    data = load_data("customers.json")
    customer = next((c for c in data if c["customer_id"] == customer_id), None)
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    return customer

# ============================================================================
# SMART METER ENDPOINTS
# ============================================================================

@app.get("/api/smart-meters")
def get_smart_meters(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    customer_id: Optional[str] = None
):
    """Get smart meter data with optional customer filter"""
    data = load_data("smart_meters.json")
    
    if customer_id:
        data = [r for r in data if r.get("customer_id") == customer_id]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

@app.get("/api/meter-readings")
def get_meter_readings(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    meter_id: Optional[str] = None,
    customer_id: Optional[str] = None
):
    """Get meter reading data with optional filters"""
    data = load_data("meter_readings.json")
    
    if meter_id:
        data = [r for r in data if r.get("meter_id") == meter_id]
    if customer_id:
        data = [r for r in data if r.get("customer_id") == customer_id]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

# ============================================================================
# GRID SENSOR ENDPOINTS
# ============================================================================

@app.get("/api/grid-sensors")
def get_grid_sensors(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get grid sensor master data"""
    data = load_data("grid_sensors.json")
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

@app.get("/api/sensor-readings")
def get_sensor_readings(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sensor_id: Optional[str] = None
):
    """Get sensor reading data with optional sensor filter"""
    data = load_data("sensor_readings.json")
    
    if sensor_id:
        data = [r for r in data if r.get("sensor_id") == sensor_id]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

# ============================================================================
# BILLING ENDPOINTS
# ============================================================================

@app.get("/api/billing")
def get_billing(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    customer_id: Optional[str] = None,
    status: Optional[str] = None
):
    """Get billing data with optional filters"""
    data = load_data("billing_records.json")
    
    if customer_id:
        data = [r for r in data if r.get("customer_id") == customer_id]
    if status:
        data = [r for r in data if r.get("status") == status]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

# ============================================================================
# WEATHER ENDPOINTS
# ============================================================================

@app.get("/api/weather")
def get_weather(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    location: Optional[str] = None
):
    """Get weather data with optional location filter"""
    data = load_data("weather_data.json")
    
    if location:
        data = [r for r in data if r.get("location") == location]
    
    total = len(data)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": data[offset:offset+limit]
    }

# ============================================================================
# SYSTEM STATUS & MONITORING
# ============================================================================

@app.get("/api/system-status")
def get_system_status():
    """Get overall system health and status"""
    base_pipelines = 42
    base_error = 0.0012
    base_score = 94
    
    # Add dynamic variance based on runs
    pipelines = base_pipelines + random.randint(-2, 5)
    error_rate = max(0, base_error + random.uniform(-0.0005, 0.0015))
    score = min(100, max(0, base_score + random.randint(-3, 4)))
    
    throughput_base = 12.4
    throughput = round(throughput_base + (system_state["runs"] * 0.2) + random.uniform(-0.5, 1.5), 1)
    
    return {
        "status": "Healthy" if score > 90 else "Warning",
        "active_pipelines": pipelines,
        "global_error_rate": round(error_rate, 4),
        "overall_quality_score": score,
        "throughput_million": throughput,
        "last_simulation": system_state["last_run_time"],
        "total_simulations": system_state["runs"]
    }

@app.get("/api/quality")
def get_quality():
    """Analyze data quality across all datasets"""
    # Load all data
    customers = load_data("customers.json")
    meter_readings = load_data("meter_readings.json")
    sensor_readings = load_data("sensor_readings.json")
    billing_records = load_data("billing_records.json")
    weather_data = load_data("weather_data.json")
    smart_meters = load_data("smart_meters.json")
    grid_sensors = load_data("grid_sensors.json")
    
    # Build complete quarantine list with ALL problematic records
    quarantine = []
    
    # Check meter readings - NULL values
    for r in meter_readings:
        if r.get("power_usage_kwh") is None:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Meter Readings",
                "issue": "Null Value in Power Usage",
                "issue_type": "null",
                "severity": "High",
                "timestamp": r.get("timestamp"),
                "customer_id": r.get("customer_id")
            })
    
    # Check meter readings - Outliers (voltage)
    for r in meter_readings:
        if r.get("voltage") and r["voltage"] > 250:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Meter Readings",
                "issue": f"Voltage Outlier ({r['voltage']}V > 250V)",
                "issue_type": "outlier",
                "severity": "Critical",
                "timestamp": r.get("timestamp"),
                "customer_id": r.get("customer_id")
            })
    
    # Check meter readings - Outliers (negative power)
    for r in meter_readings:
        if r.get("power_usage_kwh") and r["power_usage_kwh"] < 0:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Meter Readings",
                "issue": f"Negative Power Usage ({r['power_usage_kwh']} kWh)",
                "issue_type": "outlier",
                "severity": "High",
                "timestamp": r.get("timestamp"),
                "customer_id": r.get("customer_id")
            })
    
    # Check sensor readings - NULL values
    for r in sensor_readings:
        if r.get("line_tension_kg") is None:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Sensor Readings",
                "issue": "Null Value in Line Tension",
                "issue_type": "null",
                "severity": "High",
                "timestamp": r.get("timestamp"),
                "sensor_id": r.get("sensor_id")
            })
        if r.get("temperature_c") is None:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Sensor Readings",
                "issue": "Null Value in Temperature",
                "issue_type": "null",
                "severity": "Medium",
                "timestamp": r.get("timestamp"),
                "sensor_id": r.get("sensor_id")
            })
    
    # Check sensor readings - Outliers
    for r in sensor_readings:
        if r.get("line_tension_kg") and r["line_tension_kg"] < 0:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Sensor Readings",
                "issue": f"Negative Tension ({r['line_tension_kg']} kg)",
                "issue_type": "outlier",
                "severity": "Critical",
                "timestamp": r.get("timestamp"),
                "sensor_id": r.get("sensor_id")
            })
        if r.get("temperature_c") and r["temperature_c"] > 60:
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Sensor Readings",
                "issue": f"Temperature Outlier ({r['temperature_c']}°C > 60°C)",
                "issue_type": "outlier",
                "severity": "High",
                "timestamp": r.get("timestamp"),
                "sensor_id": r.get("sensor_id")
            })
    
    # Check sensor readings - Schema issues
    for r in sensor_readings:
        if r.get("timestamp") == "":
            quarantine.append({
                "id": r.get("reading_id", "Unknown"),
                "source": "Sensor Readings",
                "issue": "Empty Timestamp",
                "issue_type": "schema",
                "severity": "Medium",
                "timestamp": "N/A",
                "sensor_id": r.get("sensor_id")
            })
    
    # Check customers - NULL values
    for r in customers:
        if r.get("email") is None:
            quarantine.append({
                "id": r.get("customer_id", "Unknown"),
                "source": "Customer Data",
                "issue": "Null Email Address",
                "issue_type": "null",
                "severity": "High",
                "timestamp": r.get("registration_date"),
                "customer_id": r.get("customer_id")
            })
        if r.get("phone") is None:
            quarantine.append({
                "id": r.get("customer_id", "Unknown"),
                "source": "Customer Data",
                "issue": "Null Phone Number",
                "issue_type": "null",
                "severity": "Medium",
                "timestamp": r.get("registration_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check customers - Schema issues
    for r in customers:
        if r.get("email") and "@" not in str(r["email"]):
            quarantine.append({
                "id": r.get("customer_id", "Unknown"),
                "source": "Customer Data",
                "issue": f"Invalid Email Format: {r['email']}",
                "issue_type": "schema",
                "severity": "Medium",
                "timestamp": r.get("registration_date"),
                "customer_id": r.get("customer_id")
            })
        if r.get("state") == "XX":
            quarantine.append({
                "id": r.get("customer_id", "Unknown"),
                "source": "Customer Data",
                "issue": "Invalid State Code (XX)",
                "issue_type": "schema",
                "severity": "Low",
                "timestamp": r.get("registration_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check billing - Outliers
    for r in billing_records:
        if r.get("amount_due") and r["amount_due"] < 0:
            quarantine.append({
                "id": r.get("billing_id", "Unknown"),
                "source": "Billing Records",
                "issue": f"Negative Amount Due (${r['amount_due']})",
                "issue_type": "outlier",
                "severity": "Critical",
                "timestamp": r.get("billing_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check billing - Schema issues
    for r in billing_records:
        if r.get("status") in ["TRUE", "FALSE", "UNKNOWN", "123"]:
            quarantine.append({
                "id": r.get("billing_id", "Unknown"),
                "source": "Billing Records",
                "issue": f"Invalid Status Value: {r['status']}",
                "issue_type": "schema",
                "severity": "High",
                "timestamp": r.get("billing_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check billing - NULL values
    for r in billing_records:
        if r.get("billing_period_start") is None:
            quarantine.append({
                "id": r.get("billing_id", "Unknown"),
                "source": "Billing Records",
                "issue": "Null Billing Period Start",
                "issue_type": "null",
                "severity": "High",
                "timestamp": r.get("billing_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check weather data - NULL values
    for r in weather_data:
        if r.get("temperature_c") is None:
            quarantine.append({
                "id": r.get("weather_id", "Unknown"),
                "source": "Weather Data",
                "issue": "Null Temperature",
                "issue_type": "null",
                "severity": "Medium",
                "timestamp": r.get("timestamp"),
                "location": r.get("location")
            })
        if r.get("humidity_percent") is None:
            quarantine.append({
                "id": r.get("weather_id", "Unknown"),
                "source": "Weather Data",
                "issue": "Null Humidity",
                "issue_type": "null",
                "severity": "Low",
                "timestamp": r.get("timestamp"),
                "location": r.get("location")
            })
    
    # Check weather data - Outliers
    for r in weather_data:
        if r.get("temperature_c") and (r["temperature_c"] < -50 or r["temperature_c"] > 60):
            quarantine.append({
                "id": r.get("weather_id", "Unknown"),
                "source": "Weather Data",
                "issue": f"Temperature Outlier ({r['temperature_c']}°C)",
                "issue_type": "outlier",
                "severity": "High",
                "timestamp": r.get("timestamp"),
                "location": r.get("location")
            })
        if r.get("wind_speed_kmh") and r["wind_speed_kmh"] > 200:
            quarantine.append({
                "id": r.get("weather_id", "Unknown"),
                "source": "Weather Data",
                "issue": f"Wind Speed Outlier ({r['wind_speed_kmh']} km/h)",
                "issue_type": "outlier",
                "severity": "Medium",
                "timestamp": r.get("timestamp"),
                "location": r.get("location")
            })
    
    # Check smart meters - NULL values
    for r in smart_meters:
        if r.get("installation_date") is None:
            quarantine.append({
                "id": r.get("meter_id", "Unknown"),
                "source": "Smart Meters",
                "issue": "Null Installation Date",
                "issue_type": "null",
                "severity": "Medium",
                "timestamp": r.get("last_maintenance_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Check smart meters - Schema issues
    for r in smart_meters:
        if r.get("status") not in ["Active", "Inactive", "Maintenance"]:
            quarantine.append({
                "id": r.get("meter_id", "Unknown"),
                "source": "Smart Meters",
                "issue": f"Invalid Status: {r.get('status')}",
                "issue_type": "schema",
                "severity": "Medium",
                "timestamp": r.get("last_maintenance_date"),
                "customer_id": r.get("customer_id")
            })
    
    # Calculate counts by type
    null_count = len([q for q in quarantine if q["issue_type"] == "null"])
    outlier_count = len([q for q in quarantine if q["issue_type"] == "outlier"])
    schema_issues = len([q for q in quarantine if q["issue_type"] == "schema"])
    
    total_records = len(customers) + len(meter_readings) + len(sensor_readings) + len(billing_records) + len(weather_data) + len(smart_meters) + len(grid_sensors)
    error_count = len(quarantine)
    score = max(0, 100 - (error_count / total_records * 100)) if total_records > 0 else 100
    
    return {
        "score": round(score, 1),
        "issues": {
            "nulls": null_count,
            "outliers": outlier_count,
            "schema_mismatch": schema_issues
        },
        "quarantine": quarantine,  # Return ALL quarantine items
        "total_records_analyzed": total_records
    }

@app.post("/api/quality/purge")
def purge_failures():
    """Fix data quality issues in quarantined records"""
    # Load all data
    customers = load_data("customers.json")
    meter_readings = load_data("meter_readings.json")
    sensor_readings = load_data("sensor_readings.json")
    billing_records = load_data("billing_records.json")
    
    fixed_count = 0
    
    # Fix meter readings
    for record in meter_readings:
        if record.get("power_usage_kwh") is None:
            record["power_usage_kwh"] = 0.0
            fixed_count += 1
        if record.get("power_usage_kwh") and record["power_usage_kwh"] < 0:
            record["power_usage_kwh"] = abs(record["power_usage_kwh"])
            fixed_count += 1
    
    # Fix sensor readings
    for record in sensor_readings:
        if record.get("line_tension_kg") and record["line_tension_kg"] < 0:
            record["line_tension_kg"] = abs(record["line_tension_kg"])
            fixed_count += 1
        if record.get("temperature_c") is None:
            record["temperature_c"] = 20.0
            fixed_count += 1
        if record.get("timestamp") == "":
            record["timestamp"] = datetime.now().isoformat()
            fixed_count += 1
    
    # Fix customers
    for record in customers:
        if record.get("email") and "@" not in str(record["email"]):
            record["email"] = f"fixed_{record.get('customer_id', 'unknown')}@example.com"
            fixed_count += 1
        if record.get("state") == "XX":
            record["state"] = "CA"
            fixed_count += 1
    
    # Fix billing
    for record in billing_records:
        if record.get("amount_due") and record["amount_due"] < 0:
            record["amount_due"] = abs(record["amount_due"])
            fixed_count += 1
        if record.get("status") in ["TRUE", "FALSE", "UNKNOWN", "123"]:
            record["status"] = "PENDING"
            fixed_count += 1
    
    # Save all fixed data
    save_processed("customers.json", customers)
    save_processed("meter_readings.json", meter_readings)
    save_processed("sensor_readings.json", sensor_readings)
    save_processed("billing_records.json", billing_records)
    
    return {
        "status": "success",
        "message": f"Quarantine purged and {fixed_count} issues fixed",
        "fixed_count": fixed_count
    }

@app.get("/api/history")
def get_history():
    """Get ETL job history and orchestration stats"""
    runs = system_state["runs"]
    
    # Generate log history
    history = []
    base_time = datetime.now()
    
    sources = [
        "Meter Readings Pipeline",
        "Sensor Readings Pipeline", 
        "Customer Data Sync",
        "Billing Pipeline",
        "Weather Data Ingestion"
    ]
    
    for i in range(10):
        volume = random.randint(3000, 8000)
        errors = random.randint(0, 45)
        
        if i == 0 and runs > 0:
            status = "Completed"
            errors = random.randint(0, 10)
        else:
            status = random.choice(["Completed", "Completed", "Completed", "Completed", "Failed", "Warning"])
        
        history.append({
            "job_id": f"ETL-{9000 - i}",
            "source": random.choice(sources),
            "timestamp": (base_time - timedelta(hours=i*2 + random.randint(0, 1))).strftime("%b %d, %Y %H:%M"),
            "status": status,
            "volume": volume,
            "errors": errors if status != "Failed" else "N/A",
            "duration": f"{random.randint(45, 180)}s"
        })
    
    # Orchestration stats
    completed = 72 + random.randint(-5, 5)
    failed = 4 + random.randint(-2, 3)
    retrying = 12 + random.randint(-4, 4)
    
    # Volume chart
    chart_data = []
    for i in range(7):
        chart_data.append({
            "day": (base_time - timedelta(days=6-i)).strftime("%a"),
            "success": random.randint(30, 50),
            "failed": random.randint(0, 5)
        })
    
    # Generate dummy pipeline runs with last one using actual file data
    pipeline_runs = load_run_history()
    
    # If no real runs exist, generate dummy data
    if len(pipeline_runs) == 0:
        # Get actual record counts from files
        customers = load_data("customers.json")
        smart_meters = load_data("smart_meters.json")
        meter_readings = load_data("meter_readings.json")
        grid_sensors = load_data("grid_sensors.json")
        sensor_readings = load_data("sensor_readings.json")
        billing_records = load_data("billing_records.json")
        weather_data = load_data("weather_data.json")
        
        actual_total = (len(customers) + len(smart_meters) + len(meter_readings) +
                       len(grid_sensors) + len(sensor_readings) + len(billing_records) +
                       len(weather_data))
        
        # Calculate actual quality score
        total_records = actual_total
        null_issues = (sum(1 for c in customers if not c.get("email") or not c.get("phone")) +
                      sum(1 for m in smart_meters if not m.get("installation_date")) +
                      sum(1 for r in meter_readings if not r.get("power_usage_kwh")) +
                      sum(1 for s in sensor_readings if not s.get("temperature_c")) +
                      sum(1 for b in billing_records if not b.get("billing_period_start")) +
                      sum(1 for w in weather_data if not w.get("temperature_c")))
        
        outlier_issues = (sum(1 for r in meter_readings if r.get("voltage") and r["voltage"] > 250) +
                         sum(1 for r in billing_records if r.get("amount_due") and r["amount_due"] < 0))
        
        total_issues = null_issues + outlier_issues
        actual_quality = round(max(0, 100 - (total_issues / total_records * 100)), 1) if total_records > 0 else 100
        
        # Generate 10 dummy runs with variations
        dummy_runs = []
        base_time = datetime.now()
        
        for i in range(10):
            is_latest = (i == 9)  # Last one is the actual data
            
            if is_latest:
                # Use actual data for the latest run
                records = actual_total
                quality = actual_quality
            else:
                # Generate dummy data with ±10% variation from actual for volume
                variation_pct = random.uniform(-0.10, 0.10)
                records = int(actual_total * (1 + variation_pct))
                # Quality varies by ±8%
                quality = round(max(65, min(100, actual_quality + random.uniform(-8, 8))), 1)
            
            dummy_runs.append({
                "run_id": f"RUN-{i+1}",
                "timestamp": (base_time - timedelta(minutes=(9-i)*15)).isoformat(),
                "records_processed": records,
                "quality_score": quality,
                "issues_found": int(records * (100 - quality) / 100),
                "duration_s": random.randint(45, 180)
            })
        
        pipeline_runs = dummy_runs

    return {
        "logs": history,
        "orchestration": {
            "completed": completed,
            "failed": failed,
            "retrying": retrying
        },
        "volume_chart": chart_data,
        "pipeline_runs": pipeline_runs[-10:]  # last 10 runs for the chart
    }

# ============================================================================
# DATA RELATIONSHIPS & ANALYTICS
# ============================================================================

@app.get("/api/customer-analytics/{customer_id}")
def get_customer_analytics(customer_id: str):
    """Get comprehensive analytics for a specific customer"""
    # Load related data
    customers = load_data("customers.json")
    smart_meters = load_data("smart_meters.json")
    meter_readings = load_data("meter_readings.json")
    billing_records = load_data("billing_records.json")
    
    # Find customer
    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Find related meters
    meters = [m for m in smart_meters if m["customer_id"] == customer_id]
    
    # Find related readings
    readings = [r for r in meter_readings if r["customer_id"] == customer_id]
    
    # Find related billing
    bills = [b for b in billing_records if b["customer_id"] == customer_id]
    
    # Calculate stats
    total_usage = sum(r.get("power_usage_kwh", 0) for r in readings if r.get("power_usage_kwh"))
    avg_usage = total_usage / len(readings) if readings else 0
    total_billed = sum(b.get("amount_due", 0) for b in bills if b.get("amount_due") and b["amount_due"] > 0)
    
    return {
        "customer": customer,
        "meters": meters,
        "stats": {
            "total_meters": len(meters),
            "total_readings": len(readings),
            "total_usage_kwh": round(total_usage, 2),
            "avg_usage_kwh": round(avg_usage, 2),
            "total_bills": len(bills),
            "total_amount_billed": round(total_billed, 2)
        },
        "recent_readings": readings[-10:] if readings else [],
        "recent_bills": bills[-5:] if bills else []
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# Made with Bob
