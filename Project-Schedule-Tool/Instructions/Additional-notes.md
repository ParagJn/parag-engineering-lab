One enhancement I would add
I would ask Codex not to build the Excel directly from the React grid.
Instead, have a central scheduling engine that produces an object like:
ProjectPlan
    Tasks
        Schedule
            WeeklyAllocation
                ExcelRenderer
                ReactTimeline
                FuturePDF
                FutureGantt



This is a react based app for now, so lets just build that only. 
