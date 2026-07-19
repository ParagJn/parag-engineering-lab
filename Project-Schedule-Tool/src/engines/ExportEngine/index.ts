import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';
import type { Project } from '../../models/Project';
import type { Task } from '../../models/Task';
import type { Week } from '../../models/Week';

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

export async function exportProjectToExcel(
  project: Project,
  tasks: Task[],
  weeks: Week[]
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

  // Set metadata columns G-M
  worksheet.getColumn(7).width = 8;    // G: Index
  worksheet.getColumn(8).width = 32;   // H: Activity/Task
  worksheet.getColumn(9).width = 13;   // I: Est. Hours
  worksheet.getColumn(10).width = 13;  // J: Est. Days
  worksheet.getColumn(11).width = 13;  // K: Est. Weeks
  worksheet.getColumn(12).width = 8;    // L: FTE
  worksheet.getColumn(13).width = 13;  // M: Dependency

  // Set timeline columns N onwards
  const startTimelineColIdx = 14; // Col N is 14
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

  // Week Ending Dates Merged Header (Col N to last week column)
  const lastWeekColIdx = startTimelineColIdx + weeks.length - 1;
  const lastWeekColLetter = getColumnLetter(lastWeekColIdx);
  const weekEndingRange = `N4:${lastWeekColLetter}4`;
  worksheet.mergeCells(weekEndingRange);
  const weekEndingHeaderCell = worksheet.getCell('N4');
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
    { col: 7, val: 'Index' },
    { col: 8, val: 'Activity/Task' },
    { col: 9, val: 'Est. Hours' },
    { col: 10, val: 'Est. Days' },
    { col: 11, val: 'Est Weeks' },
    { col: 12, val: 'FTE' },
    { col: 13, val: 'Dependency' }
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

  // 7. Write Task Rows (starting from Row 8)
  tasks.forEach((task, taskIdx) => {
    const rowIdx = 8 + taskIdx;

    // Col G: Index
    const indexCell = worksheet.getCell(rowIdx, 7);
    indexCell.value = task.index;
    indexCell.font = defaultFont;
    indexCell.alignment = { horizontal: 'center' };
    indexCell.border = thinBorder;

    // Col H: Activity/Task Name
    const activityCell = worksheet.getCell(rowIdx, 8);
    activityCell.value = task.activity;
    activityCell.font = defaultFont;
    activityCell.alignment = { horizontal: 'left' };
    activityCell.border = thinBorder;

    // Col I: Est. Hours
    const hoursCell = worksheet.getCell(rowIdx, 9);
    hoursCell.value = task.estimatedHours;
    hoursCell.font = defaultFont;
    hoursCell.numFmt = '#,##0';
    hoursCell.alignment = { horizontal: 'center' };
    hoursCell.border = thinBorder;

    // Col J: Est. Days (=ROUND(I{row}/8, 0))
    const daysCell = worksheet.getCell(rowIdx, 10);
    daysCell.value = { formula: `=ROUND(I${rowIdx}/8,0)` };
    daysCell.font = defaultFont;
    daysCell.numFmt = '#,##0';
    daysCell.alignment = { horizontal: 'center' };
    daysCell.border = thinBorder;

    // Col K: Est. Weeks (=ROUND(J{row}/5, 0))
    const weeksCell = worksheet.getCell(rowIdx, 11);
    weeksCell.value = { formula: `=ROUND(J${rowIdx}/5,0)` };
    weeksCell.font = defaultFont;
    weeksCell.numFmt = '#,##0';
    weeksCell.alignment = { horizontal: 'center' };
    weeksCell.border = thinBorder;

    // Col L: FTE
    const fteCell = worksheet.getCell(rowIdx, 12);
    fteCell.value = task.fte;
    fteCell.font = defaultFont;
    fteCell.numFmt = '#,##0';
    fteCell.alignment = { horizontal: 'center' };
    fteCell.border = thinBorder;

    // Col M: Dependency
    const depCell = worksheet.getCell(rowIdx, 13);
    depCell.value = task.dependency || null;
    depCell.font = defaultFont;
    depCell.alignment = { horizontal: 'center' };
    depCell.border = thinBorder;

    // Apply alternating row shading to the task metadata columns G-M
    if (taskIdx % 2 === 1) {
      for (let colIdx = 7; colIdx <= 13; colIdx++) {
        worksheet.getCell(rowIdx, colIdx).fill = alternateRowFill;
      }
    }

    // Set timeline cells borders (empty grid style)
    weeks.forEach((_, idx) => {
      const colIdx = startTimelineColIdx + idx;
      worksheet.getCell(rowIdx, colIdx).border = thinBorder;
    });

    // 8. Draw Timeline Task Color Bar
    const weekAss = task.weekAssignments || {};
    const activeWeeks = weeks.filter(w => (weekAss[w.fridayDate] || 0) > 0);

    if (activeWeeks.length > 0) {
      // Find starting and ending week columns
      const firstActiveWeek = activeWeeks[0];
      const lastActiveWeek = activeWeeks[activeWeeks.length - 1];

      const startCol = weeks.findIndex(w => w.fridayDate === firstActiveWeek.fridayDate) + startTimelineColIdx;
      const endCol = weeks.findIndex(w => w.fridayDate === lastActiveWeek.fridayDate) + startTimelineColIdx;

      // Merge active columns in this row
      if (startCol < endCol) {
        worksheet.mergeCells(rowIdx, startCol, rowIdx, endCol);
      }

      // Configure the merged cell representing the bar
      const barCell = worksheet.getCell(rowIdx, startCol);
      barCell.value = `${task.fte} FTE`;

      const barColorHex = hexToArgb(task.color, 'FF2196F3');
      const barFill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: barColorHex }
      } as ExcelJS.Fill;

      // Style all cells in the bar range to ensure fill and border are drawn nicely
      for (let c = startCol; c <= endCol; c++) {
        const cCell = worksheet.getCell(rowIdx, c);
        cCell.fill = barFill;
        cCell.border = thinBorder;
      }

      // Style the text inside the bar
      // Determine appropriate text color for contrast (simple luminance heuristic)
      const r = parseInt(barColorHex.substring(2, 4), 16);
      const g = parseInt(barColorHex.substring(4, 6), 16);
      const b = parseInt(barColorHex.substring(6, 8), 16);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      const barTextColor = luminance > 0.6 ? 'FF000000' : 'FFFFFFFF'; // black for light background, white for dark

      barCell.font = {
        name: fontName,
        size: 10,
        bold: true,
        color: { argb: barTextColor }
      };
      barCell.alignment = { horizontal: 'center', vertical: 'middle' };
    }
  });

  // Freeze Panes (Freeze columns A-M, and rows 1-7)
  worksheet.views = [
    {
      state: 'frozen',
      xSplit: 13, // freeze columns A-M (columns 1 to 13)
      ySplit: 7,  // freeze rows 1-7
      topLeftCell: 'N8',
      activeCell: 'N8'
    }
  ];

  // Auto-Filter on Columns G-M
  worksheet.autoFilter = `G7:M7`;

  // Generate and Download Excel
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  });
  const filename = `${project.name.replace(/\s+/g, '_')}_Schedule.xlsx`;
  saveAs(blob, filename);
}
