import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';
import dayjs from 'dayjs';
import type { Project } from '../../models/Project';
import type { Task } from '../../models/Task';
import type { Week } from '../../models/Week';
import type { HolidayEntry } from '../../models/Holiday';

// Helper: Convert hex color to ARGB (hex without '#' prefixed by 'FF' for alpha)
function hexToArgb(hex: string, defaultColor = 'FFCCCCCC'): string {
  if (!hex) return defaultColor;
  const clean = hex.replace('#', '');
  if (clean.length === 6) return 'FF' + clean;
  if (clean.length === 8) return clean;
  return defaultColor;
}

// Helper: Determine column letter from 1-based index (e.g. 1 -> A, 27 -> AA)
function getColumnLetter(colIndex: number): string {
  let temp = colIndex;
  let letter = '';
  while (temp > 0) {
    const modulo = (temp - 1) % 26;
    letter = String.fromCharCode(65 + modulo) + letter;
    temp = Math.floor((temp - modulo) / 26);
  }
  return letter;
}

type DayBoxState = 'active' | 'inactive' | 'holiday';

// Helper: Calculate which days (Mon-Fri) are active for a task in a given week,
// marking any active day that falls on a holiday separately so it renders as 'H'
// (mirrors the on-screen Gantt behavior when a Vic/Ind holiday adjustment is applied)
function calculateActiveDaysForWeek(task: Task, week: Week, holidayMap: Record<string, string> = {}): DayBoxState[] {
  const startD = dayjs(task.calculatedStartDate);
  const finishD = dayjs(task.calculatedFinishDate);
  const weekFri = dayjs(week.fridayDate);

  const dayStates: DayBoxState[] = ['inactive', 'inactive', 'inactive', 'inactive', 'inactive'];

  // Check each day of the week (Monday=0 to Friday=4)
  for (let d = 0; d < 5; d++) {
    const dayDate = weekFri.subtract(4 - d, 'day');
    const isActive = (dayDate.isAfter(startD, 'day') || dayDate.isSame(startD, 'day')) &&
      (dayDate.isBefore(finishD, 'day') || dayDate.isSame(finishD, 'day'));
    if (isActive) {
      dayStates[d] = holidayMap[dayDate.format('YYYY-MM-DD')] ? 'holiday' : 'active';
    }
  }

  return dayStates;
}

// Helper: Generate box string for the day states (▪ active, ▫ inactive, H holiday)
// Using U+25AA and U+25AB small squares for clean rendering
function generateDayBoxes(dayStates: DayBoxState[]): string {
  return dayStates.map(state => state === 'holiday' ? 'H' : state === 'active' ? '▪' : '▫').join(' ');
}

export async function exportProjectToExcel(
  project: Project,
  tasks: Task[],
  weeks: Week[],
  background?: string,
  assumptions?: string,
  outOfScope?: string,
  mawDeliverables?: string,
  vicHolidays?: HolidayEntry[],
  indiaHolidays?: HolidayEntry[],
  activeHolidayMap?: Record<string, string>
): Promise<void> {
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet('Project Schedule', {
    views: [{ showGridLines: true }]
  });

  // Page Setup (Landscape, A4, Fit to page width)
  worksheet.pageSetup = {
    orientation: 'landscape',
    fitToPage: true,
    fitToWidth: 1,
    fitToHeight: 0, // auto height
    paperSize: 9, // A4
    margins: {
      left: 0.5,
      right: 0.5,
      top: 0.75,
      bottom: 0.75,
      header: 0.3,
      footer: 0.3
    }
  };

  // Header and Footer
  worksheet.headerFooter = {
    oddHeader: `&L&"Aptos Narrow,Bold"&12${project.name} - Project Schedule&R&"Aptos Narrow"&10Customer: ${project.customer}`,
    oddFooter: `&L&"Aptos Narrow,Italic"&9[Company Logo/Name Placeholder]&R&"Aptos Narrow"&9Page &P of &N`
  };

  // Column Widths
  // Set margin columns A-F
  for (let c = 1; c <= 6; c++) {
    worksheet.getColumn(c).width = 3;
  }

  // Set metadata columns G-P
  worksheet.getColumn(7).width = 8;    // G: Index
  worksheet.getColumn(8).width = 32;   // H: Activity/Task
  worksheet.getColumn(9).width = 13;   // I: Est. Hours
  worksheet.getColumn(10).width = 13;  // J: Est. Days
  worksheet.getColumn(11).width = 13;  // K: Est. Weeks
  worksheet.getColumn(12).width = 8;   // L: FTE
  worksheet.getColumn(13).width = 12;  // M: Man Days
  worksheet.getColumn(14).width = 16;  // N: Mode
  worksheet.getColumn(15).width = 18;  // O: Dep. Link
  worksheet.getColumn(16).width = 13;  // P: Dependency (raw)

  // Set timeline columns Q onwards
  const startTimelineColIdx = 17; // Col Q is 17
  weeks.forEach((_, idx) => {
    worksheet.getColumn(startTimelineColIdx + idx).width = 12;
  });

  // Fonts & Borders Definitions
  const fontName = 'Aptos Narrow';
  const defaultFont = { name: fontName, size: 11 };
  const headerFont = { name: fontName, size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
  const titleFont = { name: fontName, size: 16, bold: true, color: { argb: 'FF1F497D' } };
  const metadataLabelFont = { name: fontName, size: 11, bold: true };
  const logoPlaceholderFont = { name: fontName, size: 10, italic: true, color: { argb: 'FF7F7F7F' } };

  const thinBorder = {
    top: { style: 'thin', color: { argb: 'FFD9D9D9' } },
    left: { style: 'thin', color: { argb: 'FFD9D9D9' } },
    bottom: { style: 'thin', color: { argb: 'FFD9D9D9' } },
    right: { style: 'thin', color: { argb: 'FFD9D9D9' } }
  } as ExcelJS.Borders;

  const headerFill = {
    type: 'pattern',
    pattern: 'solid',
    fgColor: { argb: 'FF366092' } // Professional Dark Slate Blue
  } as ExcelJS.Fill;

  const alternateRowFill = {
    type: 'pattern',
    pattern: 'solid',
    fgColor: { argb: 'FFF2F5F8' } // Light bluish-gray
  } as ExcelJS.Fill;

  // 1. Logo/Company Name Placeholder in G1
  const logoCell = worksheet.getCell('G1');
  logoCell.value = '[ COMPANY LOGO / NAME PLACEHOLDER ]';
  logoCell.font = logoPlaceholderFont;

  // 2. Project Title & Customer in G2 and G3
  worksheet.getCell('G2').value = project.name;
  worksheet.getCell('G2').font = titleFont;
  worksheet.getCell('G3').value = `Customer: ${project.customer}`;
  worksheet.getCell('G3').font = { name: fontName, size: 12, italic: true, color: { argb: 'FF595959' } };

  // 3. Row 4: Suggested Start Date (G4-H4) & Week Ending Dates Merged Title Header (N4 onwards)
  worksheet.getCell('G4').value = 'Suggested Start Date';
  worksheet.getCell('G4').font = metadataLabelFont;
  worksheet.getCell('G4').alignment = { horizontal: 'left' };

  const startDateCell = worksheet.getCell('H4');
  startDateCell.value = project.suggestedStartDate;
  startDateCell.font = defaultFont;
  startDateCell.numFmt = 'yyyy-mm-dd';
  startDateCell.alignment = { horizontal: 'left' };

  // Week Ending Dates Merged Header (Col Q to last week column)
  const lastWeekColIdx = startTimelineColIdx + weeks.length - 1;
  const lastWeekColLetter = getColumnLetter(lastWeekColIdx);
  const weekEndingRange = `Q4:${lastWeekColLetter}4`;
  worksheet.mergeCells(weekEndingRange);
  const weekEndingHeaderCell = worksheet.getCell('Q4');
  weekEndingHeaderCell.value = 'Week Ending Dates';
  weekEndingHeaderCell.font = { name: fontName, size: 11, bold: true, color: { argb: 'FF1F497D' } };
  weekEndingHeaderCell.alignment = { horizontal: 'center', vertical: 'middle' };

  // 4. Row 5: Wk1, Wk2 labels (N5 onwards)
  weeks.forEach((week, idx) => {
    const colIdx = startTimelineColIdx + idx;
    const cell = worksheet.getCell(5, colIdx);
    cell.value = week.label;
    cell.font = metadataLabelFont;
    cell.alignment = { horizontal: 'center' };
  });

  // 5. Row 6: Friday dates using formulas (N6 onwards)
  // Week 1: =H4+4. Week 2+: =N6+7, =O6+7 ...
  weeks.forEach((_, idx) => {
    const colIdx = startTimelineColIdx + idx;
    const cell = worksheet.getCell(6, colIdx);
    if (idx === 0) {
      cell.value = { formula: '=H4+4' };
    } else {
      const prevColLetter = getColumnLetter(colIdx - 1);
      cell.value = { formula: `=${prevColLetter}6+7` };
    }
    cell.font = { name: fontName, size: 10, color: { argb: 'FF595959' } };
    cell.numFmt = 'dd-mmm';
    cell.alignment = { horizontal: 'center' };
    cell.border = {
      bottom: { style: 'medium', color: { argb: 'FF366092' } }
    };
  });

  // 6. Row 7: Grid Column Headers
  const gridHeaders = [
    { col: 7,  val: 'Index' },
    { col: 8,  val: 'Activity/Task' },
    { col: 9,  val: 'Est. Hours' },
    { col: 10, val: 'Est. Days' },
    { col: 11, val: 'Est Weeks' },
    { col: 12, val: 'FTE' },
    { col: 13, val: 'Man Days' },
    { col: 14, val: 'Mode' },
    { col: 15, val: 'Dep. Link' },
    { col: 16, val: 'Dependency' }
  ];

  gridHeaders.forEach(h => {
    const cell = worksheet.getCell(7, h.col);
    cell.value = h.val;
    cell.font = headerFont;
    cell.fill = headerFill;
    cell.alignment = { horizontal: h.col === 8 ? 'left' : 'center', vertical: 'middle' };
    cell.border = thinBorder;
  });

  // Setup header border for timeline columns in row 7
  weeks.forEach((_, idx) => {
    const colIdx = startTimelineColIdx + idx;
    const cell = worksheet.getCell(7, colIdx);
    cell.border = {
      top: thinBorder.top,
      bottom: thinBorder.bottom
    };
  });

  // 7. Write Task Rows (starting from Row 8) with sub-activities
  const subActivityFont = { name: fontName, size: 10, italic: true, color: { argb: 'FF666666' } };
  let currentRow = 8;

  tasks.forEach((task, taskIdx) => {
    const taskRowIdx = currentRow;

    // Col G: Index
    const indexCell = worksheet.getCell(taskRowIdx, 7);
    indexCell.value = task.index;
    indexCell.font = { ...defaultFont, bold: true };
    indexCell.alignment = { horizontal: 'center' };
    indexCell.border = thinBorder;

    // Col H: Activity/Task Name
    const activityCell = worksheet.getCell(taskRowIdx, 8);
    activityCell.value = task.activity;
    activityCell.font = { ...defaultFont, bold: true };
    activityCell.alignment = { horizontal: 'left' };
    activityCell.border = thinBorder;

    // Col I: Est. Hours
    const hoursCell = worksheet.getCell(taskRowIdx, 9);
    hoursCell.value = task.estimatedHours;
    hoursCell.font = defaultFont;
    hoursCell.numFmt = '#,##0';
    hoursCell.alignment = { horizontal: 'center' };
    hoursCell.border = thinBorder;

    // Col J: Est. Days (=ROUND(I{row}/8, 0))
    const daysCell = worksheet.getCell(taskRowIdx, 10);
    daysCell.value = { formula: `=ROUND(I${taskRowIdx}/8,0)` };
    daysCell.font = defaultFont;
    daysCell.numFmt = '#,##0';
    daysCell.alignment = { horizontal: 'center' };
    daysCell.border = thinBorder;

    // Col K: Est. Weeks (=ROUND(J{row}/5, 0))
    const weeksCell = worksheet.getCell(taskRowIdx, 11);
    weeksCell.value = { formula: `=ROUND(J${taskRowIdx}/5,0)` };
    weeksCell.font = defaultFont;
    weeksCell.numFmt = '#,##0';
    weeksCell.alignment = { horizontal: 'center' };
    weeksCell.border = thinBorder;

    // Col L: FTE
    const fteCell = worksheet.getCell(taskRowIdx, 12);
    fteCell.value = task.fte;
    fteCell.font = defaultFont;
    fteCell.numFmt = '#,##0';
    fteCell.alignment = { horizontal: 'center' };
    fteCell.border = thinBorder;

    // Col M: Man Days (=ROUND(J{row}*L{row},0)  — Est.Days × FTE)
    const manDaysCell = worksheet.getCell(taskRowIdx, 13);
    manDaysCell.value = { formula: `=ROUND(J${taskRowIdx}*L${taskRowIdx},0)` };
    manDaysCell.font = { name: fontName, size: 11, bold: true, color: { argb: 'FF92400E' } };
    manDaysCell.numFmt = '#,##0';
    manDaysCell.alignment = { horizontal: 'center', vertical: 'middle' };
    manDaysCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFFBEB' } } as ExcelJS.Fill;
    manDaysCell.border = thinBorder;

    // Col N: Mode (duration mode badge)
    const modeCell = worksheet.getCell(taskRowIdx, 14);
    const isFixed = task.durationMode === 'fixed-duration';
    modeCell.value = isFixed ? '📌 Fixed Duration' : '⚡ Effort Driven';
    modeCell.font = {
      name: fontName, size: 10, bold: true,
      color: { argb: isFixed ? 'FF64748B' : 'FF2563EB' }
    };
    modeCell.alignment = { horizontal: 'center', vertical: 'middle' };
    modeCell.border = thinBorder;

    // Col O: Dep. Link (dependency chain indicator)
    const depLinkCell = worksheet.getCell(taskRowIdx, 15);
    const hasDeps = task.dependency && task.dependency.trim() !== '';
    if (hasDeps) {
      const depNums = task.dependency.split(',').map((s: string) => s.trim()).filter(Boolean);
      depLinkCell.value = `🔗 Task ${depNums.join(', ')}`;
      depLinkCell.font = { name: fontName, size: 10, bold: true, color: { argb: 'FF1D4ED8' } };
    } else {
      depLinkCell.value = null;
    }
    depLinkCell.alignment = { horizontal: 'left', vertical: 'middle' };
    depLinkCell.border = thinBorder;

    // Col P: Dependency (raw index string)
    const depCell = worksheet.getCell(taskRowIdx, 16);
    depCell.value = task.dependency || null;
    depCell.font = defaultFont;
    depCell.alignment = { horizontal: 'center' };
    depCell.border = thinBorder;

    // Apply alternating row shading to the task metadata columns G-P (skip M=ManDays which has its own fill)
    if (taskIdx % 2 === 1) {
      for (let colIdx = 7; colIdx <= 16; colIdx++) {
        if (colIdx !== 13) { // skip Man Days column — it has its own amber fill
          worksheet.getCell(taskRowIdx, colIdx).fill = alternateRowFill;
        }
      }
    }

    // Set timeline cells borders (empty grid style)
    weeks.forEach((_, idx) => {
      const colIdx = startTimelineColIdx + idx;
      worksheet.getCell(taskRowIdx, colIdx).border = thinBorder;
    });

    // 8. Draw Timeline Task Color Bar with 5-Box Daily Indicators
    const weekAss = task.weekAssignments || {};
    const activeWeeks = weeks.filter(w => (weekAss[w.fridayDate] || 0) > 0);

    if (activeWeeks.length > 0) {
      const barColorHex = hexToArgb(task.color, 'FF2196F3');
      const barFill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: barColorHex }
      } as ExcelJS.Fill;

      // Determine appropriate text color for contrast (simple luminance heuristic)
      const r = parseInt(barColorHex.substring(2, 4), 16);
      const g = parseInt(barColorHex.substring(4, 6), 16);
      const b = parseInt(barColorHex.substring(6, 8), 16);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      const barTextColor = luminance > 0.6 ? 'FF000000' : 'FFFFFFFF'; // black for light background, white for dark

      // For each active week, show the 5-box daily indicator
      activeWeeks.forEach(week => {
        const weekColIdx = weeks.findIndex(w => w.fridayDate === week.fridayDate) + startTimelineColIdx;
        const weekCell = worksheet.getCell(taskRowIdx, weekColIdx);
        
        // Calculate which days are active for this week (and which fall on an applied holiday)
        const dayStates = calculateActiveDaysForWeek(task, week, activeHolidayMap);
        const hasHoliday = dayStates.some(s => s === 'holiday');

        if (hasHoliday) {
          // Render as rich text so the 'H' holiday markers stand out in white
          // against the task's own colored cell background
          const baseFont = { name: fontName, size: 10, bold: true, color: { argb: barTextColor } };
          const holidayFont = { name: fontName, size: 10, bold: true, color: { argb: 'FFFFFFFF' } };
          const richText: { text: string; font: typeof baseFont }[] = [];
          dayStates.forEach((state, idx) => {
            if (idx > 0) richText.push({ text: ' ', font: baseFont });
            richText.push({
              text: state === 'holiday' ? 'H' : state === 'active' ? '▪' : '▫',
              font: state === 'holiday' ? holidayFont : baseFont
            });
          });
          weekCell.value = { richText };
        } else {
          weekCell.value = generateDayBoxes(dayStates);
          weekCell.font = {
            name: fontName,
            size: 10,
            bold: true,
            color: { argb: barTextColor }
          };
        }

        // Apply colored background fill
        weekCell.fill = barFill;
        weekCell.border = thinBorder;
        weekCell.alignment = { horizontal: 'center', vertical: 'middle' };
      });
    }

    currentRow++;

    // 9. Write Sub-Activity rows (indented under the task, no Gantt bar)
    const subActivities = task.subActivities || [];
    subActivities.forEach((subAct, subIdx) => {
      const subRowIdx = currentRow;

      // Col G: Sub-index (e.g. "1.1", "1.2")
      const subIdxCell = worksheet.getCell(subRowIdx, 7);
      subIdxCell.value = `${task.index}.${subIdx + 1}`;
      subIdxCell.font = subActivityFont;
      subIdxCell.alignment = { horizontal: 'center' };
      subIdxCell.border = thinBorder;

      // Col H: Sub-activity name (indented with arrow)
      const subActCell = worksheet.getCell(subRowIdx, 8);
      subActCell.value = `  ↳ ${subAct}`;
      subActCell.font = subActivityFont;
      subActCell.alignment = { horizontal: 'left', indent: 2 };
      subActCell.border = thinBorder;

      // Light fill for sub-activity rows
      const subActFill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFF9FAFB' }
      } as ExcelJS.Fill;

      for (let colIdx = 7; colIdx <= 16; colIdx++) {
        worksheet.getCell(subRowIdx, colIdx).fill = subActFill;
        if (colIdx > 8) {
          worksheet.getCell(subRowIdx, colIdx).border = thinBorder;
        }
      }

      currentRow++;
    });
  });

  // Freeze Panes (Freeze columns A-P, and rows 1-7)
  worksheet.views = [
    {
      state: 'frozen',
      xSplit: 16, // freeze columns A-P (columns 1 to 16)
      ySplit: 7,  // freeze rows 1-7
      topLeftCell: 'Q8',
      activeCell: 'Q8'
    }
  ];

  // Auto-Filter on Columns G-P
  worksheet.autoFilter = `G7:P7`;

  // Assumptions Section (below task rows)
  if (assumptions && assumptions.trim()) {
    const assumptionsStartRow = currentRow + 2; // Leave a blank row gap

    // Title
    const titleCell = worksheet.getCell(assumptionsStartRow, 7); // Column G
    titleCell.value = 'Assumptions & Notes';
    titleCell.font = { name: fontName, size: 13, bold: true, color: { argb: 'FF1F497D' } };
    worksheet.mergeCells(assumptionsStartRow, 7, assumptionsStartRow, 16);
    titleCell.border = {
      bottom: { style: 'medium', color: { argb: 'FF366092' } }
    };

    // Write each assumption line
    const lines = assumptions.split('\n').filter((l: string) => l.trim().length > 0);
    lines.forEach((line: string, idx: number) => {
      const rowIdx = assumptionsStartRow + 1 + idx;
      const cell = worksheet.getCell(rowIdx, 7);
      cell.value = line.trim();
      cell.font = { name: fontName, size: 11, color: { argb: 'FF333333' } };
      cell.alignment = { wrapText: true, vertical: 'top' };
      worksheet.mergeCells(rowIdx, 7, rowIdx, 16);
      currentRow = rowIdx;
    });
  }

  // Out of Scope Section (below assumptions or task rows)
  if (outOfScope && outOfScope.trim()) {
    const outOfScopeStartRow = currentRow + 2; // Leave a blank row gap

    // Title
    const titleCell = worksheet.getCell(outOfScopeStartRow, 7); // Column G
    titleCell.value = 'Out of Scope & Exclusions';
    titleCell.font = { name: fontName, size: 13, bold: true, color: { argb: 'FFC00000' } }; // Dark red header for exclusions
    worksheet.mergeCells(outOfScopeStartRow, 7, outOfScopeStartRow, 16);
    titleCell.border = {
      bottom: { style: 'medium', color: { argb: 'FFC00000' } }
    };

    // Write each out of scope line
    const lines = outOfScope.split('\n').filter((l: string) => l.trim().length > 0);
    lines.forEach((line: string, idx: number) => {
      const rowIdx = outOfScopeStartRow + 1 + idx;
      const cell = worksheet.getCell(rowIdx, 7);
      cell.value = line.trim();
      cell.font = { name: fontName, size: 11, color: { argb: 'FF333333' } };
      cell.alignment = { wrapText: true, vertical: 'top' };
      worksheet.mergeCells(rowIdx, 7, rowIdx, 16);
      currentRow = rowIdx;
    });
  }

  // Public Holidays Section (below out of scope / task rows)
  if ((vicHolidays && vicHolidays.length > 0) || (indiaHolidays && indiaHolidays.length > 0)) {
    const holidaysStartRow = currentRow + 2; // Leave a blank row gap

    // Title
    const titleCell = worksheet.getCell(holidaysStartRow, 7); // Column G
    titleCell.value = 'Public Holidays';
    titleCell.font = { name: fontName, size: 13, bold: true, color: { argb: 'FF1F497D' } };
    worksheet.mergeCells(holidaysStartRow, 7, holidaysStartRow, 16);
    titleCell.border = {
      bottom: { style: 'medium', color: { argb: 'FF366092' } }
    };

    // Sub-headers: Vic Holidays in column G, Ind Holidays in column J
    const subHeaderRow = holidaysStartRow + 1;
    const vicHeaderCell = worksheet.getCell(subHeaderRow, 7);
    vicHeaderCell.value = 'Vic Holidays';
    vicHeaderCell.font = { name: fontName, size: 11, bold: true, color: { argb: 'FF92400E' } };

    const indHeaderCell = worksheet.getCell(subHeaderRow, 10);
    indHeaderCell.value = 'Ind Holidays';
    indHeaderCell.font = { name: fontName, size: 11, bold: true, color: { argb: 'FF92400E' } };

    const maxRows = Math.max(vicHolidays?.length || 0, indiaHolidays?.length || 0);
    for (let i = 0; i < maxRows; i++) {
      const rowIdx = subHeaderRow + 1 + i;

      const vic = vicHolidays?.[i];
      if (vic) {
        const cell = worksheet.getCell(rowIdx, 7);
        cell.value = `${vic.date} — ${vic.name}`;
        cell.font = { name: fontName, size: 10, color: { argb: 'FF333333' } };
      }

      const ind = indiaHolidays?.[i];
      if (ind) {
        const cell = worksheet.getCell(rowIdx, 10);
        cell.value = `${ind.date} — ${ind.name}`;
        cell.font = { name: fontName, size: 10, color: { argb: 'FF333333' } };
      }

      currentRow = rowIdx;
    }
  }

  // Create Background worksheet if background text exists
  if (background && background.trim()) {
    const backgroundSheet = workbook.addWorksheet('Background');
    
    // Set column widths
    backgroundSheet.getColumn(1).width = 3;  // Margin
    backgroundSheet.getColumn(2).width = 80; // Content
    backgroundSheet.getColumn(3).width = 3;  // Margin
    
    // Page Setup
    backgroundSheet.pageSetup = {
      orientation: 'portrait',
      fitToPage: true,
      fitToWidth: 1,
      fitToHeight: 0,
      paperSize: 9, // A4
      margins: {
        left: 0.75,
        right: 0.75,
        top: 1.0,
        bottom: 1.0,
        header: 0.3,
        footer: 0.3
      }
    };

    // Header
    backgroundSheet.headerFooter = {
      oddHeader: `&L&"Aptos Narrow,Bold"&12${project.name} - Project Background&R&"Aptos Narrow"&10Customer: ${project.customer}`,
      oddFooter: `&L&"Aptos Narrow,Italic"&9[Company Logo/Name Placeholder]&R&"Aptos Narrow"&9Page &P of &N`
    };

    // Title
    const titleCell = backgroundSheet.getCell('B2');
    titleCell.value = 'Project Background';
    titleCell.font = { name: fontName, size: 16, bold: true, color: { argb: 'FF1F497D' } };
    backgroundSheet.mergeCells('B2:B2');

    // Subtitle with project info
    const subtitleCell = backgroundSheet.getCell('B3');
    subtitleCell.value = `${project.name} - ${project.customer}`;
    subtitleCell.font = { name: fontName, size: 12, italic: true, color: { argb: 'FF595959' } };
    backgroundSheet.mergeCells('B3:B3');

    // Divider
    const dividerCell = backgroundSheet.getCell('B4');
    dividerCell.border = {
      bottom: { style: 'medium', color: { argb: 'FF366092' } }
    };

    // Background content starting from row 6
    const backgroundLines = background.split('\n');
    let currentBackgroundRow = 6;

    backgroundLines.forEach((line: string) => {
      const cell = backgroundSheet.getCell(currentBackgroundRow, 2);
      cell.value = line;
      cell.font = { name: fontName, size: 11, color: { argb: 'FF333333' } };
      cell.alignment = { wrapText: true, vertical: 'top' };
      
      currentBackgroundRow++;
    });
  }

  // Create MAW Deliverables worksheet if mawDeliverables text exists
  if (mawDeliverables && mawDeliverables.trim()) {
    const mawSheet = workbook.addWorksheet('MAW Deliverables');
    
    // Set column widths
    mawSheet.getColumn(1).width = 3;  // Margin
    mawSheet.getColumn(2).width = 80; // Content
    mawSheet.getColumn(3).width = 3;  // Margin
    
    // Page Setup
    mawSheet.pageSetup = {
      orientation: 'portrait',
      fitToPage: true,
      fitToWidth: 1,
      fitToHeight: 0,
      paperSize: 9, // A4
      margins: {
        left: 0.75,
        right: 0.75,
        top: 1.0,
        bottom: 1.0,
        header: 0.3,
        footer: 0.3
      }
    };

    // Header
    mawSheet.headerFooter = {
      oddHeader: `&L&"Aptos Narrow,Bold"&12${project.name} - MAW Deliverables&R&"Aptos Narrow"&10Customer: ${project.customer}`,
      oddFooter: `&L&"Aptos Narrow,Italic"&9[Company Logo/Name Placeholder]&R&"Aptos Narrow"&9Page &P of &N`
    };

    // Title
    const titleCell = mawSheet.getCell('B2');
    titleCell.value = 'MAW Deliverables';
    titleCell.font = { name: fontName, size: 16, bold: true, color: { argb: 'FF1F497D' } };
    mawSheet.mergeCells('B2:B2');

    // Subtitle with project info
    const subtitleCell = mawSheet.getCell('B3');
    subtitleCell.value = `${project.name} - ${project.customer}`;
    subtitleCell.font = { name: fontName, size: 12, italic: true, color: { argb: 'FF595959' } };
    mawSheet.mergeCells('B3:B3');

    // Divider
    const dividerCell = mawSheet.getCell('B4');
    dividerCell.border = {
      bottom: { style: 'medium', color: { argb: 'FF366092' } }
    };

    // MAW Deliverables content starting from row 6
    const mawLines = mawDeliverables.split('\n');
    let currentMawRow = 6;

    mawLines.forEach((line: string) => {
      const cell = mawSheet.getCell(currentMawRow, 2);
      cell.value = line;
      cell.font = { name: fontName, size: 11, color: { argb: 'FF333333' } };
      cell.alignment = { wrapText: true, vertical: 'top' };
      
      currentMawRow++;
    });
  }

  // Generate and Download Excel
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  });
  const filename = `${project.name.replace(/\s+/g, '_')}_Schedule.xlsx`;
  saveAs(blob, filename);
}
