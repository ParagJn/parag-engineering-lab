# Project Schedule Tool

A professional, AI-powered web application designed to create, manage, and visualize project schedules with intelligent document generation capabilities. Built with React, TypeScript, Material-UI (v6), AG Grid, ExcelJS, and SAP AI Core integration.

---

## 🌟 Key Features

### 1. AI-Powered Statement of Work (SoW) Generation ✨ NEW
* **Dual AI Provider Support**: Switch between SAP AI Core (Claude 4.7 Opus) and IBM ICA (Claude Sonnet 5) via Settings page 🆕
* **Provider Persistence**: Selected provider preference saved locally and remembered across sessions
* **Real-Time Provider Status**: Settings UI shows availability status for each configured provider
* **Intelligent Document Creation**: Generate professional SoW documents using enterprise-grade AI models
* **Context-Aware Analysis**: AI analyzes your project background, assumptions, and scope to create comprehensive work statements
* **Smart Content Validation**: System requests additional information if initial context is insufficient
* **Professional Formatting**: Auto-generates structured sections including Background, Scope, Deliverables, and Out-of-Scope items
* **Word Export**: Export generated SoW to Microsoft Word (.docx) format with proper formatting, headers, and tables
* **Draft Management**: Save, load, and regenerate SoW drafts linked to project names in `drafts/` folder
* **View & Regenerate**: Review existing SoW drafts or create fresh versions with updated information
* **One-Click Generation**: Single button click to generate comprehensive project documentation

### 2. Dynamic Scheduling Engine
* **Critical Path Calculations**: Topologically sorts task dependencies and automatically chains start/finish dates
* **Weekend-Aware Calculator**: Skips Saturdays and Sundays when resolving working day offsets
* **Monday Dependency Alignment**: Child tasks start on Monday following parent completion for clean weekly boundaries
* **Effort Spillover**: Allocates task effort percentages into weekly buckets based on precise working day boundaries
* **Rounding Calculations**: Rounds estimated days and weeks to the nearest whole integer for clean estimation reports
* **Sub-Activities Support**: Break down tasks into detailed sub-activities for granular planning

### 3. Dual-Grid Split Workspace
* **Task Metadata Grid (40% width)**: Edit index, activities, hours, FTEs, dependency indices, and display colors
* **Gantt Timeline Grid (60% width)**: Horizontal scrolling timeline showing Friday-ending week columns
* **Day-Level Visual Representation**: Tasks render with precise day offsets within weekly cells to prevent visual overlap
* **Synchronized Vertical Scroll**: Both grids scroll together in real time with zero lag
* **Inline Editing**: Edit task properties directly in the grid with instant validation
* **Color-Coded Tasks**: Visual distinction with customizable color coding per task

### 4. Intelligent Draft & Project Management
* **Auto-Save**: Automatically saves project drafts every 2 minutes to prevent data loss
* **Draft Validation**: Prevents saving with default or empty project names to avoid "Untitled" clutter
* **Separate SoW Storage**: SoW files stored independently as `SoW-Draft-{ProjectName}.json` in `drafts/` folder
* **Project Drafts**: Regular project saves as `{ProjectName}_draft.json` for work-in-progress
* **Dashboard Overview**: Clean dashboard view showing only project drafts (SoW files filtered out)
* **Load Existing Plans**: Open saved plans from Dashboard with full task and metadata restoration
* **Browser LocalStorage**: Store plans locally with metadata, timestamps, and quick access
* **JSON Import/Export**: Upload or download complete project plans as JSON configuration files

### 5. Consulting-Grade Excel Export
* **Excel Formulas**: Inserts live formula bindings (`ROUND`, division, additions) instead of static values
* **Gantt Renderings**: Merges weekly cells and formats them with matching colors and FTE labels
* **Page Layout Setup**: Landscape orientation, fit-to-width print properties, auto-fit columns, borders, and frozen panes
* **Professional Formatting**: Headers, borders, color schemes optimized for executive presentations
* **Resource Allocation**: Clear FTE (Full-Time Equivalent) displays per task and week

### 7. Public Holiday Adjustment 🆕
* **Region-Specific Holiday Lists**: Configure Victoria, Australia and India public holidays on the Settings page — paste raw text copied from any webpage/spreadsheet and the AI extracts a clean date/name list for the current year
* **One-Click Toggle Buttons**: "Adjust Vic. Holidays" 🇦🇺 and "Adjust Ind. Holidays" 🇮🇳 buttons in the Planner toolbar, next to "Force Recalculate"
* **Automatic Schedule Shifting**: When enabled, any task day that falls on an applied holiday shifts forward by a working day, and the shift cascades through all dependent tasks automatically (holidays are treated exactly like weekends by the scheduling engine)
* **Region-Colored "H" Markers**: Holiday days render an **H** marker instead of the normal task box — **orange/amber** for Victoria holidays, **blue** for India holidays — both regions can be toggled on simultaneously
* **Excel Export Parity**: The exported Gantt grid mirrors the on-screen holiday adjustment exactly (same dates shifted, same "H" markers, rendered in white for contrast against the task's colored cell)
* **Public Holidays Reference Section**: Excel export adds a dedicated section below "Out of Scope & Exclusions" listing every Victoria and India holiday date/name, independent of which toggles are currently active

### 8. Enterprise-Grade AI Backend
* **Dual Provider Architecture**: Switch between SAP AI Core and IBM ICA providers at runtime 🆕
* **SAP AI Core Integration**: Production-ready integration with SAP's AI orchestration platform (Claude 4.7 Opus)
* **IBM ICA Integration**: IBM watsonx Code Assistant support (Claude Sonnet 5, Gemini models) 🆕
* **Provider Settings API**: RESTful endpoints for provider selection and status checking 🆕
* **Settings Persistence**: Provider preference stored in `backend/settings.json` and survives restarts 🆕
* **AI-Powered Holiday Parsing**: `/holidays/parse` endpoint uses the active AI provider to extract structured date/name holiday lists from pasted raw text 🆕
* **Multi-Model Support**: Architecture supports OpenAI, Google Gemini, Azure OpenAI, and Anthropic
* **OAuth 2.0 Authentication**: Automatic token management, caching, and refresh for SAP AI Core
* **Orchestration API**: Uses SAP AI Core orchestration format v2 for advanced prompt engineering
* **RESTful API**: Clean, well-documented FastAPI endpoints at `http://localhost:8000`
* **Interactive API Docs**: Swagger UI available at `http://localhost:8000/docs`
* **Response Logging**: Configurable request/response logging for debugging and monitoring
* **Error Handling**: Comprehensive error handling with detailed feedback for troubleshooting

---

## 📂 Project Architecture

```
Project-Schedule-Tool/
├── backend/                          # AI-powered FastAPI backend
│   ├── main.py                       # FastAPI app with SoW + holiday parsing endpoints
│   ├── llm_client.py                 # Universal LLM client (SAP AI Core, OpenAI, etc.)
│   ├── config.json                   # Multi-provider model configuration
│   ├── data/                         # Saved public holiday lists ✨ NEW
│   │   ├── holidays_vic_australia.json
│   │   └── holidays_india.json
│   ├── requirements.txt              # Python dependencies (FastAPI, requests, etc.)
│   ├── .env                          # Environment variables (SAP credentials, not in git)
│   ├── Generate-SoW.md               # SoW feature documentation
│   └── backend-instructions.md       # Backend setup and API documentation
├── src/
│   ├── app/
│   │   ├── App.tsx                   # Main application component
│   │   ├── routes.tsx                # React Router configuration
│   │   ├── providers.tsx             # Context providers setup
│   │   └── theme.ts                  # Material-UI theme customization
│   ├── components/
│   │   └── SoWModal.tsx              # SoW display/edit/export modal ✨ NEW
│   ├── engines/
│   │   ├── SchedulingEngine/         # Dependency chain, weekend offsets, unit tests
│   │   └── ExportEngine/             # ExcelJS spreadsheet generator
│   ├── models/
│   │   ├── Project.ts                # Project metadata interface
│   │   ├── Task.ts                   # Task structure with dependencies
│   │   ├── Week.ts                   # Week calculation model
│   │   └── Holiday.ts                # Holiday entry type (date + name) ✨ NEW
│   ├── pages/
│   │   ├── Dashboard/                # Project hub with saved plans and drafts
│   │   ├── Planner/                  # Interactive split grid workspace with SoW button
│   │   └── Settings/                 # Configuration and preferences
│   ├── services/
│   │   ├── api/
│   │   │   ├── sowApi.ts             # SoW generation API client ✨ NEW
│   │   │   ├── exportApi.ts          # Export functionality
│   │   │   ├── mockApi.ts            # Mock data for development
│   │   │   └── projectApi.ts         # Project CRUD operations
│   │   └── storage/
│   │       └── index.ts              # localStorage persistence utility
│   ├── state/
│   │   ├── projectStore.ts           # Zustand store for project metadata
│   │   └── taskStore.ts              # Zustand store for task management
│   ├── utils/
│   │   ├── wordExport.ts             # Word (.docx) export utility ✨ NEW
│   │   └── sowStorage.ts             # SoW draft save/load functions ✨ NEW
│   ├── index.css                     # Global styles and AG Grid theme overrides
│   └── main.tsx                      # Application entry point
├── drafts/                           # Auto-generated draft storage
│   ├── {ProjectName}_draft.json      # Regular project drafts (on Dashboard)
│   └── SoW-Draft-{ProjectName}.json  # SoW documents (separate storage) ✨ NEW
├── Instructions/                     # Feature documentation and planning docs
├── start.sh                          # Unified startup script (backend + frontend)
├── vite.config.ts                    # Vite configuration with draft API endpoints
├── package.json                      # Frontend dependencies
├── tsconfig.json                     # TypeScript configuration
└── README.md                         # This file
```

---

## 🚀 Getting Started

### Prerequisites
* **Node.js** (v18+) and npm
* **Python** 3.9+ (for AI-powered backend features)
* **Virtual Environment** recommended (e.g., `/Users/paragjain/dev-works/myenv`)
* **SAP AI Core Account** (for SoW generation) or configure alternative LLM provider

### Installation

#### 1. Clone and Navigate
```bash
cd Project-Schedule-Tool
```

#### 2. Install Frontend Dependencies
```bash
npm install
```

#### 3. Install Backend Dependencies
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

#### 4. Configure Backend Environment
Create a `.env` file in the `backend/` directory:
```bash
cd backend
cp .env.example .env
```

Edit `.env` and add your credentials:
```env
# SAP AI Core Configuration
SAP_AI_CORE_AUTH_URL=https://your-auth-server.authentication.sap.hana.ondemand.com/oauth/token
SAP_AI_CORE_CLIENT_ID=your-client-id
SAP_AI_CORE_CLIENT_SECRET=your-client-secret
SAP_AI_CORE_RESOURCE_GROUP=your-resource-group
SAP_AI_CORE_API_BASE=https://api.ai.your-region.aws.ml.hana.ondemand.com/v2

# IBM ICA Configuration (NEW - Optional)
IBM_ICA_API_KEY=your-ibm-ica-api-key
IBM_ICA_MODEL_ID=claude-sonnet-5
IBM_ICA_ENDPOINT=https://api.nextgen-beta.ica.ibm.com/ica

# Optional: Other LLM Providers
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key
```

#### 5. Configure Model Settings
Edit `backend/config.json` to select your AI model:
```json
{
  "active_provider": "sap",
  "sap": {
    "deployment_id": "d021935c4e8c3985",
    "model_name": "anthropic--claude-4.7-opus"
  },
  "log_requests": true,
  "log_responses": true,
  "max_tokens": 25000
}
```

---

### Running the Application

#### 🎯 Quick Start - Both Services (Recommended)
Start both backend and frontend with a single command:
```bash
./start.sh
```

This will:
- ✅ Check all prerequisites
- ✅ Activate virtual environment
- ✅ Install missing dependencies
- ✅ Start the FastAPI backend at [http://localhost:8000](http://localhost:8000)
- ✅ Start the React frontend at [http://localhost:5173](http://localhost:5173)
- ✅ Handle graceful shutdown with Ctrl+C

**Access Points:**
- **Frontend App**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

#### Frontend Only
Start just the Vite development server:
```bash
npm run dev
```
Open [http://localhost:5173/](http://localhost:5173/) in your browser.

#### Backend Only
Start just the FastAPI backend:
```bash
cd backend
source venv/bin/activate  # or your virtual environment
python main.py
```

---

## 💡 Usage Guide

### Selecting Your AI Provider 🆕
1. Navigate to **Settings** page from the top navigation
2. Locate the **"AI Provider Selection"** section
3. Choose between:
   - **SAP AI Core (Claude 4.7 Opus)**: Enterprise SAP integration
   - **IBM ICA (Claude Sonnet 5)**: IBM watsonx Code Assistant
4. Provider availability status shown with colored chips:
   - 🟢 **Available**: Provider is configured and ready
   - 🔴 **Not Available**: Check `.env` configuration
5. Selected provider is automatically saved to `backend/settings.json`
6. All SoW generation uses the selected provider until changed

### Creating a New Project
1. Click **"New Project"** on the Dashboard
2. Enter a **unique project name** and **customer name** (required for SoW generation)
3. Fill in project details:
   - **Start Date**: Project kickoff date
   - **Background**: Project context, objectives, and requirements
   - **Assumptions**: Key assumptions for planning
   - **Out of Scope**: Items explicitly excluded from the project
4. Add tasks with dependencies, hours, and FTE allocations

### Generating a Statement of Work (SoW) ✨ NEW
1. Complete project details (name, customer, background, assumptions, scope)
2. Click the **"SoW Draft"** button in the toolbar
3. AI analyzes your project information:
   - If insufficient context: System prompts for additional information
   - If context is good: Generates comprehensive SoW document
4. Review the generated SoW in the modal:
   - **View Mode**: Read the formatted document
   - **Edit Mode**: Make manual adjustments if needed
   - **Regenerate**: Create a fresh version with updated information
5. **Export to Word**: Click "Export to Word" to download as `.docx` file
6. SoW is automatically saved to `drafts/SoW-Draft-{ProjectName}.json`

### Loading Existing SoW
- Open a project plan → If SoW exists, button shows **"View SoW Draft"**
- Click to view → No regeneration, instant display
- Click **"Regenerate"** in modal → Creates fresh SoW and overwrites existing file

### Auto-Save Behavior
- Project drafts auto-save every **2 minutes**
- Only saves when project has a unique name (not "New Project Schedule")
- Saves to `drafts/{ProjectName}_draft.json`
- SoW files stored separately and not affected by project deletion

### Configuring & Applying Public Holidays 🆕
1. Go to **Settings** → **Public Holidays**, pick a region (Victoria, Australia or India), click **"Add / Update Holidays"**, and paste the raw holiday text
2. The AI parses the text and saves the current year's dates for that region (overwrites any previously saved list)
3. In the **Planner** toolbar, click **"Adjust Vic. Holidays"** and/or **"Adjust Ind. Holidays"** to toggle each region on
4. When toggled on, tasks that fall on a holiday shift forward by a working day (cascading to dependents) and render an **H** marker — orange for Vic, blue for India — instead of the normal task box
5. Click a toggle again to turn it off and recalculate without that region's holidays
6. Excel export always includes a **Public Holidays** reference section (both regions' full lists) and mirrors whichever toggles are active on screen in the Gantt grid itself

### Exporting to Excel
1. Complete your project schedule with all tasks and dependencies
2. Click **"Export to Excel"** in the toolbar
3. Excel file includes:
   - Task metadata (activities, hours, FTEs, dependencies)
   - Gantt chart with colored weekly cells
   - Live Excel formulas for calculations
   - Professional formatting ready for presentations

---

## 🧪 Testing & Development

### Build for Production
Compile the production bundle:
```bash
npm run build
```

Output: `dist/` folder with optimized static files

### Run Scheduling Engine Tests
Execute automated unit tests for the scheduling logic:
```bash
npx vite-node src/engines/SchedulingEngine/test.ts
```

### Check TypeScript Types
Validate TypeScript compilation:
```bash
npx tsc -b
```

### Backend Health Check
Verify backend is running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-07-29T10:30:00.000000",
  "llm_client_initialized": true
}
```

---

## 📡 API Endpoints

### Provider Settings API 🆕
**GET** `/settings/provider`
- **Description**: Get current AI provider and availability status
- **Response**:
  ```json
  {
    "success": true,
    "ai_provider": "sap",
    "sap_available": true,
    "ibm_ica_available": true
  }
  ```

**POST** `/settings/provider`
- **Description**: Switch AI provider (sap or ibm_ica)
- **Request Body**:
  ```json
  {
    "ai_provider": "ibm_ica"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "ai_provider": "ibm_ica",
    "sap_available": true,
    "ibm_ica_available": true,
    "message": "Provider successfully switched to IBM_ICA"
  }
  ```

### SoW Generation API ✨ NEW
**POST** `/generate/sow`
- **Description**: Generate Statement of Work using AI
- **Request Body**:
  ```json
  {
    "project_name": "PCR-001",
    "customer": "AusNet",
    "background": "Project context and requirements...",
    "assumptions": "Key assumptions...",
    "out_of_scope": "Excluded items..."
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "sow_content": "## Background and Context\n\n...",
    "timestamp": "2026-07-29T10:30:00",
    "needs_more_info": false
  }
  ```

**POST** `/save/sow-draft`
- **Description**: Save SoW draft to `drafts/` folder
- **Request Body**: SoW draft object with project details and content
- **Response**: Success message with file path

**GET** `/load/sow-draft/{project_name}`
- **Description**: Load existing SoW draft by project name
- **Response**: SoW draft object or `exists: false`

### Public Holidays API 🆕
**POST** `/holidays/parse`
- **Description**: AI-parses pasted holiday text into a structured date/name list and saves it, overwriting the existing list for that region
- **Request Body**:
  ```json
  {
    "region": "vic_australia",
    "raw_text": "1 January 2026 - New Year's Day\n26 January 2026 - Australia Day..."
  }
  ```
- **Response**:
  ```json
  { "success": true, "count": 12, "year": 2026 }
  ```

**GET** `/holidays/{region}`
- **Description**: Retrieve the saved holiday list for a region (`vic_australia` or `india`)
- **Response**:
  ```json
  { "holidays": [{ "date": "2026-01-01", "name": "New Year's Day" }, ...] }
  ```

### Other Endpoints
- **GET** `/health` - Backend health check
- **POST** `/generate/tasks` - AI-powered task generation (future)
- **POST** `/analyze/dependencies` - Dependency analysis (future)

Full API documentation available at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Technology Stack

### Frontend
- **React** 19.2.7 - UI framework
- **TypeScript** 6.0.2 - Type safety
- **Material-UI** v9.2.0 - Component library
- **AG Grid** - High-performance data grids
- **Zustand** - State management
- **React Router** - Navigation
- **Vite** 8.1.5 - Build tool and dev server
- **ExcelJS** - Excel export
- **docx** - Word document generation ✨ NEW

### Backend
- **Python** 3.9+
- **FastAPI** - Modern async API framework
- **Uvicorn** - ASGI server
- **SAP AI Core** - Enterprise AI orchestration
- **IBM ICA** - IBM watsonx Code Assistant 🆕
- **Claude 4.7 Opus** - SAP AI Core model
- **Claude Sonnet 5** - IBM ICA model 🆕
- **OAuth 2.0** - SAP authentication

---

## 📝 File Storage Structure

### Drafts Folder
```
drafts/
├── ControlM-Upgrade-ROM_draft.json        # Regular project draft
├── PCR-001_draft.json                     # Regular project draft
├── SoW-Draft-ControlM-Upgrade-ROM.json    # SoW document (separate)
└── SoW-Draft-PCR-001.json                 # SoW document (separate)
```

**Key Points:**
- Project drafts: `{ProjectName}_draft.json` (shown on Dashboard)
- SoW drafts: `SoW-Draft-{ProjectName}.json` (linked by project name, not shown on Dashboard)
- Deleting a project draft does NOT delete its SoW file
- Each project can have one associated SoW draft

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
lsof -ti:8000

# Kill existing process
kill -9 $(lsof -ti:8000)

# Check Python environment
which python
python --version
```

### Frontend won't start
```bash
# Check if port 5173 is in use
lsof -ti:5173

# Clear node modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### SoW Generation Errors
1. Check backend logs in terminal
2. Verify active provider credentials in `.env`:
   - SAP AI Core: `SAP_AI_CORE_*` variables
   - IBM ICA: `IBM_ICA_API_KEY`, `IBM_ICA_MODEL_ID`, `IBM_ICA_ENDPOINT`
3. Check current provider selection in Settings page
4. Review `backend/settings.json` for active provider
5. For SAP: Check `backend/config.json` for correct deployment_id
6. Ensure `log_requests: true` in config.json to see API calls
7. Validate project name and customer are not empty/default

### Build Errors
```bash
# Check TypeScript errors
npm run build

# Fix import issues
npm install --save-dev @types/node
```

---

## 📜 License

Proprietary - Internal Use Only

---

## 👥 Contributing

This is an internal project. For questions or contributions, contact the development team.

---

## 🎯 Roadmap

### Completed Features ✅
- ✅ Dual AI provider support (SAP AI Core + IBM ICA)
- ✅ Provider selection UI with real-time availability status
- ✅ Provider preference persistence across sessions
- ✅ AI-powered SoW generation with Claude models
- ✅ Word document export for SoW
- ✅ Auto-save with validation
- ✅ Separate SoW and project draft storage
- ✅ Dashboard filtering (SoW files hidden)
- ✅ Region-aware public holiday adjustment (Vic. Australia + India) with cascading reschedule, region-colored "H" markers, and Excel export parity 🆕

### Recent Fixes 🩹
- 🐛 Fixed Duration tasks with FTE > 1 now render their full Gantt bar span (weekly effort allocation previously always divided by FTE regardless of duration mode, cutting the bar short)
- 🐛 "New Project" on the Dashboard now fully resets the task list and holiday toggles instead of carrying over the previous project's schedule until a manual page refresh

### Future Enhancements 🚀
- 🔄 AI-powered task generation from project description
- 🔄 Intelligent dependency suggestion
- 🔄 Resource optimization recommendations
- 🔄 Risk analysis and mitigation strategies
- 🔄 Multi-project portfolio view
- 🔄 Team collaboration features
- 🔄 Advanced reporting and analytics
- 🔄 Integration with Jira, Azure DevOps, etc.

---

**Built with ❤️ for professional project planning**
