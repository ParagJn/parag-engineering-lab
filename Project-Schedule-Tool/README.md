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

---

## 📂 Project Architecture

```
Project-Schedule-Tool/
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
│   │   ├── api/                  # Future API connection placeholders
│   │   └── storage/              # localStorage persistence utility
│   ├── state/                    # Zustand stores for project metadata and tasks
│   ├── index.css                 # Styling baseline and AG Grid theme overrides
│   └── main.tsx                  # App entry point
├── package.json
└── tsconfig.json
```

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Node.js (v18+) and npm installed.

### Installation
1. Navigate to the project folder:
   ```bash
   cd Project-Schedule-Tool
   ```
2. Install dependencies:
   ```bash
   npm install
   ```

### Running Locally
Start the local Vite development server:
```bash
npm run dev
```
Open [http://localhost:5173/](http://localhost:5173/) in your web browser.

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
