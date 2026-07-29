/**
 * Utility for exporting Statement of Work to Word document
 * Uses docx library to generate .docx files
 */

import { saveAs } from 'file-saver';

/**
 * Parse markdown-style content and convert to docx Document
 */
async function parseMarkdownToDocx(content: string, projectName: string) {
  // Dynamic import to reduce initial bundle size
  const { Document, Paragraph, TextRun, HeadingLevel, Packer, Table, TableRow, TableCell, WidthType } = await import('docx');
  
  const lines = content.split('\n');
  const paragraphs: any[] = [];

  // Add title
  paragraphs.push(
    new Paragraph({
      text: 'Statement of Work',
      heading: HeadingLevel.HEADING_1,
      spacing: {
        after: 200,
      },
    })
  );

  paragraphs.push(
    new Paragraph({
      text: projectName,
      heading: HeadingLevel.HEADING_2,
      spacing: {
        after: 400,
      },
    })
  );

  let inList = false;
  let currentParagraphText = '';
  let tableRows: string[] = [];
  let inTable = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Detect table rows (contains |)
    if (line.includes('|')) {
      if (currentParagraphText) {
        paragraphs.push(
          new Paragraph({
            children: [new TextRun(currentParagraphText)],
            spacing: { after: 200 },
          })
        );
        currentParagraphText = '';
      }
      
      tableRows.push(line);
      inTable = true;
      continue;
    }

    // If we were in a table and now hit a non-table line, create the table
    if (inTable && !line.includes('|')) {
      if (tableRows.length > 0) {
        // Filter out separator rows (---)
        const dataRows = tableRows.filter(row => !row.match(/^\|[\s\-:]+\|$/));
        
        if (dataRows.length > 0) {
          const rows = dataRows.map((row, idx) => {
            const cells = row
              .split('|')
              .map(cell => cell.trim())
              .filter(cell => cell.length > 0);
            
            const isHeader = idx === 0;
            
            return new TableRow({
              children: cells.map(cellText => 
                new TableCell({
                  children: [new Paragraph({
                    children: [new TextRun({
                      text: cellText,
                      bold: isHeader,
                    })],
                  })],
                  width: {
                    size: 100 / cells.length,
                    type: WidthType.PERCENTAGE,
                  },
                })
              ),
            });
          });
          
          paragraphs.push(
            new Table({
              rows,
              width: {
                size: 100,
                type: WidthType.PERCENTAGE,
              },
            })
          );
          
          paragraphs.push(new Paragraph({ text: '', spacing: { after: 200 } }));
        }
      }
      
      tableRows = [];
      inTable = false;
    }

    // Skip empty lines
    if (!line.trim()) {
      if (currentParagraphText) {
        paragraphs.push(
          new Paragraph({
            children: [new TextRun(currentParagraphText)],
            spacing: { after: 200 },
          })
        );
        currentParagraphText = '';
      }
      if (inList) {
        inList = false;
      }
      continue;
    }

    // H2 headers (##)
    if (line.startsWith('## ')) {
      if (currentParagraphText) {
        paragraphs.push(
          new Paragraph({
            children: [new TextRun(currentParagraphText)],
            spacing: { after: 200 },
          })
        );
        currentParagraphText = '';
      }
      paragraphs.push(
        new Paragraph({
          text: line.replace('## ', ''),
          heading: HeadingLevel.HEADING_1,
          spacing: {
            before: 400,
            after: 200,
          },
        })
      );
      continue;
    }

    // H3 headers (###)
    if (line.startsWith('### ')) {
      if (currentParagraphText) {
        paragraphs.push(
          new Paragraph({
            children: [new TextRun(currentParagraphText)],
            spacing: { after: 200 },
          })
        );
        currentParagraphText = '';
      }
      paragraphs.push(
        new Paragraph({
          text: line.replace('### ', ''),
          heading: HeadingLevel.HEADING_2,
          spacing: {
            before: 300,
            after: 150,
          },
        })
      );
      continue;
    }

    // Bullet points
    if (line.startsWith('• ') || line.startsWith('* ') || line.startsWith('- ')) {
      if (currentParagraphText) {
        paragraphs.push(
          new Paragraph({
            children: [new TextRun(currentParagraphText)],
            spacing: { after: 200 },
          })
        );
        currentParagraphText = '';
      }

      const bulletText = line.replace(/^[•\*\-]\s+/, '');
      const textRuns: any[] = [];

      // Parse bold text (**text**)
      const boldRegex = /\*\*(.*?)\*\*/g;
      let lastIndex = 0;
      let match;

      while ((match = boldRegex.exec(bulletText)) !== null) {
        // Add text before bold
        if (match.index > lastIndex) {
          textRuns.push(new TextRun(bulletText.substring(lastIndex, match.index)));
        }
        // Add bold text
        textRuns.push(new TextRun({ text: match[1], bold: true }));
        lastIndex = match.index + match[0].length;
      }

      // Add remaining text
      if (lastIndex < bulletText.length) {
        textRuns.push(new TextRun(bulletText.substring(lastIndex)));
      }

      paragraphs.push(
        new Paragraph({
          children: textRuns.length > 0 ? textRuns : [new TextRun(bulletText)],
          bullet: {
            level: 0,
          },
          spacing: { after: 100 },
        })
      );
      inList = true;
      continue;
    }

    // Regular paragraphs with bold support
    const textRuns: any[] = [];
    const boldRegex = /\*\*(.*?)\*\*/g;
    let lastIndex = 0;
    let match;

    while ((match = boldRegex.exec(line)) !== null) {
      // Add text before bold
      if (match.index > lastIndex) {
        textRuns.push(new TextRun(line.substring(lastIndex, match.index)));
      }
      // Add bold text
      textRuns.push(new TextRun({ text: match[1], bold: true }));
      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < line.length) {
      textRuns.push(new TextRun(line.substring(lastIndex)));
    }

    if (textRuns.length > 0) {
      paragraphs.push(
        new Paragraph({
          children: textRuns,
          spacing: { after: 150 },
        })
      );
    } else if (line.trim()) {
      paragraphs.push(
        new Paragraph({
          children: [new TextRun(line)],
          spacing: { after: 150 },
        })
      );
    }
  }

  return { Document, Packer, paragraphs };
}

/**
 * Export Statement of Work content to Word document
 */
export async function exportSoWToWord(content: string, projectName: string): Promise<void> {
  try {
    const { Document, Packer, paragraphs } = await parseMarkdownToDocx(content, projectName);
    
    const { convertInchesToTwip } = await import('docx');

    const doc = new Document({
      sections: [
        {
          properties: {
            page: {
              margin: {
                top: convertInchesToTwip(1),
                right: convertInchesToTwip(1),
                bottom: convertInchesToTwip(1),
                left: convertInchesToTwip(1),
              },
            },
          },
          children: paragraphs,
        },
      ],
    });

    // Generate the document as a blob
    const blob = await Packer.toBlob(doc);

    // Save the file
    const filename = `${projectName.replace(/\s+/g, '_')}_Statement_of_Work.docx`;
    saveAs(blob, filename);
  } catch (error) {
    console.error('Error exporting to Word:', error);
    throw new Error('Failed to export document. Please try again.');
  }
}
