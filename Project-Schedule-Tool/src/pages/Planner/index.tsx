import React, { useRef, useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import type { ColDef } from 'ag-grid-community';
import dayjs from 'dayjs';

// Register AG Grid v36 modules
ModuleRegistry.registerModules([AllCommunityModule]);

// AG Grid styles
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';

import {
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Typography,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Save as SaveIcon,
  UploadFile as UploadFileIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

import { useProjectStore } from '../../state/projectStore';
import { useTaskStore } from '../../state/taskStore';
import { exportProjectToExcel } from '../../engines/ExportEngine';
import { storage } from '../../services/storage';
import type { Task } from '../../models/Task';

// Curated list of premium colors for the task bars
const PRESET_COLORS = [
  { value: '#FFEB3B', name: 'Yellow' },
  { value: '#2196F3', name: 'Blue' },
  { value: '#4CAF50', name: 'Green' },
  { value: '#FF9800', name: 'Orange' },
  { value: '#9C27B0', name: 'Purple' },
  { value: '#009688', name: 'Teal' },
  { value: '#F44336', name: 'Red' },
  { value: '#3F51B5', name: 'Indigo' },
  { value: '#795548', name: 'Brown' },
  { value: '#607D8B', name: 'Slate' }
];

export function Planner() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Project store hooks
  const project = useProjectStore((s) => s.project);
  const setProjectName = useProjectStore((s) => s.setProjectName);
  const setCustomer = useProjectStore((s) => s.setCustomer);
  const setStartDate = useProjectStore((s) => s.setStartDate);
  const loadProject = useProjectStore((s) => s.loadProject);

  // Task store hooks
  const tasks = useTaskStore((s) => s.tasks);
  const weeks = useTaskStore((s) => s.weeks);
  const minWeeksToShow = useTaskStore((s) => s.minWeeksToShow);
  const addTask = useTaskStore((s) => s.addTask);
  const deleteTask = useTaskStore((s) => s.deleteTask);
  const updateTask = useTaskStore((s) => s.updateTask);
  const setTasks = useTaskStore((s) => s.setTasks);
  const recalculate = useTaskStore((s) => s.recalculate);
  const setMinWeeksToShow = useTaskStore((s) => s.setMinWeeksToShow);

  // Dialog and Snackbar states
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [customPlanName, setCustomPlanName] = useState(project.name);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'info' | 'error'>('success');
  const [lastDraftSavedTime, setLastDraftSavedTime] = useState<string | null>(null);

  // Synchronize dynamic customPlanName when project.name updates in store
  useEffect(() => {
    setCustomPlanName(project.name);
  }, [project.name]);

  // Sync scroll references
  const [grid1Api, setGrid1Api] = useState<any>(null);
  const [grid2Api, setGrid2Api] = useState<any>(null);

  const onGrid1Ready = (params: any) => setGrid1Api(params.api);
  const onGrid2Ready = (params: any) => setGrid2Api(params.api);

  // Bidirectional vertical scroll synchronizer
  const onBodyScroll1 = (event: any) => {
    if (event.direction === 'vertical' && grid2Api) {
      const top = event.top;
      const grid2Viewport = document.querySelector('#grid-2 .ag-body-viewport') as HTMLElement;
      if (grid2Viewport && grid2Viewport.scrollTop !== top) {
        grid2Viewport.scrollTop = top;
      }
    }
  };

  const onBodyScroll2 = (event: any) => {
    if (event.direction === 'vertical' && grid1Api) {
      const top = event.top;
      const grid1Viewport = document.querySelector('#grid-1 .ag-body-viewport') as HTMLElement;
      if (grid1Viewport && grid1Viewport.scrollTop !== top) {
        grid1Viewport.scrollTop = top;
      }
    }
  };

  // Open Save dialog
  const handleOpenSaveDialog = () => {
    setCustomPlanName(project.name);
    setSaveDialogOpen(true);
  };

  // Save to browser local storage
  const handleSaveToBrowser = () => {
    if (!customPlanName.trim()) {
      alert('Please enter a valid plan name.');
      return;
    }

    // Update project name in store
    setProjectName(customPlanName);
    const updatedProject = { ...project, name: customPlanName };

    // Save
    storage.savePlan(updatedProject, tasks);
    setSaveDialogOpen(false);
    setSnackbarSeverity('success');
    setSnackbarMessage(`Plan "${customPlanName}" successfully saved to browser local storage!`);
    setSnackbarOpen(true);
  };

  // Download plan JSON file
  const handleSaveJSON = () => {
    if (!customPlanName.trim()) {
      alert('Please enter a valid plan name.');
      return;
    }

    setProjectName(customPlanName);
    const updatedProject = { ...project, name: customPlanName };

    const dataToSave = {
      project: updatedProject,
      tasks
    };
    const jsonString = JSON.stringify(dataToSave, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const filename = `${customPlanName.replace(/\s+/g, '_')}_plan.json`;

    // Save to disk
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setSaveDialogOpen(false);
    setSnackbarSeverity('success');
    setSnackbarMessage(`Plan downloaded as "${filename}"`);
    setSnackbarOpen(true);
  };

  // Ref to track latest project & tasks for background auto-save
  const latestDataRef = useRef({ project, tasks });
  useEffect(() => {
    latestDataRef.current = { project, tasks };
  }, [project, tasks]);

  // Save draft locally to drafts/ folder
  const handleSaveDraft = async (isAutoSave = false) => {
    const now = new Date();
    // Format: YYYY-MM-DD_HH-mm-ss
    const datetimeStr = now.getFullYear() +
      '-' + String(now.getMonth() + 1).padStart(2, '0') +
      '-' + String(now.getDate()).padStart(2, '0') +
      '_' + String(now.getHours()).padStart(2, '0') +
      '-' + String(now.getMinutes()).padStart(2, '0') +
      '-' + String(now.getSeconds()).padStart(2, '0');

    const currentProj = latestDataRef.current.project;
    const currentTasks = latestDataRef.current.tasks;
    const cleanProjectName = (currentProj.name || 'Untitled').trim().replace(/[^a-zA-Z0-9-_]/g, '_') || 'Untitled';
    const filename = `${cleanProjectName}_${datetimeStr}_draft.json`;

    const dataToSave = {
      project: currentProj,
      tasks: currentTasks
    };

    try {
      const response = await fetch('/api/save-draft', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          filename,
          data: dataToSave
        })
      });
      
      const result = await response.json();
      if (result.success) {
        const timeStr = now.toLocaleTimeString();
        setLastDraftSavedTime(timeStr);
        if (!isAutoSave) {
          setSnackbarSeverity('success');
          setSnackbarMessage(`Draft saved successfully to drafts/${filename}`);
          setSnackbarOpen(true);
        }
      } else {
        throw new Error(result.error || 'Unknown error');
      }
    } catch (error: any) {
      if (!isAutoSave) {
        setSnackbarSeverity('error');
        setSnackbarMessage(`Failed to save draft: ${error.message}`);
        setSnackbarOpen(true);
      } else {
        console.error('Auto-save failed:', error);
      }
    }
  };

  // Auto-save draft every 120 seconds in the background
  useEffect(() => {
    const interval = setInterval(() => {
      if (latestDataRef.current.tasks.length > 0) {
        handleSaveDraft(true);
      }
    }, 120000); // 2 minutes
    return () => clearInterval(interval);
  }, []);

  // JSON Load functionality
  const handleOpenJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target?.result as string);
        if (data.project && Array.isArray(data.tasks)) {
          loadProject(data.project);
          setTasks(data.tasks);
          setSnackbarSeverity('info');
          setSnackbarMessage('Loaded project plan from JSON file.');
          setSnackbarOpen(true);
        } else {
          alert('Invalid file format. Make sure it contains project and tasks data.');
        }
      } catch (err) {
        alert('Failed to parse project file.');
      }
    };
    reader.readAsText(file);
  };

  // Excel Export triggering
  const handleExportExcel = async () => {
    try {
      await exportProjectToExcel(project, tasks, weeks);
      setSnackbarSeverity('success');
      setSnackbarMessage('Excel sheet generated successfully!');
      setSnackbarOpen(true);
    } catch (err) {
      alert('Failed to export Excel file.');
      console.error(err);
    }
  };

  // Grid Cell edit request listener (Zustand state is immutable, so readOnlyEdit must be true)
  const onCellEditRequest = (event: any) => {
    const { data, colDef, newValue } = event;
    const field = colDef.field;
    if (!field) return;

    // Propagate updates to store
    updateTask(data.id, { [field]: newValue });
  };

  // Define column definitions for Left Task Grid (40%)
  const leftColumnDefs = useMemo<ColDef[]>(() => {
    return [
      {
        headerName: 'Index',
        field: 'index',
        width: 70,
        sortable: false,
        editable: false,
        cellStyle: { textAlign: 'center', fontWeight: 'bold' }
      },
      {
        headerName: 'Activity / Task',
        field: 'activity',
        width: 200,
        editable: true,
        cellEditor: 'agTextCellEditor'
      },
      {
        headerName: 'Est. Hours',
        field: 'estimatedHours',
        width: 100,
        editable: true,
        cellEditor: 'agNumberCellEditor',
        cellStyle: { textAlign: 'center' }
      },
      {
        headerName: 'Est. Days',
        field: 'estimatedDays',
        width: 90,
        editable: false,
        valueGetter: (params) => {
          const hours = params.data.estimatedHours || 0;
          return Math.round(hours / 8);
        },
        cellStyle: { textAlign: 'center', color: '#64748b' }
      },
      {
        headerName: 'Est. Weeks',
        field: 'estimatedWeeks',
        width: 90,
        editable: false,
        valueGetter: (params) => {
          const hours = params.data.estimatedHours || 0;
          return Math.round(hours / 40);
        },
        cellStyle: { textAlign: 'center', color: '#64748b' }
      },
      {
        headerName: 'FTE',
        field: 'fte',
        width: 80,
        editable: true,
        cellEditor: 'agNumberCellEditor',
        cellStyle: { textAlign: 'center' }
      },
      {
        headerName: 'Dependency',
        field: 'dependency',
        width: 100,
        editable: true,
        cellEditor: 'agTextCellEditor',
        cellStyle: { textAlign: 'center' }
      },
      {
        headerName: 'Calc. Start',
        field: 'calculatedStartDate',
        width: 110,
        editable: false,
        cellStyle: { textAlign: 'center', color: '#1e293b' }
      },
      {
        headerName: 'Calc. Finish',
        field: 'calculatedFinishDate',
        width: 110,
        editable: false,
        cellStyle: { textAlign: 'center', color: '#1e293b' }
      },
      {
        headerName: 'Color',
        field: 'color',
        width: 100,
        editable: true,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: {
          values: PRESET_COLORS.map(c => c.value)
        },
        refData: PRESET_COLORS.reduce((acc, c) => ({ ...acc, [c.value]: c.name }), {}),
        cellRenderer: (params: any) => {
          const val = params.value;
          const colorName = PRESET_COLORS.find(c => c.value === val)?.name || 'Default';
          return (
            <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 1, height: '100%', py: 0.5 }}>
              <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: val, border: '1px solid #cbd5e1' }} />
              <Typography variant="body2">{colorName}</Typography>
            </Box>
          );
        }
      },
      {
        headerName: '',
        field: 'actions',
        width: 60,
        editable: false,
        cellRenderer: (params: any) => {
          return (
            <IconButton
              size="small"
              color="error"
              onClick={() => deleteTask(params.data.id)}
              sx={{ py: 0.5 }}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          );
        }
      }
    ] as ColDef[];
  }, [deleteTask]);

  // Define column definitions for Right Timeline Grid (60%)
  const rightColumnDefs = useMemo<ColDef[]>(() => {
    return weeks.map((week) => ({
      headerName: `${week.label}\n${dayjs(week.fridayDate).format('DD MMM')}`,
      headerClass: 'multiline-header-cell',
      field: `week_${week.fridayDate}`,
      width: 90,
      resizable: true,
      sortable: false,
      editable: false,
      cellRenderer: (params: any) => {
        const task = params.data as Task;
        const allocation = task.weekAssignments?.[week.fridayDate] || 0;
        if (allocation <= 0) return null;

        const startD = dayjs(task.calculatedStartDate);
        const finishD = dayjs(task.calculatedFinishDate);
        const weekFri = dayjs(week.fridayDate);

        // Find active working days of the week (Monday=0 to Friday=4)
        let firstActiveIdx = -1;
        let lastActiveIdx = -1;

        for (let d = 0; d < 5; d++) {
          const dayDate = weekFri.subtract(4 - d, 'day');
          const isActive = (dayDate.isAfter(startD, 'day') || dayDate.isSame(startD, 'day')) &&
            (dayDate.isBefore(finishD, 'day') || dayDate.isSame(finishD, 'day'));
          if (isActive) {
            if (firstActiveIdx === -1) firstActiveIdx = d;
            lastActiveIdx = d;
          }
        }

        if (firstActiveIdx === -1) return null;

        const pctStart = firstActiveIdx * 20;
        const pctEnd = (lastActiveIdx + 1) * 20;

        // Contrast calculation for text color
        const color = task.color || '#2196F3';
        const r = parseInt(color.substring(1, 3), 16) || 0;
        const g = parseInt(color.substring(3, 5), 16) || 0;
        const b = parseInt(color.substring(5, 7), 16) || 0;
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        const textColor = luminance > 0.6 ? '#000000' : '#ffffff';

        return (
          <Box sx={{ position: 'relative', width: '100%', height: '100%', display: 'flex', alignItems: 'center' }}>
            <Box
              sx={{
                position: 'absolute',
                left: `${pctStart}%`,
                width: `${pctEnd - pctStart}%`,
                height: '24px',
                bgcolor: color,
                color: textColor,
                fontWeight: 'bold',
                fontSize: '11px',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis',
                px: 0.5
              }}
            >
              {task.fte} FTE
            </Box>
          </Box>
        );
      }
    }));
  }, [weeks]);

  // Inject multiline header and vertical scroll hiding CSS
  useEffect(() => {
    const styleId = 'ag-grid-split-scrolling';
    let styleEl = document.getElementById(styleId);
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = styleId;
      styleEl.innerHTML = `
        .multiline-header-cell .ag-header-cell-label {
          white-space: pre-line !important;
          text-align: center !important;
          line-height: 1.3 !important;
          justify-content: center !important;
        }
        .multiline-header-cell {
          text-align: center !important;
        }
        /* Hide vertical scrollbar of grid-1 to keep it clean */
        #grid-1 .ag-body-viewport {
          overflow-y: hidden !important;
        }
      `;
      document.head.appendChild(styleEl);
    }
    return () => {
      styleEl?.remove();
    };
  }, []);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: 'background.default', width: '100vw', overflow: 'hidden' }}>
      {/* 1. Header Toolbar (Full screen width) */}
      <Box sx={{ borderBottom: '1px solid #e2e8f0', bgcolor: 'background.paper', px: 3, py: 1.5 }}>
        <Box sx={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 2 }}>
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/')}
              variant="outlined"
              size="small"
            >
              Dashboard
            </Button>
            <Typography variant="h6" color="text.primary" sx={{ fontWeight: '800' }}>
              Planner Workspace
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'row', gap: 1.5 }}>
            <input
              type="file"
              accept=".json"
              style={{ display: 'none' }}
              ref={fileInputRef}
              onChange={handleOpenJSON}
            />
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel id="timeline-duration-label" sx={{ fontSize: '0.85rem', top: -1 }}>Timeline Range</InputLabel>
              <Select
                labelId="timeline-duration-label"
                id="timeline-duration"
                value={minWeeksToShow}
                label="Timeline Range"
                onChange={(e) => setMinWeeksToShow(Number(e.target.value))}
                sx={{ height: 34, fontSize: '0.85rem' }}
              >
                <MenuItem value={13}>13 Weeks (~3 Months)</MenuItem>
                <MenuItem value={26}>26 Weeks (~6 Months)</MenuItem>
                <MenuItem value={52}>52 Weeks (1 Year)</MenuItem>
                <MenuItem value={104}>104 Weeks (2 Years)</MenuItem>
                <MenuItem value={156}>156 Weeks (3 Years)</MenuItem>
              </Select>
            </FormControl>
            <Button
              variant="outlined"
              startIcon={<UploadFileIcon />}
              size="small"
              onClick={() => fileInputRef.current?.click()}
            >
              Open JSON
            </Button>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Button
                variant="outlined"
                color="warning"
                startIcon={<SaveIcon />}
                size="small"
                onClick={() => handleSaveDraft(false)}
                sx={{ height: 34 }}
              >
                Save Draft
              </Button>
              {lastDraftSavedTime && (
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '9px', mt: 0.25, lineHeight: 1 }}>
                  Saved: {lastDraftSavedTime}
                </Typography>
              )}
            </Box>
            <Button
              variant="outlined"
              startIcon={<SaveIcon />}
              size="small"
              onClick={handleOpenSaveDialog}
            >
              Save Plan
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<DownloadIcon />}
              size="small"
              onClick={handleExportExcel}
            >
              Export Excel
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Main Workspace Body */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 3, gap: 2 }}>
        {/* 2. Project Details Banner (Compact, full width) */}
        <Card sx={{ boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            <Box sx={{ display: 'flex', flexDirection: 'row', gap: 3, alignItems: 'center' }}>
              <TextField
                label="Project Name"
                value={project.name}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="Enter project name..."
                size="small"
                sx={{ flex: 1 }}
              />
              <TextField
                label="Customer"
                value={project.customer}
                onChange={(e) => setCustomer(e.target.value)}
                placeholder="Enter customer name..."
                size="small"
                sx={{ flex: 1 }}
              />
              <TextField
                label="Tentative Start Date"
                type="date"
                value={project.suggestedStartDate}
                onChange={(e) => setStartDate(e.target.value)}
                slotProps={{ inputLabel: { shrink: true } }}
                size="small"
                sx={{ width: 180 }}
              />
            </Box>
          </CardContent>
        </Card>

        {/* 3. Split Screen task list and timeline */}
        <Card sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 2, overflow: 'hidden' }}>
          {/* Section Toolbar */}
          <Box sx={{ display: 'flex', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: '700', color: 'text.primary' }}>
              Schedule Workspace
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'row', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                size="small"
                onClick={() => recalculate()}
              >
                Force Recalculate
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                size="small"
                onClick={addTask}
              >
                Add Task
              </Button>
            </Box>
          </Box>

          {/* Grids Split Layout (40/60) */}
          <Box sx={{ display: 'flex', flexDirection: 'row', flexGrow: 1, overflow: 'hidden', gap: 2 }}>

            {/* Left Grid: Task Metadata (40%) */}
            <Box
              id="grid-1"
              className="ag-theme-quartz"
              sx={{
                flex: '0 0 40%',
                height: '100%',
                borderRight: '2px solid #e2e8f0'
              }}
            >
              <AgGridReact
                rowData={tasks}
                columnDefs={leftColumnDefs}
                readOnlyEdit={true}
                onCellEditRequest={onCellEditRequest}
                onGridReady={onGrid1Ready}
                onBodyScroll={onBodyScroll1}
                animateRows={true}
                headerHeight={48}
                rowHeight={38}
                suppressDragLeaveHidesColumns={true}
              />
            </Box>

            {/* Right Grid: Gantt Weekly Timeline (60%) */}
            <Box
              id="grid-2"
              className="ag-theme-quartz"
              sx={{
                flex: '0 0 60%',
                height: '100%'
              }}
            >
              <AgGridReact
                rowData={tasks}
                columnDefs={rightColumnDefs}
                onGridReady={onGrid2Ready}
                onBodyScroll={onBodyScroll2}
                animateRows={true}
                headerHeight={48}
                rowHeight={38}
                suppressDragLeaveHidesColumns={true}
              />
            </Box>
          </Box>
        </Card>
      </Box>

      {/* 4. Save Plan Dialog */}
      <Dialog open={saveDialogOpen} onClose={() => setSaveDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: '800' }}>Save Project Plan</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Define a unique name to identify this plan. You can either save it in your browser storage or download it as a `.json` backup file.
          </Typography>
          <TextField
            label="Plan / File Name"
            value={customPlanName}
            onChange={(e) => setCustomPlanName(e.target.value)}
            fullWidth
            autoFocus
            size="small"
          />
        </DialogContent>
        <DialogActions sx={{ p: 3, gap: 1 }}>
          <Button onClick={() => setSaveDialogOpen(false)} variant="outlined">
            Cancel
          </Button>
          <Button onClick={handleSaveJSON} variant="contained" color="secondary" startIcon={<DownloadIcon />}>
            Download JSON
          </Button>
          <Button onClick={handleSaveToBrowser} variant="contained" color="primary" startIcon={<SaveIcon />}>
            Save to Browser
          </Button>
        </DialogActions>
      </Dialog>

      {/* 5. Notifications Toast */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={4000}
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbarSeverity} onClose={() => setSnackbarOpen(false)} sx={{ width: '100%' }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}
