import React, { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton
} from '@mui/material';
import {
  Add as AddIcon,
  UploadFile as UploadFileIcon,
  Schedule as ScheduleIcon,
  Delete as DeleteIcon,
  FolderOpen as FolderOpenIcon,
  AccessTime as AccessTimeIcon
} from '@mui/icons-material';
import { useProjectStore } from '../../state/projectStore';
import { useTaskStore } from '../../state/taskStore';
import { storage } from '../../services/storage';

export function Dashboard() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resetProject = useProjectStore((s) => s.resetProject);
  const loadProject = useProjectStore((s) => s.loadProject);
  const setTasks = useTaskStore((s) => s.setTasks);

  interface DraftPlan {
    filename: string;
    name: string;
    customer: string;
    lastSaved: string;
  }

  const [savedPlans, setSavedPlans] = useState<any[]>([]);
  const [drafts, setDrafts] = useState<DraftPlan[]>([]);

  const fetchDrafts = async () => {
    try {
      const response = await fetch('/api/list-drafts');
      if (response.ok) {
        const data = await response.json();
        setDrafts(data);
      }
    } catch (e) {
      console.error('Failed to fetch drafts:', e);
    }
  };

  useEffect(() => {
    setSavedPlans(storage.getPlans());
    fetchDrafts();
  }, []);

  const handleOpenDraft = async (filename: string) => {
    try {
      const response = await fetch(`/api/load-draft?filename=${encodeURIComponent(filename)}`);
      if (response.ok) {
        const data = await response.json();
        if (data.project && Array.isArray(data.tasks)) {
          loadProject(data.project);
          setTasks(data.tasks);
          navigate('/planner');
        }
      } else {
        alert('Failed to load draft file.');
      }
    } catch (e) {
      console.error(e);
      alert('Error loading draft file.');
    }
  };

  const handleDeleteDraft = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this draft file?')) {
      try {
        const response = await fetch('/api/delete-draft', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ filename })
        });
        if (response.ok) {
          fetchDrafts();
        }
      } catch (e) {
        console.error(e);
      }
    }
  };

  const handleNewProject = () => {
    resetProject();
    navigate('/planner');
  };

  const handleUploadJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target?.result as string);
        if (data.project && Array.isArray(data.tasks)) {
          loadProject(data.project);
          setTasks(data.tasks);
          navigate('/planner');
        } else {
          alert('Invalid file format. Make sure it contains project and tasks data.');
        }
      } catch (err) {
        alert('Failed to parse project file.');
      }
    };
    reader.readAsText(file);
  };

  const handleOpenPlan = (id: string) => {
    const plan = storage.loadPlan(id);
    if (plan) {
      loadProject(plan.project);
      setTasks(plan.tasks);
      navigate('/planner');
    } else {
      alert('Plan data not found.');
    }
  };

  const handleDeletePlan = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this saved plan?')) {
      storage.deletePlan(id);
      setSavedPlans(storage.getPlans());
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(to bottom, #eff6ff, #f8fafc)',
        py: 8
      }}
    >
      <Container maxWidth="lg">
        {/* Welcome Section */}
        <Box sx={{ mb: 8, textAlign: 'center' }}>
          <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 1.5, mb: 2 }}>
            <Box
              sx={{
                width: 48,
                height: 48,
                borderRadius: '12px',
                background: 'linear-gradient(to right, #2563eb, #3b82f6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                boxShadow: '0 4px 10px rgba(37, 99, 235, 0.3)'
              }}
            >
              <ScheduleIcon />
            </Box>
            <Typography variant="h4" component="h1" color="primary.main" sx={{ fontWeight: '800' }}>
              Project Schedule Tool
            </Typography>
          </Box>
          <Typography variant="h3" component="h2" sx={{ mb: 2, fontWeight: '800' }}>
            Project Planning, Simplified.
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 800, mx: 'auto', fontWeight: 400 }}>
            Quickly create project schedule and then export them to the Microsoft Excel.
            <br />Use High level estimations (in man-days) to create detailed project schedule.

          </Typography>
        </Box>

        {/* Action Cards */}
        <Grid container spacing={4} sx={{ justifyContent: 'center', mb: 6 }}>
          <Grid size={{ xs: 12, sm: 6, md: 5 }}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                border: '1.5px solid rgba(66, 133, 244, 0.3)',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
                transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
                '&:hover': {
                  transform: 'translateY(-6px)',
                  borderColor: '#4285F4',
                  boxShadow: '0 20px 25px -5px rgba(66, 133, 244, 0.15), 0 0 0 1px rgba(66, 133, 244, 0.2)'
                }
              }}
            >
              <CardContent sx={{ p: 4, flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h5" gutterBottom sx={{ fontWeight: '700' }}>
                    Create New Plan
                  </Typography>
                  <Typography color="text.secondary" sx={{ mb: 4 }}>
                    Start fresh. Define tasks, hours, FTE allocations, and build your critical path timeline from scratch.
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<AddIcon />}
                  onClick={handleNewProject}
                  fullWidth
                >
                  Get Started
                </Button>
              </CardContent>
            </Card>
          </Grid>

          <Grid size={{ xs: 12, sm: 6, md: 5 }}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                border: '1.5px solid rgba(234, 67, 53, 0.3)',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
                transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
                '&:hover': {
                  transform: 'translateY(-6px)',
                  borderColor: '#EA4335',
                  boxShadow: '0 20px 25px -5px rgba(234, 67, 53, 0.15), 0 0 0 1px rgba(234, 67, 53, 0.2)'
                }
              }}
            >
              <CardContent sx={{ p: 4, flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h5" gutterBottom sx={{ fontWeight: '700' }}>
                    Open Existing Plan
                  </Typography>
                  <Typography color="text.secondary" sx={{ mb: 4 }}>
                    Upload a previously saved `.json` file to restore your schedule, tasks, and project configurations.
                  </Typography>
                </Box>
                <input
                  type="file"
                  accept=".json"
                  style={{ display: 'none' }}
                  ref={fileInputRef}
                  onChange={handleUploadJSON}
                />
                <Button
                  variant="outlined"
                  size="large"
                  startIcon={<UploadFileIcon />}
                  onClick={() => fileInputRef.current?.click()}
                  fullWidth
                >
                  Upload JSON
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Saved Plans List */}
        {savedPlans.length > 0 && (
          <Box sx={{ mb: 6 }}>
            <Typography variant="h5" sx={{ fontWeight: '800', mb: 3 }}>
              Saved Plans in Browser
            </Typography>
            <TableContainer
              component={Paper}
              sx={{
                borderRadius: 3,
                border: '1.5px solid rgba(52, 168, 83, 0.4)',
                boxShadow: 'none',
                transition: 'all 0.3s ease',
                '&:hover': {
                  borderColor: '#34A853',
                  boxShadow: '0 12px 20px -10px rgba(52, 168, 83, 0.1)'
                }
              }}
            >
              <Table>
                <TableHead sx={{ bgcolor: '#f1f5f9' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: '700' }}>Project Name</TableCell>
                    <TableCell sx={{ fontWeight: '700' }}>Customer</TableCell>
                    <TableCell sx={{ fontWeight: '700' }}>Last Saved</TableCell>
                    <TableCell align="right" sx={{ fontWeight: '700', pr: 4 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {savedPlans.map((plan) => (
                    <TableRow
                      key={plan.id}
                      hover
                      onClick={() => handleOpenPlan(plan.id)}
                      sx={{ cursor: 'pointer', '&:last-child td, &:last-child th': { border: 0 } }}
                    >
                      <TableCell sx={{ fontWeight: '600', color: 'primary.main' }}>
                        {plan.name}
                      </TableCell>
                      <TableCell>{plan.customer}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', flexDirection: 'row', gap: 1, alignItems: 'center' }}>
                          <AccessTimeIcon fontSize="inherit" color="action" />
                          <Typography variant="body2">
                            {new Date(plan.lastSaved).toLocaleString()}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right" sx={{ pr: 3 }}>
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<FolderOpenIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenPlan(plan.id);
                          }}
                          sx={{ mr: 1 }}
                        >
                          Open
                        </Button>
                        <IconButton
                          color="error"
                          size="small"
                          onClick={(e) => handleDeletePlan(plan.id, e)}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* In-Progress Drafts List */}
        {drafts.length > 0 && (
          <Box sx={{ mb: 6 }}>
            <Typography variant="h5" sx={{ fontWeight: '800', mb: 3 }}>
              In-Progress Drafts (in local drafts/ folder)
            </Typography>
            <TableContainer
              component={Paper}
              sx={{
                borderRadius: 3,
                border: '1.5px solid rgba(251, 188, 5, 0.4)', // Google Yellow border
                boxShadow: 'none',
                transition: 'all 0.3s ease',
                '&:hover': {
                  borderColor: '#FBBC05',
                  boxShadow: '0 12px 20px -10px rgba(251, 188, 5, 0.15)'
                }
              }}
            >
              <Table>
                <TableHead sx={{ bgcolor: '#fffbeb' }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: '700' }}>Project Name</TableCell>
                    <TableCell sx={{ fontWeight: '700' }}>Customer</TableCell>
                    <TableCell sx={{ fontWeight: '700' }}>Last Saved</TableCell>
                    <TableCell align="right" sx={{ fontWeight: '700', pr: 4 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {drafts.map((draft) => (
                    <TableRow
                      key={draft.filename}
                      hover
                      onClick={() => handleOpenDraft(draft.filename)}
                      sx={{ cursor: 'pointer', '&:last-child td, &:last-child th': { border: 0 } }}
                    >
                      <TableCell sx={{ fontWeight: '600', color: 'warning.main' }}>
                        {draft.name}
                      </TableCell>
                      <TableCell>{draft.customer}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', flexDirection: 'row', gap: 1, alignItems: 'center' }}>
                          <AccessTimeIcon fontSize="inherit" color="action" />
                          <Typography variant="body2">
                            {new Date(draft.lastSaved).toLocaleString()}
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right" sx={{ pr: 3 }}>
                        <Button
                          variant="outlined"
                          color="warning"
                          size="small"
                          startIcon={<FolderOpenIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenDraft(draft.filename);
                          }}
                          sx={{ mr: 1 }}
                        >
                          Open Draft
                        </Button>
                        <IconButton
                          color="error"
                          size="small"
                          onClick={(e) => handleDeleteDraft(draft.filename, e)}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* Quick Instructions section */}
        <Box
          sx={{
            p: 4,
            borderRadius: 3,
            bgcolor: 'background.paper',
            border: '1.5px solid rgba(234, 67, 53, 0.4)', // Google Red border
            transition: 'all 0.3s ease',
            '&:hover': {
              borderColor: '#EA4335',
              boxShadow: '0 12px 20px -10px rgba(234, 67, 53, 0.15)'
            }
          }}
        >
          <Typography variant="h6" gutterBottom sx={{ fontWeight: '700' }}>
            Workflow Highlights
          </Typography>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid size={{ xs: 12, md: 4 }}>
              <Box sx={{ p: 1 }}>
                <Typography variant="subtitle1" color="primary.main" sx={{ fontWeight: '600' }}>
                  1. Setup Metadata
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Provide Project Name, Client, and the Project Start Date to align week ending dates.
                </Typography>
              </Box>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Box sx={{ p: 1 }}>
                <Typography variant="subtitle1" color="primary.main" sx={{ fontWeight: '600' }}>
                  2. Add & Link Tasks
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Specify estimated hours and FTE for each activity. Link tasks using the dependency column to chain dates automatically.
                </Typography>
              </Box>
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <Box sx={{ p: 1 }}>
                <Typography variant="subtitle1" color="primary.main" sx={{ fontWeight: '600' }}>
                  3. Export Excel
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Instantly download a spreadsheet complete with formulas, frozen panes, print formats, and merged colored task bars.
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </Box>
      </Container>
    </Box>
  );
}
