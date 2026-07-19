import React from 'react';
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
  TextField
} from '@mui/material';
import { Save as SaveIcon, ArrowBack as ArrowBackIcon } from '@mui/icons-material';

export function Settings() {
  const navigate = useNavigate();

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    navigate('/');
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

