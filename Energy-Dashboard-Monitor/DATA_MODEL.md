# Energy Dashboard - Data Model Documentation

## Overview
This document describes the relational data model used in the Energy Dashboard Monitor system. The model is designed to simulate a real-world energy management system with proper foreign key relationships and realistic data quality issues (10-12% error rate).

## Entity Relationship Diagram

```
┌─────────────┐
│  CUSTOMERS  │
└──────┬──────┘
       │ 1
       │
       │ N
┌──────┴──────────┐
│  SMART_METERS   │
└──────┬──────────┘
       │ 1
       │
       │ N
┌──────┴──────────────┐
│  METER_READINGS     │
└─────────────────────┘

┌─────────────┐
│  CUSTOMERS  │────────┐
└─────────────┘        │ 1
                       │
                       │ N
                ┌──────┴──────────┐
                │ BILLING_RECORDS │
                └─────────────────┘

┌──────────────┐
│ GRID_SENSORS │
└──────┬───────┘
       │ 1
       │
       │ N
┌──────┴──────────────┐
│  SENSOR_READINGS    │
└─────────────────────┘

┌──────────────┐
│ WEATHER_DATA │ (Independent)
└──────────────┘
```

## Entities

### 1. CUSTOMERS (Master Data)
**Purpose**: Core customer information for energy service accounts

**Fields**:
- `customer_id` (PK): Unique identifier (CUST-10000 to CUST-14999)
- `first_name`: Customer first name
- `last_name`: Customer last name
- `email`: Contact email
- `phone`: Contact phone number
- `address`: Street address
- `city`: City name
- `state`: State code (2 letters)
- `zip_code`: Postal code
- `account_status`: ACTIVE | SUSPENDED | INACTIVE
- `registration_date`: ISO timestamp of account creation
- `customer_type`: RESIDENTIAL | COMMERCIAL | INDUSTRIAL

**Relationships**:
- One-to-One with SMART_METERS
- One-to-Many with BILLING_RECORDS
- One-to-Many with METER_READINGS (via SMART_METERS)

**Data Quality Issues** (~12%):
- NULL values in email, phone, address, city, zip_code (8%)
- Invalid email formats (no @ symbol)
- Invalid phone formats
- Invalid zip codes (non-numeric)
- Invalid state codes (XX)

**Record Count**: 5,000

---

### 2. SMART_METERS (Master Data)
**Purpose**: Physical smart meter devices installed at customer locations

**Fields**:
- `meter_id` (PK): Unique identifier (MTR-20000 to MTR-24999)
- `customer_id` (FK): References CUSTOMERS.customer_id
- `manufacturer`: Device manufacturer (Siemens, GE, Schneider, etc.)
- `model`: Device model (SM-2000, SM-3000, etc.)
- `installation_date`: ISO timestamp of installation
- `last_calibration`: ISO timestamp of last calibration
- `status`: ACTIVE | MAINTENANCE | FAULTY
- `firmware_version`: Software version (v1.0.0 format)

**Relationships**:
- Many-to-One with CUSTOMERS (each meter belongs to one customer)
- One-to-Many with METER_READINGS

**Data Quality Issues** (~6%):
- NULL values in last_calibration, firmware_version

**Record Count**: 5,000 (1 meter per customer)

---

### 3. METER_READINGS (Transactional Data)
**Purpose**: Time-series power consumption data from smart meters

**Fields**:
- `reading_id` (PK): Unique identifier (READ-100000+)
- `meter_id` (FK): References SMART_METERS.meter_id
- `customer_id` (FK): References CUSTOMERS.customer_id (denormalized for performance)
- `timestamp`: ISO timestamp of reading
- `power_usage_kwh`: Power consumption in kilowatt-hours
- `voltage`: Line voltage in volts
- `current_ampere`: Current in amperes
- `power_factor`: Power factor (0.85-1.0)
- `frequency_hz`: AC frequency in hertz

**Relationships**:
- Many-to-One with SMART_METERS
- Many-to-One with CUSTOMERS

**Data Quality Issues** (~11%):
- NULL values in power_usage_kwh, voltage, current_ampere (6%)
- Voltage spikes (>250V)
- Negative power usage
- Extreme current values (>100A)
- Invalid frequency (outside 59.5-60.5 Hz)

**Record Count**: 10,000

---

### 4. GRID_SENSORS (Master Data)
**Purpose**: Physical sensors monitoring grid infrastructure

**Fields**:
- `sensor_id` (PK): Unique identifier (GS-1000 to GS-1049)
- `location`: Physical location (Substation-A, Transformer-1, etc.)
- `sensor_type`: TEMPERATURE | VOLTAGE | CURRENT | TENSION | VIBRATION
- `installation_date`: ISO timestamp of installation
- `last_maintenance`: ISO timestamp of last maintenance
- `status`: OPERATIONAL | CALIBRATION | OFFLINE

**Relationships**:
- One-to-Many with SENSOR_READINGS

**Data Quality Issues**: None (master data is clean)

**Record Count**: 50

---

### 5. SENSOR_READINGS (Transactional Data)
**Purpose**: Time-series monitoring data from grid sensors

**Fields**:
- `reading_id` (PK): Unique identifier (SREAD-200000+)
- `sensor_id` (FK): References GRID_SENSORS.sensor_id
- `timestamp`: ISO timestamp of reading
- `temperature_c`: Temperature in Celsius
- `line_tension_kg`: Physical tension on power lines in kg
- `vibration_level`: Vibration measurement (0-10 scale)
- `humidity_percent`: Relative humidity percentage

**Relationships**:
- Many-to-One with GRID_SENSORS

**Data Quality Issues** (~25%):
- NULL values in temperature_c, line_tension_kg, vibration_level (7%)
- Negative tension values (physically impossible)
- Extreme temperatures (>60°C)
- Invalid humidity (>100%)
- Empty timestamps

**Record Count**: 8,000

---

### 6. BILLING_RECORDS (Transactional Data)
**Purpose**: Customer billing information and payment tracking

**Fields**:
- `billing_id` (PK): Unique identifier (BILL-300000+)
- `customer_id` (FK): References CUSTOMERS.customer_id
- `billing_period_start`: ISO timestamp of billing period start
- `billing_period_end`: ISO timestamp of billing period end
- `total_kwh_used`: Total energy consumed in period
- `amount_due`: Amount owed in dollars
- `amount_paid`: Amount paid in dollars
- `due_date`: ISO timestamp of payment due date
- `payment_date`: ISO timestamp of payment (NULL if unpaid)
- `status`: PENDING | PAID | OVERDUE

**Relationships**:
- Many-to-One with CUSTOMERS

**Data Quality Issues** (~76% - intentionally high for testing):
- Negative amounts
- Invalid status values (TRUE, FALSE, UNKNOWN, 123)
- Missing billing period start dates
- Future billing dates

**Record Count**: 5,000

---

### 7. WEATHER_DATA (Independent Data)
**Purpose**: Weather conditions that may correlate with energy usage

**Fields**:
- `weather_id` (PK): Unique identifier (WTH-400000+)
- `location`: Geographic region (US-East, US-West, etc.)
- `timestamp`: ISO timestamp of observation
- `temperature_c`: Temperature in Celsius
- `humidity_percent`: Relative humidity percentage
- `wind_speed_mph`: Wind speed in miles per hour
- `precipitation_mm`: Precipitation in millimeters
- `cloud_cover_percent`: Cloud coverage percentage

**Relationships**:
- None (independent dataset for correlation analysis)

**Data Quality Issues** (~31%):
- Invalid humidity (>100%)
- String values in wind_speed_mph (Fast, Slow, N/A, ERROR)
- Negative precipitation
- Extreme temperatures (>60°C)

**Record Count**: 2,000

---

## Data Quality Summary

| Dataset | Total Records | Clean Records | Issues | Issue Rate |
|---------|--------------|---------------|--------|------------|
| Customers | 5,000 | 4,569 | 431 | 8.6% |
| Smart Meters | 5,000 | 4,687 | 313 | 6.3% |
| Meter Readings | 10,000 | 9,292 | 708 | 7.1% |
| Grid Sensors | 50 | 50 | 0 | 0.0% |
| Sensor Readings | 8,000 | 6,019 | 1,981 | 24.8% |
| Billing Records | 5,000 | 1,200 | 3,800 | 76.0% |
| Weather Data | 2,000 | 1,384 | 616 | 30.8% |
| **TOTAL** | **35,050** | **27,201** | **7,849** | **22.4%** |

**Note**: Billing Records intentionally has a high error rate for testing data quality workflows.

## Foreign Key Relationships

### Primary Relationships
1. **CUSTOMERS → SMART_METERS**: `customer_id`
   - Cardinality: 1:1 (each customer has exactly one meter)
   
2. **SMART_METERS → METER_READINGS**: `meter_id`
   - Cardinality: 1:N (each meter has multiple readings)
   
3. **CUSTOMERS → METER_READINGS**: `customer_id`
   - Cardinality: 1:N (denormalized for query performance)
   
4. **CUSTOMERS → BILLING_RECORDS**: `customer_id`
   - Cardinality: 1:N (each customer has multiple bills)
   
5. **GRID_SENSORS → SENSOR_READINGS**: `sensor_id`
   - Cardinality: 1:N (each sensor has multiple readings)

## API Endpoints Supporting Relationships

### Customer-Centric Queries
- `GET /api/customers/{customer_id}` - Get customer details
- `GET /api/smart-meters?customer_id={id}` - Get customer's meter
- `GET /api/meter-readings?customer_id={id}` - Get customer's readings
- `GET /api/billing?customer_id={id}` - Get customer's bills
- `GET /api/customer-analytics/{customer_id}` - Get comprehensive customer analytics

### Meter-Centric Queries
- `GET /api/meter-readings?meter_id={id}` - Get readings for specific meter

### Sensor-Centric Queries
- `GET /api/sensor-readings?sensor_id={id}` - Get readings for specific sensor

## Data Generation Process

1. **Generate Master Data First**:
   - Customers (5,000 records)
   - Smart Meters (5,000 records, linked to customers)
   - Grid Sensors (50 records)

2. **Generate Transactional Data**:
   - Meter Readings (10,000 records, linked to meters and customers)
   - Sensor Readings (8,000 records, linked to sensors)
   - Billing Records (5,000 records, linked to customers)
   - Weather Data (2,000 records, independent)

3. **Inject Quality Issues**:
   - NULL values at configured rates
   - Invalid data formats
   - Outliers and impossible values
   - Schema violations

## Usage Examples

### Example 1: Get Customer with All Related Data
```python
# Get customer
customer = GET /api/customers/CUST-10000

# Get their meter
meter = GET /api/smart-meters?customer_id=CUST-10000

# Get their readings
readings = GET /api/meter-readings?customer_id=CUST-10000

# Get their bills
bills = GET /api/billing?customer_id=CUST-10000

# Or get everything at once
analytics = GET /api/customer-analytics/CUST-10000
```

### Example 2: Analyze Sensor Performance
```python
# Get sensor details
sensor = GET /api/grid-sensors (find GS-1000)

# Get all readings for that sensor
readings = GET /api/sensor-readings?sensor_id=GS-1000
```

### Example 3: Data Quality Analysis
```python
# Get overall quality metrics
quality = GET /api/quality

# Returns:
# - Total issues by type (nulls, outliers, schema)
# - Quality score
# - Quarantine list with specific problematic records
```

## File Locations

- **Raw Data**: `/data/raw/*.json`
- **Processed Data**: `/data/processed/*.json` (created after simulation runs)
- **Generator Script**: `/backend/generate_mock_data.py`
- **API Server**: `/backend/main.py`

## Regenerating Data

To regenerate all mock data:

```bash
cd backend
/Users/paragjain/dev-works/myenv/bin/python generate_mock_data.py
```

This will create fresh data files with new random quality issues while maintaining the relational structure.