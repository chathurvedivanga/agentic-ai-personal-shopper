import { useEffect, useRef, useState } from "react";

function PlusIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" viewBox="0 0 24 24">
      <path
        d="M12 5v14M5 12h14"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="5" r="1.8" />
      <circle cx="12" cy="12" r="1.8" />
      <circle cx="12" cy="19" r="1.8" />
    </svg>
  );
}

function ChevronIcon({ className = "" }) {
  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 24 24">
      <path
        d="M15 6l-6 6 6 6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function formatUpdatedAt(value) {
  if (!value) {
    return "";
  }

  const date = new Date(`${value}Z`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short"
  }).format(date);
}

function sessionInitial(session) {
  const label = (session.title || "Chat").trim();
  return label.charAt(0).toUpperCase() || "C";
}

export default function SessionSidebar({
  sessions,
  activeSessionId,
  deletingSessionId,
  hasDraft,
  isBusy,
  isCollapsed,
  isLoading,
  isMobileOpen,
  onCloseMobile,
  onDeleteSession,
  onGoHome,
  onNewChat,
  onRenameSession,
  onSelectSession,
  renamingSessionId
}) {
  const [menuSessionId, setMenuSessionId] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [draftTitle, setDraftTitle] = useState("");
  const menuRootRef = useRef(null);
  const renderCollapsed = isCollapsed && !isMobileOpen;

  useEffect(() => {
    if (!menuSessionId) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (!menuRootRef.current?.contains(event.target)) {
        setMenuSessionId(null);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [menuSessionId]);

  function handleOpenRename(session) {
    setMenuSessionId(null);
    setEditingSessionId(session.id);
    setDraftTitle(session.title || "");
  }

  async function handleRenameSubmit(sessionId) {
    const nextTitle = draftTitle.trim();
    if (!nextTitle) {
      return;
    }

    const didRename = await onRenameSession(sessionId, nextTitle);
    if (didRename) {
      setEditingSessionId(null);
      setDraftTitle("");
    }
  }

  function handleRenameKeyDown(event, sessionId) {
    if (event.key === "Enter") {
      event.preventDefault();
      void handleRenameSubmit(sessionId);
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setEditingSessionId(null);
      setDraftTitle("");
    }
  }

  return (
    <>
      <div
        aria-hidden="true"
        className={`fixed inset-0 z-30 bg-black/60 backdrop-blur-sm transition lg:hidden ${
          isMobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onCloseMobile}
      />

      <aside
        className={`sidebar-surface fixed inset-y-0 left-0 z-40 flex h-full flex-col border-r border-white/6 transition-all duration-300 ${
          isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        } w-[290px] ${renderCollapsed ? "lg:w-[84px]" : "lg:w-[290px]"}`}
      >
        <div className="relative flex h-16 items-center justify-between px-4 after:absolute after:inset-x-0 after:bottom-0 after:h-px after:bg-white/6">
          <div className={`flex items-center gap-3 ${renderCollapsed ? "lg:justify-center" : ""}`}>
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/8 font-display text-sm font-semibold text-white">
              AI
            </span>
            {!renderCollapsed ? (
              <button
                className="min-w-0 rounded-2xl px-2 py-1 text-left transition hover:bg-white/[0.04]"
                onClick={onGoHome}
                type="button"
              >
                <p className="truncate text-sm font-medium text-white">AI Shopping Partner</p>
                <p className="text-xs uppercase tracking-[0.18em] text-stone-500">Chats</p>
              </button>
            ) : null}
          </div>

          <button
            aria-label="Close sidebar"
            className="rounded-full border border-white/10 p-2 text-stone-300 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white lg:hidden"
            onClick={onCloseMobile}
            type="button"
          >
            <ChevronIcon className="h-4 w-4 rotate-180" />
          </button>
        </div>

        <div className="border-b border-white/6 px-3 py-3">
          <button
            className={`inline-flex items-center rounded-2xl border border-white/10 bg-white/[0.04] text-sm font-medium text-white transition hover:border-white/20 hover:bg-white/[0.07] disabled:opacity-60 ${
              renderCollapsed ? "h-12 w-12 justify-center" : "w-full gap-3 px-4 py-3"
            }`}
            disabled={isBusy}
            onClick={onNewChat}
            title="New chat"
            type="button"
          >
            <PlusIcon />
            {!renderCollapsed ? <span>New chat</span> : null}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3">
          {renderCollapsed ? (
            <div className="space-y-2">
              {hasDraft ? (
                <button
                  className={`flex h-12 w-12 items-center justify-center rounded-2xl border text-sm font-semibold transition ${
                    activeSessionId === null
                      ? "border-white/20 bg-white/[0.08] text-white"
                      : "border-white/10 bg-white/[0.03] text-stone-300 hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                  }`}
                  disabled={isBusy}
                  onClick={() => onSelectSession(null)}
                  title="Draft chat"
                  type="button"
                >
                  D
                </button>
              ) : null}

              {sessions.slice(0, 8).map((session) => (
                <button
                  key={session.id}
                  className={`flex h-12 w-12 items-center justify-center rounded-2xl border text-sm font-semibold transition ${
                    session.id === activeSessionId
                      ? "border-white/20 bg-white/[0.08] text-white"
                      : "border-white/10 bg-white/[0.03] text-stone-300 hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                  }`}
                  disabled={isBusy}
                  onClick={() => onSelectSession(session.id)}
                  title={session.title || "Saved chat"}
                  type="button"
                >
                  {sessionInitial(session)}
                </button>
              ))}
            </div>
          ) : (
            <>
              {hasDraft ? (
                <button
                  className={`mb-2 w-full rounded-[22px] border px-4 py-3 text-left transition ${
                    activeSessionId === null
                      ? "border-white/20 bg-white/[0.08] shadow-[0_14px_30px_rgba(0,0,0,0.18)]"
                      : "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                  }`}
                  disabled={isBusy}
                  onClick={() => onSelectSession(null)}
                  type="button"
                >
                  <p className="text-sm font-medium text-white">Draft chat</p>
                  <p className="mt-1 text-xs text-stone-500">Start a fresh shopping conversation</p>
                </button>
              ) : null}

              {isLoading ? (
                <div className="rounded-[22px] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-stone-400">
                  Loading chats...
                </div>
              ) : null}

              {!isLoading && !sessions.length ? (
                <div className="rounded-[22px] border border-dashed border-white/10 bg-white/[0.03] px-4 py-5 text-sm text-stone-400">
                  Saved chats will appear here after your first message.
                </div>
              ) : null}

              <div className="space-y-2" ref={menuRootRef}>
                {sessions.map((session) => {
                  const isActive = session.id === activeSessionId;
                  const isDeleting = session.id === deletingSessionId;
                  const isRenaming = session.id === editingSessionId;
                  const isSavingRename = session.id === renamingSessionId;
                  const isMenuOpen = session.id === menuSessionId;

                  return (
                    <div
                      key={session.id}
                      className={`group relative rounded-[22px] border transition cursor-pointer ${
                        isActive
                          ? "border-white/20 bg-white/[0.08] shadow-[0_16px_30px_rgba(0,0,0,0.18)]"
                          : "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                      }`}
                      onClick={() => onSelectSession(session.id)}
                    >
                      {isRenaming ? (
                        <div className="px-4 py-4" onClick={(e) => e.stopPropagation()}>
                          <input
                            autoFocus
                            className="w-full rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none transition focus:border-white/20"
                            maxLength={80}
                            onChange={(event) => setDraftTitle(event.target.value)}
                            onKeyDown={(event) => handleRenameKeyDown(event, session.id)}
                            value={draftTitle}
                          />
                          <div className="mt-3 flex items-center justify-end gap-2">
                            <button
                              className="rounded-full border border-white/10 px-3 py-1.5 text-xs uppercase tracking-[0.14em] text-stone-400 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                              onClick={() => {
                                setEditingSessionId(null);
                                setDraftTitle("");
                              }}
                              type="button"
                            >
                              Cancel
                            </button>
                            <button
                              className="rounded-full bg-white px-3 py-1.5 text-xs font-medium uppercase tracking-[0.14em] text-stone-950 transition hover:bg-stone-200 disabled:opacity-50"
                              disabled={!draftTitle.trim() || isSavingRename}
                              onClick={() => {
                                void handleRenameSubmit(session.id);
                              }}
                              type="button"
                            >
                              {isSavingRename ? "Saving" : "Save"}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="w-full px-4 py-3 pr-14 text-left">
                            <div className="flex items-start justify-between gap-3">
                              <p className="line-clamp-2 text-sm font-medium text-white">
                                {session.title || "New chat"}
                              </p>
                              <span className="shrink-0 text-[11px] uppercase tracking-[0.12em] text-stone-600">
                                {formatUpdatedAt(session.updated_at)}
                              </span>
                            </div>

                            <p className="mt-2 line-clamp-2 text-xs leading-5 text-stone-500">
                              {session.last_message_preview || "Waiting for the first reply..."}
                            </p>
                          </div>

                          <button
                            aria-label={`Open actions for ${session.title || "chat"}`}
                            className="absolute right-3 top-3 inline-flex rounded-full border border-white/10 p-2 text-stone-500 transition hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                            disabled={isBusy}
                            onClick={(e) => {
                              e.stopPropagation();
                              setMenuSessionId((current) =>
                                current === session.id ? null : session.id
                              );
                            }}
                            type="button"
                          >
                            <DotsIcon />
                          </button>

                          {isMenuOpen ? (
                            <div className="absolute right-3 top-12 z-10 min-w-[140px] rounded-2xl border border-white/10 bg-[#101319] p-1.5 shadow-[0_18px_40px_rgba(0,0,0,0.3)]">
                              <button
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-stone-200 transition hover:bg-white/[0.05] hover:text-white"
                                onClick={() => handleOpenRename(session)}
                                type="button"
                              >
                                Rename
                              </button>
                              <button
                                className="block w-full rounded-xl px-3 py-2 text-left text-sm text-red-200 transition hover:bg-red-500/10 hover:text-red-100"
                                onClick={() => {
                                  setMenuSessionId(null);
                                  onDeleteSession(session.id);
                                }}
                                type="button"
                              >
                                {isDeleting ? "Deleting..." : "Delete"}
                              </button>
                            </div>
                          ) : null}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
