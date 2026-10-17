export type Unit = { kind: "number" | "currency" | "percent" | "ratio"; symbol?: string; suffix?: string };

export type QueryData = { columns: string[]; rows: any[][]; truncated: boolean; types?: string[] };

export type Annotation = { type: "anomaly" | "peak" | "partial"; x: any; y?: number; label: string };

export type Compare = { label: string; prev: number; diff: number; rel: number | null; display: string; direction: "up" | "down" | "flat" };

export type Panel = {
  id: string;
  chart: string;
  title: string;
  subtitle?: string;
  sql: string;
  data?: QueryData;
  unit?: Unit;
  enc?: Record<string, any>;
  recipe: Record<string, any>;
  allowed_charts?: string[];
  annotations?: Annotation[];
  caveats?: string[];
  stats?: any;
  highlight?: any;
  score?: number;
  history?: { title: string; recipe: any }[];
  error?: string;
  filtered?: boolean;
  computed_title?: string;
  // kpi
  value?: number;
  display?: string;
  compare?: Compare;
  compare_yoy?: Compare;
  spark?: [any, number][];
  spark_partial_last?: boolean;
  current_period?: string;
  current_display?: string;
  basis?: string;
  measure_label?: string;
  polarity?: "up_good" | "down_good" | "neutral";
  grain?: string;
  n?: number;
  [k: string]: any;
};

export type Section = { role: string; heading: string; panels: string[]; note?: string };

export type Insight = {
  title: string;
  what: string;
  significance: string;
  evidence: string;
  why: string;
  next: string;
  panels: string[];
  kind: "observation" | "hypothesis" | "recommendation";
};

export type Story = {
  headline: { title: string; finding?: string; summary: string; panel: string | null };
  kpis: string[];
  sections: Section[];
  insights: Insight[];
  next_steps?: string[];
  anomaly_notes?: string[];
  source: "ai" | "default";
  notice?: string;
  guarded?: string[];
};

export type Column = {
  name: string;
  label: string;
  dtype: string;
  role: string;
  agg: string;
  unit: Unit;
  distinct: number;
  missing_pct: number;
  source: string;
  derived?: string;
};

export type TimeInfo = { col: string; label: string; dtype: string; grain: string; min: string; max: string; span_days: number; has_hour: boolean };

export type Dashboard = {
  scope: string;
  story: Story;
  panels: Record<string, Panel>;
  unused: string[];
  generated: number;
  low_confidence: boolean;
  meta: {
    scope_label: string;
    rows: number;
    files: { name: string; size: number; uploaded: number }[];
    joins: { table: string; on: string }[];
    time: TimeInfo | null;
    goal: string;
    audience: string;
    columns: Column[];
  };
  // export-only
  static?: boolean;
  print?: boolean;
  exported?: number;
  filters?: Filter[];
  geo?: Record<string, any>; // map boundaries used by the report's map panels
  variants?: Record<string, Record<string, Panel>>;
};

export type Filter = { col: string; op: string; values: any[]; label?: string };

export type Issue = {
  id: string;
  severity: "block" | "warn" | "info";
  title: string;
  detail: string;
  suggestion: string;
  table: string;
  column: string;
  fix: { action: string; table: string; column?: string; format?: string; label?: string } | null;
};

export type Relationship = {
  kind: "join" | "union";
  left: string;
  right: string;
  left_col: string;
  right_col: string;
  left_match: number;
  right_match: number;
  cardinality: string;
  confidence: "strong" | "weak";
  shared_columns: string[];
  detail: string;
};

export type ColumnProfile = {
  table: string;
  name: string;
  label: string;
  dtype: string;
  role: string;
  count: number;
  missing: number;
  missing_pct: number;
  distinct: number;
  unit: Unit;
  agg: string;
  stats: Record<string, any>;
  top_values: [any, number][];
  notes: string[];
};

export type Readiness = {
  status: "pass" | "warn" | "block";
  total_rows: number;
  analysable_rows: number;
  fact_table: string;
  min_rows: number;
  issues: Issue[];
  relationships: Relationship[];
};

export type Scope = { id: string; label: string; rows: number; tables: string[]; joins: { table: string; on: string }[]; time: TimeInfo | null };

export type DatasetSummary = {
  id: string;
  files: { name: string; stored: string; size: number; uploaded: number; tables?: string[] }[];
  readiness: Readiness | null;
  profiles: Record<string, ColumnProfile[]> | null;
  rows: Record<string, number> | null;
  sources: Record<string, string> | null;
  brief: { files?: Record<string, string>; purpose?: string; goal_suggestions?: string[] } | null;
  setup: any;
  scopes: Scope[];
  dashboards: string[];
  min_rows: number;
  example: boolean;
};

export type DatasetListItem = { id: string; created: number; files: string[]; rows: number | null; title: string | null; stage: string; example?: boolean };

export type AskResult = {
  answer: string;
  kind: "answer" | "cannot" | "error";
  panel?: Panel;
  follow_ups?: string[];
  sql?: string;
  guarded?: string[];
};

export type ExecSummary = {
  title: string;
  context: string;
  bottom_line: string;
  metrics: { label: string; value: string; basis: string; change: string }[];
  highlights: { heading: string; text: string }[];
  risks: string[];
  opportunities: string[];
  actions: string[];
  notes: string[];
  markdown: string;
  generated: number;
  source: "ai" | "computed";
  notice?: string;
  guarded?: string[];
};
