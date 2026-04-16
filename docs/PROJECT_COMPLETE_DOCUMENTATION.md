# Agentic AI Personal Shopper

## Complete Project Documentation

This document captures the full journey of the **Agentic AI Personal Shopper** project from initial concept to final deployed product. It is intended to serve as a complete technical and functional record of what was built, how it evolved, what problems were solved, and what the final system delivers.

---

## 1. Project Objective

The goal of this project was to build a full-stack **AI-powered shopping assistant** with a conversational interface similar to ChatGPT, Gemini, Claude, or Copilot.

The website needed to:

- Allow users to ask shopping questions in natural language
- Research products using **YouTube review videos**
- Extract review transcripts automatically
- Use an LLM to synthesize verdicts, comparisons, and follow-up answers
- Stream the response back to the user in real time
- Preserve conversation history for future use
- Provide a polished, modern, dark-themed user interface
- Be modular, deployable, and accessible publicly

The system was designed specifically around:

- **Frontend**: React + Vite + Tailwind CSS + `react-markdown`
- **Backend**: Python Flask REST API
- **AI layer**: Google Gemini via `google-generativeai`
- **YouTube retrieval**: `youtube-search-python`
- **Transcript extraction**: `youtube-transcript-api`
- **Streaming**: Server-Sent Events (SSE)

---

## 2. Initial Scope and Core Requirements

At the start, the application was planned around two primary modules:

### Module 1: Backend

The backend needed to:

- Expose a Flask API
- Separate logic into modular files:
  - `app.py` for routes and SSE
  - `agent.py` for Gemini orchestration
  - `scraper.py` for YouTube search and transcript extraction
- Use a fast “intent router” to decide whether fresh YouTube research was needed
- Search for top YouTube review videos
- Extract transcripts in **parallel** using `ThreadPoolExecutor`
- Gracefully handle transcript failures such as:
  - `TranscriptsDisabled`
  - `NoTranscriptFound`
- Stream Gemini output to the frontend in real time
- Use a system prompt that frames the LLM as a helpful shopping assistant

### Module 2: Frontend

The frontend needed to:

- Show a scrollable chat interface
- Maintain chat history
- Receive streamed text incrementally from SSE
- Show loading states while YouTube scraping is happening
- Render markdown output cleanly, including lists and formatted sections
- Support a user experience similar to modern AI chat websites

---

## 3. Final Project Architecture

The final project structure became:

```text
server/
  app.py
  agent.py
  scraper.py
  storage.py
  requirements.txt

client/
  src/
    App.jsx
    index.css
    main.jsx
    components/
      ChatBubble.jsx
      PromptComposer.jsx
      SessionSidebar.jsx
    lib/
      sse.js

render.yaml
README.md
docs/
  PROJECT_COMPLETE_DOCUMENTATION.md
```

### Backend responsibilities

- `app.py`
  - Flask app setup
  - CORS
  - SSE streaming route
  - session CRUD endpoints
  - cookie-based browser identity
  - auto-titling scheduling

- `agent.py`
  - Gemini model configuration
  - shopping system prompt
  - YouTube research tool wrapper
  - Gemini tool-calling / hybrid routing logic
  - streaming response synthesis
  - title generation logic
  - quota fallback handling
  - response quality improvements

- `scraper.py`
  - YouTube query derivation
  - video search
  - transcript fallback retrieval
  - parallel transcript extraction
  - transcript truncation and optimization

- `storage.py`
  - database schema
  - session and message storage
  - ownership filtering
  - SQLite local support
  - Postgres production support

### Frontend responsibilities

- `App.jsx`
  - overall application shell
  - session loading
  - message streaming
  - new chat / load chat / delete / rename
  - home state and active conversation state

- `SessionSidebar.jsx`
  - saved chat sidebar
  - collapse / expand behavior
  - mobile overlay
  - rename / delete menu

- `PromptComposer.jsx`
  - prompt box
  - Enter-to-send
  - Shift+Enter for multiline
  - loading / stop interaction states

- `ChatBubble.jsx`
  - assistant and user message bubbles
  - markdown rendering
  - source chip display
  - styled response display

- `client/src/lib/sse.js`
  - SSE event parsing
  - chunk handling for streaming UI updates

---

## 4. Backend Development Journey

### 4.1 Flask API and SSE Streaming

The backend was built as a Flask application with a streaming endpoint:

- `POST /api/chat` receives the user message and history
- the server performs research and LLM orchestration
- the server emits SSE events:
  - `session`
  - `status`
  - `sources`
  - `chunk`
  - `done`
  - `error`

This allowed the frontend to show:

- status updates while the agent is researching
- response text appearing chunk by chunk
- source links as soon as they were available

### 4.2 Gemini Integration

The Gemini integration evolved in several steps:

#### Initial state

- Gemini was used to generate shopping responses from research context
- streaming output was enabled to improve UX

#### Model compatibility fixes

We encountered model issues such as:

- `gemini-1.5-flash` not being found for the SDK/API version
- quota exhaustion on free-tier models

To solve this:

- model fallback logic was added
- the app now cycles through candidate models when needed
- quota and model availability errors are handled more gracefully

#### Function calling and intent handling

The system initially overused YouTube scraping for every message.

We then implemented:

- Gemini native function calling support
- a YouTube tool wrapper: `fetch_youtube_reviews`
- a tool-use policy inside the system prompt

Later, to reduce latency:

- we moved to a **hybrid approach**
- obvious fresh-research queries fast-path directly to the tool
- follow-up or ambiguous prompts can still use Gemini tool decision logic

This reduced unnecessary decision overhead while preserving intelligence for follow-ups.

### 4.3 YouTube Search and Transcript Retrieval

The research engine was designed to rely entirely on YouTube review evidence.

Implemented features:

- query normalization
- multiple derived search variants
- Indian-market-biased query shaping
- current-year query enrichment
- candidate deduplication
- transcript extraction fallback methods

Transcript extraction logic was made resilient to:

- disabled transcripts
- missing transcripts
- generated vs manual captions
- translation fallback
- inaccessible videos

### 4.4 Parallel Transcript Extraction

To optimize latency, transcript extraction uses:

- `ThreadPoolExecutor`
- asynchronous parallel fetches across multiple candidate videos

The system searches multiple videos and stops once it has enough transcript-backed results.

This significantly improved:

- research quality
- latency
- robustness when some videos fail

### 4.5 Research Cache

To prevent repeated work and improve public-site responsiveness:

- a short-lived in-memory research cache was added
- repeated or similar prompts can reuse recent research results

Benefits:

- lower latency
- lower Gemini load
- lower duplicate transcript extraction
- better behavior for repeated public usage

### 4.6 Smarter Shopping Output

The assistant prompt was refined multiple times so answers became:

- India-first
- budget-aware
- more specific
- less generic
- more grounded in review evidence

The response policy now emphasizes:

- specific product models
- approximate Indian pricing
- verdict-first answers
- concise review focus summaries
- buyer-friendly comparisons
- source-aware but non-duplicative formatting

Ambiguous prompts such as `watches under 5000` were improved so the model:

- prefers to clarify if the category is too broad
- avoids defaulting to only brand-level suggestions

### 4.7 Auto-Titling

Auto-titling went through several iterations:

#### Stage 1

- basic title generation from the first user prompt
- titles were functional but sometimes vague

#### Stage 2

- LLM-assisted background title generation
- better prompt framing for short chat titles

#### Stage 3

- stronger deterministic heuristics
- better handling of budgets and comparisons
- smarter category extraction

#### Final behavior

- chats start as `New chat`
- after the first assistant answer, one smart background title is generated
- no intermediate draft title is shown anymore

This resulted in titles like:

- `Gaming Phones Under Rs 40,000`
- `Smartwatches Under Rs 5,000`
- `MacBook Chip Comparison`
- `Robot Vacuums for Pet Hair`

---

## 5. Frontend Development Journey

### 5.1 Initial Chat Interface

The frontend started with a standard chat layout:

- input box
- user messages
- assistant messages
- markdown rendering
- streaming updates

### 5.2 Streaming Support

The frontend was built to consume SSE from Flask.

This included:

- reading the stream incrementally
- parsing SSE events
- appending assistant chunks live
- updating sources separately
- marking completion and errors properly

This made the assistant feel much more interactive.

### 5.3 UI Modernization

The interface was redesigned several times to reduce clutter and become more professional.

Final UI characteristics:

- dark theme
- centered landing state
- minimalist top bar
- collapsible left sidebar
- mobile responsive drawer
- dedicated prompt composer
- clear message hierarchy
- visually consistent chat surfaces

The design inspiration was intentionally aligned with modern AI chat interfaces like:

- ChatGPT
- Gemini
- Claude
- Copilot

### 5.4 Better Interaction Design

Several UX improvements were added:

- Enter sends the prompt
- Shift+Enter inserts a new line
- dynamic research/loading messages
- source links displayed as chips
- home navigation from the title
- simplified controls with redundant toggles removed

### 5.5 Session Sidebar

The sidebar evolved from a simple list into a proper saved chat interface with:

- persistent session list
- active session selection
- loading states
- collapse/expand behavior
- mobile support
- clean session previews

### 5.6 Rename and Delete

To make saved chats more usable:

- delete support was added
- rename support was added
- a three-dot menu was added for each session

The final session actions resemble common LLM chat products:

- `Rename`
- `Delete`

### 5.7 Home and Navigation Behavior

Further UI improvements included:

- clicking `AI Shopping Partner` returns the user to the home state
- alignment fixes in header and sidebar separators
- cleanup of starter UI elements so the user’s first prompt becomes the real start of the conversation

---

## 6. Persistence and Session Management

### 6.1 Local Persistence

The system originally stored chats locally using SQLite.

This supported:

- saving session metadata
- saving messages
- restoring chat history
- displaying saved chats in the sidebar

### 6.2 Production Persistence

For deployment, SQLite was not sufficient because Render’s free web services do not provide durable local disk in the right way for this use case.

So the storage layer was upgraded to support:

- SQLite for local development
- Postgres for production

The backend automatically uses:

- `DB_PATH` / SQLite in local mode
- `DATABASE_URL` / Postgres in Render production

### 6.3 Privacy Problem and Fix

Once the website went public, a serious issue appeared:

- all visitors could see the same saved chat history

This happened because chat sessions were not yet scoped per viewer.

To fix this:

- each browser is now assigned an anonymous secure cookie ID
- every session is stored with an `owner_id`
- session listing, loading, renaming, and deletion are filtered by that owner

Final result:

- users on different browsers no longer see each other’s chats
- saved chat history persists for the same browser
- no authentication is required

This is **browser-scoped privacy**, not full user-account authentication.

---

## 7. Deployment Journey

### 7.1 Git and GitHub

The project was initialized as a Git repository and published to GitHub so it could be deployed from source control.

### 7.2 Why Render Was Chosen

Render was selected over Vercel because:

- the backend is a long-running Flask service
- SSE streaming works naturally with a normal web process
- the architecture fits Render web services better than serverless-first platforms
- Postgres can be provisioned alongside the backend and frontend

### 7.3 Render Blueprint

Deployment was configured through `render.yaml`.

The deployment provisions:

- Flask backend service
- static frontend service
- Render Postgres database

It also wires:

- frontend API URL from the backend
- backend CORS origin from the frontend
- backend `DATABASE_URL` from Postgres

### 7.4 Live Deployment

The site was deployed publicly to Render at:

- frontend static site
- backend API service
- managed database

This required solving:

- backend health route validation
- environment variable configuration
- build and runtime alignment
- CORS
- persistence compatibility

---

## 8. Major Problems Encountered and How They Were Solved

The project went through many real-world issues. Each one improved the final system.

### 8.1 PowerShell execution policy

Problem:

- PowerShell blocked virtual environment activation and `npm` commands

Solution:

- used direct `.venv\Scripts\python`
- used `npm.cmd`
- avoided requiring execution-policy changes

### 8.2 Python dependency incompatibility

Problem:

- `youtube-transcript-api==0.6.3` did not support Python 3.14

Solution:

- updated to a compatible version

### 8.3 YouTube search breakage

Problem:

- `youtube-search-python` conflicted with newer `httpx`

Solution:

- pinned a compatible `httpx` version

### 8.4 Gemini model errors

Problem:

- older model names were not available for the SDK/API path in use

Solution:

- updated defaults and added model fallback logic

### 8.5 Invalid function calling config

Problem:

- Gemini returned:
  - `Please set allowed_function_names only when function calling mode is ANY`

Solution:

- corrected tool configuration
- aligned function-calling settings with SDK expectations

### 8.6 Public chat leakage

Problem:

- public visitors saw the same chats

Solution:

- anonymous per-browser ownership with cookie-backed session filtering

### 8.7 Generic answers

Problem:

- prompts like `watches under 5000` produced broad brand-level output

Solution:

- improved response policy
- better shopping heuristics
- category clarification behavior
- stronger model instructions for specific product recommendations

### 8.8 Slow responses

Problem:

- fresh research prompts were slow because of:
  - cold starts
  - multiple Gemini calls
  - heavy transcript payloads

Solution:

- hybrid fast-path research routing
- transcript size optimization
- candidate count tuning
- short-lived research caching

### 8.9 Vague titles

Problem:

- auto-generated chat titles were not descriptive enough

Solution:

- stronger title heuristics
- better title prompt
- smarter single-update title behavior

### 8.10 Gemini quota exhaustion

Problem:

- free-tier Gemini quota was exceeded after public usage

Solution:

- model fallback behavior
- quota-aware fallback responses
- more efficient usage patterns

This remains an external limitation of the free Gemini tier.

---

## 9. Final Feature Set

The final website includes:

### Core AI features

- conversational shopping assistant
- Gemini-powered product recommendation synthesis
- YouTube review research
- transcript-backed reasoning
- follow-up question support
- India-focused shopping responses

### Retrieval and analysis features

- YouTube search without official YouTube Data API keys
- parallel transcript extraction
- transcript fallback retrieval
- source deduplication
- lightweight research caching

### Streaming and UX features

- SSE streaming replies
- incremental text rendering
- live research status updates
- YouTube source chips shown in the UI

### Chat/session features

- saved chat sessions
- session list sidebar
- session loading
- rename sessions
- delete sessions
- single smart auto-title generation

### Privacy features

- browser-scoped session isolation
- no cross-user chat leakage

### UI features

- modern dark interface
- collapsible sidebar
- mobile responsive layout
- centered landing page
- Enter-to-send
- home navigation from the title

### Deployment features

- GitHub repository
- Render deployment
- Postgres-backed production persistence
- auto-wired frontend/backend environment setup

---

## 10. How the Final System Works End to End

The final application flow is:

1. A user opens the website.
2. The browser receives or reuses an anonymous viewer cookie.
3. The user enters a shopping prompt.
4. The frontend sends the prompt and current history to the Flask backend.
5. The backend checks whether this is a new research request or a follow-up.
6. If fresh research is needed:
   - YouTube queries are derived
   - videos are searched
   - transcripts are extracted in parallel
7. Gemini receives the shopping context and begins generating a response.
8. Flask streams the answer back over SSE.
9. The frontend renders the assistant response live, chunk by chunk.
10. Sources are displayed as clickable YouTube links.
11. The conversation is saved to the database.
12. After the first assistant answer, a smart chat title is generated in the background.
13. The chat remains visible only to that browser owner.

---

## 11. Final Deployment State

The final deployed system includes:

- GitHub-hosted source repository
- Render static frontend
- Render Flask backend
- Render Postgres database

The app is publicly accessible while still preserving private chat history per browser.

---

## 12. Known Limitations

Even though the project is complete, a few limitations remain:

### 12.1 No login-based cross-device identity

The current privacy model is browser-scoped, not account-scoped.

That means:

- the same user on a second device will not automatically see the same chats

### 12.2 Gemini free-tier quota

If the site is used by several people, the public deployment can hit Gemini free-tier rate or quota limits.

### 12.3 Cold starts on free Render

When the backend sleeps, the first public request can be slower.

### 12.4 Source strategy limited to YouTube

The app intentionally focuses on YouTube review evidence only. This keeps the architecture simple and compliant with the chosen project scope, but it means:

- pricing is approximate
- retailer-specific availability is not fetched

---

## 13. Key Engineering Decisions

The most important engineering decisions made during the project were:

1. **Use YouTube reviews as the evidence layer**
   This gave rich product-review context without requiring YouTube Data API keys.

2. **Use parallel transcript extraction**
   This significantly improved usable latency.

3. **Use SSE for streaming**
   This produced a much more modern chat experience.

4. **Use a modular Flask backend**
   This kept routing, agent logic, scraping, and storage separated cleanly.

5. **Move production persistence to Postgres**
   This made deployment realistic on Render.

6. **Use anonymous cookie-based session ownership**
   This solved public chat leakage without adding authentication complexity.

7. **Use a hybrid tool-routing approach**
   This balanced LLM intelligence with latency reduction.

---

## 14. Final Outcome

The final result is a deployable, modular, full-stack AI shopping website that:

- feels like a modern conversational assistant
- uses real YouTube review evidence
- streams answers live
- saves conversations for later use
- keeps chats private per browser
- supports ongoing follow-up questions
- is deployed publicly on Render

It moved well beyond a basic prototype and now behaves like a practical AI shopping product with real engineering depth across:

- frontend UX
- backend orchestration
- AI integration
- retrieval
- persistence
- deployment
- privacy

---

## 15. Summary in One Paragraph

This project began as a requirement to build a conversational AI personal shopper and evolved into a production-style full-stack web application with a React frontend, Flask backend, Gemini-driven synthesis, YouTube transcript-based research, SSE streaming, saved chat sessions, session rename/delete, smart auto-titling, browser-scoped privacy, GitHub version control, and public Render deployment with Postgres persistence. Along the way, multiple real-world issues such as dependency mismatches, model errors, quota limits, UI clutter, shared public chat leakage, and vague recommendation behavior were identified and systematically solved, resulting in a polished, functional, and deployable AI shopping assistant.
