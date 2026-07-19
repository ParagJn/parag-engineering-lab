export interface Week {
  index: number; // 1-based index (e.g. 1 for Wk1)
  label: string; // "Wk1", "Wk2", etc.
  fridayDate: string; // YYYY-MM-DD representing the Friday ending date
}
