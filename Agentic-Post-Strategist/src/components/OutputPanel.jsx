export default function OutputPanel({
  title,
  content,
  accent = "border-studio-100",
  onExpand,
  compact = false
}) {
  return (
    <section
      className={`rounded-xl border bg-white p-4 shadow-panel sm:p-5 ${accent} ${
        onExpand ? "cursor-pointer transition hover:shadow-xl" : ""
      }`}
      onClick={onExpand}
      role={onExpand ? "button" : undefined}
      tabIndex={onExpand ? 0 : undefined}
      onKeyDown={
        onExpand
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onExpand();
              }
            }
          : undefined
      }
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold tracking-wide text-studio-700 uppercase">{title}</h3>
        {onExpand ? (
          <span className="rounded-full bg-studio-50 px-2 py-1 text-[11px] font-semibold text-studio-700">
            Expand
          </span>
        ) : null}
      </div>
      <pre
        className={`mt-3 overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-studio-900 ${
          compact ? "max-h-[40vh]" : "max-h-[55vh]"
        }`}
      >
        {content || "No output yet."}
      </pre>
    </section>
  );
}
