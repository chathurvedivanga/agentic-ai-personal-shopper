import { useEffect, useRef, useState } from "react";
import ChatBubble from "./components/ChatBubble";
import PromptComposer from "./components/PromptComposer";
import SessionSidebar from "./components/SessionSidebar";
import { consumeSseEvents, parseJsonPayload } from "./lib/sse";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const SIDEBAR_STORAGE_KEY = "shopper-sidebar-collapsed";

const starterPrompts = [
  "Recommend a gaming phone under Rs 40,000 in India",
  "Compare the best robot vacuums for pet hair in India",
  "Which budget laptop is best for college in India in 2026?"
];

function SidebarToggleIcon() {
  return (
    <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24">
      <path
        d="M4 7h16M4 12h16M4 17h16"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function createDraftMessages() {
  return [];
}

function makeId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sanitizeHistory(messages) {
  return messages
    .filter((message) => !message.transient && message.content?.trim())
    .map(({ role, content }) => ({ role, content }));
}

function hydrateMessages(serverMessages) {
  if (!serverMessages?.length) {
    return createDraftMessages();
  }

  return serverMessages.map((message) => ({
    id: message.id || makeId(),
    role: message.role,
    content: message.content || "",
    sources: Array.isArray(message.sources) ? message.sources : [],
    pending: false,
    error: false,
    transient: false,
    createdAt: message.created_at || ""
  }));
}

function sortSessions(items) {
  return [...items].sort((left, right) =>
    (right.updated_at || "").localeCompare(left.updated_at || "")
  );
}

function upsertSession(currentSessions, nextSession) {
  if (!nextSession?.id) {
    return currentSessions;
  }

  const remaining = currentSessions.filter((session) => session.id !== nextSession.id);
  return sortSessions([nextSession, ...remaining]);
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const details = await response.text();
    throw new Error(details || "Request failed.");
  }

  return response.json();
}

function isDesktopViewport() {
  if (typeof window === "undefined") {
    return true;
  }

  return window.innerWidth >= 1024;
}

export default function App() {
  const [messages, setMessages] = useState(createDraftMessages);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [deletingSessionId, setDeletingSessionId] = useState(null);
  const [renamingSessionId, setRenamingSessionId] = useState(null);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
  });
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [bannerError, setBannerError] = useState("");
  const bottomRef = useRef(null);
  const abortRef = useRef(null);
  const titleRefreshTimeoutRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, statusText]);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, isSidebarCollapsed ? "1" : "0");
  }, [isSidebarCollapsed]);

  useEffect(() => {
    void initializeApp();

    return () => {
      abortRef.current?.abort();
      if (titleRefreshTimeoutRef.current) {
        clearTimeout(titleRefreshTimeoutRef.current);
      }
    };
  }, []);

  async function initializeApp() {
    setIsLoadingSessions(true);
    setBannerError("");

    try {
      const payload = await fetchJson("/api/sessions");
      const items = sortSessions(payload.items || []);
      setSessions(items);

      if (items.length) {
        await loadSession(items[0].id, { suppressSidebarLoading: true, keepSidebarOpen: false });
      } else {
        startNewChat({ preserveInput: true, keepSidebarOpen: false });
      }
    } catch (error) {
      setBannerError(error.message || "Failed to load saved chats.");
      startNewChat({ preserveInput: true, keepSidebarOpen: false });
    } finally {
      setIsLoadingSessions(false);
    }
  }

  function patchMessage(messageId, updater) {
    setMessages((current) =>
      current.map((message) => (message.id === messageId ? updater(message) : message))
    );
  }

  function appendAssistantChunk(messageId, text) {
    patchMessage(messageId, (message) => ({
      ...message,
      content: `${message.content || ""}${text}`,
      pending: true,
      error: false
    }));
  }

  function setAssistantSources(messageId, sources) {
    patchMessage(messageId, (message) => ({
      ...message,
      sources
    }));
  }

  function finishAssistantMessage(messageId) {
    patchMessage(messageId, (message) => ({
      ...message,
      pending: false
    }));
  }

  function failAssistantMessage(messageId, errorMessage) {
    patchMessage(messageId, (message) => ({
      ...message,
      content: message.content || `I hit an error: ${errorMessage}`,
      pending: false,
      error: true
    }));
  }

  function scheduleSessionRefresh() {
    if (titleRefreshTimeoutRef.current) {
      clearTimeout(titleRefreshTimeoutRef.current);
    }

    titleRefreshTimeoutRef.current = window.setTimeout(() => {
      void refreshSessions();
    }, 1800);
  }

  async function refreshSessions() {
    try {
      const payload = await fetchJson("/api/sessions");
      setSessions(sortSessions(payload.items || []));
    } catch {
      // Keep current sidebar state if refresh fails.
    }
  }

  async function loadSession(sessionId, options = {}) {
    if (!sessionId) {
      startNewChat({ keepSidebarOpen: false });
      return;
    }

    setBannerError("");
    setStatusText("");
    setIsLoadingConversation(true);

    try {
      const payload = await fetchJson(`/api/sessions/${sessionId}`);
      setActiveSessionId(sessionId);
      setMessages(hydrateMessages(payload.messages || []));
      if (payload.session) {
        setSessions((current) => upsertSession(current, payload.session));
      }
      if (!options.keepSidebarOpen) {
        setIsMobileSidebarOpen(false);
      }
    } catch (error) {
      setBannerError(error.message || "Failed to load the selected chat.");
    } finally {
      setIsLoadingConversation(false);
      if (!options.suppressSidebarLoading) {
        setIsLoadingSessions(false);
      }
    }
  }

  function startNewChat(options = {}) {
    abortRef.current?.abort();
    abortRef.current = null;
    setActiveSessionId(null);
    setMessages(createDraftMessages());
    if (!options.preserveInput) {
      setInput("");
    }
    setBannerError("");
    setStatusText("");
    setIsSubmitting(false);
    setIsLoadingConversation(false);
    if (!options.keepSidebarOpen) {
      setIsMobileSidebarOpen(false);
    }
  }

  async function sendMessage(overrideText) {
    const text = (overrideText ?? input).trim();
    if (!text || isSubmitting || isLoadingConversation) {
      return;
    }

    const userMessage = {
      id: makeId(),
      role: "user",
      content: text,
      sources: [],
      pending: false,
      error: false,
      transient: false
    };

    const assistantMessageId = makeId();
    const requestHistory = sanitizeHistory(messages).concat({
      role: "user",
      content: text
    });

    let resolvedSessionId = activeSessionId;

    setMessages((current) => [
      ...current,
      userMessage,
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        sources: [],
        pending: true,
        error: false,
        transient: false
      }
    ]);
    setInput("");
    setBannerError("");
    setStatusText("Agent is evaluating whether fresh review research is needed...");
    setIsSubmitting(true);
    setIsMobileSidebarOpen(false);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream"
        },
        body: JSON.stringify({
          message: text,
          history: requestHistory,
          session_id: activeSessionId
        }),
        signal: controller.signal
      });

      if (!response.ok || !response.body) {
        const details = await response.text();
        throw new Error(details || "The backend did not return a stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parsed = consumeSseEvents(buffer);
        buffer = parsed.remainder;

        for (const event of parsed.events) {
          const payload = parseJsonPayload(event.data);

          if (event.event === "session") {
            const session = payload.session;
            if (session?.id) {
              resolvedSessionId = session.id;
              setActiveSessionId(session.id);
              setSessions((current) => upsertSession(current, session));
            }
            continue;
          }

          if (event.event === "status") {
            setStatusText(payload.message || "Agent is working...");
            continue;
          }

          if (event.event === "sources") {
            setAssistantSources(assistantMessageId, payload.items || []);
            continue;
          }

          if (event.event === "chunk") {
            setStatusText("");
            appendAssistantChunk(assistantMessageId, payload.text || "");
            continue;
          }

          if (event.event === "error") {
            setStatusText("");
            failAssistantMessage(assistantMessageId, payload.message || "Unknown error.");
            setBannerError(payload.message || "The assistant failed to finish the response.");
            continue;
          }

          if (event.event === "done") {
            setStatusText("");
            finishAssistantMessage(assistantMessageId);
            if (payload.session) {
              setSessions((current) => upsertSession(current, payload.session));
            }
          }
        }
      }

      finishAssistantMessage(assistantMessageId);
    } catch (error) {
      if (error.name !== "AbortError") {
        const message =
          error.message || "Network error while streaming the assistant response.";
        failAssistantMessage(assistantMessageId, message);
        setBannerError(message);
      } else {
        finishAssistantMessage(assistantMessageId);
      }
    } finally {
      abortRef.current = null;
      setStatusText("");
      setIsSubmitting(false);
      await refreshSessions();
      if (resolvedSessionId) {
        setActiveSessionId(resolvedSessionId);
        scheduleSessionRefresh();
      }
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    void sendMessage();
  }

  function handleComposerKeyDown(event) {
    if (event.nativeEvent?.isComposing || event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();
    if (!isBusy && input.trim()) {
      void sendMessage();
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatusText("");
    setIsSubmitting(false);
  }

  function handleSelectSession(sessionId) {
    if (sessionId === null) {
      startNewChat({ preserveInput: true });
      return;
    }

    if (sessionId === activeSessionId || isSubmitting) {
      return;
    }

    void loadSession(sessionId);
  }

  async function handleDeleteSession(sessionId) {
    if (!sessionId || isBusy || deletingSessionId || renamingSessionId) {
      return;
    }

    const targetSession = sessions.find((session) => session.id === sessionId);
    const title = targetSession?.title || "this chat";
    const confirmed = window.confirm(`Delete "${title}"? This cannot be undone.`);
    if (!confirmed) {
      return;
    }

    setBannerError("");
    setDeletingSessionId(sessionId);
    const remainingSessions = sessions.filter((session) => session.id !== sessionId);

    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: "DELETE"
      });

      if (!response.ok) {
        const details = await response.text();
        throw new Error(details || "Failed to delete the selected chat.");
      }

      setSessions(remainingSessions);

      if (sessionId === activeSessionId) {
        if (remainingSessions.length) {
          await loadSession(remainingSessions[0].id, {
            suppressSidebarLoading: true,
            keepSidebarOpen: false
          });
        } else {
          startNewChat({ preserveInput: true, keepSidebarOpen: false });
        }
      }
    } catch (error) {
      setBannerError(error.message || "Failed to delete the selected chat.");
      await refreshSessions();
    } finally {
      setDeletingSessionId(null);
    }
  }

  async function handleRenameSession(sessionId, nextTitle) {
    const title = (nextTitle || "").trim();
    if (!sessionId || !title || isBusy || renamingSessionId || deletingSessionId) {
      return false;
    }

    setBannerError("");
    setRenamingSessionId(sessionId);

    try {
      const response = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ title })
      });

      if (!response.ok) {
        const details = await response.text();
        throw new Error(details || "Failed to rename the selected chat.");
      }

      const payload = await response.json();
      if (payload.session) {
        setSessions((current) => upsertSession(current, payload.session));
      }
      return true;
    } catch (error) {
      setBannerError(error.message || "Failed to rename the selected chat.");
      return false;
    } finally {
      setRenamingSessionId(null);
    }
  }

  function handleToggleSidebar() {
    if (isDesktopViewport()) {
      setIsSidebarCollapsed((current) => !current);
      return;
    }

    setIsMobileSidebarOpen((current) => !current);
  }

  function handleCloseMobileSidebar() {
    setIsMobileSidebarOpen(false);
  }

  function handleGoHome() {
    startNewChat({ keepSidebarOpen: false });
  }

  const activeSession = sessions.find((session) => session.id === activeSessionId) || null;
  const isBusy =
    isSubmitting ||
    isLoadingConversation ||
    Boolean(deletingSessionId) ||
    Boolean(renamingSessionId);
  const showLanding = !isLoadingConversation && messages.length === 0;

  return (
    <main className="min-h-screen bg-[#07090d] text-stone-100">
        <SessionSidebar
          activeSessionId={activeSessionId}
          deletingSessionId={deletingSessionId}
          hasDraft={activeSessionId === null}
          isBusy={isBusy}
          isCollapsed={isSidebarCollapsed}
          isLoading={isLoadingSessions}
          isMobileOpen={isMobileSidebarOpen}
          onCloseMobile={handleCloseMobileSidebar}
          onDeleteSession={handleDeleteSession}
          onGoHome={handleGoHome}
          onNewChat={() => startNewChat()}
          onRenameSession={handleRenameSession}
          onSelectSession={handleSelectSession}
          renamingSessionId={renamingSessionId}
          sessions={sessions}
        />

      <div
        className={`flex min-h-screen min-w-0 flex-col transition-[margin] duration-300 ${
          isSidebarCollapsed ? "lg:ml-[84px]" : "lg:ml-[290px]"
        }`}
      >
        <header className="sticky top-0 z-20 bg-[#07090d]/88 backdrop-blur-xl after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-white/6">
          <div className="relative flex h-16 items-center justify-between px-4 sm:px-6">
            <div className="flex items-center">
              <button
                aria-label="Toggle sidebar"
                className="inline-flex rounded-full border border-white/10 p-2.5 text-stone-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                onClick={handleToggleSidebar}
                type="button"
              >
                <SidebarToggleIcon />
              </button>
            </div>

            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              <button
                className="font-display rounded-full px-3 py-1 text-lg font-medium tracking-[0.02em] text-white transition hover:bg-white/[0.04] hover:text-stone-100 sm:text-xl"
                onClick={handleGoHome}
                type="button"
              >
                AI Shopping Partner
              </button>
            </div>
          </div>
        </header>

        {bannerError ? (
          <div className="px-4 pt-4 sm:px-6">
            <div className="mx-auto max-w-4xl rounded-[22px] border border-red-400/20 bg-red-950/25 px-4 py-3 text-sm text-red-100">
              {bannerError}
            </div>
          </div>
        ) : null}

        {showLanding ? (
          <section className="flex flex-1 flex-col px-4 pb-10 pt-8 sm:px-6">
            <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center">
              <div className="max-w-2xl text-center">
                <p className="text-xs uppercase tracking-[0.34em] text-stone-500">
                  Personal shopping research
                </p>
                <h1 className="font-display mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                  AI Shopping Partner
                </h1>
                <p className="mx-auto mt-4 max-w-xl text-base leading-7 text-stone-400">
                  Ask for recommendations, compare options, and revisit earlier research from the
                  sidebar whenever you need to continue a buying decision.
                </p>
              </div>

              <div className="mt-8 w-full max-w-3xl">
                <PromptComposer
                  input={input}
                  isBusy={isBusy}
                  isSubmitting={isSubmitting}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  onStop={handleStop}
                  onSubmit={handleSubmit}
                  statusText={statusText}
                  variant="landing"
                />
              </div>

              <div className="mt-6 flex w-full max-w-4xl flex-wrap justify-center gap-3">
                {starterPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-stone-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                    disabled={isBusy}
                    onClick={() => setInput(prompt)}
                    type="button"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </section>
        ) : (
          <section className="flex min-h-0 flex-1 flex-col px-4 py-4 sm:px-6">
            <div className="mx-auto flex w-full max-w-4xl min-h-0 flex-1 flex-col">
              <div className="mb-4">
                <h2 className="text-lg font-medium text-white">
                  {activeSession?.title || "New chat"}
                </h2>
              </div>

              <section className="main-surface flex min-h-0 flex-1 flex-col overflow-hidden rounded-[30px] border border-white/6">
                <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
                  {isLoadingConversation ? (
                    <div className="flex h-full items-center justify-center">
                      <div className="rounded-[24px] border border-white/8 bg-white/[0.03] px-5 py-4 text-sm text-stone-400">
                        Loading saved conversation...
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      {messages.map((message) => (
                        <ChatBubble
                          key={message.id}
                          loadingText={statusText}
                          message={message}
                        />
                      ))}
                      <div ref={bottomRef} />
                    </div>
                  )}
                </div>

                <div className="border-t border-white/6 bg-black/15 px-4 py-4 sm:px-6">
                  <PromptComposer
                    input={input}
                    isBusy={isBusy}
                    isSubmitting={isSubmitting}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={handleComposerKeyDown}
                    onStop={handleStop}
                    onSubmit={handleSubmit}
                    statusText={statusText}
                    variant="chat"
                  />
                </div>
              </section>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
