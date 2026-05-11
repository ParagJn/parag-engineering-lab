# Energy Dashboard Monitor - VoltStream

A comprehensive full-stack data quality monitoring and ETL pipeline visualization application for energy data management systems.

## 🎯 Overview

VoltStream Energy Dashboard simulates a real-time data processing system for smart meters, grid sensors, billing, and weather data. It features a relational data model with realistic data quality issues (10-12% error rate) for testing and demonstration purposes.

## 📊 Features

### Data Model
- **7 interconnected datasets** with proper foreign key relationships
- **35,050+ records** across all datasets
- **Realistic data quality issues** (nulls, outliers, schema violations)
- **Master-detail relationships** (Customers → Meters → Readings)

### Backend API (FastAPI)
- **20+ REST endpoints** with filtering and pagination
- **Real-time simulation** of data processing
- **Data quality analysis** across all datasets
- **Quarantine management** with auto-fix capabilities
- **Customer analytics** with relationship traversal

### Frontend Dashboard (React + TypeScript)
- **Pipeline Overview** - System health and dataset statistics
- **Real-Time Monitor** - Live ETL pipeline visualization
- **Data Quality Lab** - Quality metrics and quarantine management
- **Load History** - Historical job performance tracking

## 🏗️ Architecture

```
Energy-Dashboard-Monitor/
├── backend/
│   ├── main.py                    # FastAPI application
│   ├── generate_mock_data.py      # Data generator
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                 # Dashboard pages
│   │   ├── components/            # Reusable components
│   │   ├── context/               # React context
│   │   └── main.tsx               # App entry point
│   └── package.json
├── data/
│   ├── raw/                       # Original mock data
│   └── processed/                 # Transformed data
├── DATA_MODEL.md                  # Detailed data model docs
└── start.sh                       # Startup script
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ (with virtual environment at `/Users/paragjain/dev-works/myenv`)
- Node.js 18+
- npm or yarn

### Installation

1. **Clone the repository**
```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Energy-Dashboard-Monitor
```

2. **Install backend dependencies**
```bash
cd backend
/Users/paragjain/dev-works/myenv/bin/pip install -r requirements.txt
```

3. **Install frontend dependencies**
```bash
cd ../frontend
npm install
```

4. **Generate mock data**
```bash
cd ../backend
/Users/paragjain/dev-works/myenv/bin/python generate_mock_data.py
```

### Running the Application

**Option 1: Use the startup script**
```bash
chmod +x start.sh
./start.sh
```

**Option 2: Manual startup**

Terminal 1 - Backend:
```bash
cd backend
/Users/paragjain/dev-works/myenv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 - Frontend:
```bash
cd frontend
npm run dev
```

### Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 📚 Data Model

### Entities

1. **CUSTOMERS** (5,000 records)
   - Master customer information
   - 8.6% data quality issues

2. **SMART_METERS** (5,000 records)
   - Physical meter devices
   - Linked to customers (1:1)
   - 6.3% data quality issues

3. **METER_READINGS** (10,000 records)
   - Time-series power consumption
   - Linked to meters and customers
   - 7.1% data quality issues

4. **GRID_SENSORS** (50 records)
   - Infrastructure monitoring sensors
   - Clean master data

5. **SENSOR_READINGS** (8,000 records)
   - Grid monitoring data
   - Linked to sensors
   - 24.8% data quality issues

6. **BILLING_RECORDS** (5,000 records)
   - Customer billing information
   - Linked to customers
   - 76% data quality issues (intentionally high)

7. **WEATHER_DATA** (2,000 records)
   - Weather observations
   - Independent dataset
   - 30.8% data quality issues

See [DATA_MODEL.md](./DATA_MODEL.md) for detailed documentation.

## 🔌 API Endpoints

### Customer APIs
- `GET /api/customers` - List customers with filters
- `GET /api/customers/{id}` - Get specific customer
- `GET /api/customer-analytics/{id}` - Comprehensive customer analytics

### Meter APIs
- `GET /api/smart-meters` - List smart meters
- `GET /api/meter-readings` - List meter readings with filters

### Sensor APIs
- `GET /api/grid-sensors` - List grid sensors
- `GET /api/sensor-readings` - List sensor readings with filters

### Billing & Weather APIs
- `GET /api/billing` - List billing records with filters
- `GET /api/weather` - List weather data with filters

### System APIs
- `GET /api/system-status` - Overall system health
- `GET /api/quality` - Data quality analysis
- `POST /api/quality/purge` - Fix quarantined data
- `GET /api/history` - ETL job history
- `POST /api/simulate` - Run data simulation

## 🎮 Usage

### Running a Simulation
1. Navigate to any dashboard page
2. Click the "Run Simulation" button in the sidebar
3. Watch the ETL pipeline animate through stages:
   - Acquisition → Validation → Cleansing → Transformation → Lakehouse
4. Data quality metrics update automatically

### Viewing Data Quality
1. Go to **Data Quality Lab** page
2. View quality metrics (nulls, outliers, schema issues)
3. Inspect quarantined records
4. Click "Purge All Failures" to fix issues

### Analyzing Customer Data
```bash
# Get customer with all related data
curl http://localhost:8000/api/customer-analytics/CUST-10000
```

### Regenerating Data
```bash
cd backend
/Users/paragjain/dev-works/myenv/bin/python generate_mock_data.py
```

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation

### Frontend
- **React 19** - UI library
- **TypeScript 6** - Type safety
- **Vite 8** - Build tool
- **Tailwind CSS 3** - Styling
- **Axios** - HTTP client
- **React Router DOM 7** - Routing

### Design System
- **Material Design 3** inspired
- **Material Symbols** icons
- Custom color tokens and typography

## 📈 Data Quality Statistics

| Dataset | Records | Clean | Issues | Rate |
|---------|---------|-------|--------|------|
| Customers | 5,000 | 4,569 | 431 | 8.6% |
| Smart Meters | 5,000 | 4,687 | 313 | 6.3% |
| Meter Readings | 10,000 | 9,292 | 708 | 7.1% |
| Grid Sensors | 50 | 50 | 0 | 0.0% |
| Sensor Readings | 8,000 | 6,019 | 1,981 | 24.8% |
| Billing Records | 5,000 | 1,200 | 3,800 | 76.0% |
| Weather Data | 2,000 | 1,384 | 616 | 30.8% |
| **TOTAL** | **35,050** | **27,201** | **7,849** | **22.4%** |

## 🔧 Configuration

### Backend Configuration
Edit `backend/main.py`:
- `BASE_DIR` - Data directory location
- CORS settings for frontend origin

### Frontend Configuration
Edit `frontend/vite.config.ts`:
- Proxy settings for API calls
- Port configuration

### Data Generation
Edit `backend/generate_mock_data.py`:
- Record counts per dataset
- Data quality issue rates
- Field configurations

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 <PID>
```

### Frontend won't start
```bash
# Clear node modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### No data showing
```bash
# Regenerate mock data
cd backend
/Users/paragjain/dev-works/myenv/bin/python generate_mock_data.py
```

### API errors
- Check backend logs in terminal
- Verify data files exist in `data/raw/`
- Test endpoints: http://localhost:8000/docs

## 📝 Development

### Adding New Endpoints
1. Add route in `backend/main.py`
2. Update frontend API calls
3. Test with curl or Postman

### Adding New Pages
1. Create component in `frontend/src/pages/`
2. Add route in `frontend/src/main.tsx`
3. Add navigation in `Sidebar.tsx`

### Modifying Data Model
1. Update `backend/generate_mock_data.py`
2. Regenerate data
3. Update API endpoints in `backend/main.py`
4. Update frontend components

## 🤝 Contributing

This is a demonstration project. Feel free to fork and modify for your needs.

## 📄 License

MIT License - feel free to use this project for learning and demonstration purposes.

## 👤 Author

Parag Jain - Energy Dashboard Monitor

## 🙏 Acknowledgments

- Material Design 3 for design inspiration
- FastAPI for excellent API framework
- React team for amazing frontend library