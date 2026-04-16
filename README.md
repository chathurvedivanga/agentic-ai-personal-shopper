# Agentic AI Personal Shopper

Full-stack shopping assistant with:

- React + Vite + Tailwind frontend
- Flask REST backend
- Mixture-of-Agents response pipeline
- OpenRouter Layer 1 agents for critique, summarization, and extraction
- Gemini Layer 2 synthesis with a current Flash model
- YouTube review search via `youtube-search-python`
- Parallel transcript extraction via `ThreadPoolExecutor`
- SQLite/Postgres saved chats with full agent breakdowns and background auto-titling

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
OPENROUTER_API_KEY=your_openrouter_key
DATABASE_URL=
DB_PATH=agentic_shopper.db
```

For local Neon Postgres testing, paste the Neon connection string into `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@ep-example.ap-south-1.aws.neon.tech/dbname?sslmode=require
```

Leave `DATABASE_URL=` empty if you want local development to keep using SQLite.

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
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_APP_TITLE=AI Shopping Partner
OPENROUTER_HTTP_REFERER=https://your-frontend-domain.onrender.com
CORS_ORIGIN=https://your-frontend-domain.onrender.com
DATABASE_URL=postgresql://user:password@ep-example.region.aws.neon.tech/dbname?sslmode=require
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

### Render Blueprint Notes

If you deploy using the included `render.yaml`, Render auto-wires:

- `VITE_API_BASE_URL` from the backend service's `RENDER_EXTERNAL_URL`
- `CORS_ORIGIN` from the frontend service's `RENDER_EXTERNAL_URL`
- `OPENROUTER_HTTP_REFERER` from the frontend service's `RENDER_EXTERNAL_URL`
- `DATABASE_URL` is marked as a secret value; paste your Neon Postgres connection string into the backend service environment

The backend also accepts comma-separated CORS origins and falls back to permissive CORS on Render if no origin is injected, which helps prevent first-deploy CORS failures.

### Storage Model

- Local development uses SQLite by default through `DB_PATH=agentic_shopper.db`
- Production uses `DATABASE_URL` and stores chat history in Neon Postgres 17

This lets you keep lightweight local setup while avoiding ephemeral filesystem issues in deployment.

### Neon Postgres Setup

Use Neon as the production database by setting the backend `DATABASE_URL` environment variable.

1. In Neon, copy the pooled or direct PostgreSQL connection string.
2. Make sure the URL includes `sslmode=require`.
3. In Render, open the backend service `agentic-ai-personal-shopper-api`.
4. Go to **Environment**.
5. Add or update `DATABASE_URL` with the Neon connection string.
6. Save changes and redeploy the backend service.

Do not paste the real Neon connection string into GitHub, `README.md`, or `.env.example`.

### Mixture-of-Agents Pipeline

For every shopping request, the backend:

1. Searches YouTube reviews without the official YouTube Data API.
2. Extracts available transcripts in parallel using `ThreadPoolExecutor`.
3. Sends the query plus review evidence to three OpenRouter agents concurrently with `asyncio.gather` and `httpx`:
   - Critic: flags flaws and risks.
   - Summarizer: lists the top reviewed strengths.
   - Extractor: returns structured JSON specs.
4. Sends the three Layer 1 outputs to Gemini for the final recommendation.
5. Saves `user_query`, `layer1_critic`, `layer1_summarizer`, `layer1_extractor`, and `final_synthesis` in the chat database.

The frontend displays the final answer first, with a collapsible **Behind the Scenes: AI Agent Debate** panel for the individual agent outputs.
