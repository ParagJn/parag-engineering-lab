export default function OperationCard({ operation, selected, onSelect, accent }) {
  const baseAccent = accent || "border-blue-500 hover:border-blue-600";
  const selectedAccent = accent ? accent.replace("hover:", "") : "border-blue-500";

  return (
    <button
      type="button"
      onClick={() => onSelect(operation.id)}
      className={`w-full rounded-xl border p-4 text-left transition ${
        selected
          ? `${selectedAccent} bg-studio-100/70 shadow-md`
          : `${baseAccent} bg-white`
      }`}
    >
      <p className="text-sm font-semibold text-studio-800">{operation.label}</p>
      <p className="mt-2 text-xs leading-5 text-studio-600">{operation.instruction}</p>
    </button>
  );
}
