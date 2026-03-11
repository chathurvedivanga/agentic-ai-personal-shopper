# Assessment 3 - Full Stack Laboratory

## Frontend Module Implementation Report
### Project Title: Agentic AI Personal Shopper / AI Shopping Partner

**Student Name:** `<NAME>`  
**Register Number:** `<REGISTER_NUMBER>`  
**Technology Stack:** React.js (Vite), Tailwind CSS, React Markdown, Flask REST API, Server-Sent Events

## 1. Project Overview

The project developed for this assessment is an AI-driven shopping assistant called **Agentic AI Personal Shopper**, presented in the interface as **AI Shopping Partner**. The objective of the frontend is to provide a clean conversational interface through which a user can ask for product recommendations, compare alternatives, review YouTube-based shopping research, revisit earlier conversations, and continue the same chat later.

The frontend is implemented as a **single-page React application** created with Vite and styled with Tailwind CSS. Instead of using multiple web pages, the application uses a workspace-style interface similar to ChatGPT, Gemini, and Claude. This approach keeps the shopping flow continuous and makes follow-up questions feel natural. The frontend communicates with the Flask backend through REST APIs and receives live assistant output using **Server-Sent Events (SSE)**.

## 2. Frontend Architecture

The frontend is modular and component-based. The main orchestration happens in `App.jsx`, while specialized UI behavior is delegated to reusable components:

- `App.jsx`: main application state, API integration, session loading, SSE streaming, home/chat switching.
- `PromptComposer.jsx`: prompt input box, submit handling, Enter-to-send behavior, stop button, and status text.
- `SessionSidebar.jsx`: saved chat list, collapsible side panel, new chat action, rename and delete controls.
- `ChatBubble.jsx`: renders assistant and user messages, markdown formatting, loading state, and YouTube source chips.
- `lib/sse.js`: parses streamed events coming from the Flask backend.

This design improves maintainability because each UI responsibility is isolated into a dedicated module.

## 3. User Interface Design

The frontend follows a dark, professional, low-clutter design intended for long sessions of reading shopping recommendations. The major UI sections are:

### 3.1 Home / Landing View

The landing view displays:

- the centered title **AI Shopping Partner**
- a large prompt composer
- starter prompts for common shopping use cases

This view acts as the entry point for new users and new sessions. It is intentionally minimal so the prompt box remains the main focus.

### 3.2 Conversation Workspace

Once the user submits a prompt, the interface transitions into the conversation workspace. This area contains:

- the active chat title
- user and assistant chat bubbles
- live streaming response output
- YouTube links used as supporting evidence
- the bottom prompt composer for follow-up questions

The assistant reply supports markdown formatting through `react-markdown`, which allows readable verdicts, pros/cons, shortlists, headings, and linked references.

### 3.3 Saved Chats Sidebar

The left sidebar stores earlier conversations and behaves like a modern AI product sidebar. It supports:

- creating a new chat
- loading older chats from the database
- collapsing on desktop to save space
- opening as an overlay on mobile
- renaming a chat
- deleting a chat

This gives the project a production-style user experience rather than a simple one-time prompt page.

## 4. Routing and Navigation

This project does **not use React Router**. The frontend is implemented as a **single-workspace SPA** where navigation is handled by React state instead of URL-based routes. This decision is appropriate because the application behavior is centered around one conversational workspace rather than many independent pages.

Navigation is achieved through the following state-driven transitions:

- selecting **New chat** resets the interface to a draft conversation
- clicking **AI Shopping Partner** returns the user to the home state
- selecting a saved session loads the corresponding conversation from the backend
- collapsing or expanding the sidebar changes the available workspace width
- on mobile, the sidebar opens as a drawer and closes after a session is selected

The collapsed state of the sidebar is stored in `localStorage`, so the desktop preference is preserved across refreshes.

## 5. User Interaction Handling

The frontend includes several interaction-handling mechanisms to make the chat system responsive and user-friendly.

### 5.1 Prompt Input and Form Handling

The prompt box is implemented as a controlled textarea. Important behaviors include:

- Enter sends the prompt
- Shift + Enter inserts a new line
- empty prompts are blocked
- the textarea is limited to 2000 characters
- a live character count is shown

This prevents invalid input and improves usability for both short and detailed shopping questions.

### 5.2 API Request Handling

When a prompt is sent, the frontend submits a `POST /api/chat` request containing:

- the new message
- prior chat history
- the active session ID, when available

The response is consumed as an SSE stream. The frontend listens for multiple event types such as:

- `session`
- `status`
- `sources`
- `chunk`
- `error`
- `done`

This allows the assistant to type its answer progressively, similar to commercial AI chat interfaces.

### 5.3 Real-Time Feedback

The user receives immediate feedback while the backend is processing:

- status text while research is being prepared
- streaming assistant text during generation
- a stop button during active streaming
- error banners if the network or backend fails
- automatic scroll to the latest message

These details significantly improve perceived responsiveness.

### 5.4 Saved Chat Actions

The frontend supports persistent chat management:

- rename chat title using a three-dot action menu
- delete unwanted chats
- load existing threads for future follow-up questions

This makes the interface suitable for long-term product research rather than one-off interactions.

## 6. Responsive User Interface

Responsiveness is an important part of the frontend implementation. The same application layout adapts to desktop and mobile screens using flexible Tailwind utility classes and conditional UI behavior.

Responsive decisions include:

- fixed sidebar on desktop, drawer sidebar on mobile
- collapsible desktop sidebar for more reading space
- scrollable chat area with fixed composer
- constrained content width for better readability
- adaptive spacing and typography across screen sizes

This ensures the website remains usable on laptops, tablets, and phones without redesigning the entire structure.

## 7. Component-Based Design and Dynamic Data Rendering

The project strongly follows component-based development. Instead of hardcoding content, the UI is rendered from dynamic state.

Examples of dynamic rendering:

- the sidebar maps over the `sessions` array to display saved chats
- the conversation area maps over the `messages` array to display user and assistant messages
- assistant source links are rendered only when source data exists
- chat titles are updated after the backend auto-titles the session
- active session ordering is refreshed after rename, delete, or new responses

This pattern reduces duplication and makes the UI easier to extend.

## 8. API Documentation for Frontend Integration

The frontend uses the following backend endpoints:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/sessions` | GET | Fetch all saved chat sessions for the sidebar |
| `/api/sessions/<id>` | GET | Load a selected conversation and its messages |
| `/api/sessions/<id>` | PATCH | Rename a chat title |
| `/api/sessions/<id>` | DELETE | Delete a saved chat |
| `/api/chat` | POST | Send the current message and receive an SSE response |

The `/api/chat` route streams structured events that allow the frontend to update the UI incrementally instead of waiting for the full response.

## 9. Conclusion

The frontend of **Agentic AI Personal Shopper** was implemented as a modern React single-page application focused on clarity, responsiveness, and continuity of user interaction. The system combines a clean landing page, a chat-first research workspace, persistent conversation history, real-time streaming, and responsive layout behavior. From an engineering perspective, the frontend demonstrates component-based design, asynchronous event handling, dynamic data rendering, and practical user experience improvements suitable for a production-style AI assistant.

---

## Appendix A - Frontend Code Summary

### A.1 UI Components

- `App.jsx` coordinates application state and screen transitions.
- `PromptComposer.jsx` handles prompt entry, submission, and active-stream controls.
- `SessionSidebar.jsx` manages chat history visibility and session actions.
- `ChatBubble.jsx` renders formatted conversation content and YouTube source links.

### A.2 Form Handling

Key form-handling logic:

```jsx
function handleComposerKeyDown(event) {
  if (event.nativeEvent?.isComposing || event.key !== "Enter" || event.shiftKey) {
    return;
  }

  event.preventDefault();
  if (!isBusy && input.trim()) {
    void sendMessage();
  }
}
```

This ensures the prompt is sent with Enter while still supporting multi-line input with Shift + Enter.

### A.3 SSE Streaming Logic

```jsx
if (event.event === "chunk") {
  setStatusText("");
  appendAssistantChunk(assistantMessageId, payload.text || "");
}
```

This enables real-time assistant output instead of waiting for a complete response.

### A.4 Routing Logic

The application uses state-based routing instead of React Router:

```jsx
function handleGoHome() {
  startNewChat({ keepSidebarOpen: false });
}
```

This design is sufficient because the application is centered around one conversational workspace rather than multiple independent route pages.

### A.5 Frontend Files Referenced

- `client/src/App.jsx`
- `client/src/components/PromptComposer.jsx`
- `client/src/components/SessionSidebar.jsx`
- `client/src/components/ChatBubble.jsx`
- `client/src/lib/sse.js`

### A.6 Submission Note

Before submission, replace `<NAME>` and `<REGISTER_NUMBER>`, then export this document as PDF using the format:

`Assessment 3_FullStack_<RegisterNumber>_<Name>.pdf`
