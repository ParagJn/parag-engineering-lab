export const ROLE_LABEL: Record<string, string> = {
  measure: "Measure",
  dimension: "Category",
  time: "Date",
  id: "Identifier",
  text: "Free text",
  flag: "Yes/No",
};

export function roleDot(role: string): string {
  const m: Record<string, string> = { measure: "bg-[#2a78d6]", dimension: "bg-[#1baf7a]", time: "bg-[#eb6834]", id: "bg-[#c3c2b7]", text: "bg-[#c3c2b7]", flag: "bg-[#6250d6]" };
  return m[role] ?? "bg-line";
}
