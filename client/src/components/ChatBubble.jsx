import { useState } from "react";
import ReactMarkdown from "react-markdown";

const markdownComponents = {
  a: ({ ...props }) => (
    <a
      {...props}
      className="text-amber-200 underline decoration-amber-400/40 underline-offset-4 transition hover:text-amber-100"
      rel="noreferrer"
      target="_blank"
    />
  ),
  h2: ({ ...props }) => (
    <h2
      {...props}
      className="mt-6 mb-3 text-xl font-semibold tracking-tight text-white first:mt-0"
    />
  ),
  h3: ({ ...props }) => (
    <h3
      {...props}
      className="mt-5 mb-3 text-sm font-semibold uppercase tracking-[0.18em] text-amber-200"
    />
  ),
  h4: ({ ...props }) => (
    <h4
      {...props}
      className="mt-4 mb-2 rounded-2xl border border-amber-300/15 bg-amber-300/8 px-3 py-2 text-base font-semibold text-amber-50"
    />
  ),
  p: ({ ...props }) => <p {...props} className="mb-3 last:mb-0" />,
  ul: ({ ...props }) => <ul {...props} className="mb-3 list-disc space-y-1 pl-5 last:mb-0" />,
  ol: ({ ...props }) => <ol {...props} className="mb-3 list-decimal space-y-1 pl-5 last:mb-0" />,
  li: ({ ...props }) => <li {...props} className="pl-1" />,
  strong: ({ ...props }) => <strong {...props} className="font-semibold text-white" />,
  code: ({ inline, children, ...props }) =>
    inline ? (
      <code
        {...props}
        className="rounded bg-black/25 px-1.5 py-0.5 text-[0.9em] text-amber-100"
      >
        {children}
      </code>
    ) : (
      <code
        {...props}
        className="block overflow-x-auto rounded-2xl bg-black/30 p-4 text-sm text-amber-50"
      >
        {children}
      </code>
    ),
  table: ({ ...props }) => (
    <div className="comparison-shell mb-4 overflow-x-auto rounded-[24px] border border-white/10 bg-black/20 last:mb-0">
      <table
        {...props}
        className="comparison-table min-w-[720px] border-collapse text-left text-sm"
      />
    </div>
  ),
  thead: ({ ...props }) => (
    <thead
      {...props}
      className="comparison-table-head bg-gradient-to-r from-amber-300/12 via-orange-300/10 to-transparent"
    />
  ),
  th: ({ ...props }) => (
    <th
      {...props}
      className="border-b border-white/10 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-100"
    />
  ),
  td: ({ ...props }) => (
    <td
      {...props}
      className="border-b border-white/10 px-4 py-3 align-top text-sm leading-6 text-stone-200"
    />
  )
};

function renderExtractor(extractor) {
  if (!extractor) {
    return "No extractor output was returned.";
  }

  if (typeof extractor === "string") {
    return extractor;
  }

  return JSON.stringify(extractor, null, 2);
}

function AgentDebate({ breakdown }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!breakdown) {
    return null;
  }

  return (
    <div className="mt-5 rounded-[22px] border border-white/10 bg-black/20">
      <button
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <div>
          <p className="text-sm font-semibold text-white">
            Behind the Scenes: AI Agent Debate
          </p>
          <p className="mt-1 text-xs text-stone-500">
            Critic, summarizer, and structured extractor outputs
          </p>
        </div>
        <span className="rounded-full border border-white/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-stone-400">
          {isOpen ? "Hide" : "View"}
        </span>
      </button>

      {isOpen ? (
        <div className="border-t border-white/8 px-4 py-4">
          <div className="grid gap-3 lg:grid-cols-3">
            <section className="rounded-2xl border border-red-300/10 bg-red-950/15 p-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-red-100/80">
                Critic
              </p>
              <p className="text-sm leading-6 text-stone-200">
                {breakdown.critic || "No critic output was returned."}
              </p>
            </section>

            <section className="rounded-2xl border border-amber-300/10 bg-amber-950/10 p-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-100/80">
                Summarizer
              </p>
              <div className="text-sm leading-6 text-stone-200">
                <ReactMarkdown components={markdownComponents}>
                  {breakdown.summarizer || "No summarizer output was returned."}
                </ReactMarkdown>
              </div>
            </section>

            <section className="rounded-2xl border border-sky-300/10 bg-sky-950/10 p-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-100/80">
                Extractor
              </p>
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-black/25 p-3 text-xs leading-5 text-stone-200">
                {renderExtractor(breakdown.extractor)}
              </pre>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function ChatBubble({ message, loadingText }) {
  const isAssistant = message.role === "assistant";
  const bubbleClass = isAssistant
    ? "border border-white/8 bg-[#11151d] text-stone-100"
    : "border border-white/10 bg-[#171c26] text-stone-100";

  const label = isAssistant ? "Personal Shopper" : "You";

  return (
    <div className={`flex ${isAssistant ? "justify-start" : "justify-end"}`}>
      <article
        className={`w-full max-w-3xl rounded-[26px] px-5 py-4 ${bubbleClass} ${
          message.error ? "border-red-400/30 bg-red-950/40" : ""
        }`}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.3em] text-stone-500">
            {label}
          </span>
          {message.pending ? (
            <span className="text-[11px] uppercase tracking-[0.2em] text-stone-500">
              Live
            </span>
          ) : null}
        </div>

        {message.content ? (
          <div className="text-[15px] leading-7 text-stone-100">
            <ReactMarkdown components={markdownComponents}>
              {message.content}
            </ReactMarkdown>
          </div>
        ) : null}

        {message.pending && !message.content ? (
          <div className="flex items-center gap-3 text-sm text-stone-200">
            <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-amber-300" />
            <span>{loadingText || "Agent is working..."}</span>
          </div>
        ) : null}

        {isAssistant && message.sources?.length ? (
          <div className="mt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.22em] text-stone-400">
              YouTube Links
            </p>
            <div className="flex flex-wrap gap-2.5">
              {message.sources.map((source) => (
                <a
                  key={`${source.url}-${source.title}`}
                  className="rounded-full border border-white/10 bg-black/20 px-3 py-2 text-xs text-stone-200 transition hover:border-amber-300/30 hover:bg-white/[0.05] hover:text-white"
                  href={source.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  {source.channel ? `${source.channel}: ` : ""}
                  {source.title}
                </a>
              ))}
            </div>
          </div>
        ) : null}

        {isAssistant && !message.pending ? (
          <AgentDebate breakdown={message.agentBreakdown} />
        ) : null}
      </article>
    </div>
  );
}
