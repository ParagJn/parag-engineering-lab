import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  TextField,
  Typography,
  CircularProgress,
  Alert,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import EditIcon from '@mui/icons-material/Edit';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import SlideshowIcon from '@mui/icons-material/Slideshow';

interface SoWModalProps {
  open: boolean;
  onClose: () => void;
  sowContent: string;
  loading: boolean;
  error?: string;
  needsMoreInfo?: boolean;
  questions?: string[];
  onRegenerate?: () => void;
  onRegenerateWithMoreInfo?: (additionalInfo: string) => void;
  onExportToWord: (content: string) => void;
  onGenerateISBD?: () => void;
  isbdLoading?: boolean;
}

export const SoWModal: React.FC<SoWModalProps> = ({
  open,
  onClose,
  sowContent,
  loading,
  error,
  needsMoreInfo,
  questions,
  onRegenerate,
  onRegenerateWithMoreInfo,
  onExportToWord,
  onGenerateISBD,
  isbdLoading,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(sowContent);
  const [additionalInfo, setAdditionalInfo] = useState('');

  // Update edited content when sowContent changes
  React.useEffect(() => {
    setEditedContent(sowContent);
  }, [sowContent]);

  const handleSaveEdit = () => {
    setIsEditing(false);
  };

  const handleExport = () => {
    const contentToExport = isEditing ? editedContent : sowContent;
    onExportToWord(contentToExport);
  };

  const handleProvideMoreInfo = () => {
    if (onRegenerateWithMoreInfo && additionalInfo.trim()) {
      onRegenerateWithMoreInfo(additionalInfo);
      setAdditionalInfo('');
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            height: '90vh',
            maxHeight: '900px',
          },
        },
      }}
    >
      <DialogTitle
        sx={{
          fontWeight: 700,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid',
          borderColor: 'divider',
        }}
      >
        <Typography variant="h6" component="span" sx={{ fontWeight: 700 }}>
          Statement of Work - Draft
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 3, overflow: 'auto' }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
            <CircularProgress />
            <Typography variant="body1" sx={{ ml: 2 }}>
              Generating Statement of Work...
            </Typography>
          </Box>
        )}

        {error && !loading && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {needsMoreInfo && questions && questions.length > 0 && (
          <Box sx={{ mb: 3 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                More Information Needed
              </Typography>
              <Typography variant="body2">
                Please provide additional details to generate a comprehensive Statement of Work:
              </Typography>
            </Alert>

            <Box sx={{ mb: 2 }}>
              {questions.map((question, idx) => (
                <Typography key={idx} variant="body2" sx={{ mb: 1, pl: 2 }}>
                  • {question}
                </Typography>
              ))}
            </Box>

            <TextField
              fullWidth
              multiline
              minRows={4}
              maxRows={10}
              label="Additional Information"
              placeholder="Provide the requested information here..."
              value={additionalInfo}
              onChange={(e) => setAdditionalInfo(e.target.value)}
              sx={{ mb: 2 }}
            />

            <Button
              variant="contained"
              onClick={handleProvideMoreInfo}
              disabled={!additionalInfo.trim()}
            >
              Regenerate with More Information
            </Button>
          </Box>
        )}

        {!loading && !needsMoreInfo && sowContent && (
          <Box>
            {isEditing ? (
              <TextField
                fullWidth
                multiline
                value={editedContent}
                onChange={(e) => setEditedContent(e.target.value)}
                variant="outlined"
                sx={{
                  '& .MuiInputBase-root': {
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                  },
                }}
                minRows={20}
              />
            ) : (
              <Box
                sx={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'system-ui, -apple-system, sans-serif',
                  lineHeight: 1.6,
                  '& h2': {
                    fontSize: '1.5rem',
                    fontWeight: 700,
                    mt: 3,
                    mb: 2,
                    color: 'primary.main',
                    borderBottom: '2px solid',
                    borderColor: 'primary.main',
                    pb: 1,
                  },
                  '& h3': {
                    fontSize: '1.25rem',
                    fontWeight: 600,
                    mt: 2.5,
                    mb: 1.5,
                    color: 'text.primary',
                  },
                }}
              >
                {editedContent.split('\n').map((line, idx) => {
                  // Headers
                  if (line.startsWith('## ')) {
                    return (
                      <Typography key={idx} variant="h5" sx={{ fontSize: '1.5rem', fontWeight: 700, mt: 3, mb: 2, color: 'primary.main', borderBottom: '2px solid', borderColor: 'primary.main', pb: 1 }}>
                        {line.replace('## ', '')}
                      </Typography>
                    );
                  }
                  if (line.startsWith('### ')) {
                    return (
                      <Typography key={idx} variant="h6" sx={{ fontSize: '1.25rem', fontWeight: 600, mt: 2.5, mb: 1.5 }}>
                        {line.replace('### ', '')}
                      </Typography>
                    );
                  }
                  // Bullet points
                  if (line.match(/^[•\-\*]\s+/)) {
                    const bulletText = line.replace(/^[•\-\*]\s+/, '');
                    return (
                      <Box key={idx} sx={{ display: 'flex', mb: 0.5, ml: 2 }}>
                        <Typography component="span" sx={{ mr: 1 }}>•</Typography>
                        <Typography component="span" sx={{ flex: 1 }}>
                          {bulletText.split(/(\*\*.*?\*\*)/).map((part, i) => {
                            if (part.startsWith('**') && part.endsWith('**')) {
                              return <strong key={i}>{part.slice(2, -2)}</strong>;
                            }
                            return part;
                          })}
                        </Typography>
                      </Box>
                    );
                  }
                  // Empty lines
                  if (!line.trim()) {
                    return <Box key={idx} sx={{ height: '0.5rem' }} />;
                  }
                  // Regular paragraphs
                  return (
                    <Typography key={idx} sx={{ mb: 1, display: 'block' }}>
                      {line.split(/(\*\*.*?\*\*)/).map((part, i) => {
                        if (part.startsWith('**') && part.endsWith('**')) {
                          return <strong key={i}>{part.slice(2, -2)}</strong>;
                        }
                        return part;
                      })}
                    </Typography>
                  );
                })}
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ borderTop: '1px solid', borderColor: 'divider', p: 2, gap: 1 }}>
        {!loading && !needsMoreInfo && sowContent && (
          <>
            {isEditing ? (
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSaveEdit}
              >
                Save Changes
              </Button>
            ) : (
              <Button
                variant="outlined"
                startIcon={<EditIcon />}
                onClick={() => setIsEditing(true)}
              >
                Edit
              </Button>
            )}
            {onRegenerate && (
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={onRegenerate}
                color="secondary"
              >
                Regenerate
              </Button>
            )}
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={handleExport}
              color="primary"
            >
              Export to Word
            </Button>
            {onGenerateISBD && (
              <Button
                variant="outlined"
                startIcon={isbdLoading ? <CircularProgress size={16} /> : <SlideshowIcon />}
                onClick={onGenerateISBD}
                disabled={isbdLoading}
              >
                Generate ISBD Content
              </Button>
            )}
          </>
        )}
        <Button onClick={onClose} variant="outlined" color="inherit">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};
