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
  InputLabel,
  Slide,
  Chip,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails
} from '@mui/material';
import type { TransitionProps } from '@mui/material/transitions';
import {
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Save as SaveIcon,
  UploadFile as UploadFileIcon,
  Refresh as RefreshIcon,
  ListAlt as ListAltIcon,
  Close as CloseIcon,
  Description as DescriptionIcon,
  Settings as SettingsIcon,
  ExpandMore as ExpandMoreIcon
} from '@mui/icons-material';

import { useProjectStore } from '../../state/projectStore';
import { useTaskStore } from '../../state/taskStore';
import { exportProjectToExcel } from '../../engines/ExportEngine';
import { storage } from '../../services/storage';
import type { Task } from '../../models/Task';
import { sowApi } from '../../services/api/sowApi';
import type { SoWGenerationResponse } from '../../services/api/sowApi';
import { SoWModal } from '../../components/SoWModal';
import { exportSoWToWord } from '../../utils/wordExport';
import { saveSoWDraft, loadSoWDraft } from '../../utils/sowStorage';
import type { SoWDraft } from '../../utils/sowStorage';

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

// Smooth slide-up transition for dialogs
const SlideTransition = React.forwardRef(function Transition(
  props: TransitionProps & { children: React.ReactElement },
  ref: React.Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />;
});

export function Planner() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Project store hooks
  const project = useProjectStore((s) => s.project);
  const setProjectName = useProjectStore((s) => s.setProjectName);
  const setCustomer = useProjectStore((s) => s.setCustomer);
  const setStartDate = useProjectStore((s) => s.setStartDate);
  const setBackground = useProjectStore((s) => s.setBackground);
  const setAssumptions = useProjectStore((s) => s.setAssumptions);
  const setOutOfScope = useProjectStore((s) => s.setOutOfScope);
  const setMawDeliverables = useProjectStore((s) => s.setMawDeliverables);
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
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'info' | 'error' | 'warning'>('success');
  const [lastDraftSavedTime, setLastDraftSavedTime] = useState<string | null>(null);
  const [timelineMode, setTimelineMode] = useState<'weekly' | 'weekday'>('weekly');

  // Sub-Activities Modal state
  const [subActDialogOpen, setSubActDialogOpen] = useState(false);
  const [subActTaskId, setSubActTaskId] = useState<string | null>(null);
  const [subActTaskName, setSubActTaskName] = useState('');
  const [subActItems, setSubActItems] = useState<string[]>([]);

  // SoW Generation Modal state
  const [sowModalOpen, setSowModalOpen] = useState(false);
  const [sowLoading, setSowLoading] = useState(false);
  const [sowContent, setSowContent] = useState('');
  const [sowError, setSowError] = useState<string | undefined>(undefined);
  const [sowNeedsMoreInfo, setSowNeedsMoreInfo] = useState(false);
  const [sowQuestions, setSowQuestions] = useState<string[]>([]);

  // Accordion expansion state
  const [expandedAccordions, setExpandedAccordions] = useState<{
    details: boolean;
    background: boolean;
    assumptions: boolean;
    maw: boolean;
  }>({
    details: true,
    background: false,
    assumptions: false,
    maw: false
  });

  const handleAccordionChange = (panel: keyof typeof expandedAccordions) => (
    _event: React.SyntheticEvent,
    isExpanded: boolean
  ) => {
    setExpandedAccordions(prev => ({ ...prev, [panel]: isExpanded }));
  };

  // Load existing SoW draft when project name changes
  useEffect(() => {
    const loadExistingSoW = async () => {
      if (project.name) {
        const existingDraft = await loadSoWDraft(project.name);
        if (existingDraft && existingDraft.sow_content) {
          setSowContent(existingDraft.sow_content);
          console.log('✓ Loaded existing SoW draft for:', project.name);
        } else {
          // Clear content if no draft exists
          setSowContent('');
        }
      }
    };
    
    loadExistingSoW();
  }, [project.name]);

  const handleOpenSubActivities = (task: Task) => {
    setSubActTaskId(task.id);
    setSubActTaskName(task.activity);
    // Start with existing sub-activities or 5 empty slots
    const existing = task.subActivities || [];
    const items = [...existing];
    while (items.length < 5) items.push('');
    setSubActItems(items);
    setSubActDialogOpen(true);
  };

  const handleSaveSubActivities = () => {
    if (subActTaskId) {
      // Filter out empty strings for storage, but keep non-empty ones
      const cleaned = subActItems.filter(s => s.trim() !== '');
      updateTask(subActTaskId, { subActivities: cleaned.length > 0 ? cleaned : undefined });
      setSnackbarSeverity('success');
      setSnackbarMessage(`Sub-activities saved for "${subActTaskName}"`);
      setSnackbarOpen(true);
    }
    setSubActDialogOpen(false);
  };

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
    const currentProj = latestDataRef.current.project;
    const currentTasks = latestDataRef.current.tasks;
    
    // Skip saving if project name is empty or default
    if (!currentProj.name || currentProj.name.trim() === '' || currentProj.name === 'New Project Schedule') {
      if (!isAutoSave) {
        setSnackbarSeverity('warning');
        setSnackbarMessage('Please enter a unique project name before saving.');
        setSnackbarOpen(true);
      }
      return;
    }
    
    const cleanProjectName = currentProj.name.trim().replace(/[^a-zA-Z0-9-_]/g, '_');
    const filename = `${cleanProjectName}_draft.json`;

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
      await exportProjectToExcel(project, tasks, weeks, project.background, project.assumptions, project.outOfScope, project.mawDeliverables);
      setSnackbarSeverity('success');
      setSnackbarMessage('Excel sheet generated successfully!');
      setSnackbarOpen(true);
    } catch (err) {
      alert('Failed to export Excel file.');
      console.error(err);
    }
  };

  // SoW Generation handlers
  const handleGenerateSoW = async () => {
    // If SoW already exists, just open the modal to view it
    if (sowContent) {
      setSowModalOpen(true);
      return;
    }

    // Validate project name before generating SoW
    if (!project.name || project.name.trim() === '' || project.name === 'New Project Schedule') {
      setSnackbarSeverity('warning');
      setSnackbarMessage('Please enter a unique project name before generating the SoW.');
      setSnackbarOpen(true);
      return;
    }

    // Validate customer before generating SoW
    if (!project.customer || project.customer.trim() === '' || project.customer === 'Acme Corp') {
      setSnackbarSeverity('warning');
      setSnackbarMessage('Please enter a customer name before generating the SoW.');
      setSnackbarOpen(true);
      return;
    }

    // Otherwise, generate new SoW
    setSowModalOpen(true);
    setSowLoading(true);
    setSowError(undefined);
    setSowContent('');
    setSowNeedsMoreInfo(false);
    setSowQuestions([]);

    try {
      const response: SoWGenerationResponse = await sowApi.generateSoW({
        project_name: project.name,
        customer: project.customer,
        background: project.background,
        assumptions: project.assumptions,
        out_of_scope: project.outOfScope,
        maw_deliverables: project.mawDeliverables,
      });

      if (response.success && response.sow_content) {
        setSowContent(response.sow_content);
        
        // Save to JSON file in drafts folder
        const draft: SoWDraft = {
          project_name: project.name,
          customer: project.customer,
          background: project.background || '',
          assumptions: project.assumptions,
          out_of_scope: project.outOfScope,
          maw_deliverables: project.mawDeliverables,
          sow_content: response.sow_content,
          timestamp: response.timestamp,
          version: '1.0'
        };
        await saveSoWDraft(draft);
        
        setSnackbarSeverity('success');
        setSnackbarMessage('SoW generated and saved to drafts/');
        setSnackbarOpen(true);
      } else if (response.needs_more_info && response.questions) {
        setSowNeedsMoreInfo(true);
        setSowQuestions(response.questions);
      } else if (response.error) {
        setSowError(response.error);
      }
    } catch (error) {
      console.error('SoW generation error:', error);
      setSowError('Failed to generate Statement of Work. Please check your backend connection.');
    } finally {
      setSowLoading(false);
    }
  };

  const handleRegenerateSoW = async () => {
    // Validate project name before regenerating SoW
    if (!project.name || project.name.trim() === '' || project.name === 'New Project Schedule') {
      setSnackbarSeverity('warning');
      setSnackbarMessage('Please enter a unique project name before regenerating the SoW.');
      setSnackbarOpen(true);
      return;
    }

    // Validate customer before regenerating SoW
    if (!project.customer || project.customer.trim() === '' || project.customer === 'Acme Corp') {
      setSnackbarSeverity('warning');
      setSnackbarMessage('Please enter a customer name before regenerating the SoW.');
      setSnackbarOpen(true);
      return;
    }

    setSowLoading(true);
    setSowError(undefined);
    setSowContent('');
    setSowNeedsMoreInfo(false);
    setSowQuestions([]);

    try {
      const response: SoWGenerationResponse = await sowApi.generateSoW({
        project_name: project.name,
        customer: project.customer,
        background: project.background,
        assumptions: project.assumptions,
        out_of_scope: project.outOfScope,
        maw_deliverables: project.mawDeliverables,
      });

      if (response.success && response.sow_content) {
        setSowContent(response.sow_content);
        
        // Save to JSON file in drafts folder
        const draft: SoWDraft = {
          project_name: project.name,
          customer: project.customer,
          background: project.background || '',
          assumptions: project.assumptions,
          out_of_scope: project.outOfScope,
          maw_deliverables: project.mawDeliverables,
          sow_content: response.sow_content,
          timestamp: response.timestamp,
          version: '1.0'
        };
        await saveSoWDraft(draft);
        
        setSnackbarSeverity('success');
        setSnackbarMessage('SoW regenerated and saved to drafts/');
        setSnackbarOpen(true);
      } else if (response.needs_more_info && response.questions) {
        setSowNeedsMoreInfo(true);
        setSowQuestions(response.questions);
      } else if (response.error) {
        setSowError(response.error);
      }
    } catch (error) {
      console.error('SoW regeneration error:', error);
      setSowError('Failed to regenerate Statement of Work. Please check your backend connection.');
    } finally {
      setSowLoading(false);
    }
  };

  const handleRegenerateWithMoreInfo = async (additionalInfo: string) => {
    setSowLoading(true);
    setSowError(undefined);
    setSowNeedsMoreInfo(false);

    try {
      // Append additional info to background
      const updatedBackground = project.background
        ? `${project.background}\n\nAdditional Information:\n${additionalInfo}`
        : additionalInfo;

      const response: SoWGenerationResponse = await sowApi.generateSoW({
        project_name: project.name,
        customer: project.customer,
        background: updatedBackground,
        assumptions: project.assumptions,
        out_of_scope: project.outOfScope,
        maw_deliverables: project.mawDeliverables,
      });

      if (response.success && response.sow_content) {
        setSowContent(response.sow_content);
        
        // Save to JSON file
        const draft: SoWDraft = {
          project_name: project.name,
          customer: project.customer,
          background: updatedBackground,
          assumptions: project.assumptions,
          out_of_scope: project.outOfScope,
          maw_deliverables: project.mawDeliverables,
          sow_content: response.sow_content,
          timestamp: response.timestamp,
          version: '1.0'
        };
        await saveSoWDraft(draft);
        
        setSnackbarSeverity('success');
        setSnackbarMessage('SoW generated with additional information!');
        setSnackbarOpen(true);
      } else if (response.error) {
        setSowError(response.error);
      }
    } catch (error) {
      console.error('SoW regeneration error:', error);
      setSowError('Failed to regenerate Statement of Work.');
    } finally {
      setSowLoading(false);
    }
  };

  const handleExportSoWToWord = async (content: string) => {
    try {
      await exportSoWToWord(content, project.name);
      setSnackbarSeverity('success');
      setSnackbarMessage('Statement of Work exported to Word successfully!');
      setSnackbarOpen(true);
    } catch (error) {
      console.error('Word export error:', error);
      setSnackbarSeverity('error');
      setSnackbarMessage('Failed to export to Word. Please try again.');
      setSnackbarOpen(true);
    }
  };

  // Grid Cell edit request listener (Zustand state is immutable, so readOnlyEdit must be true)
  const onCellEditRequest = (event: any) => {
    const { data, colDef, newValue } = event;
    const field = colDef.field;
    if (!field) return;

    if (field === 'calculatedStartDate') {
      let manualStartDate: string | undefined = undefined;
      const strVal = String(newValue || '').trim();
      if (strVal !== '') {
        const parsed = dayjs(strVal);
        if (parsed.isValid()) {
          manualStartDate = parsed.format('YYYY-MM-DD');
        }
      }
      updateTask(data.id, { manualStartDate });
    } else {
      // Propagate updates to store
      updateTask(data.id, { [field]: newValue });
    }
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
        headerName: '',
        field: 'subActivitiesCol',
        width: 45,
        editable: false,
        sortable: false,
        cellStyle: { textAlign: 'center' },
        cellRenderer: (params: any) => {
          const task = params.data as Task;
          const hasSubActs = task.subActivities && task.subActivities.length > 0;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <IconButton
                size="small"
                color={hasSubActs ? 'primary' : 'default'}
                onClick={() => handleOpenSubActivities(task)}
                sx={{ py: 0.5, position: 'relative' }}
                title="Manage Sub-Activities"
              >
                <ListAltIcon fontSize="small" />
                {hasSubActs && (
                  <Box sx={{
                    position: 'absolute', top: 2, right: 2,
                    bgcolor: '#4285F4', color: '#fff',
                    borderRadius: '50%', width: 14, height: 14,
                    fontSize: '9px', fontWeight: 'bold',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {task.subActivities!.length}
                  </Box>
                )}
              </IconButton>
            </Box>
          );
        }
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
        width: 130,
        editable: true,
        cellEditor: 'agDateCellEditor',
        cellStyle: (params: any) => {
          const hasManual = !!params.data?.manualStartDate;
          return {
            textAlign: 'center',
            color: hasManual ? '#1d4ed8' : '#1e293b',
            fontWeight: hasManual ? '600' : 'normal',
            backgroundColor: hasManual ? '#eff6ff' : 'transparent'
          };
        }
      },
      {
        headerName: 'Calc. Finish',
        field: 'calculatedFinishDate',
        width: 115,
        editable: false,
        cellStyle: { textAlign: 'center', color: '#64748b' }
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
    if (timelineMode === 'weekday') {
      // Generate individual weekday columns from project start
      const startDate = dayjs(project.suggestedStartDate || new Date().toISOString().split('T')[0]);
      const daysToShow = minWeeksToShow * 5; // Convert weeks to weekdays
      const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
      const columns: ColDef[] = [];
      let currentDate = startDate;
      let dayCount = 0;

      while (dayCount < daysToShow) {
        const dow = currentDate.day(); // 0=Sun, 6=Sat
        if (dow !== 0 && dow !== 6) {
          const dateStr = currentDate.format('YYYY-MM-DD');
          const dayLabel = dayNames[dow - 1];
          // Show month only on Mondays or 1st of month to keep columns compact
          const dateLabel = (dow === 1 || currentDate.date() === 1)
            ? currentDate.format('DD MMM')
            : currentDate.format('DD');
          const capturedDate = dateStr;

          columns.push({
            headerName: `${dayLabel}\n${dateLabel}`,
            headerClass: 'multiline-header-cell',
            field: `day_${capturedDate}`,
            width: 80,
            resizable: true,
            sortable: false,
            editable: false,
            cellRenderer: (params: any) => {
              const task = params.data as Task;
              const taskStart = task.calculatedStartDate;
              const taskFinish = task.calculatedFinishDate;
              if (!taskStart || !taskFinish) return null;

              const cellDate = dayjs(capturedDate);
              const isActive = (cellDate.isAfter(dayjs(taskStart), 'day') || cellDate.isSame(dayjs(taskStart), 'day')) &&
                (cellDate.isBefore(dayjs(taskFinish), 'day') || cellDate.isSame(dayjs(taskFinish), 'day'));

              if (!isActive) return null;

              const color = task.color || '#2196F3';
              const r = parseInt(color.substring(1, 3), 16) || 0;
              const g = parseInt(color.substring(3, 5), 16) || 0;
              const b = parseInt(color.substring(5, 7), 16) || 0;
              const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
              const textColor = luminance > 0.6 ? '#000000' : '#ffffff';

              return (
                <Box sx={{
                  width: '100%',
                  height: '24px',
                  bgcolor: color,
                  color: textColor,
                  fontWeight: 'bold',
                  fontSize: '9px',
                  borderRadius: '3px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                  mt: '4px'
                }}>
                  ●
                </Box>
              );
            }
          });
          dayCount++;
        }
        currentDate = currentDate.add(1, 'day');
      }
      return columns;
    }

    // Weekly mode (default)
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
        const activeDays: boolean[] = [false, false, false, false, false];
        let activeDayCount = 0;

        for (let d = 0; d < 5; d++) {
          const dayDate = weekFri.subtract(4 - d, 'day');
          const isActive = (dayDate.isAfter(startD, 'day') || dayDate.isSame(startD, 'day')) &&
            (dayDate.isBefore(finishD, 'day') || dayDate.isSame(finishD, 'day'));
          if (isActive) {
            activeDays[d] = true;
            activeDayCount++;
          }
        }

        if (activeDayCount === 0) return null;

        const color = task.color || '#2196F3';

        return (
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            height: '100%',
            gap: '2px'
          }}>
            {activeDays.map((isActive, index) => (
              <Box
                key={index}
                sx={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '2px',
                  backgroundColor: isActive ? color : 'transparent',
                  border: isActive ? 'none' : '1px solid #e0e0e0',
                  boxShadow: isActive ? '0 1px 2px rgba(0,0,0,0.15)' : 'none',
                  transition: 'all 0.2s ease'
                }}
              />
            ))}
          </Box>
        );
      }
    }));
  }, [weeks, timelineMode, project.suggestedStartDate, minWeeksToShow]);

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
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel id="timeline-mode-label" sx={{ fontSize: '0.85rem', top: -1 }}>Timeline Mode</InputLabel>
              <Select
                labelId="timeline-mode-label"
                id="timeline-mode"
                value={timelineMode}
                label="Timeline Mode"
                onChange={(e) => {
                  const mode = e.target.value as 'weekly' | 'weekday';
                  setTimelineMode(mode);
                  // Set sensible defaults when switching
                  if (mode === 'weekday') {
                    setMinWeeksToShow(9); // ~2 months of weekdays
                  } else {
                    setMinWeeksToShow(52); // 1 year of weeks
                  }
                }}
                sx={{ height: 34, fontSize: '0.85rem' }}
              >
                <MenuItem value="weekly">Weekly</MenuItem>
                <MenuItem value="weekday">Weekday</MenuItem>
              </Select>
            </FormControl>
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
                {timelineMode === 'weekday' ? [
                  <MenuItem key={9} value={9}>~2 Months (45 Days)</MenuItem>,
                  <MenuItem key={13} value={13}>~3 Months (65 Days)</MenuItem>,
                  <MenuItem key={22} value={22}>~5 Months (110 Days)</MenuItem>,
                  <MenuItem key={26} value={26}>~6 Months (130 Days)</MenuItem>,
                  <MenuItem key={52} value={52}>~1 Year (260 Days)</MenuItem>
                ] : [
                  <MenuItem key={13} value={13}>13 Weeks (~3 Months)</MenuItem>,
                  <MenuItem key={26} value={26}>26 Weeks (~6 Months)</MenuItem>,
                  <MenuItem key={52} value={52}>52 Weeks (1 Year)</MenuItem>,
                  <MenuItem key={104} value={104}>104 Weeks (2 Years)</MenuItem>,
                  <MenuItem key={156} value={156}>156 Weeks (3 Years)</MenuItem>
                ]}
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
              variant="outlined"
              startIcon={<DescriptionIcon />}
              size="small"
              onClick={handleGenerateSoW}
              color="secondary"
            >
              {sowContent ? 'View SoW Draft' : 'SoW Draft'}
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
            <Button
              variant="outlined"
              startIcon={<SettingsIcon />}
              size="small"
              onClick={() => navigate('/settings')}
            >
              Settings
            </Button>
          </Box>
        </Box>
      </Box>

      {/* Main Workspace Body */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', p: 3, gap: 2 }}>
        {/* 2. Project Details Banner (Compact, full width) */}
        <Accordion 
          expanded={expandedAccordions.details} 
          onChange={handleAccordionChange('details')}
          sx={{ boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" sx={{ fontWeight: '600' }}>
              Project Details
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
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
          </AccordionDetails>
        </Accordion>

        {/* Project Background Card */}
        <Accordion 
          expanded={expandedAccordions.background} 
          onChange={handleAccordionChange('background')}
          sx={{ boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" sx={{ fontWeight: '600' }}>
              Project Background
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TextField
              label="Project Background"
              value={project.background || ''}
              onChange={(e) => setBackground(e.target.value)}
              placeholder="Enter project background, context, objectives, or business case here. This will be exported to a separate 'Background' worksheet in Excel."
              multiline
              minRows={3}
              maxRows={8}
              fullWidth
              size="small"
              sx={{ '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
            />
          </AccordionDetails>
        </Accordion>

        {/* Assumptions & Out of Scope Card */}
        <Accordion 
          expanded={expandedAccordions.assumptions} 
          onChange={handleAccordionChange('assumptions')}
          sx={{ boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" sx={{ fontWeight: '600' }}>
              Assumptions & Out of Scope
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
              <TextField
                label="Assumptions & Notes"
                value={project.assumptions || ''}
                onChange={(e) => setAssumptions(e.target.value)}
                placeholder="Enter project assumptions, constraints, or notes here. These will be exported below the schedule in Excel."
                multiline
                minRows={2}
                maxRows={6}
                fullWidth
                size="small"
                sx={{ flex: 1, '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
              />
              <TextField
                label="Out of Scope & Exclusions"
                value={project.outOfScope || ''}
                onChange={(e) => setOutOfScope(e.target.value)}
                placeholder="Enter out of scope items, exclusions, or boundaries here. These will be exported below the schedule in Excel."
                multiline
                minRows={2}
                maxRows={6}
                fullWidth
                size="small"
                sx={{ flex: 1, '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
              />
            </Box>
          </AccordionDetails>
        </Accordion>

        {/* MAW Deliverables Card */}
        <Accordion 
          expanded={expandedAccordions.maw} 
          onChange={handleAccordionChange('maw')}
          sx={{ boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" sx={{ fontWeight: '600' }}>
              MAW Deliverables
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TextField
              label="MAW Deliverables"
              value={project.mawDeliverables || ''}
              onChange={(e) => setMawDeliverables(e.target.value)}
              placeholder="Enter MAW deliverables for this project. These will be exported to a separate Excel sheet."
              multiline
              minRows={3}
              maxRows={8}
              fullWidth
              size="small"
              sx={{ '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
            />
          </AccordionDetails>
        </Accordion>

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
                headerHeight={56}
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

      {/* 5. Sub-Activities Modal Dialog */}
      <Dialog
        open={subActDialogOpen}
        onClose={() => setSubActDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        slots={{ transition: SlideTransition }}
        slotProps={{
          transition: { timeout: { enter: 350, exit: 250 } },
          paper: {
            sx: {
              borderRadius: 3,
              boxShadow: '0 24px 48px rgba(0,0,0,0.2)',
              overflow: 'hidden'
            }
          }
        }}
      >
        <DialogTitle sx={{
          fontWeight: '800',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: '#f8f9fa',
          borderBottom: '1px solid #e2e8f0',
          py: 1.5
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <ListAltIcon sx={{ color: '#4285F4' }} />
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 800, lineHeight: 1.2 }}>
                Sub-Activities
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {subActTaskName}
              </Typography>
            </Box>
          </Box>
          <IconButton size="small" onClick={() => setSubActDialogOpen(false)}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ pt: 2, pb: 1 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Add detailed activities under this task. These will appear as sub-items in the exported Excel file.
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {subActItems.map((item, idx) => (
              <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  label={idx + 1}
                  size="small"
                  sx={{
                    minWidth: 28, height: 24,
                    fontWeight: 'bold',
                    fontSize: '11px',
                    bgcolor: '#e8f0fe',
                    color: '#1a73e8'
                  }}
                />
                <TextField
                  value={item}
                  onChange={(e) => {
                    const updated = [...subActItems];
                    updated[idx] = e.target.value;
                    setSubActItems(updated);
                  }}
                  placeholder={`Activity ${idx + 1}`}
                  size="small"
                  fullWidth
                  sx={{ '& .MuiInputBase-root': { fontSize: '0.875rem' } }}
                />
                {subActItems.length > 1 && (
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => {
                      const updated = subActItems.filter((_, i) => i !== idx);
                      setSubActItems(updated);
                    }}
                    sx={{ p: 0.5 }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            ))}
          </Box>
          <Button
            variant="text"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setSubActItems([...subActItems, ''])}
            sx={{ mt: 1.5, textTransform: 'none', fontWeight: 600 }}
          >
            Add Activity
          </Button>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ p: 2, gap: 1 }}>
          <Button
            onClick={() => setSubActDialogOpen(false)}
            variant="outlined"
            size="small"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSaveSubActivities}
            variant="contained"
            color="primary"
            size="small"
            startIcon={<SaveIcon />}
          >
            Save Activities
          </Button>
        </DialogActions>
      </Dialog>

      {/* 6. SoW Generation Modal */}
      <SoWModal
        open={sowModalOpen}
        onClose={() => setSowModalOpen(false)}
        sowContent={sowContent}
        loading={sowLoading}
        error={sowError}
        needsMoreInfo={sowNeedsMoreInfo}
        questions={sowQuestions}
        onRegenerate={handleRegenerateSoW}
        onRegenerateWithMoreInfo={handleRegenerateWithMoreInfo}
        onExportToWord={handleExportSoWToWord}
      />

      {/* 7. Notifications Toast */}
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
