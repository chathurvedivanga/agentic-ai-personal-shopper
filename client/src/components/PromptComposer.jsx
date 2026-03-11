function SendIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M5 12h12M13 4l8 8-8 8"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export default function PromptComposer({
  input,
  isBusy,
  isSubmitting,
  onChange,
  onKeyDown,
  onStop,
  onSubmit,
  statusText,
  variant = "chat"
}) {
  const isLanding = variant === "landing";

  return (
    <form
      className={`rounded-[30px] border border-white/10 bg-[#111318]/95 shadow-[0_22px_60px_rgba(0,0,0,0.28)] ${
        isLanding ? "p-4 sm:p-5" : "p-3.5"
      }`}
      onSubmit={onSubmit}
    >
      <label className="sr-only" htmlFor="message">
        Shopping prompt
      </label>
      <div className="rounded-[24px] border border-white/6 bg-black/25 px-4 py-3">
        <textarea
          className={`w-full resize-none bg-transparent text-stone-100 outline-none placeholder:text-stone-500 ${
            isLanding ? "min-h-[124px] text-[1rem] leading-7" : "min-h-[110px] text-[0.98rem] leading-7"
          }`}
          disabled={isBusy}
          id="message"
          maxLength={2000}
          onChange={onChange}
          onKeyDown={onKeyDown}
          placeholder="Ask about any product, budget, comparison, or follow-up..."
          value={input}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="min-w-0">
          <p className="truncate text-sm text-stone-400">
            {statusText || "Press Enter to send. Use Shift + Enter for a new line."}
          </p>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-stone-500">
            {input.trim().length}/2000
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isSubmitting ? (
            <button
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-stone-300 transition hover:border-white/20 hover:bg-white/[0.04] hover:text-white"
              onClick={onStop}
              type="button"
            >
              Stop
            </button>
          ) : null}

          <button
            className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-stone-950 transition hover:bg-stone-200 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isBusy || !input.trim()}
            type="submit"
          >
            <span>{isSubmitting ? "Working" : "Send"}</span>
            <SendIcon />
          </button>
        </div>
      </div>
    </form>
  );
}
