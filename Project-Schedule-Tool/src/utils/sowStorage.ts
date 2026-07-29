/**
 * Utility functions for saving and loading SoW drafts
 */

export interface SoWDraft {
  project_name: string;
  customer: string;
  background: string;
  assumptions?: string;
  out_of_scope?: string;
  sow_content: string;
  timestamp: string;
  version: string;
}

/**
 * Save SoW content to a JSON file in the drafts folder via backend API
 */
export async function saveSoWDraft(draft: SoWDraft): Promise<void> {
  try {
    const response = await fetch('http://localhost:8000/save/sow-draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(draft),
    });

    if (!response.ok) {
      throw new Error(`Failed to save SoW draft: ${response.statusText}`);
    }

    const result = await response.json();
    console.log(`✓ ${result.message}`);
    console.log(`  Path: ${result.path}`);
  } catch (error) {
    console.error('Error saving SoW draft:', error);
    throw error;
  }
}

/**
 * Parse markdown content into structured sections for rendering
 */
export interface SoWSection {
  type: 'heading' | 'subheading' | 'paragraph' | 'bullet' | 'table' | 'bold';
  content: string;
  level?: number; // for headings
}

export function parseMarkdownToSections(markdown: string): SoWSection[] {
  const lines = markdown.split('\n');
  const sections: SoWSection[] = [];
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    if (!trimmed) {
      continue; // Skip empty lines
    }
    
    // Heading (##)
    if (trimmed.startsWith('## ')) {
      sections.push({
        type: 'heading',
        content: trimmed.substring(3),
        level: 2
      });
    }
    // Subheading (###)
    else if (trimmed.startsWith('### ')) {
      sections.push({
        type: 'subheading',
        content: trimmed.substring(4),
        level: 3
      });
    }
    // Bullet point
    else if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
      sections.push({
        type: 'bullet',
        content: trimmed.substring(2)
      });
    }
    // Table header or row
    else if (trimmed.includes('|')) {
      sections.push({
        type: 'table',
        content: trimmed
      });
    }
    // Regular paragraph
    else {
      sections.push({
        type: 'paragraph',
        content: trimmed
      });
    }
  }
  
  return sections;
}
