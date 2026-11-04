import { describe, expect, it } from 'vitest'
import { CODE_ARTEFACT_TYPES, PROTOTYPE_NOTICE, downloadName, extensionFor, filePathBefore, isCodeArtefact, lineCount } from './codeFiles'

describe('which artefacts hold code', () => {
  it('exactly the four the server writes into a workspace', () => {
    expect([...CODE_ARTEFACT_TYPES]).toEqual(['database_schema', 'backend_code', 'frontend_code', 'test_suite'])
    for (const t of CODE_ARTEFACT_TYPES) expect(isCodeArtefact(t)).toBe(true)
  })
  it.each(['low_level_design', 'test_report', 'code_security_review', 'personas', ''])('%s does not', (t) => expect(isCodeArtefact(t)).toBe(false))
})

describe('the prototype notice', () => {
  it('says what the code is and what it is not, in plain words', () => {
    expect(PROTOTYPE_NOTICE.title).toBe('Prototype code')
    expect(PROTOTYPE_NOTICE.text).toBe('Generated to show the idea and to be tried out. It is not production code: have production code written and reviewed outside this tool.')
  })
})

describe('the format a download is saved in', () => {
  it.each([['sql', 'sql'], ['python', 'py'], ['py', 'py'], ['javascript', 'js'], ['js', 'js'], ['html', 'html'], ['css', 'css'], ['json', 'json'], ['bash', 'sh']])('language %s gives .%s', (language, ext) => {
    expect(extensionFor(language, null)).toBe(ext)
  })
  it('the language is read without regard to case or spaces', () => expect(extensionFor('  SQL ', null)).toBe('sql'))
  it('an unknown or missing language falls back to plain text', () => {
    for (const language of ['brainfuck', '', null, '   ']) expect(extensionFor(language, null)).toBe('txt')
  })
  it('the file name wins over the language when it has a type we know', () => {
    expect(extensionFor('python', 'db/schema.sql')).toBe('sql')
    expect(extensionFor(null, 'frontend/app.js')).toBe('js')
  })
  it('a file name with a type we do not know falls back to the language, then to text', () => {
    expect(extensionFor('python', 'notes.weird')).toBe('py')
    expect(extensionFor(null, 'notes.weird')).toBe('txt')
    expect(extensionFor(null, 'Makefile')).toBe('txt')
  })
  it('a dot at either end of a name is not a type', () => {
    expect(extensionFor(null, '.hidden')).toBe('txt')
    expect(extensionFor(null, 'trailing.')).toBe('txt')
  })
})

describe('the name a download is saved as', () => {
  it('is the last part of the path, with its own type', () => {
    expect(downloadName('db/schema.sql', 'sql')).toBe('schema.sql')
    expect(downloadName('backend/main.py', 'python')).toBe('main.py')
    expect(downloadName('frontend/css/site.css', null)).toBe('site.css')
  })
  it('keeps the type from the language when the name has none', () => expect(downloadName('backend/runner', 'python')).toBe('runner.py'))
  it('a block with no file name is named from its language', () => {
    expect(downloadName(null, 'sql')).toBe('code.sql')
    expect(downloadName(null, 'javascript', 'snippet')).toBe('snippet.js')
    expect(downloadName(null, null)).toBe('code.txt')
  })
  it('never carries a folder, a leading dot or an unsafe character', () => {
    expect(downloadName('../../etc/pass wd.py', 'python')).toBe('pass_wd.py')
    expect(downloadName('a/b/<x>.sql', 'sql')).toBe('_x_.sql')
    expect(downloadName('.hidden.py', 'python')).not.toMatch(/^\./)
    expect(downloadName('///', 'sql')).toBe('code.sql')
  })
})

describe('counting lines', () => {
  it('counts the lines of text, with or without a final newline', () => {
    expect(lineCount('a\nb\nc\n')).toBe(3)
    expect(lineCount('a\nb\nc')).toBe(3)
    expect(lineCount('one')).toBe(1)
    expect(lineCount('')).toBe(0)
  })
})

describe('finding the file name the artefact gave a code block', () => {
  const BODY = ['## Code', 'File: db/schema.sql', '```sql', 'SELECT 1;', '```', '', 'File: backend/main.py', '```python', 'x = 1', '```', '', '```python', 'orphan', '```'].join('\n')
  it('reads the File line straight above a block (the block starts on the line after it)', () => {
    expect(filePathBefore(BODY, 3)).toBe('db/schema.sql')
    expect(filePathBefore(BODY, 8)).toBe('backend/main.py')
  })
  it('a block with no File line above it has no name', () => expect(filePathBefore(BODY, 12)).toBeNull())
  it.each(['**File: a.sql**', '### File: a.sql', '- File: a.sql', 'File: `a.sql`', '  File:   a.sql  '])('reads the usual ways a model writes it: %s', (line) => {
    expect(filePathBefore(`${line}\n\`\`\`sql\nx\n\`\`\``, 2)).toBe('a.sql')
  })
  it('skips one blank line but not ordinary text', () => {
    expect(filePathBefore('File: a.sql\n\n```sql\nx\n```', 3)).toBe('a.sql')
    expect(filePathBefore('File: a.sql\nsome words\n```sql\nx\n```', 3)).toBeNull()
  })
  it('the first line of the text has nothing above it', () => expect(filePathBefore('```sql\nx\n```', 1)).toBeNull())
})
