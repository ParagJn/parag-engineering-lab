# Project

Build a professional Project Planning application similar to Microsoft Project Lite.

The application must be React based with a clean modern interface.

The purpose is to allow users to quickly create implementation plans and export them into a professionally formatted Excel workbook.

The application should NOT be an Excel editor.

Instead Excel is only the final output.

---

# Technology Stack

Frontend

- React
- TypeScript
- Vite
- Material UI
- AG Grid

Backend

- Node.js
- Express

Libraries

- dayjs
- exceljs
- file-saver

---

# Architecture

Separate the application into independent engines.

UI Layer

↓

Planning Engine

↓

Scheduling Engine

↓

Excel Rendering Engine

The UI must never calculate schedules.

All calculations happen inside the scheduling engine.

---

# Core Data Model

Task

id

index

activity

estimatedHours

estimatedDays

estimatedWeeks

fte

dependency

manualStartDate

calculatedStartDate

calculatedFinishDate

weekAssignments

color

status

---

# User Workflow

User creates project

↓

Enter project start date

↓

Add task

↓

Enter hours

↓

Enter FTE

↓

(Optional) choose dependency

↓

Plan recalculates automatically

↓

Timeline updates

↓

Export Excel
