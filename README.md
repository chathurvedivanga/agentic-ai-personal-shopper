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
Saved chats are stored in SQLite when `DATABASE_URL` is empty, or in Neon Postgres when `DATABASE_URL` is set.

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
- Neon is the database provider only. It does not host the Flask backend or React frontend.
- If you deploy the frontend/backend later on another platform, set `DATABASE_URL`, `VITE_API_BASE_URL`, and `CORS_ORIGIN` accordingly.

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

## Neon Postgres 17 Setup

Neon is used as the persistent database for saved chats, session titles, and MoA agent outputs.

Backend environment variables for Neon-backed storage:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODELS=gemini-2.0-flash,gemini-flash-latest
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_APP_TITLE=AI Shopping Partner
OPENROUTER_HTTP_REFERER=http://localhost:5173
CORS_ORIGIN=http://localhost:5173
DATABASE_URL=postgresql://user:password@ep-example.region.aws.neon.tech/dbname?sslmode=require
```

Setup steps:

1. In Neon, copy your pooled or direct PostgreSQL connection string.
2. Paste it into `server/.env` as `DATABASE_URL`.
3. Make sure it includes `sslmode=require`.
4. Start the Flask backend with `python app.py`.
5. Start the React frontend with `npm run dev` from `client`.

The app creates the required tables automatically on startup:

- `sessions`
- `messages`
- `moa_messages`

### Storage Model

- `DATABASE_URL` set: chat history is stored in Neon Postgres 17.
- `DATABASE_URL` empty: local development falls back to SQLite through `DB_PATH=agentic_shopper.db`.

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
