# Project Structure

The project should follow a feature-first modular architecture.

The React UI should only be responsible for rendering.

All business rules must live outside React components.

The structure must support replacing local engines with backend APIs in the future without changing the UI.

---

src/

│

├── app/

│   ├── App.tsx

│   ├── routes.tsx

│   ├── providers.tsx

│   └── theme.ts

│

├── assets/

│

├── components/

│   ├── common/

│   ├── layout/

│   ├── toolbar/

│   ├── timeline/

│   ├── forms/

│   └── dialogs/

│

├── features/

│

│   ├── project/

│   │

│   ├── task/

│   │

│   ├── planning/

│   │

│   ├── timeline/

│   │

│   └── export/

│

├── pages/

│

│   ├── Dashboard/

│   ├── Planner/

│   └── Settings/

│

├── models/

│

│   ├── Project.ts

│   ├── Task.ts

│   ├── Week.ts

│   ├── Timeline.ts

│   └── Schedule.ts

│

├── services/

│

│   ├── api/

│   │      mockApi.ts
│   │      projectApi.ts
│   │      planningApi.ts
│   │      exportApi.ts
│   │
│   ├── excel/
│   │
│   └── storage/
│
├── engines/

│

│   ├── PlanningEngine/

│   │

│   ├── SchedulingEngine/

│   │

│   ├── TimelineEngine/

│   │

│   ├── CalendarEngine/

│   │

│   ├── ValidationEngine/

│   │

│   └── ExportEngine/

│

├── hooks/

│

├── contexts/

│

├── state/

│

│   ├── projectStore.ts

│   ├── taskStore.ts

│   └── uiStore.ts

│

├── utils/

│

├── constants/

│

├── types/

│

└── styles/
