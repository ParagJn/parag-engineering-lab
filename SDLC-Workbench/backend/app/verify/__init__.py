"""Build Verify (S20, S20f): how far did the real build drift from the design?

Reads the user's own backend folder as TEXT (the frontend was dropped in S20f: a screen is too hard to trace back to a design line), on the same computer, and never runs anything in them. This package holds the safe walk (`walk`), the readers
that turn source text into plain facts (`readers/`), and, in later slices, the matching and the report.
"""
