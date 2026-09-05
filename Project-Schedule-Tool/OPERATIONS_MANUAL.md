# Project Schedule Tool - Operations Manual

**Version:** 2.2  
**Last Updated:** September 3, 2026  
**Document Owner:** Project Management Office  

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Dashboard Overview](#3-dashboard-overview)
4. [Creating a New Project](#4-creating-a-new-project)
5. [Working with Tasks](#5-working-with-tasks)
6. [Gantt Timeline Visualization](#6-gantt-timeline-visualization)
7. [Public Holiday Adjustments](#7-public-holiday-adjustments)
8. [AI Provider Selection](#8-ai-provider-selection)
9. [Generating Statement of Work (SoW)](#9-generating-statement-of-work-sow)
10. [Exporting to Excel](#10-exporting-to-excel)
11. [Saving and Loading Projects](#11-saving-and-loading-projects)
12. [Settings and Configuration](#12-settings-and-configuration)
13. [Troubleshooting](#13-troubleshooting)
14. [Best Practices](#14-best-practices)

---

## 1. Introduction

### 1.1 Purpose
The Project Schedule Tool is an AI-powered web application designed to help project managers create, manage, and visualize project schedules with professional documentation generation capabilities.

### 1.2 Key Capabilities
- **Smart Scheduling**: Automatic dependency resolution and critical path calculations
- **Public Holiday Adjustment**: Toggle Victoria (Australia) and India public holidays on and shift the whole schedule around them automatically
- **AI-Powered Documentation**: Generate professional Statement of Work documents using enterprise AI
- **Dual AI Providers**: Choose between SAP AI Core (Claude 4.7 Opus) or IBM ICA (Claude Sonnet 5)
- **Visual Timeline**: Interactive Gantt chart with week-by-week task allocation
- **Professional Exports**: Export to Microsoft Excel with formulas and formatting
- **Auto-Save**: Automatic draft saving to prevent data loss

### 1.3 System Requirements
- **Web Browser**: Chrome, Firefox, Safari, or Edge (latest version)
- **Internet Connection**: Required for AI-powered features
- **Screen Resolution**: Minimum 1366x768 (1920x1080 recommended)

---

## 2. Getting Started

### 2.1 Accessing the Application

1. Open your web browser
2. Navigate to: **http://localhost:5173** (or the URL provided by your IT team)
3. The application loads directly to the **Dashboard** page

<<Screenshot Here: screenshot-01-login-screen.png - Main application login/landing page>>

### 2.2 Application Layout

The application consists of three main sections:

- **Top Navigation Bar**: Access Dashboard, Create New Project, and Settings
- **Main Content Area**: Your workspace for project planning
- **Action Buttons**: Quick access to Export, SoW Generation, and Save functions

<<Screenshot Here: screenshot-02-application-layout.png - Annotated view showing navigation bar, content area, and action buttons>>

---

## 3. Dashboard Overview

### 3.1 Dashboard Features

The Dashboard is your project hub, displaying all saved project drafts.

**Key Elements:**
- **Project Cards**: Each card shows project name, last modified date, and customer
- **Search Bar**: Filter projects by name or customer
- **New Project Button**: Quick access to create a new schedule
- **Load Button**: Open an existing project for editing

<<Screenshot Here: screenshot-03-dashboard-view.png - Dashboard showing multiple project cards>>

### 3.2 Loading an Existing Project

1. Locate your project card on the Dashboard
2. Click the **"Load"** button on the project card
3. The project opens in the Planner workspace

<<Screenshot Here: screenshot-04-load-project.png - Hovering over Load button on project card>>

### 3.3 Deleting a Project Draft

1. Find the project card you want to delete
2. Click the **"Delete"** button (trash icon)
3. Confirm deletion when prompted
4. **Note**: This only deletes the project schedule, not the associated SoW document

---

## 4. Creating a New Project

### 4.1 Starting a New Project

1. Click **"New Project"** in the top navigation bar
2. The Planner workspace opens with a blank project template

<<Screenshot Here: screenshot-05-new-project-button.png - New Project button highlighted in navigation>>

### 4.2 Project Metadata

Fill in the project details in the left metadata panel:

**Required Fields:**
- **Project Name**: Unique identifier (e.g., "PCR-001-CRM-Upgrade")
- **Customer**: Client or department name (e.g., "AusNet Services")
- **Start Date**: Project kickoff date

**Optional Fields:**
- **Background**: Project context, objectives, business drivers
- **Assumptions**: Key planning assumptions (resource availability, technology choices)
- **Out of Scope**: Explicitly excluded items

<<Screenshot Here: screenshot-06-project-metadata.png - Project metadata form with fields filled>>

### 4.3 Importance of Metadata

Complete metadata is crucial for:
- **AI-Generated SoW**: Richer context produces better documentation
- **Project Continuity**: Helps team members understand project context
- **Stakeholder Communication**: Provides clear scope boundaries

---

## 5. Working with Tasks

### 5.1 Task Grid Layout

The workspace features a **dual-grid layout**:

- **Left Grid (40%)**: Task metadata and properties
- **Right Grid (60%)**: Gantt timeline visualization

Both grids scroll vertically together for seamless navigation.

<<Screenshot Here: screenshot-07-dual-grid-layout.png - Split view showing task grid and Gantt timeline>>

### 5.2 Task Properties

Each task has the following properties:

| Column | Description | Editable |
|--------|-------------|----------|
| **Index** | Sequential task number (1, 2, 3...) | No |
| **Activity/Task** | Task name or description | Yes |
| **Hours** | Estimated effort in hours | Yes |
| **FTE** | Full-Time Equivalent allocation (0.1 to 1.0) | Yes |
| **Man Days** | Calculated staffing effort: `Est. Days × FTE`, rounded | No |
| **Mode** | Duration mode badge — ⚡ Effort Driven or 📌 Fixed Duration (see [5.7](#57-duration-mode-effort-driven-vs-fixed-duration)) | Yes |
| **Dependency** | Parent task index (e.g., "1" or "2,3") | Yes |
| **Calc. Start** | Calculated start date (can override) | Yes |
| **Calc. Finish** | Calculated finish date | No |
| **Color** | Task color in timeline | Yes |

> **New in v2.1 — Man Days vs. Est. Days:** "Est. Days" is the task's calendar span (compressed by FTE under Effort Driven mode); "Man Days" is the actual staffing effort (`Est. Days × FTE`) and does not compress — it reflects total person-days of work regardless of duration mode.

### 5.3 Adding Tasks

**Method 1: Direct Entry**
1. Click on an empty row in the task grid
2. Start typing in the "Activity/Task" column
3. Press **Tab** to move to the next field
4. Enter Hours, FTE, and Dependency values

**Method 2: Bulk Import**
1. Prepare tasks in a spreadsheet
2. Copy task data
3. Paste into the grid (future feature)

**Method 3: Insert via Row Action Toolbar**
1. Hover over any existing task row in the left grid
2. A small dot appears on the right edge of the **Actions** column — hovering reveals a floating pill toolbar
3. Click the **insert above** or **insert below** icon to add a new blank task immediately adjacent to that row
4. All task indexes and dependency numbering are automatically renumbered

<<Screenshot Here: screenshot-08-adding-tasks.png - User entering task information in grid>>

### 5.4 Row Actions Toolbar

*(New in v2.1)*

The rightmost column of the task grid hosts a **hover-reveal action toolbar** instead of a static delete button:

- **Idle state**: a subtle gray dot indicates the row has actions available
- **On hover**: a floating pill expands with three icons:
  - **➕ Insert Above** — inserts a new task directly above the current row
  - **➕ Insert Below** — inserts a new task directly below the current row
  - **🗑️ Delete** — removes the task (same behavior as before)
- Each action triggers a confirmation **snackbar** at the bottom of the screen (e.g., "New task inserted above", "Task deleted")
- Inserting a task automatically re-runs the scheduling engine so dates and dependent tasks stay in sync

<<Screenshot Here: screenshot-08b-row-action-toolbar.png - Hover toolbar showing insert above/below/delete icons>>

### 5.5 Editing Task Details

1. **Double-click** any editable cell to modify
2. For **Calc. Start** dates:
   - The existing date remains visible when editing
   - Enter date in **YYYY-MM-DD** format (e.g., 2026-10-15)
   - Press **Enter** to save
   - Invalid dates will revert to the original value
3. Changes are automatically saved to the draft every 2 minutes

<<Screenshot Here: screenshot-09-editing-date.png - Date cell in edit mode showing existing value>>

### 5.6 Task Dependencies

Dependencies define the task execution order.

**Dependency Rules:**
- Leave blank for tasks that can start immediately
- Enter a single index (e.g., "1") for one dependency
- Enter multiple indices separated by commas (e.g., "2,3") for multiple dependencies
- **Example**: Task 4 depends on Tasks 2 and 3 → Enter "2,3" in Dependency column

**Automatic Calculations:**
- Child tasks start the **Monday following** parent task completion
- Weekends are automatically skipped in calculations
- Critical path is calculated automatically

**Visual Dependency Indicator** *(New in v2.1)*:
- A **🔗 chain icon** appears on the first active day (daily view) or first active week (weekly view) of any task that has a dependency
- Hover over the icon to see a tooltip: *"Depends on: Task(s) X, Y"*
- This makes it easy to spot dependent tasks directly on the Gantt timeline without checking the Dependency column

<<Screenshot Here: screenshot-10-task-dependencies.png - Task grid showing dependency relationships and chain icon>>

### 5.7 Duration Mode: Effort Driven vs. Fixed Duration

*(New in v2.1)*

Each task now has a **Mode** setting that controls how adding FTE (staff) affects the task's calendar duration:

| Mode | Behavior | Formula |
|------|----------|---------|
| **⚡ Effort Driven** (default) | More FTE compresses the calendar span — classic "add people to finish faster" | `Calendar Days = (Hours / 8) / FTE` |
| **📌 Fixed Duration** | FTE does **not** compress the timeline — the task always spans its natural day count, regardless of staffing | `Calendar Days = Hours / 8` |

**When to use Fixed Duration:**
- Tasks gated by external factors (e.g., a mandatory review period, a vendor SLA, a training course) where adding people doesn't shorten the calendar time
- Tasks where FTE represents parallel workstreams tracked for cost/Man Days purposes only, not schedule compression

**How to change the mode:**
1. Click on the **Mode** cell for a task
2. Select **effort-driven** or **fixed-duration** from the dropdown
3. The Gantt timeline and all dependent task dates recalculate automatically

<<Screenshot Here: screenshot-10b-duration-mode.png - Mode column showing Effort Driven and Fixed Duration badges>>

### 5.8 Task Colors

Assign colors to differentiate task types or phases:

1. Click on the **Color** cell for a task
2. Select from the color palette or enter a hex code (e.g., #FF5733)
3. The timeline bar updates automatically

**Color Coding Suggestions:**
- 🔵 Blue: Planning/Design tasks
- 🟢 Green: Development/Implementation
- 🟡 Yellow: Testing/QA
- 🔴 Red: Critical path items
- 🟣 Purple: Management/Governance

<<Screenshot Here: screenshot-11-color-selection.png - Color picker for task>>

---

## 6. Gantt Timeline Visualization

### 6.1 Timeline Overview

The right-hand grid displays a visual Gantt chart:

- **Columns**: Each column represents a week (ending on Friday)
- **Colored Cells**: Tasks appear as colored cells in their scheduled weeks
- **5-Box Indicators**: Small squares showing daily activity (Monday-Friday)
- **Filled Boxes (▪)**: Work is scheduled on that day
- **Empty Boxes (▫)**: No work scheduled on that day
- **🔗 Chain Icon** *(New in v2.1)*: Appears on the first active day/week of any task with a dependency — hover for a tooltip naming the parent task(s)

<<Screenshot Here: screenshot-12-gantt-timeline.png - Gantt timeline showing tasks with 5-box daily indicators and dependency chain icons>>

### 6.2 Reading the Timeline

**Example:**
```
Task 1: ▪ ▪ ▪ ▫ ▫  (Work on Mon, Tue, Wed only)
Task 2: ▪ ▪ ▪ ▪ ▪  (Work all week)
Task 3: ▫ ▫ ▪ ▪ ▪  (Work Wed, Thu, Fri only)
```

### 6.3 Horizontal Scrolling

- Use the **scrollbar** at the bottom of the timeline grid to navigate forward/backward in time
- Scroll right to view future weeks
- Scroll left to return to earlier weeks

<<Screenshot Here: screenshot-13-timeline-scrolling.png - Timeline scrolled to show future weeks>>

### 6.4 Manual Date Override

To override calculated start dates:

1. Double-click the **Calc. Start** date cell
2. Edit the date (format: YYYY-MM-DD)
3. Press **Enter** to save
4. The cell turns **blue** with a light blue background to indicate a manual override
5. The finish date and dependent tasks recalculate automatically

<<Screenshot Here: screenshot-14-manual-date-override.png - Task with manually overridden date shown in blue>>

---

## 7. Public Holiday Adjustments

*(New in v2.2)*

### 7.1 Configuring Holiday Lists

Public holidays are configured once per region on the **Settings** page and then reused by every project.

1. Navigate to **Settings** → **Public Holidays**
2. Select a region: **Victoria, Australia** or **India**
3. Click **"Add / Update Holidays"**
4. Paste the holiday list copied from a webpage or spreadsheet into the text box (any format — the AI extracts the dates)
5. Click **"Parse & Save"**
6. The AI extracts this year's holidays and overwrites the existing saved list for that region
7. A confirmation snackbar shows how many holidays were saved

<<Screenshot Here: screenshot-27-holiday-settings.png - Public Holidays card on Settings page with paste modal open>>

**Note**: Saving a new list for a region completely replaces the previous one for that region — re-paste the full list (not just new entries) each time you update it.

### 7.2 Turning Holiday Adjustment On

In the **Planner** toolbar, next to **"Force Recalculate"**, there are two toggle buttons:

- **🇦🇺 Adjust Vic. Holidays**
- **🇮🇳 Adjust Ind. Holidays**

1. Click a button to turn that region's holidays **on**
2. The schedule immediately recalculates: any task day landing on one of that region's holidays shifts forward to the next working day
3. The shift **cascades** — every task depending (directly or indirectly) on a shifted task moves accordingly, exactly as if the holiday were an extra weekend day
4. Click the same button again to turn that region **off** and recalculate without it
5. Both regions can be enabled at the same time — a day that is a holiday in either active region is skipped

<<Screenshot Here: screenshot-28-holiday-toggle-buttons.png - Planner toolbar showing Force Recalculate, Adjust Vic. Holidays, Adjust Ind. Holidays buttons>>

### 7.3 Reading the "H" Marker

When a task's scheduled day falls on an active holiday, the Gantt cell shows an **H** instead of the normal task box/color:

| Region | On-Screen Color |
|--------|------------------|
| Victoria, Australia | 🟠 Orange / amber |
| India | 🔵 Blue |

- Hover over an **H** marker to see the holiday's name in a tooltip
- This applies in both the weekly 5-box view and the day-by-day view

<<Screenshot Here: screenshot-29-holiday-h-marker.png - Gantt cells showing orange H for Vic and blue H for India holidays>>

### 7.4 Holidays in the Excel Export

- The exported Gantt grid mirrors the on-screen state exactly: whichever regions are toggled on in the Planner at export time are the ones reflected in the spreadsheet's shifted dates and "H" markers
- In Excel, the "H" character is rendered in **white** so it stands out against the task's own colored cell background
- A **Public Holidays** section is added below "Out of Scope & Exclusions" listing every saved holiday for **both** regions (Vic Holidays and Ind. Holidays, each with its dates), regardless of which toggles were active — this is a permanent reference, not tied to the on-screen toggle state

<<Screenshot Here: screenshot-30-excel-public-holidays.png - Excel sheet showing Public Holidays reference section and white H markers>>

---

## 8. AI Provider Selection

### 8.1 Accessing Provider Settings

The tool supports two enterprise AI providers for document generation.

**Steps to Change Provider:**

1. Click **"Settings"** in the top navigation bar
2. Locate the **"AI Provider Selection"** section
3. Choose between:
   - **SAP AI Core (Claude 4.7 Opus)**: Enterprise SAP integration
   - **IBM ICA (Claude Sonnet 5)**: IBM watsonx Code Assistant

<<Screenshot Here: screenshot-15-settings-page.png - Settings page with AI Provider Selection section>>

### 8.2 Provider Availability Status

Each provider shows an availability indicator:

- **🟢 Available**: Provider is configured and ready to use
- **🔴 Not Available**: Configuration issue - contact your IT administrator

<<Screenshot Here: screenshot-16-provider-status.png - Provider selection showing availability chips>>

### 8.3 Switching Providers

1. Select your preferred provider radio button
2. A success message confirms the switch
3. Your selection is automatically saved
4. All future SoW generation uses the selected provider until changed

**Note**: The selected provider persists across sessions - you don't need to re-select it each time you use the application.

---

## 9. Generating Statement of Work (SoW)

### 9.1 Prerequisites

Before generating a SoW, ensure you have:

✅ **Project Name** entered (not "New Project Schedule")  
✅ **Customer Name** entered  
✅ **Background** information provided  
✅ **Assumptions** listed  
✅ **Out of Scope** items defined (optional but recommended)

### 9.2 Generating Your First SoW

1. Complete the project metadata in the left panel
2. Click the **"SoW Draft"** button in the toolbar
3. Wait for the AI to analyze your project (10-30 seconds)
4. The SoW modal opens displaying the generated document

<<Screenshot Here: screenshot-17-sow-button.png - SoW Draft button highlighted in toolbar>>

### 9.3 AI Analysis Process

The AI performs intelligent analysis:

- **Sufficient Context**: Generates a comprehensive SoW immediately
- **Insufficient Context**: Prompts you to provide additional information
  - Review the AI's questions
  - Update your project metadata with more details
  - Click **"Regenerate"** to try again

<<Screenshot Here: screenshot-18-sow-generation-loading.png - Loading spinner during SoW generation>>

### 9.4 Reviewing the SoW

The generated SoW includes:

**Standard Sections:**
- Executive Summary
- Background and Context
- Project Scope
- Key Assumptions
- Deliverables
- Out of Scope Items
- Timeline and Milestones
- Success Criteria

<<Screenshot Here: screenshot-19-sow-modal-view.png - SoW modal showing generated content>>

### 9.5 Editing the SoW

1. Click **"Edit"** button in the SoW modal
2. The content becomes editable (Markdown format)
3. Make your changes directly in the text area
4. Click **"Save"** to preserve your edits
5. The draft is automatically saved to `drafts/SoW-Draft-{ProjectName}.json`

<<Screenshot Here: screenshot-20-sow-edit-mode.png - SoW modal in edit mode>>

### 9.6 Regenerating a SoW

To create a fresh version:

1. Update your project metadata with new information
2. Click **"Regenerate"** in the SoW modal
3. Confirm that you want to overwrite the existing SoW
4. A new SoW is generated and replaces the previous version

**Warning**: Regeneration overwrites any manual edits. Save important custom content elsewhere before regenerating.

### 9.7 Exporting to Microsoft Word

1. Review the SoW content in the modal
2. Click **"Export to Word"** button
3. A `.docx` file downloads automatically
4. Open in Microsoft Word for final formatting and distribution

**File Name Format**: `SoW-{ProjectName}-{Timestamp}.docx`

<<Screenshot Here: screenshot-21-export-word.png - Export to Word button and downloaded file>>

### 9.8 Loading Existing SoW

If a SoW already exists for your project:

1. The toolbar button changes to **"View SoW Draft"**
2. Click to open the existing SoW instantly (no regeneration)
3. Review, edit, or regenerate as needed

---

## 10. Exporting to Excel

### 10.1 Excel Export Features

Export your project schedule to a consulting-grade Excel workbook with:

- ✅ **Task metadata table** (Index, Activity, Hours, FTE, Man Days, Mode, Dependencies)
- ✅ **Gantt chart visualization** with colored cells
- ✅ **5-box daily indicators** showing Mon-Fri activity
- ✅ **Live Excel formulas** for calculations
- ✅ **Professional formatting** ready for executive presentations
- ✅ **Landscape orientation** with optimized print settings
- ✅ **Public holiday parity** *(new in v2.2)* — whichever holiday regions are toggled on in the Planner are reflected in the export, with a **Public Holidays** reference section listing both regions' dates and "H" markers rendered in **white** text (see [7.4](#74-holidays-in-the-excel-export))

> **New in v2.1:** The metadata table now includes three additional columns — **Man Days**, **Mode**, and **Dep. Link** — carried over from the Planner grid. See [10.3](#103-excel-file-structure) for the full column layout.

### 10.2 Exporting Your Schedule

1. Ensure all tasks are entered and dependencies set
2. Click **"Export to Excel"** button in the toolbar
3. The Excel file downloads automatically
4. Open in Microsoft Excel to review

<<Screenshot Here: screenshot-22-export-excel-button.png - Export to Excel button in toolbar>>

### 10.3 Excel File Structure

**Sheet 1: Project Schedule**

| Section | Description |
|---------|-------------|
| Header Row | Project Name, Customer, Start Date |
| Task Metadata Columns | Index, Activity, Hours, Days, Weeks, FTE, Man Days, Mode, Dep. Link, Dependency |
| Gantt Timeline Columns | Weekly columns with colored cells and 5-box indicators |

**Metadata Column Layout** *(updated in v2.1 — now spans G through P, was G through M)*:

| Column | Field | Notes |
|--------|-------|-------|
| G | Index | |
| H | Activity/Task | |
| I | Est. Hours | |
| J | Est. Days | |
| K | Est. Weeks | |
| L | FTE | |
| M | **Man Days** *(new)* | Amber-highlighted; live formula `=ROUND(J×L,0)` |
| N | **Mode** *(new)* | "⚡ Effort Driven" or "📌 Fixed Duration" badge |
| O | **Dep. Link** *(new)* | "🔗 Task X, Y" — readable dependency chain summary |
| P | Dependency | Raw index string (e.g., "2,3") — moved from column M |
| Q onward | Weekly Gantt columns | Timeline start column shifted from N to Q |

Frozen panes, auto-filter range, and the Assumptions/Out-of-Scope merged sections were all widened to match (previously froze/filtered A–M; now A–P).

<<Screenshot Here: screenshot-23-excel-output.png - Excel file showing complete project schedule with Man Days, Mode, and Dep. Link columns>>

### 10.4 Understanding the Excel Timeline

Each week column shows:
- **Colored background**: Matches task color from the planner
- **5 small squares**: Represent Monday through Friday
  - **Filled (▪)**: Work scheduled on that day
  - **Empty (▫)**: No work on that day

**Example Reading:**
```
Week ending 2026-10-09: ▪ ▪ ▪ ▫ ▫
Interpretation: Task runs Monday-Wednesday only
```

<<Screenshot Here: screenshot-24-excel-daily-boxes.png - Close-up of Excel cells showing 5-box indicators>>

### 10.5 Excel Formulas

The exported file includes live formulas:

- **Estimated Days**: `=ROUND(Hours/8, 0)`
- **Estimated Weeks**: `=ROUND(Days/5, 0)`
- **Man Days** *(new in v2.1)*: `=ROUND(EstDays × FTE, 0)` — evaluates per row as `=ROUND(J{row}*L{row},0)`
- **Total Hours**: `=SUM(Hours column)`

You can modify hours and the calculations update automatically.

---

## 11. Saving and Loading Projects

### 11.1 Auto-Save Feature

The application **automatically saves** your work every **2 minutes** to prevent data loss.

**Auto-Save Requirements:**
- ✅ Project name must be unique (not "New Project Schedule")
- ✅ At least one task must be present
- ✅ Project name must not be empty

**Save Location**: `drafts/{ProjectName}_draft.json`

<<Screenshot Here: screenshot-25-autosave-notification.png - Auto-save success notification>>

### 11.2 Manual Saving

To manually save your project:

1. Click the **"Save"** button in the toolbar
2. A success notification confirms the save
3. The project appears on the Dashboard

**Note**: Manual saves are typically unnecessary due to auto-save, but useful before major changes.

### 11.3 Save File Locations

Your projects are stored locally in the `drafts/` folder:

```
drafts/
├── PCR-001-CRM-Upgrade_draft.json          ← Project schedule
├── SoW-Draft-PCR-001-CRM-Upgrade.json      ← Associated SoW document
├── ControlM-Migration_draft.json           ← Another project
└── SoW-Draft-ControlM-Migration.json       ← Its SoW
```

**Key Points:**
- Project drafts and SoW documents are **separate files**
- Deleting a project draft does **not** delete its SoW
- SoW files are **not** shown on the Dashboard

### 11.4 Loading Projects from Dashboard

1. Navigate to the **Dashboard**
2. Locate your project card
3. Click **"Load"**
4. The project opens in the Planner workspace with all tasks restored

### 11.5 Exporting Project as JSON

To back up or share a project:

1. Save your project normally
2. Navigate to the `drafts/` folder on your computer
3. Copy the `{ProjectName}_draft.json` file
4. Share via email or store in a backup location

**Future Feature**: Direct JSON export from the application interface.

---

## 12. Settings and Configuration

### 12.1 Settings Page Overview

Access **Settings** from the top navigation bar.

**Available Settings:**

1. **AI Provider Selection**
   - Choose between SAP AI Core and IBM ICA
   - View availability status for each provider

2. **User Preferences** *(Future)*
   - Default FTE allocation
   - Auto-save interval
   - Date format preferences

<<Screenshot Here: screenshot-26-full-settings-page.png - Complete settings page>>

### 12.2 Provider Configuration

Your IT administrator configures the AI providers. If a provider shows as **"Not Available"**:

1. Verify your network connection
2. Contact your IT support team
3. Check for system maintenance notifications

### 12.3 Application Information

The Settings page displays:
- Application version number
- Last updated date
- API endpoint status
- Documentation links

---

## 13. Troubleshooting

### 13.1 Common Issues and Solutions

#### Issue: SoW Generation Fails

**Symptoms**: Error message when clicking "SoW Draft" button

**Solutions**:
1. ✅ Verify **Project Name** is not empty or "New Project Schedule"
2. ✅ Verify **Customer Name** is filled in
3. ✅ Check **AI Provider** status in Settings (must show "Available")
4. ✅ Ensure internet connection is active
5. ✅ Try switching to the alternate AI provider
6. ✅ Refresh the page and try again

#### Issue: Auto-Save Not Working

**Symptoms**: No auto-save notifications appearing

**Solutions**:
1. ✅ Check project name is unique (not default name)
2. ✅ Ensure at least one task exists
3. ✅ Verify no browser pop-up blocker is interfering
4. ✅ Check browser console for errors (press F12)
5. ✅ Try manual save to test functionality

#### Issue: Tasks Not Showing in Timeline

**Symptoms**: Left grid has tasks but right grid (Gantt) is empty

**Solutions**:
1. ✅ Verify **Hours** value is greater than 0
2. ✅ Verify **FTE** value is between 0.1 and 1.0
3. ✅ Check **Start Date** is set at project level
4. ✅ Scroll horizontally in the timeline to locate tasks
5. ✅ Refresh the page to recalculate schedule

#### Issue: Dependencies Not Working

**Symptoms**: Child tasks not starting after parent completion

**Solutions**:
1. ✅ Verify dependency index exists (e.g., don't reference Task 10 if only 5 tasks exist)
2. ✅ Check dependency format (e.g., "1,2" not "1 2" or "1, 2")
3. ✅ Ensure no circular dependencies (Task 1 → Task 2 → Task 1)
4. ✅ Verify parent task has hours and duration
5. ✅ Refresh to recalculate dependency chain

#### Issue: Excel Export Not Downloading

**Symptoms**: Click "Export to Excel" but no file downloads

**Solutions**:
1. ✅ Check browser download settings/permissions
2. ✅ Look for download in browser's downloads folder
3. ✅ Disable browser pop-up blocker for this site
4. ✅ Try a different browser
5. ✅ Ensure project has at least one task

#### Issue: Date Editing Deletes Value

**Symptoms**: Double-clicking date clears the field

**Solutions**:
1. ✅ This should be fixed in the latest version (v2.0)
2. ✅ Refresh the page to load the latest code
3. ✅ Clear browser cache (Ctrl+Shift+Delete)
4. ✅ The existing date should remain visible when editing

### 13.2 Browser Compatibility

**Recommended Browsers:**
- ✅ Google Chrome 90+
- ✅ Mozilla Firefox 88+
- ✅ Microsoft Edge 90+
- ✅ Safari 14+

**Not Supported:**
- ❌ Internet Explorer (all versions)
- ❌ Mobile browsers (phone/tablet)

### 13.3 Getting Help

If issues persist:

1. **Check Application Logs**:
   - Press **F12** to open browser developer tools
   - Click **Console** tab
   - Screenshot any red error messages

2. **Contact Support**:
   - Email: project-tools-support@yourcompany.com
   - Include: Project name, error message, screenshots
   - Attach console logs if available

3. **Known Issues**:
   - Check the project README for known limitations
   - Review recent release notes for bug fixes

---

## 14. Best Practices

### 14.1 Project Planning

**✅ DO:**
- Use descriptive project names (e.g., "PCR-001-CRM-Upgrade" not "Project 1")
- Complete all metadata fields for better AI-generated SoW quality
- Define clear assumptions and scope boundaries upfront
- Review and update dependencies as tasks evolve
- Use consistent color coding across related projects

**❌ DON'T:**
- Use special characters in project names (/, \, :, *, ?, ", <, >, |)
- Leave Background field empty when planning to generate SoW
- Create circular dependencies (Task A depends on Task B which depends on Task A)
- Change project names after SoW generation (breaks the link)

### 14.2 Task Management

**✅ DO:**
- Break large tasks into smaller sub-activities (< 40 hours each)
- Use realistic FTE allocations (0.5-0.8 is common for part-time resources)
- Include buffer tasks for testing, reviews, and contingency
- Assign colors by project phase or workstream for clarity
- Validate dependency chains before finalizing

**❌ DON'T:**
- Create tasks with 0 hours (they won't appear in timeline)
- Use FTE > 1.0 (represents more than full-time, unrealistic)
- Skip dependency definitions (results in overlapping parallel work assumptions)
- Mix different project phases in the same color

### 14.3 SoW Generation

**✅ DO:**
- Provide rich, detailed background information (3-5 sentences minimum)
- List 5-10 key assumptions to set context
- Clearly define out-of-scope items to manage expectations
- Review and edit AI-generated content before sharing
- Export to Word for final formatting and branding

**❌ DON'T:**
- Generate SoW with minimal metadata (results in generic content)
- Skip proofreading AI-generated text
- Share raw SoW without adding company branding/headers
- Forget to update SoW when project scope changes significantly

### 14.4 Collaboration

**✅ DO:**
- Use consistent naming conventions across project teams
- Share JSON export files for collaboration
- Document major scope changes in project metadata
- Keep stakeholders informed via exported Excel/Word documents
- Archive completed projects for future reference

**❌ DON'T:**
- Have multiple people editing the same project simultaneously
- Delete drafts without backing up first
- Share sensitive project information via insecure channels

### 14.5 Performance Optimization

**✅ DO:**
- Close unnecessary browser tabs while using the tool
- Work with projects under 100 tasks for optimal performance
- Save regularly when making bulk changes
- Use auto-save for background protection

**❌ DON'T:**
- Keep multiple projects open in different tabs simultaneously
- Create mega-projects with 200+ tasks (consider breaking into phases)
- Disable auto-save for critical projects

---

## Appendix A: Keyboard Shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| Save Project | `Ctrl+S` (Windows) / `Cmd+S` (Mac) | Manual save |
| Navigate to Dashboard | `Alt+D` | Return to Dashboard |
| New Project | `Ctrl+N` | Create new project |
| Copy Cell | `Ctrl+C` | Copy selected cell |
| Paste Cell | `Ctrl+V` | Paste into selected cell |
| Undo | `Ctrl+Z` | Undo last change |
| Start Editing | `F2` | Edit selected cell |
| Exit Editing | `Esc` | Cancel cell edit |
| Next Cell | `Tab` | Move to next cell |
| Previous Cell | `Shift+Tab` | Move to previous cell |

*(Note: Some shortcuts may vary by browser)*

---

## Appendix B: Date Format Reference

**Standard Format**: `YYYY-MM-DD`

**Examples:**
- October 5, 2026 → `2026-10-05`
- January 15, 2027 → `2027-01-15`
- December 1, 2026 → `2026-12-01`

**Tips:**
- Always use 4-digit year
- Always use 2-digit month (01-12)
- Always use 2-digit day (01-31)
- Use hyphens (-) not slashes (/)

---

## Appendix C: Dependency Syntax

**Single Dependency:**
```
Task 3 depends on Task 1:
Enter in Dependency column: 1
```

**Multiple Dependencies:**
```
Task 5 depends on Tasks 2 and 4:
Enter in Dependency column: 2,4
```

**No Dependency:**
```
Task 1 can start immediately:
Leave Dependency column empty
```

**Invalid Formats:**
- ❌ "1 2" (space separated)
- ❌ "1, 2" (space after comma)
- ❌ "task 1" (text instead of number)
- ❌ "1-2" (range notation)

**Valid Formats:**
- ✅ "1"
- ✅ "1,2"
- ✅ "1,2,3,4"

**Visual Confirmation** *(New in v2.1)*: Once a valid dependency is entered, a 🔗 icon appears on the task's first active day/week in the Gantt timeline (Planner) and in the "Dep. Link" column (Excel export), so you can visually confirm the link was registered correctly.

---

## Appendix D: Color Hex Codes Reference

Common project colors:

| Color | Hex Code | Use Case |
|-------|----------|----------|
| 🔵 Blue | #3B82F6 | Planning/Design |
| 🟢 Green | #10B981 | Development |
| 🟡 Yellow | #F59E0B | Testing/QA |
| 🔴 Red | #EF4444 | Critical Path |
| 🟣 Purple | #8B5CF6 | Management |
| 🟠 Orange | #F97316 | Infrastructure |
| 🔴 Pink | #EC4899 | Documentation |
| ⚫ Gray | #6B7280 | Completed |

---

## Appendix E: File Storage Locations

**Project Drafts:**
```
drafts/{ProjectName}_draft.json
```

**SoW Documents:**
```
drafts/SoW-Draft-{ProjectName}.json
```

**Excel Exports:**
```
Downloads/Project_Schedule_{ProjectName}_{Timestamp}.xlsx
```

**Word SoW Exports:**
```
Downloads/SoW-{ProjectName}-{Timestamp}.docx
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-15 | PMO Team | Initial release |
| 1.5 | 2026-08-10 | PMO Team | Added SoW generation section |
| 2.0 | 2026-08-30 | PMO Team | Added dual AI provider support, 5-box daily indicators, date editing improvements |
| 2.1 | 2026-09-01 | PMO Team | Added row action toolbar (insert above/below), Man Days column, Effort Driven/Fixed Duration mode, dependency chain (🔗) indicator on Gantt timeline, and matching Excel export columns (Man Days, Mode, Dep. Link) |
| 2.2 | 2026-09-03 | PMO Team | Added Public Holiday Adjustment feature (region-specific toggles for Victoria/India, cascading reschedule, color-coded "H" markers — orange for Vic, blue for India — and matching white "H" markers plus a Public Holidays reference section in the Excel export); fixed a Gantt rendering bug for Fixed Duration tasks with FTE > 1; fixed "New Project" not resetting task data from the previous project |

---
