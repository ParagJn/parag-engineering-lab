import { calculateSchedule } from './index';
import type { Task } from '../../models/Task';



function runTests() {
  console.log('Running Scheduling Engine Tests...\n');

  // Test Case 1: Simple Task, Monday Start
  console.log('Test 1: Simple task 40h, 1 FTE, Monday start');
  const tasks1: Task[] = [
    {
      id: 't1',
      index: 1,
      activity: 'Task 1',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '',
      color: 'yellow',
      status: 'planned'
    }
  ];
  
  const result1 = calculateSchedule(tasks1, '2026-07-20'); // Monday 20 July 2026
  const t1_res = result1.tasks[0];
  console.log(`- Start Date: ${t1_res.calculatedStartDate} (Expected: 2026-07-20)`);
  console.log(`- Finish Date: ${t1_res.calculatedFinishDate} (Expected: 2026-07-24)`);
  console.log(`- Est Days: ${t1_res.estimatedDays} (Expected: 5)`);
  console.log(`- Est Weeks: ${t1_res.estimatedWeeks} (Expected: 1)`);
  console.log(`- Week 1 Assignment: ${t1_res.weekAssignments?.['2026-07-24']} (Expected: 1)\n`);

  if (t1_res.calculatedStartDate !== '2026-07-20' || t1_res.calculatedFinishDate !== '2026-07-24') {
    throw new Error('Test 1 Failed');
  }

  // Test Case 2: Dependency & Weekend Skip
  console.log('Test 2: Dependent task, starts after weekend');
  const tasks2: Task[] = [
    {
      id: 't1',
      index: 1,
      activity: 'Task 1',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '',
      color: 'yellow',
      status: 'planned'
    },
    {
      id: 't2',
      index: 2,
      activity: 'Task 2',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '1',
      color: 'blue',
      status: 'planned'
    }
  ];

  const result2 = calculateSchedule(tasks2, '2026-07-20');
  const t2_res = result2.tasks[1];
  console.log(`- Task 2 Start Date: ${t2_res.calculatedStartDate} (Expected: 2026-07-27)`);
  console.log(`- Task 2 Finish Date: ${t2_res.calculatedFinishDate} (Expected: 2026-07-31)`);
  console.log(`- Task 2 Week 2 Assignment: ${t2_res.weekAssignments?.['2026-07-31']} (Expected: 1)\n`);

  if (t2_res.calculatedStartDate !== '2026-07-27' || t2_res.calculatedFinishDate !== '2026-07-31') {
    throw new Error('Test 2 Failed');
  }

  // Test Case 3: Partial Week (Starting Wednesday)
  console.log('Test 3: Partial week starting Wednesday');
  const tasks3: Task[] = [
    {
      id: 't1',
      index: 1,
      activity: 'Task 1',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '',
      color: 'yellow',
      status: 'planned'
    }
  ];
  // 2026-07-22 is Wednesday. Friday is 2026-07-24.
  // Working days: Wed (1), Thu (2), Fri (3) -> Week 1 (3 days)
  // Mon (4), Tue (5) -> Week 2 (2 days)
  const result3 = calculateSchedule(tasks3, '2026-07-22');
  const t3_res = result3.tasks[0];
  console.log(`- Start Date: ${t3_res.calculatedStartDate} (Expected: 2026-07-22)`);
  console.log(`- Finish Date: ${t3_res.calculatedFinishDate} (Expected: 2026-07-28)`);
  console.log(`- Week 1 Assignment: ${t3_res.weekAssignments?.['2026-07-24']} (Expected: 0.6)`);
  console.log(`- Week 2 Assignment: ${t3_res.weekAssignments?.['2026-07-31']} (Expected: 0.4)\n`);

  if (t3_res.calculatedStartDate !== '2026-07-22' || t3_res.calculatedFinishDate !== '2026-07-28') {
    throw new Error('Test 3 Failed');
  }

  // Test Case 4: Circular Dependency Detection
  console.log('Test 4: Circular dependencies (Task 1 -> Task 2 -> Task 1)');
  const tasks4: Task[] = [
    {
      id: 't1',
      index: 1,
      activity: 'Task 1',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '2',
      color: 'yellow',
      status: 'planned'
    },
    {
      id: 't2',
      index: 2,
      activity: 'Task 2',
      estimatedHours: 40,
      estimatedDays: 0,
      estimatedWeeks: 0,
      fte: 1,
      dependency: '1',
      color: 'blue',
      status: 'planned'
    }
  ];

  const result4 = calculateSchedule(tasks4, '2026-07-20');
  console.log(`- Task 1 Start Date: ${result4.tasks[0].calculatedStartDate} (Expected: 2026-07-20)`);
  console.log(`- Task 2 Start Date: ${result4.tasks[1].calculatedStartDate} (Expected: 2026-07-20)`);
  console.log('- Circular dependency test passed without crash.\n');

  console.log('ALL TESTS PASSED SUCCESSFULLY!');
}

runTests();
