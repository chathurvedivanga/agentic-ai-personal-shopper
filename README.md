# Agentic AI Personal Shopper

Full-stack shopping assistant with:

- React + Vite + Tailwind frontend
- Flask REST backend
- Gemini streaming responses with a current Flash model
- YouTube review search via `youtube-search-python`
- Parallel transcript extraction via `ThreadPoolExecutor`
- SSE streaming from Flask to the browser
- SQLite-backed saved chats with background auto-titling

## Project Structure

```text
server/
  app.py
  agent.py
  storage.py
  scraper.py
  requirements.txt
client/
  src/
    App.jsx
    components/ChatBubble.jsx
    components/SessionSidebar.jsx
    lib/sse.js
```

## Backend Setup

```bash
cd server
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then add your Gemini key to `server/.env`:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
DB_PATH=agentic_shopper.db
```

Run the backend:

```bash
python app.py
```

The Flask API will be available at `http://localhost:5000`.
Saved chats are stored locally in SQLite and appear in the left sidebar.

## Frontend Setup

```bash
cd client
npm install
npm run dev
```

The Vite app will run at `http://localhost:5173`.

## Production Notes

- Backend: `gunicorn app:app`
- Frontend: `npm run build`
- If you deploy the frontend separately, set `VITE_API_BASE_URL` and `CORS_ORIGIN` accordingly.

## GitHub Setup

Initialize the repo locally:

```bash
git init -b main
git add .
git commit -m "Initial commit"
```

Then create an empty GitHub repository and connect it:

```bash
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## Free Deployment

The cleanest free path for this codebase is:

- Render web service for the Flask backend
- Render static site for the Vite frontend

This repo includes a root `render.yaml` so Render can import both services from the same GitHub repository.

### Backend Service

Render settings if you create it manually:

- Service type: `Web Service`
- Root Directory: `server`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --worker-class gthread --threads 8 --timeout 120 --bind 0.0.0.0:$PORT`
- Health Check Path: `/api/health`

Backend environment variables:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODELS=gemini-2.0-flash,gemini-flash-latest
CORS_ORIGIN=https://your-frontend-domain.onrender.com
DB_PATH=agentic_shopper.db
```

### Frontend Service

Render settings if you create it manually:

- Service type: `Static Site`
- Root Directory: `client`
- Build Command: `npm install && npm run build`
- Publish Directory: `dist`

Frontend environment variable:

```env
VITE_API_BASE_URL=https://your-backend-domain.onrender.com
```

### Important Free-Tier Limitation

The current app stores saved chats in a local SQLite file. On a free deployment, that works for demos, but it is **not durable infrastructure**. If the backend is restarted or redeployed, saved chats can be lost because the database file lives on the service filesystem.

If you want durable production-style chat history, the next step is migrating storage from SQLite to a hosted Postgres database.
