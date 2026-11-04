"""Build Verify (S20): how far did the real build drift from the design?

Reads the user's own backend and frontend folders as TEXT, on the same computer, and never runs anything in them. This package holds the safe walk (`walk`), the readers
that turn source text into plain facts (`readers/`), and, in later slices, the matching and the report.
"""
