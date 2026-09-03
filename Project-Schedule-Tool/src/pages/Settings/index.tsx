import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Container,
  Typography,
  FormControlLabel,
  Checkbox,
  TextField,
  Alert,
  CircularProgress,
  Chip,
  Radio,
  RadioGroup,
  FormControl,
  FormLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar
} from '@mui/material';
import {
  Save as SaveIcon,
  ArrowBack as ArrowBackIcon,
  Event as EventIcon
} from '@mui/icons-material';

export function Settings() {
  const navigate = useNavigate();

  // AI Provider Selection State (SAP vs IBM ICA)
  const [selectedProvider, setSelectedProvider] = useState<'sap' | 'ibm_ica'>('sap');
  const [providerSwitchLoading, setProviderSwitchLoading] = useState(false);
  const [providerSwitchSuccess, setProviderSwitchSuccess] = useState(false);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [sapAvailable, setSapAvailable] = useState(false);
  const [ibmIcaAvailable, setIbmIcaAvailable] = useState(false);

  // Public Holidays State
  const [holidayRegion, setHolidayRegion] = useState<'vic_australia' | 'india'>('vic_australia');
  const [holidayModalOpen, setHolidayModalOpen] = useState(false);
  const [holidayRawText, setHolidayRawText] = useState('');
  const [holidayParsing, setHolidayParsing] = useState(false);
  const [holidayError, setHolidayError] = useState<string | null>(null);
  const [holidaySnackbarOpen, setHolidaySnackbarOpen] = useState(false);
  const [holidaySnackbarMessage, setHolidaySnackbarMessage] = useState('');

  // Load current configuration on mount
  useEffect(() => {
    loadProviderSettings();
  }, []);

  const loadProviderSettings = async () => {
    try {
      const response = await fetch('http://localhost:8000/settings/provider');
      
      if (!response.ok) {
        throw new Error('Failed to load provider settings');
      }
      
      const data = await response.json();
      if (data.success) {
        setSelectedProvider(data.ai_provider);
        setSapAvailable(data.sap_available);
        setIbmIcaAvailable(data.ibm_ica_available);
      }
    } catch (err: any) {
      console.error('Error loading provider settings:', err);
      setProviderError('Could not load provider settings');
    }
  };

  const handleProviderChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const newProvider = event.target.value as 'sap' | 'ibm_ica';
    
    setProviderSwitchLoading(true);
    setProviderError(null);
    setProviderSwitchSuccess(false);
    
    try {
      const response = await fetch('http://localhost:8000/settings/provider', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ai_provider: newProvider
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update provider');
      }
      
      const data = await response.json();
      if (data.success) {
        setSelectedProvider(newProvider);
        setProviderSwitchSuccess(true);
        setTimeout(() => setProviderSwitchSuccess(false), 5000);
      }
    } catch (err: any) {
      console.error('Error updating provider:', err);
      setProviderError(err.message || 'Failed to switch provider');
    } finally {
      setProviderSwitchLoading(false);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    navigate('/');
  };

  const handleParseHolidays = async () => {
    if (!holidayRawText.trim()) {
      setHolidayError('Paste some holiday text first');
      return;
    }

    setHolidayParsing(true);
    setHolidayError(null);

    try {
      const response = await fetch('http://localhost:8000/holidays/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          region: holidayRegion,
          raw_text: holidayRawText
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.detail || 'Failed to parse holidays');
      }

      setHolidaySnackbarMessage(
        `Saved ${data.count} holiday${data.count === 1 ? '' : 's'} for ${holidayRegion === 'vic_australia' ? 'Victoria, Australia' : 'India'} (${data.year})`
      );
      setHolidaySnackbarOpen(true);
      setHolidayModalOpen(false);
      setHolidayRawText('');
    } catch (err: any) {
      console.error('Error parsing holidays:', err);
      setHolidayError(err.message || 'Failed to parse holidays');
    } finally {
      setHolidayParsing(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 6 }}>
      <Box sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 2, mb: 4 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} variant="outlined">
          Back
        </Button>
        <Typography variant="h4" component="h1" sx={{ fontWeight: '800' }}>
          Planner Settings
        </Typography>
      </Box>

      <form onSubmit={handleSave}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          
          {/* AI Provider Selection Section */}
          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: '700', mb: 1 }}>
                AI Provider Selection
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Choose which AI service to use for SoW generation and intelligent features.
              </Typography>

              {providerError && (
                <Alert severity="error" sx={{ mb: 3 }} onClose={() => setProviderError(null)}>
                  {providerError}
                </Alert>
              )}

              {providerSwitchSuccess && (
                <Alert severity="success" sx={{ mb: 3 }} onClose={() => setProviderSwitchSuccess(false)}>
                  Provider successfully switched! The new provider will be used for all AI operations.
                </Alert>
              )}

              <FormControl component="fieldset" disabled={providerSwitchLoading}>
                <FormLabel component="legend" sx={{ mb: 2, fontWeight: '600' }}>
                  Active AI Provider
                </FormLabel>
                <RadioGroup
                  value={selectedProvider}
                  onChange={handleProviderChange}
                >
                  <FormControlLabel
                    value="sap"
                    control={<Radio />}
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body1" sx={{ fontWeight: '600' }}>
                          SAP AI Core (Claude 4.7 Opus)
                        </Typography>
                        {sapAvailable ? (
                          <Chip label="Available" size="small" color="success" />
                        ) : (
                          <Chip label="Not Available" size="small" color="error" />
                        )}
                      </Box>
                    }
                    disabled={!sapAvailable}
                    sx={{ mb: 2, p: 2, border: '1px solid', borderColor: selectedProvider === 'sap' ? 'primary.main' : 'divider', borderRadius: 1 }}
                  />
                  <Box sx={{ ml: 4, mb: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      Enterprise-grade AI powered by SAP Business Technology Platform with Claude 4.7 Opus model.
                      Requires SAP credentials configured in backend.
                    </Typography>
                  </Box>

                  <FormControlLabel
                    value="ibm_ica"
                    control={<Radio />}
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body1" sx={{ fontWeight: '600' }}>
                          IBM ICA (Claude Sonnet 5)
                        </Typography>
                        {ibmIcaAvailable ? (
                          <Chip label="Available" size="small" color="success" />
                        ) : (
                          <Chip label="Not Available" size="small" color="error" />
                        )}
                      </Box>
                    }
                    disabled={!ibmIcaAvailable}
                    sx={{ mb: 2, p: 2, border: '1px solid', borderColor: selectedProvider === 'ibm_ica' ? 'primary.main' : 'divider', borderRadius: 1 }}
                  />
                  <Box sx={{ ml: 4, mb: 2 }}>
                    <Typography variant="caption" color="text.secondary">
                      IBM ICA (watsonx Code Assistant) with Claude Sonnet 5 or Gemini models.
                      Requires IBM_ICA_API_KEY and IBM_ICA_ENDPOINT configured in backend .env file.
                    </Typography>
                  </Box>
                </RadioGroup>
              </FormControl>

              {providerSwitchLoading && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2" color="text.secondary">
                    Switching provider...
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Public Holidays Section */}
          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: '700', mb: 1 }}>
                Public Holidays
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Select a region, then paste holiday text copied from a webpage or spreadsheet.
                The AI will extract this year's holidays and save them.
              </Typography>

              <FormControl component="fieldset" sx={{ mb: 3 }}>
                <FormLabel component="legend" sx={{ mb: 1, fontWeight: '600' }}>
                  Region
                </FormLabel>
                <RadioGroup
                  row
                  value={holidayRegion}
                  onChange={(e) => setHolidayRegion(e.target.value as 'vic_australia' | 'india')}
                >
                  <FormControlLabel value="vic_australia" control={<Radio />} label="Victoria, Australia" />
                  <FormControlLabel value="india" control={<Radio />} label="India" />
                </RadioGroup>
              </FormControl>

              <Box>
                <Button
                  variant="outlined"
                  startIcon={<EventIcon />}
                  onClick={() => { setHolidayError(null); setHolidayModalOpen(true); }}
                >
                  Add / Update Holidays
                </Button>
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: '700' }}>
                Scheduling Engine Constants
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure standard calculations used by the local scheduling engine.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <TextField
                  label="Working Hours per Day"
                  type="number"
                  defaultValue={8}
                  disabled
                  helperText="Default value set to 8 hours. (Rule 2)"
                  fullWidth
                />

                <TextField
                  label="Working Days per Week"
                  type="number"
                  defaultValue={5}
                  disabled
                  helperText="Default value set to 5 days (Monday to Friday). (Rule 3 & 8)"
                  fullWidth
                />
              </Box>
            </CardContent>
          </Card>

          <Card>
            <CardContent sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: '700' }}>
                Excel Export Defaults
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure spreadsheet layouts and styling defaults.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <TextField
                  label="Company Logo / Header Text"
                  defaultValue="[IBM Pty. Ltd.]"
                  fullWidth
                />

                <FormControlLabel
                  control={<Checkbox defaultChecked disabled />}
                  label="Freeze Metadata Columns (Col A-M)"
                />

                <FormControlLabel
                  control={<Checkbox defaultChecked disabled />}
                  label="Enable Alternating Row Shading"
                />

                <FormControlLabel
                  control={<Checkbox defaultChecked disabled />}
                  label="Enable Autofilters on Column Headers"
                />
              </Box>
            </CardContent>
          </Card>

          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
            <Button variant="outlined" onClick={() => navigate(-1)}>
              Cancel
            </Button>
            <Button variant="contained" startIcon={<SaveIcon />} type="submit">
              Save Settings
            </Button>
          </Box>
        </Box>
      </form>

      <Dialog
        open={holidayModalOpen}
        onClose={() => !holidayParsing && setHolidayModalOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          Paste Holidays — {holidayRegion === 'vic_australia' ? 'Victoria, Australia' : 'India'}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Copy the holiday list from a webpage or spreadsheet and paste it below.
            Only holidays for the current year will be kept, and this will overwrite
            the existing saved list for this region.
          </Typography>

          {holidayError && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setHolidayError(null)}>
              {holidayError}
            </Alert>
          )}

          <TextField
            multiline
            minRows={10}
            fullWidth
            placeholder="e.g. 1 January 2026 - New Year's Day&#10;26 January 2026 - Australia Day&#10;..."
            value={holidayRawText}
            onChange={(e) => setHolidayRawText(e.target.value)}
            disabled={holidayParsing}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHolidayModalOpen(false)} disabled={holidayParsing}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleParseHolidays}
            disabled={holidayParsing}
            startIcon={holidayParsing ? <CircularProgress size={16} /> : undefined}
          >
            {holidayParsing ? 'Parsing...' : 'Parse & Save'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={holidaySnackbarOpen}
        autoHideDuration={5000}
        onClose={() => setHolidaySnackbarOpen(false)}
        message={holidaySnackbarMessage}
      />
    </Container>
  );
}

