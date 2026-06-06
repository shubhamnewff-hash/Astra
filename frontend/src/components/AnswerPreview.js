import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles } from "lucide-react";

/**
 * AnswerPreview renders a chat-bubble preview of how the AI assistant
 * will display the configured answer to end users. Supports markdown
 * (bold, italics, lists), numbered steps, suggestion buttons, and
 * action buttons exactly like UserPortal.js.
 */
export default function AnswerPreview({
  explanation = "",
  steps = [],
  suggestions = [],
  buttons = [],
  resources = [],
  title = "Live Preview",
  emptyHint = "Start typing to see the preview…",
}) {
  // Build the full content the way build_knowledge_context does on backend
  const lines = [];
  if (explanation && explanation.trim()) lines.push(explanation.trim());
  if (Array.isArray(steps) && steps.length > 0) {
    lines.push("");
    lines.push(...steps.map((s, i) => `${i + 1}. ${s}`));
  }
  const content = lines.join("\n");
  const hasAnything =
    !!content.trim() ||
    suggestions.length > 0 ||
    buttons.length > 0 ||
    resources.length > 0;

  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-gradient-to-br from-[#F8FAFC] to-white p-4" data-testid="answer-preview">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded-lg flex items-center justify-center" style={{ background: "#FF6B00" }}>
          <Sparkles className="w-3.5 h-3.5 text-white" />
        </div>
        <span className="text-xs font-bold uppercase tracking-[0.12em]" style={{ color: "#64748B" }}>
          {title}
        </span>
        <span className="text-[10px] text-[#94A3B8] ml-auto">As users will see it in chat</span>
      </div>

      {!hasAnything ? (
        <div className="text-sm text-center py-8" style={{ color: "#94A3B8" }}>
          {emptyHint}
        </div>
      ) : (
        <div className="flex">
          <div className="max-w-[95%]">
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm border border-[#E2E8F0] bg-white">
              {content && (
                <div className="chat-message-content text-sm" style={{ color: "#334155" }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </div>
              )}

              {Array.isArray(suggestions) && suggestions.length > 0 && (
                <div className={`${content ? "mt-3 pt-3 border-t border-[#E2E8F0]" : ""}`}>
                  <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#64748B" }}>
                    Suggested Questions
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {suggestions.map((q, i) => (
                      <button key={i} type="button" tabIndex={-1}
                        className="text-left text-sm px-3 py-2 rounded-lg border border-[#E2E8F0] hover:border-[#FF6B00] hover:text-[#FF6B00] transition-colors bg-white"
                        style={{ color: "#334155" }}>
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {Array.isArray(buttons) && buttons.length > 0 && (
                <div className={`${content || suggestions.length ? "mt-3 pt-3 border-t border-[#E2E8F0]" : ""} flex flex-wrap gap-2`}>
                  {buttons.map((btn, i) => (
                    <span key={i}
                      className="px-4 py-2 rounded-lg text-sm font-medium border border-[#FF6B00] text-[#FF6B00] bg-white">
                      {btn.label || "Button"}
                    </span>
                  ))}
                </div>
              )}

              {Array.isArray(resources) && resources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[#E2E8F0]">
                  <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#64748B" }}>
                    Reference Materials
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {resources.map((r, i) => (
                      <span key={i}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#E2E8F0] bg-white text-xs font-medium"
                        style={{ color: "#334155" }}>
                        {r.title || r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
