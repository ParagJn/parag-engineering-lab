# Quick Start Guide

## First Time Setup

### 1. Verify Prerequisites
```bash
# Check Python
python3 --version  # Should be 3.8+

# Check Node.js
node --version     # Should be 16+
npm --version
```

### 2. Verify Environment
```bash
# Check virtual environment
ls -la /Users/paragjain/dev-works/myenv/bin/activate

# Check .env file
cat .env
```

### 3. Install Dependencies

**Backend:**
```bash
source /Users/paragjain/dev-works/myenv/bin/activate
cd backend
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

## Starting the Application

### Method 1: One-Command Start (Recommended)
```bash
./start.sh
```

This starts both servers. Access at:
- Frontend: http://localhost:5173
- Backend: http://localhost:8000

Press `Ctrl+C` to stop both servers.

### Method 2: Manual Start

**Terminal 1 - Backend:**
```bash
source /Users/paragjain/dev-works/myenv/bin/activate
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## Testing

### 1. Test IBM ICA Connection
```bash
source /Users/paragjain/dev-works/myenv/bin/activate
python Test-IBM-ICA-Client.py
```

Expected output:
```
Endpoint: https://api.nextgen-beta.ica.ibm.com/ica
Model:    claude-sonnet-5
SSL Mode: VERIFIED

Interactive chat started. Press Ctrl+C to exit.

🧑 You: Hello
🤖 Assistant: [response from model]
```

### 2. Test Backend API
```bash
# In a browser or using curl
curl http://localhost:8000/health

# Expected: {"status":"ok"}
```

### 3. Test Frontend
Open http://localhost:5173 in your browser.

## First Use

1. **Create a Session**
   - Click "New Session" button
   - You should see "New conversation" in the sidebar

2. **Send a Test Message**
   - Type: "Hello, can you help me?"
   - Press Enter
   - Wait for AI response

3. **Upload a Test File**
   - Click 📎 button
   - Select a .txt or .md file
   - Send message: "What is in this file?"

## Common Issues

### Backend won't start

**Port already in use:**
```bash
lsof -i :8000
kill -9 <PID>
```

**Missing dependencies:**
```bash
source /Users/paragjain/dev-works/myenv/bin/activate
pip install -r backend/requirements.txt
```

**Configuration error:**
```bash
# Verify .env file exists
ls -la .env

# Check contents
cat .env
```

### Frontend won't start

**Port already in use:**
```bash
lsof -i :5173
kill -9 <PID>
```

**Missing dependencies:**
```bash
cd frontend
npm install
```

**Build errors:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Model not responding

**Check credentials:**
```bash
cat .env
# Verify IBM_ICA_API_KEY and IBM_ICA_ENDPOINT are correct
```

**Test connection:**
```bash
source /Users/paragjain/dev-works/myenv/bin/activate
python Test-IBM-ICA-Client.py
```

**Check backend logs:**
Look for error messages in the terminal running the backend.

### File upload fails

**Check file size:**
- Maximum: 50MB
- Reduce file size if needed

**Check file type:**
- Supported: .pdf, .docx, .txt, .md, .png, .jpg, .jpeg, .gif, .webp

**Check directory:**
```bash
ls -la data/documents/
# Should exist and be writable
```

## Development Tips

### Backend Hot Reload
The backend runs with `--reload` flag, so code changes are automatically applied.

### Frontend Hot Reload
Vite provides instant HMR (Hot Module Replacement) for frontend changes.

### View API Documentation
http://localhost:8000/docs - Interactive Swagger UI

### Check Session Data
```bash
# List all sessions
ls -la data/sessions/

# View a session
cat data/sessions/sess_<id>.json | jq
```

### Check Uploaded Documents
```bash
# List documents
ls -la data/documents/

# View extracted markdown
cat data/documents/att_<id>/content.md
```

## Stopping the Application

### If using start.sh
Press `Ctrl+C` - Both servers will stop automatically

### If running manually
Press `Ctrl+C` in each terminal

### Force stop all
```bash
# Find processes
ps aux | grep uvicorn
ps aux | grep vite

# Kill processes
pkill -f uvicorn
pkill -f vite
```

## Next Steps

- Explore the application
- Try different file types
- Test conversation continuity
- Review the Architecture documentation
- Check the API documentation at http://localhost:8000/docs
