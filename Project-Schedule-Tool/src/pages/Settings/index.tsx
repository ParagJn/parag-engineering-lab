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
  IconButton,
  InputAdornment,
  Chip,
  Radio,
  RadioGroup,
  FormControl,
  FormLabel
} from '@mui/material';
import {
  Save as SaveIcon,
  ArrowBack as ArrowBackIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  CheckCircle as CheckCircleIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';

interface ProviderStatus {
  enabled: boolean;
  provider: string;
  has_api_key: boolean;
}

interface ProvidersConfig {
  anthropic?: ProviderStatus;
  openai?: ProviderStatus;
  google_gemini?: ProviderStatus;
}

export function Settings() {
  const navigate = useNavigate();
  
  // AI Provider Selection State (SAP vs IBM ICA)
  const [selectedProvider, setSelectedProvider] = useState<'sap' | 'ibm_ica'>('sap');
  const [providerSwitchLoading, setProviderSwitchLoading] = useState(false);
  const [providerSwitchSuccess, setProviderSwitchSuccess] = useState(false);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [sapAvailable, setSapAvailable] = useState(false);
  const [ibmIcaAvailable, setIbmIcaAvailable] = useState(false);
  
  // AI Provider Configuration State
  const [providers, setProviders] = useState<ProvidersConfig>({});
  const [apiKeys, setApiKeys] = useState({
    anthropic: '',
    openai: '',
    google_gemini: ''
  });
  const [showApiKeys, setShowApiKeys] = useState({
    anthropic: false,
    openai: false,
    google_gemini: false
  });
  const [loading, setLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [configLoading, setConfigLoading] = useState(true);

  // Load current configuration on mount
  useEffect(() => {
    loadProviderSettings();
    loadConfiguration();
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

  const loadConfiguration = async () => {
    try {
      setConfigLoading(true);
      const response = await fetch('http://localhost:8000/config/providers');
      
      if (!response.ok) {
        throw new Error('Failed to load configuration');
      }
      
      const data = await response.json();
      if (data.success) {
        setProviders(data.providers);
      }
    } catch (err: any) {
      console.error('Error loading configuration:', err);
      setError('Could not connect to backend. Please ensure the backend is running.');
    } finally {
      setConfigLoading(false);
    }
  };

  const handleApiKeyChange = (provider: string, value: string) => {
    setApiKeys(prev => ({ ...prev, [provider]: value }));
    setSaveSuccess(false);
    setError(null);
  };

  const toggleShowApiKey = (provider: string) => {
    setShowApiKeys(prev => ({ ...prev, [provider]: !prev[provider as keyof typeof prev] }));
  };

  const handleSaveProvider = async (provider: string) => {
    const apiKey = apiKeys[provider as keyof typeof apiKeys];
    
    if (!apiKey || apiKey.trim() === '') {
      setError(`Please enter an API key for ${getProviderDisplayName(provider)}`);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSaveSuccess(false);
      
      console.log('Saving provider:', provider);
      console.log('API URL:', 'http://localhost:8000/config/update-provider');
      
      const response = await fetch('http://localhost:8000/config/update-provider', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider: provider,
          api_key: apiKey,
          enabled: true
        })
      });

      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);

      if (!response.ok) {
        const errorData = await response.json();
        console.error('Error response:', errorData);
        throw new Error(errorData.detail || 'Failed to update configuration');
      }

      const result = await response.json();
      console.log('Success result:', result);
      
      if (result.success) {
        setSaveSuccess(true);
        setApiKeys(prev => ({ ...prev, [provider]: '' })); // Clear the input
        
        // Reload configuration to reflect changes
        await loadConfiguration();
        
        // Show restart message as info, not error
        setTimeout(() => {
          setSaveSuccess(false);
        }, 3000);
      }
    } catch (err: any) {
      console.error('Error saving configuration:', err);
      setError(err.message || 'Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const getProviderDisplayName = (provider: string): string => {
    const names: { [key: string]: string } = {
      'anthropic': 'Anthropic',
      'openai': 'OpenAI',
      'google_gemini': 'Google Gemini'
    };
    return names[provider] || provider;
  };

  const getProviderDescription = (provider: string): string => {
    const descriptions: { [key: string]: string } = {
      'anthropic': 'Claude models (Opus, Sonnet) - Best for complex reasoning and analysis',
      'openai': 'GPT-4 and GPT-3.5 models - General-purpose AI with broad capabilities',
      'google_gemini': 'Gemini 2.0 and 1.5 models - Fast and efficient with vision capabilities'
    };
    return descriptions[provider] || '';
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    navigate('/');
  };

  if (configLoading) {
    return (
      <Container maxWidth="md" sx={{ py: 6, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <CircularProgress />
      </Container>
    );
  }

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

          {/* AI Models Configuration Section */}
          <Card>
            <CardContent sx={{ p: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: '700' }}>
                  AI Models Configuration
                </Typography>
                <IconButton onClick={loadConfiguration} size="small" title="Refresh">
                  <RefreshIcon />
                </IconButton>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure AI providers for Statement of Work generation and intelligent features.
              </Typography>

              {error && (
                <Alert severity={error.includes('restart') ? 'warning' : 'error'} sx={{ mb: 3 }} onClose={() => setError(null)}>
                  {error}
                </Alert>
              )}

              {saveSuccess && (
                <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSaveSuccess(false)}>
                  <Typography variant="body2" sx={{ fontWeight: '600', mb: 1 }}>
                    ✅ Configuration saved successfully!
                  </Typography>
                  <Typography variant="body2">
                    Please restart the backend for changes to take effect:
                  </Typography>
                  <Typography variant="body2" component="pre" sx={{ mt: 1, p: 1, bgcolor: 'grey.100', borderRadius: 1, fontSize: '0.75rem' }}>
                    lsof -ti:8000 | xargs kill -9{'\n'}
                    cd backend && python main.py
                  </Typography>
                </Alert>
              )}

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {/* Anthropic */}
                <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: '600', display: 'flex', alignItems: 'center', gap: 1 }}>
                        Anthropic Claude
                        {providers.anthropic?.enabled && providers.anthropic?.has_api_key && (
                          <Chip label="Configured" size="small" color="success" icon={<CheckCircleIcon />} />
                        )}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {getProviderDescription('anthropic')}
                      </Typography>
                    </Box>
                  </Box>
                  
                  <TextField
                    fullWidth
                    label="API Key"
                    type={showApiKeys.anthropic ? 'text' : 'password'}
                    value={apiKeys.anthropic}
                    onChange={(e) => handleApiKeyChange('anthropic', e.target.value)}
                    placeholder="sk-ant-api03-..."
                    helperText="Get your API key from https://console.anthropic.com"
                    slotProps={{
                      input: {
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => toggleShowApiKey('anthropic')} edge="end">
                              {showApiKeys.anthropic ? <VisibilityOffIcon /> : <VisibilityIcon />}
                            </IconButton>
                          </InputAdornment>
                        )
                      }
                    }}
                    sx={{ mb: 2 }}
                  />
                  
                  <Button
                    variant="contained"
                    onClick={() => handleSaveProvider('anthropic')}
                    disabled={loading || !apiKeys.anthropic || apiKeys.anthropic.trim() === ''}
                    startIcon={loading ? <CircularProgress size={16} /> : <SaveIcon />}
                    fullWidth
                  >
                    {loading ? 'Saving...' : 'Save Anthropic Configuration'}
                  </Button>
                  {!apiKeys.anthropic && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      Enter an API key to enable the save button
                    </Typography>
                  )}
                </Box>

                {/* OpenAI */}
                <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: '600', display: 'flex', alignItems: 'center', gap: 1 }}>
                        OpenAI
                        {providers.openai?.enabled && providers.openai?.has_api_key && (
                          <Chip label="Configured" size="small" color="success" icon={<CheckCircleIcon />} />
                        )}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {getProviderDescription('openai')}
                      </Typography>
                    </Box>
                  </Box>
                  
                  <TextField
                    fullWidth
                    label="API Key"
                    type={showApiKeys.openai ? 'text' : 'password'}
                    value={apiKeys.openai}
                    onChange={(e) => handleApiKeyChange('openai', e.target.value)}
                    placeholder="sk-proj-..."
                    helperText="Get your API key from https://platform.openai.com/api-keys"
                    slotProps={{
                      input: {
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => toggleShowApiKey('openai')} edge="end">
                              {showApiKeys.openai ? <VisibilityOffIcon /> : <VisibilityIcon />}
                            </IconButton>
                          </InputAdornment>
                        )
                      }
                    }}
                    sx={{ mb: 2 }}
                  />
                  
                  <Button
                    variant="contained"
                    onClick={() => handleSaveProvider('openai')}
                    disabled={loading || !apiKeys.openai || apiKeys.openai.trim() === ''}
                    startIcon={loading ? <CircularProgress size={16} /> : <SaveIcon />}
                    fullWidth
                  >
                    {loading ? 'Saving...' : 'Save OpenAI Configuration'}
                  </Button>
                  {!apiKeys.openai && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      Enter an API key to enable the save button
                    </Typography>
                  )}
                </Box>

                {/* Google Gemini */}
                <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Box>
                      <Typography variant="subtitle1" sx={{ fontWeight: '600', display: 'flex', alignItems: 'center', gap: 1 }}>
                        Google Gemini
                        {providers.google_gemini?.enabled && providers.google_gemini?.has_api_key && (
                          <Chip label="Configured" size="small" color="success" icon={<CheckCircleIcon />} />
                        )}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {getProviderDescription('google_gemini')}
                      </Typography>
                    </Box>
                  </Box>
                  
                  <TextField
                    fullWidth
                    label="API Key"
                    type={showApiKeys.google_gemini ? 'text' : 'password'}
                    value={apiKeys.google_gemini}
                    onChange={(e) => handleApiKeyChange('google_gemini', e.target.value)}
                    placeholder="AIza..."
                    helperText="Get your API key from https://aistudio.google.com/apikey"
                    slotProps={{
                      input: {
                        endAdornment: (
                          <InputAdornment position="end">
                            <IconButton onClick={() => toggleShowApiKey('google_gemini')} edge="end">
                              {showApiKeys.google_gemini ? <VisibilityOffIcon /> : <VisibilityIcon />}
                            </IconButton>
                          </InputAdornment>
                        )
                      }
                    }}
                    sx={{ mb: 2 }}
                  />
                  
                  <Button
                    variant="contained"
                    onClick={() => handleSaveProvider('google_gemini')}
                    disabled={loading || !apiKeys.google_gemini || apiKeys.google_gemini.trim() === ''}
                    startIcon={loading ? <CircularProgress size={16} /> : <SaveIcon />}
                    fullWidth
                  >
                    {loading ? 'Saving...' : 'Save Google Gemini Configuration'}
                  </Button>
                  {!apiKeys.google_gemini && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                      Enter an API key to enable the save button
                    </Typography>
                  )}
                </Box>
              </Box>

              <Alert severity="info" sx={{ mt: 3 }}>
                <Typography variant="body2" sx={{ fontWeight: '600', mb: 1 }}>
                  Important Notes:
                </Typography>
                <Typography variant="body2" component="div">
                  • API keys are stored securely in the backend .env file<br />
                  • You need to restart the backend after saving configuration changes<br />
                  • Only one provider can be active at a time<br />
                  • API keys are never stored in browser storage
                </Typography>
              </Alert>
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
                  defaultValue="[ COMPANY LOGO / NAME PLACEHOLDER ]"
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
    </Container>
  );
}

