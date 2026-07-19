import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2563eb', // Modern Blue
      light: '#60a5fa',
      dark: '#1d4ed8',
      contrastText: '#ffffff'
    },
    secondary: {
      main: '#4f46e5', // Indigo
      light: '#818cf8',
      dark: '#3730a3',
      contrastText: '#ffffff'
    },
    background: {
      default: '#f8fafc', // Very Light Gray/Blue background
      paper: '#ffffff'
    },
    text: {
      primary: '#0f172a', // Slate 900
      secondary: '#475569' // Slate 600
    },
    divider: '#e2e8f0'
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontWeight: 800,
      letterSpacing: '-0.025em'
    },
    h2: {
      fontWeight: 700,
      letterSpacing: '-0.02em'
    },
    h3: {
      fontWeight: 700,
      letterSpacing: '-0.015em'
    },
    h4: {
      fontWeight: 600,
      letterSpacing: '-0.015em'
    },
    h5: {
      fontWeight: 600
    },
    h6: {
      fontWeight: 600
    },
    button: {
      textTransform: 'none',
      fontWeight: 600
    }
  },
  shape: {
    borderRadius: 8
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: ({ ownerState }: any) => ({
          borderRadius: 8,
          padding: '8px 16px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'
          },
          ...(ownerState?.variant === 'contained' && ownerState?.color === 'primary' && {
            background: 'linear-gradient(to right, #2563eb, #3b82f6)',
            '&:hover': {
              background: 'linear-gradient(to right, #1d4ed8, #2563eb)'
            }
          })
        })
      }
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
          borderRadius: 8
        }
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
          border: '1px solid #f1f5f9'
        }
      }
    }
  }
});
