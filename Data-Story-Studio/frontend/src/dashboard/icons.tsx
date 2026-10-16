type P = { className?: string };
const base = "w-4 h-4 shrink-0";
const svg = (d: string, cls?: string) => (
  <svg className={`${base} ${cls ?? ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);
export const IconUp = ({ className }: P) => svg("M7 17 17 7M9 7h8v8", className);
export const IconDown = ({ className }: P) => svg("M7 7l10 10M17 9v8H9", className);
export const IconFlat = ({ className }: P) => svg("M5 12h14", className);
export const IconCode = ({ className }: P) => svg("m8 8-4 4 4 4M16 8l4 4-4 4", className);
export const IconTable = ({ className }: P) => svg("M4 5h16v14H4zM4 10h16M4 15h16M10 5v14", className);
export const IconWand = ({ className }: P) => svg("M15 4V2M15 10V8M12 5h-2M20 5h-2M18 3l-1 1M13 3l1 1M3 21l10-10", className);
export const IconUndo = ({ className }: P) => svg("M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3", className);
export const IconSend = ({ className }: P) => svg("M5 12h13M13 6l6 6-6 6", className);
export const IconX = ({ className }: P) => svg("M6 6l12 12M18 6 6 18", className);
export const IconPlay = ({ className }: P) => svg("M7 5v14l11-7z", className);
export const IconPause = ({ className }: P) => svg("M8 5v14M16 5v14", className);
export const IconDownload = ({ className }: P) => svg("M12 4v11M7 10l5 5 5-5M5 20h14", className);
export const IconSpark = ({ className }: P) => svg("M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6", className);
export const IconInfo = ({ className }: P) => svg("M12 8h.01M11 12h1v5h1M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", className);
export const IconWarn = ({ className }: P) => svg("M12 9v4M12 17h.01M10.3 3.9 2.2 18a2 2 0 0 0 1.7 3h16.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z", className);
export const IconBlock = ({ className }: P) => svg("M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM5.6 5.6l12.8 12.8", className);
export const IconCheck = ({ className }: P) => svg("M5 12.5 10 17l9-10", className);
export const IconUpload = ({ className }: P) => svg("M12 16V4M7 9l5-5 5 5M5 20h14", className);
export const IconFile = ({ className }: P) => svg("M14 3H6v18h12V7zM14 3v4h4", className);
export const IconLink = ({ className }: P) => svg("M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1", className);
export const IconChat = ({ className }: P) => svg("M4 5h16v11H8l-4 4z", className);
export const IconPin = ({ className }: P) => svg("M12 17v5M8 3h8l-1 6 3 3v2H6v-2l3-3z", className);
export const IconFilter = ({ className }: P) => svg("M4 5h16l-6 8v6l-4-2v-4z", className);
export const IconBack = ({ className }: P) => svg("M15 6l-6 6 6 6", className);
export const IconTrash = ({ className }: P) => svg("M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3", className);
export const IconPlus = ({ className }: P) => svg("M12 5v14M5 12h14", className);
export const IconEye = ({ className }: P) => svg("M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z", className);

export function Spinner({ className = "" }: P) {
  return <span className={`inline-block w-4 h-4 rounded-full border-2 border-current border-r-transparent spin ${className}`} aria-hidden="true" />;
}
