# Quick Start Guide - Project Schedule Tool

## 🚀 Start Both Services with One Command

The easiest way to run the Project Schedule Tool is using the unified `start.sh` script.

### Step 1: Navigate to Project Root

```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Project-Schedule-Tool
```

### Step 2: Make the Script Executable (First Time Only)

```bash
chmod +x start.sh
```

### Step 3: Run the Script

```bash
./start.sh
```

## What Happens When You Run start.sh?

The script will automatically:

1. ✅ **Check Prerequisites**
   - Verifies Node.js and npm are installed
   - Verifies Python 3 is installed
   - Checks that virtual environment exists

2. ✅ **Install Dependencies** (if needed)
   - Installs frontend npm packages
   - Installs backend Python packages

3. ✅ **Build Frontend**
   - Runs `npm run build` to compile TypeScript

4. ✅ **Start Backend**
   - Activates Python virtual environment
   - Loads environment variables from `backend/.env`
   - Starts FastAPI server on port 8000
   - Runs in background

5. ✅ **Start Frontend**
   - Starts Vite dev server on port 5173
   - Runs in foreground (you'll see the output)

6. ✅ **Graceful Shutdown**
   - Press `Ctrl+C` to stop both services
   - Both backend and frontend will be stopped cleanly

## Access Your Application

Once started, you can access:

- **Frontend Application**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative API Docs**: http://localhost:8000/redoc

## Stopping the Services

Press `Ctrl+C` in the terminal where you ran `./start.sh`

The script will automatically stop both the backend and frontend services.

## Troubleshooting

### Virtual Environment Not Found

If you see an error about the virtual environment not found:

```bash
python3 -m venv /Users/paragjain/dev-works/myenv
source /Users/paragjain/dev-works/myenv/bin/activate
cd /Users/paragjain/dev-works/parag-engineering-lab/Project-Schedule-Tool/backend
pip install -r requirements.txt
```

### Backend .env File Missing

If you see a warning about missing `.env` file:

```bash
cd backend
cp .env.example .env
# Edit .env and add your API credentials
nano .env  # or use your favorite editor
```

### Port Already in Use

If port 8000 or 5173 is already in use:

```bash
# Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9

# Find and kill the process using port 5173
lsof -ti:5173 | xargs kill -9
```

### Check Backend Logs

If the backend fails to start, check the log file:

```bash
cat backend.log
```

## Running Services Separately

If you want to run services individually:

### Frontend Only

```bash
npm run dev
```

### Backend Only

```bash
cd backend
source /Users/paragjain/dev-works/myenv/bin/activate
python main.py
```

## Development Tips

- The frontend runs in **hot-reload mode** - changes to React files will automatically refresh
- Backend logs are written to `backend.log` in the project root
- Use the **API docs** at http://localhost:8000/docs to test backend endpoints
- The backend uses **auto-reload** - Python file changes will restart the server

## Next Steps

1. Open http://localhost:5173 in your browser
2. Create a new project or load a saved one
3. Add tasks and dependencies
4. Export to Excel when ready
5. Use the AI-powered features via the backend API

Enjoy! 🎉
