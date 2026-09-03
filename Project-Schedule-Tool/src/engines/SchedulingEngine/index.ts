import dayjs from 'dayjs';
import type { Task } from '../../models/Task';
import type { Week } from '../../models/Week';

// Helper: Check if a date is a working day (Monday - Friday, and not a holiday)
export function isWorkingDay(date: dayjs.Dayjs, holidayDates: Set<string> = new Set()): boolean {
  const day = date.day();
  if (day === 0 || day === 6) return false; // 0 = Sunday, 6 = Saturday
  return !holidayDates.has(date.format('YYYY-MM-DD'));
}

// Helper: Move a date to the next working day if it falls on a weekend or holiday
export function moveToWorkingDay(date: dayjs.Dayjs, holidayDates: Set<string> = new Set()): dayjs.Dayjs {
  let current = date;
  while (!isWorkingDay(current, holidayDates)) {
    current = current.add(1, 'day');
  }
  return current;
}

// Helper: Add N working days to a start date (skipping weekends and holidays)
export function addWorkingDays(startDate: dayjs.Dayjs, days: number, holidayDates: Set<string> = new Set()): dayjs.Dayjs {
  let current = moveToWorkingDay(startDate, holidayDates);
  let remaining = days;
  while (remaining > 0) {
    current = current.add(1, 'day');
    if (isWorkingDay(current, holidayDates)) {
      remaining--;
    }
  }
  return current;
}

// Helper: Parse comma-separated dependencies into an array of task indexes
export function parseDependencies(depStr: string): number[] {
  if (!depStr || depStr.trim() === '') return [];
  return depStr
    .split(',')
    .map(s => parseInt(s.trim(), 10))
    .filter(val => !isNaN(val) && val > 0);
}

// Helper: Calculate Friday of the week containing a date
export function getFridayOfWeek(date: dayjs.Dayjs): dayjs.Dayjs {
  const day = date.day();
  if (day === 5) return date; // Friday
  if (day === 6) return date.add(6, 'day'); // Saturday -> next Friday
  if (day === 0) return date.add(5, 'day'); // Sunday -> next Friday
  // Monday (1) to Thursday (4) -> Friday of the same week
  return date.day(5);
}

export interface SchedulingResult {
  tasks: Task[];
  weeks: Week[];
}

export function calculateSchedule(
  tasks: Task[],
  suggestedStartDateStr: string,
  minWeeksToShow = 10,
  holidayDates: Set<string> = new Set()
): SchedulingResult {
  if (tasks.length === 0) {
    return { tasks: [], weeks: [] };
  }

  // 1. Initial parse of start date
  const projectStartDate = moveToWorkingDay(dayjs(suggestedStartDateStr), holidayDates);
  const week1Friday = getFridayOfWeek(projectStartDate);

  // 2. Map tasks by their index for fast lookup
  const tasksByIndex = new Map<number, Task>();
  tasks.forEach((t, i) => {
    // Ensure index is set correctly based on row ordering
    t.index = i + 1;
    tasksByIndex.set(t.index, t);
  });

  // 3. Topological Sort to handle dependencies
  const sortedTasks: Task[] = [];
  const visited = new Set<string>();
  const visiting = new Set<string>();
  const circularTasks = new Set<string>();

  function visit(task: Task) {
    if (visiting.has(task.id)) {
      circularTasks.add(task.id);
      return; // Cycle detected
    }
    if (!visited.has(task.id)) {
      visiting.add(task.id);
      const deps = parseDependencies(task.dependency);
      for (const depIndex of deps) {
        const parentTask = tasksByIndex.get(depIndex);
        // Avoid self-dependency and process parent
        if (parentTask && parentTask.id !== task.id) {
          visit(parentTask);
        }
      }
      visiting.delete(task.id);
      visited.add(task.id);
      sortedTasks.push(task);
    }
  }

  tasks.forEach(t => visit(t));

  // 4. Calculate task dates and durations in topological order
  const calculatedTasksMap = new Map<string, Task>();

  sortedTasks.forEach(task => {
    // Basic effort calculations
    const hours = Math.max(0, task.estimatedHours || 0);
    const fte = Math.max(0.1, task.fte || 1.0);
    const days = hours / 8;
    const weeks = days / 5;
    const effectiveDurationDays =
      task.durationMode === 'fixed-duration'
        ? days        // FTE doesn't compress duration — task spans its natural day count
        : days / fte; // effort-driven (default): more FTE → shorter calendar span

    // Determine start date
    let startDate = projectStartDate;

    // Resolve dependencies (if not circular)
    if (!circularTasks.has(task.id)) {
      const deps = parseDependencies(task.dependency);
      let maxParentFinish: dayjs.Dayjs | null = null;

      deps.forEach(depIndex => {
        const parentTask = tasksByIndex.get(depIndex);
        if (parentTask) {
          const parentCalculated = calculatedTasksMap.get(parentTask.id);
          if (parentCalculated && parentCalculated.calculatedFinishDate) {
            const parentFinish = dayjs(parentCalculated.calculatedFinishDate);
            if (!maxParentFinish || parentFinish.isAfter(maxParentFinish)) {
              maxParentFinish = parentFinish;
            }
          }
        }
      });

      if (maxParentFinish) {
        // Child starts on the Monday of the week after the parent task finishes
        const parentFriday = getFridayOfWeek(maxParentFinish);
        startDate = parentFriday.add(3, 'day'); // Friday + 3 days = next Monday
      }
    }

    // Manual start date override if specified and valid
    if (task.manualStartDate && dayjs(task.manualStartDate).isValid()) {
      startDate = dayjs(task.manualStartDate);
    }

    // Ensure the start date itself isn't a weekend/holiday (e.g. dependency-driven Monday, or manual override)
    startDate = moveToWorkingDay(startDate, holidayDates);

    // Calculate finish date
    let finishDate = startDate;
    if (effectiveDurationDays > 0) {
      const daysToSpan = Math.ceil(effectiveDurationDays);
      finishDate = addWorkingDays(startDate, daysToSpan - 1, holidayDates);
    }

    const calculatedTask: Task = {
      ...task,
      estimatedDays: Math.round(days),
      estimatedWeeks: Math.round(weeks),
      calculatedStartDate: startDate.format('YYYY-MM-DD'),
      calculatedFinishDate: finishDate.format('YYYY-MM-DD'),
      weekAssignments: {} // Will calculate below
    };

    calculatedTasksMap.set(task.id, calculatedTask);
  });

  // Re-order tasks back to their original input indexes
  const calculatedTasks = tasks.map(t => calculatedTasksMap.get(t.id)!);

  // 5. Determine maximum date to size the timeline
  let maxDate = week1Friday.add(minWeeksToShow - 1, 'week');
  calculatedTasks.forEach(t => {
    if (t.calculatedFinishDate) {
      const taskFinish = dayjs(t.calculatedFinishDate);
      if (taskFinish.isAfter(maxDate)) {
        maxDate = taskFinish;
      }
    }
  });

  // Calculate Friday ending dates for the timeline
  const weeksList: Week[] = [];
  let currentFriday = week1Friday;
  let weekIndex = 1;

  while (currentFriday.isBefore(maxDate) || currentFriday.isSame(maxDate, 'day') || weekIndex <= minWeeksToShow) {
    weeksList.push({
      index: weekIndex,
      label: `Wk${weekIndex}`,
      fridayDate: currentFriday.format('YYYY-MM-DD')
    });
    currentFriday = currentFriday.add(7, 'day');
    weekIndex++;
  }

  // 6. Allocate task efforts into weekly buckets
  calculatedTasks.forEach(task => {
    const startStr = task.calculatedStartDate!;
    const hours = task.estimatedHours || 0;
    const fte = task.fte || 1.0;
    const days = hours / 8;
    // Must mirror the duration logic used to derive calculatedFinishDate above,
    // otherwise fixed-duration tasks with FTE > 1 span more calendar days than
    // get allocated here, leaving later weeks with 0 allocation (Gantt bar cuts short).
    const totalWorkingDays = task.durationMode === 'fixed-duration' ? days : days / fte;

    if (totalWorkingDays <= 0) {
      task.weekAssignments = {};
      return;
    }

    const start = dayjs(startStr);
    const assignments: Record<string, number> = {};

    // Generate daily portions of the task
    const totalSegments = Math.ceil(totalWorkingDays);
    const segments: { dateStr: string; portion: number }[] = [];

    for (let k = 0; k < totalSegments; k++) {
      const segDate = addWorkingDays(start, k, holidayDates);
      const portion = (k === totalSegments - 1) ? (totalWorkingDays - k) : 1.0;
      segments.push({
        dateStr: segDate.format('YYYY-MM-DD'),
        portion
      });
    }

    // Distribute daily segments into weeks
    weeksList.forEach((week, wIdx) => {
      const fri = dayjs(week.fridayDate);
      const prevFri = wIdx === 0 ? null : dayjs(weeksList[wIdx - 1].fridayDate);

      // A segment date belongs to this week if:
      // Week 1: date <= Friday 1
      // Week N (N>1): Friday N-1 < date <= Friday N
      let weekDaysSum = 0;
      segments.forEach(seg => {
        const segDate = dayjs(seg.dateStr);
        let inWeek = false;

        if (wIdx === 0) {
          inWeek = segDate.isBefore(fri) || segDate.isSame(fri, 'day');
        } else if (prevFri) {
          inWeek = segDate.isAfter(prevFri, 'day') && (segDate.isBefore(fri) || segDate.isSame(fri, 'day'));
        }

        if (inWeek) {
          weekDaysSum += seg.portion;
        }
      });

      if (weekDaysSum > 0) {
        // Percentage of task's duration in this week
        assignments[week.fridayDate] = Number((weekDaysSum / totalWorkingDays).toFixed(4));
      }
    });

    task.weekAssignments = assignments;
  });

  return {
    tasks: calculatedTasks,
    weeks: weeksList
  };
}
