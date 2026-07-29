# Project Schedule Tool

A professional, high-performance web application designed to create, manage, and visualize project schedules using a high-level estimation model. Built with React, TypeScript, Material-UI (v6), AG Grid, and ExcelJS.

---

## 🌟 Key Features

### 1. Dynamic Scheduling Engine
* **Critical Path Calculations**: Topologically sorts task dependencies and automatically chains start/finish dates.
* **Weekend-Aware Calculator**: Skips Saturdays and Sundays when resolving working day offsets.
* **Monday Dependency Alignment**: If a parent task finishes mid-week, any dependent child task is scheduled to start on the Monday of the following week to ensure clean, high-level weekly boundaries.
* **Effort Spillover**: Allocates task effort percentages into weekly buckets based on precise working day boundaries.
* **Rounding Calculations**: Rounds estimated days and weeks to the nearest whole integer for clean estimation reports.

### 2. Dual-Grid Split Workspace
* **Task Metadata Grid (40% width)**: Edit index, activities, hours, FTEs, dependency indices, and display colors.
* **Gantt Timeline Grid (60% width)**: Horizontal scrolling timeline showing Friday-ending week columns.
* **Day-Level Visual Representation**: Tasks that start or end mid-week render Gantt bars offset absolutely in the weekly cell (e.g. occupying only Monday–Wednesday or Thursday–Friday) to prevent visual overlap of sequential tasks sharing a week.
* **Synchronized Vertical Scroll**: Scrolling either grid vertically scrolls the other in real time with zero lag.

### 3. Plan Storage & Management
* **Unique Save Dialog**: Save plans locally under a custom project name or download them as `.json` configuration backups.
* **Saved Plans Portal**: Displays a list of all locally saved plans on the welcome page, complete with metadata, timestamps, load triggers, and delete features.

### 4. Consulting-Grade Excel Export
* **Excel Formulas**: Inserts live formula bindings (`ROUND`, division, additions) instead of static values.
* **Gantt Renderings**: Merges weekly cells and formats them with matching colors and FTE labels.
* **Page Layout Setup**: Configured with landscape orientation, fit-to-width print properties, auto-fit columns, borders, and frozen panes.

### 5. AI-Powered Intelligence (Backend)
* **Universal LLM Integration**: Support for multiple AI providers (SAP AI Core, OpenAI, Google Gemini, Azure, Anthropic)
* **Task Analysis**: AI-powered task breakdown, effort estimation, and dependency identification
* **Project Optimization**: Intelligent suggestions for resource allocation and timeline optimization
* **Natural Language Queries**: Ask questions about your project in plain English
* **RESTful API**: Clean, well-documented FastAPI endpoints for frontend integration
* **Automatic Token Management**: OAuth 2.0 token caching and refresh for seamless authentication

---

## 📂 Project Architecture

```
Project-Schedule-Tool/
├── backend/                      # AI-powered FastAPI backend
│   ├── main.py                   # FastAPI application and endpoints
│   ├── llm_client.py             # Universal LLM client (reusable)
│   ├── config.json               # Multi-provider model configuration
│   ├── requirements.txt          # Python dependencies
│   ├── .env                      # Environment variables (not in git)
│   └── README.md                 # Backend documentation
├── src/
│   ├── app/                      # Providers, Router, and Theme Overrides
│   ├── engines/
│   │   ├── SchedulingEngine/     # Dependency chain calculations, weekend offsets, and unit tests
│   │   └── ExportEngine/         # ExcelJS spreadsheet generator
│   ├── models/                   # Project, Task, and Week typescript interfaces
│   ├── pages/
│   │   ├── Dashboard/            # Project hub & saved plans manager
│   │   └── Planner/              # Interactive split grid workspace
│   ├── services/
│   │   ├── api/                  # API integration with backend
│   │   └── storage/              # localStorage persistence utility
│   ├── state/                    # Zustand stores for project metadata and tasks
│   ├── index.css                 # Styling baseline and AG Grid theme overrides
│   └── main.tsx                  # App entry point
├── start.sh                      # Unified startup script (backend + frontend)
├── package.json
└── tsconfig.json
```

---

## 🚀 Getting Started

### Prerequisites
* **Node.js** (v18+) and npm
* **Python** 3.9+ (for AI-powered backend features)
* **Virtual Environment** at `/Users/paragjain/dev-works/myenv` (or update path in start.sh)

### Installation
1. Navigate to the project folder:
   ```bash
   cd Project-Schedule-Tool
   ```
2. Install frontend dependencies:
   ```bash
   npm install
   ```
3. Install backend dependencies:
   ```bash
   cd backend
   source /Users/paragjain/dev-works/myenv/bin/activate
   pip install -r requirements.txt
   cd ..
   ```
4. Configure backend environment:
   ```bash
   cd backend
   cp .env.example .env
   # Edit .env and add your API credentials
   cd ..
   ```

### Running the Application

#### Quick Start - Both Services (Recommended)
Start both backend and frontend with a single command:
```bash
./start.sh
```

This will:
- ✅ Check all prerequisites
- ✅ Install missing dependencies
- ✅ Start the FastAPI backend at [http://localhost:8000](http://localhost:8000)
- ✅ Start the React frontend at [http://localhost:5173](http://localhost:5173)
- ✅ Handle graceful shutdown with Ctrl+C

Access:
- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

#### Frontend Only
Start just the Vite development server:
```bash
npm run dev
```
Open [http://localhost:5173/](http://localhost:5173/) in your web browser.

#### Backend Only
Start just the FastAPI backend:
```bash
cd backend
source /Users/paragjain/dev-works/myenv/bin/activate
python main.py
```

### Building for Production
Compile the production bundle:
```bash
npm run build
```

### Running Engine Tests
Execute the automated unit tests for the scheduling logic:
```bash
npx vite-node src/engines/SchedulingEngine/test.ts
```
