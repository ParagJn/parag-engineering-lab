export interface Project {
  id: string;
  name: string;
  customer: string;
  suggestedStartDate: string; // YYYY-MM-DD
  assumptions?: string; // Free-text assumptions for the project
  outOfScope?: string; // Free-text out of scope / exclusions for the project
}
