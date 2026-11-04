// Code in a Build artefact (S18): collapsed until opened, downloadable in its own format, marked as a prototype, with a disabled Connector placeholder.
// Rendered to static HTML, like every component test here: what is asserted is what a person would see.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { decodeArtefactDetail, type ArtefactDetail } from '../api'
import artefactJson from '../contract/artefact_detail.json'
import { PROTOTYPE_NOTICE } from '../lib/codeFiles'
import { ArtefactReader } from './ArtefactReader'
import { CodeBlock } from './CodeBlock'
import { ConnectorButton } from './ConnectorButton'
import { PrototypeNotice } from './PrototypeNotice'
import { SafeMarkdown } from './SafeMarkdown'

const html = (node: React.ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const base = decodeArtefactDetail(artefactJson)
const BODY = [
  '## Overview', 'Two files.', '', '## Code',
  'File: db/schema.sql', '```sql', 'CREATE TABLE notes (id INTEGER);', '```', '',
  'File: backend/main.py', '```python', 'from fastapi import FastAPI', 'app = FastAPI()', '```', '',
  '```javascript', 'let orphan = 1;', '```',
].join('\n')
const as = (type: string, body = BODY): ArtefactDetail => ({ ...base, type, body, renderings: null, review: null })
const read = (a: ArtefactDetail) => html(<ArtefactReader artefact={a} onClose={() => {}} onVersion={() => {}} />)

describe('code in a Build artefact', () => {
  const out = read(as('backend_code'))
  it('every block is collapsed on open: a details element with no open attribute', () => {
    expect(out.match(/<details class="code-block/g)).toHaveLength(3)
    expect(out).not.toMatch(/<details[^>]*\sopen/)
  })
  it('the summary says which file it is, how long and in what format', () => {
    expect(out).toContain('db/schema.sql</span><span class="text-xs text-slate-500">1 line · .sql')
    expect(out).toContain('backend/main.py</span><span class="text-xs text-slate-500">2 lines · .py')
  })
  it('each file can be downloaded under its own name and type', () => {
    expect(out).toContain('aria-label="Download schema.sql"')
    expect(out).toContain('aria-label="Download main.py"')
  })
  it('a block with no file name is named from its language, and still downloads', () => {
    expect(out).toContain('javascript block</span>')
    expect(out).toContain('aria-label="Download code.js"')
  })
  it('the code itself is still there as text, inside a pre', () => {
    expect(out).toContain('<pre><code class="language-sql">CREATE TABLE notes (id INTEGER);')
  })
  it('code that looks like markup is escaped, never interpreted', () => {
    const evil = read(as('frontend_code', 'File: frontend/index.html\n```html\n<script>alert(1)</script><img src=x onerror=alert(1)>\n```\n'))
    expect(evil).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(evil).not.toMatch(/<script>alert/)
    expect(evil).not.toMatch(/<img src=x/)
    expect(evil).toContain('aria-label="Download index.html"')
  })
})

describe('the file types a download gets', () => {
  it.each([['sql', 'x.sql'], ['python', 'x.py'], ['javascript', 'x.js'], ['html', 'x.html'], ['css', 'x.css']])('%s block with a file name keeps its own type', (language, file) => {
    const out = html(<CodeBlock code="x" language={language} path={`folder/${file}`}><pre>x</pre></CodeBlock>)
    expect(out).toContain(`aria-label="Download ${file}"`)
  })
  it('a language it does not know falls back to .txt', () => {
    expect(html(<CodeBlock code="x" language="brainfuck" path={null}><pre>x</pre></CodeBlock>)).toContain('aria-label="Download code.txt"')
    expect(html(<CodeBlock code="x" language={null} path={null}><pre>x</pre></CodeBlock>)).toContain('aria-label="Download code.txt"')
  })
  it('one line reads as a line, not lines', () => expect(html(<CodeBlock code="x" language="sql" path="a.sql"><pre>x</pre></CodeBlock>)).toContain('1 line ·'))
})

describe('the prototype notice', () => {
  it('is shown on all four code artefacts, in the same words', () => {
    for (const type of ['database_schema', 'backend_code', 'frontend_code', 'test_suite']) {
      const out = read(as(type))
      expect(out).toContain('aria-label="Prototype notice"')
      expect(out).toContain(`<strong>${PROTOTYPE_NOTICE.title}.</strong> ${PROTOTYPE_NOTICE.text}`)
    }
  })
  it('stands on its own too, with the plain wording', () => {
    const out = html(<PrototypeNotice />)
    expect(out).toContain('role="note"')
    expect(out).toContain('It is not production code: have production code written and reviewed outside this tool.')
  })
})

describe('the Connector placeholder', () => {
  it('is disabled, says Coming soon, and is described by that caption', () => {
    const out = html(<ConnectorButton />)
    expect(out).toMatch(/<button[^>]*\sdisabled=""[^>]*aria-disabled="true"/)
    expect(out).toContain('aria-describedby="connector-soon"')
    expect(out).toContain('Connector')
    expect(out).toContain('id="connector-soon"')
    expect(out).toContain('Coming soon')
  })
  it('has no click behaviour to trigger', () => expect(html(<ConnectorButton />)).not.toContain('onclick'))
  it('is in the header area of every code artefact', () => {
    for (const type of ['database_schema', 'backend_code', 'frontend_code', 'test_suite']) expect(read(as(type))).toContain('Coming soon')
  })
})

describe('everything that is not code is untouched', () => {
  it.each(['low_level_design', 'functional_requirements', 'test_report', 'code_security_review', 'personas'])('%s has no banner, no connector and plain code blocks', (type) => {
    const out = read(as(type))
    expect(out).not.toContain('Prototype notice')
    expect(out).not.toContain('Coming soon')
    expect(out).not.toContain('code-block')
    expect(out).toContain('<pre><code class="language-sql">')
  })
  it('the markdown renderer collapses code only when asked to', () => {
    expect(html(<SafeMarkdown>{'```sql\nx\n```'}</SafeMarkdown>)).not.toContain('<details')
    expect(html(<SafeMarkdown collapseCode>{'```sql\nx\n```'}</SafeMarkdown>)).toContain('<details class="code-block')
  })
  it('a drawing in a code artefact is still a drawing, not a download block', () => {
    const out = html(<SafeMarkdown collapseCode>{'```svg\n<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>\n```'}</SafeMarkdown>)
    expect(out).not.toContain('code-block')
  })
})
