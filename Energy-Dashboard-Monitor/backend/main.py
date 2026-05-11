import json
import os
import random
import time
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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

# Global variables to simulate dynamic system changes over time
system_state = {
    "runs": 0,
    "last_run_time": None
}

def load_data(filename):
    processed_path = os.path.join(PROCESSED_DIR, filename)
    raw_path = os.path.join(RAW_DIR, filename)
    
    file_path = processed_path if os.path.exists(processed_path) else raw_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Data file not found")
        
    with open(file_path, "r") as f:
        return json.load(f)

def save_processed(filename, data):
    processed_path = os.path.join(PROCESSED_DIR, filename)
    with open(processed_path, "w") as f:
        json.dump(data, f)

@app.post("/api/simulate")
def run_simulation():
    # 1. Load raw data
    smart_meters = load_data("smart_meter_data.json")
    grid_sensors = load_data("grid_sensor_data.json")
    billing = load_data("billing_data.json")
    weather = load_data("weather_data.json")
    
    # 2. Add random variance to smart meters
    for record in smart_meters:
        if record.get("power_usage_kwh") is not None:
            # +/- 5% variance
            variance = random.uniform(0.95, 1.05)
            record["power_usage_kwh"] = round(record["power_usage_kwh"] * variance, 2)
            
        # Occasionally fix or introduce a null
        if random.random() < 0.01:
            record["power_usage_kwh"] = round(random.uniform(0.5, 5.0), 2)
        elif random.random() < 0.005:
            record["power_usage_kwh"] = None
            
    # 3. Add random variance to grid sensors
    for record in grid_sensors:
        if record.get("line_tension_kg") is not None:
            variance = random.uniform(0.98, 1.02)
            record["line_tension_kg"] = round(record["line_tension_kg"] * variance, 0)
            
    # 4. Save to processed
    save_processed("smart_meter_data.json", smart_meters)
    save_processed("grid_sensor_data.json", grid_sensors)
    save_processed("billing_data.json", billing)
    save_processed("weather_data.json", weather)
    
    system_state["runs"] += 1
    system_state["last_run_time"] = datetime.now().isoformat()
    
    # Small delay to simulate processing time
    time.sleep(1)
    
    return {"status": "success", "message": "Simulation run complete", "runs": system_state["runs"]}

@app.get("/api/smart-meters")
def get_smart_meters(limit: int = 100, offset: int = 0):
    data = load_data("smart_meter_data.json")
    return {"total": len(data), "data": data[offset:offset+limit]}

@app.get("/api/grid-sensors")
def get_grid_sensors(limit: int = 100, offset: int = 0):
    data = load_data("grid_sensor_data.json")
    return {"total": len(data), "data": data[offset:offset+limit]}

@app.get("/api/billing")
def get_billing(limit: int = 100, offset: int = 0):
    data = load_data("billing_data.json")
    return {"total": len(data), "data": data[offset:offset+limit]}

@app.get("/api/weather")
def get_weather(limit: int = 100, offset: int = 0):
    data = load_data("weather_data.json")
    return {"total": len(data), "data": data[offset:offset+limit]}

@app.get("/api/system-status")
def get_system_status():
    base_pipelines = 42
    base_error = 0.0012
    base_score = 94
    
    # Add some dynamic variance based on runs
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
        "throughput_million": throughput
    }

@app.get("/api/quality")
def get_quality():
    # Analyze data to find actual issues
    smart_meters = load_data("smart_meter_data.json")
    grid_sensors = load_data("grid_sensor_data.json")
    
    null_count = sum(1 for r in smart_meters if r.get("power_usage_kwh") is None)
    outlier_count = sum(1 for r in smart_meters if r.get("voltage", 0) > 250) + \
                    sum(1 for r in grid_sensors if r.get("line_tension_kg", 0) < 0)
    
    total_records = len(smart_meters) + len(grid_sensors)
    
    # Calculate a dynamic score based on actual data
    error_count = null_count + outlier_count
    score = 100 - (error_count / total_records * 1000) if total_records > 0 else 100
    
    quarantine = []
    # Fetch first few nulls for quarantine table
    for r in smart_meters:
        if r.get("power_usage_kwh") is None:
            quarantine.append({
                "id": r.get("meter_id", "Unknown"),
                "source": "Smart Meter Load",
                "issue": "Null Value in Power Usage",
                "severity": "High",
                "timestamp": r.get("timestamp")
            })
            if len(quarantine) >= 3:
                break
                
    for r in grid_sensors:
        if r.get("line_tension_kg", 0) < 0:
            quarantine.append({
                "id": r.get("sensor_id", "Unknown"),
                "source": "Grid Sensor Load",
                "issue": "Negative Tension (Physics Error)",
                "severity": "Critical",
                "timestamp": r.get("timestamp")
            })
            if len(quarantine) >= 5:
                break

    return {
        "score": round(max(0, score), 1),
        "issues": {
            "nulls": null_count,
            "outliers": outlier_count,
            "schema_mismatch": random.randint(0, 5) # Keep some random
        },
        "quarantine": quarantine
    }

@app.post("/api/quality/purge")
def purge_failures():
    # Load processed data
    smart_meters = load_data("smart_meter_data.json")
    grid_sensors = load_data("grid_sensor_data.json")
    
    # "Fix" the data instead of deleting to keep the simulation volume
    for record in smart_meters:
        if record.get("power_usage_kwh") is None:
            record["power_usage_kwh"] = 0.0
            
    for record in grid_sensors:
        if record.get("line_tension_kg", 0) < 0:
            record["line_tension_kg"] = abs(record["line_tension_kg"])
            
    # Save processed data
    save_processed("smart_meter_data.json", smart_meters)
    save_processed("grid_sensor_data.json", grid_sensors)
    
    return {"status": "success", "message": "Quarantine purged and data fixed"}

@app.get("/api/history")
def get_history():
    runs = system_state["runs"]
    
    # Generate log history
    history = []
    base_time = datetime.now()
    
    for i in range(10):
        # Calculate dynamic values based on index and runs
        volume = 4800 + random.randint(-500, 1500)
        errors = random.randint(0, 45)
        if i == 0 and runs > 0:
            # The most recent simulated run
            status = "Completed"
            errors = random.randint(0, 10)
        else:
            status = random.choice(["Completed", "Completed", "Completed", "Completed", "Failed", "Warning"])
            
        history.append({
            "job_id": f"EXT-{8892 - i}",
            "source": random.choice(["Smart Meter US-East", "Grid Sensors EU", "Billing Database"]),
            "timestamp": (base_time - timedelta(hours=i*2 + random.randint(0, 1))).strftime("%b %d, %Y %H:%M"),
            "status": status,
            "volume": volume,
            "errors": errors if status != "Failed" else "N/A",
            "duration": f"{random.randint(45, 120)}s"
        })
        
    # Orchestration chart
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

    return {
        "logs": history,
        "orchestration": {
            "completed": completed,
            "failed": failed,
            "retrying": retrying
        },
        "volume_chart": chart_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
