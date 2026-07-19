# Scheduling Rules

This file defines every scheduling rule.

---

## Rule 1

Hours

Input by user.

---

## Rule 2

Days

Days = Hours / 8

Automatically calculated.

Never editable.

---

## Rule 3

Weeks

Weeks = Days / 5

Automatically calculated.

Display with two decimals.

---

## Rule 4

FTE

Default = 1

Effective Duration

EffectiveWeeks = Weeks / FTE

Examples

40 hours

5 days

1 week

FTE = 1

Duration = 1 week

---

80 hours

10 days

2 weeks

FTE = 2

Duration = 1 week

---

160 hours

20 days

4 weeks

FTE = 4

Duration = 1 week

---

## Rule 5

Dependencies

Dependency references the Index column.

Example

Task 6

Dependency = 3

Task 6 cannot begin until Task 3 finishes.

Multiple dependency support should be designed although UI initially supports only one dependency.

---

## Rule 6

No Dependency

Task starts on the project start date.

---

## Rule 7

Dependent Tasks

Start Date

=

Parent Finish Date

+

1 Working Day

---

## Rule 8

Working Days

Monday-Friday

Saturday

Non-working

Sunday

Non-working

Future support should allow holidays.

---

## Rule 9

Week Columns

Week headers always represent Friday.

Example

Project starts

Monday

21 July

Week 1 header

Friday 25 July

Week 2 header

Friday 1 August

Week 3 header

Friday 8 August

etc.

---

## Rule 10

Partial Week

If project starts Wednesday

Week 1

Wed

Thu

Fri

Only three working days.

Remaining effort moves into Week 2.

---

## Rule 11

Timeline Allocation

Effort should spill week by week.

Each week cell stores percentage completion.

Excel rendering fills cells appropriately.

---

## Rule 12

Automatic Recalculation

Changing

Hours

FTE

Dependency

Start Date

must recalculate the entire downstream schedule.