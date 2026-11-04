// S22a: the checklist is no longer Deploy's alone. Everything it says (title, groups, the words for the answers) comes from the server's list for the phase,
// and every address carries the phase. Drawn here with a made-up hand-over style list so nothing is borrowed from Deploy by accident.
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { ContractError, decodeChecklist, makeClient, type Checklist } from '../api'
import answered from '../contract/checklist_answered.json'
import { allChecks, headline, reportPath, standing, wordFor } from '../lib/checklist'
import { answerCheckWith, answerForPhase, checklistWanted, loadChecklistWith } from '../state/useProjectScreen'
import { ChecklistPanel } from './ChecklistPanel'

const html = (node: ReactElement) => renderToStaticMarkup(node).replace(/<!-- -->/g, '')
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))
const handover = (): Checklist => {
  const raw = clone(answered) as Record<string, any>
  raw.phase = 'handover'; raw.title = 'Handover sign-off'
  raw.answer_words = { go: 'Accept', no_go: 'Not accepted', not_applicable: 'Not applicable' }
  raw.groups[0].key = 'support_given'; raw.groups[0].title = 'What support has been given'
  raw.totals.no_go = 1
  return decodeChecklist(raw)
}
const panel = (c: Checklist) => html(<ChecklistPanel checklist={c} canAnswer busy={null} error={null} onAnswer={() => {}} projectId="p1" />)
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })

describe('the list says what it is', () => {
  it('reads the phase, the title and the answer words, and refuses a list without them', () => {
    const list = handover()
    expect(list.phase).toBe('handover'); expect(list.title).toBe('Handover sign-off'); expect(list.answer_words.go).toBe('Accept')
    for (const key of ['phase', 'title', 'answer_words']) {
      const bad = clone(answered) as Record<string, unknown>; delete bad[key]
      expect(() => decodeChecklist(bad), key).toThrow(ContractError)
    }
    for (const word of ['go', 'no_go', 'not_applicable']) {
      const gone = clone(answered) as Record<string, any>; delete gone.answer_words[word]
      expect(() => decodeChecklist(gone), `${word} missing`).toThrow(ContractError)
      const number = clone(answered) as Record<string, any>; number.answer_words[word] = 7
      expect(() => decodeChecklist(number), `${word} a number`).toThrow(ContractError)
    }
  })
  it('takes any group key the server sends, in the server\'s order', () => {
    expect(handover().groups[0].key).toBe('support_given'); expect(handover().groups.map((g) => g.title)[0]).toBe('What support has been given')
  })
})

describe('the words of an answer', () => {
  it('come from the list, not from Deploy', () => {
    const list = handover()
    expect(wordFor(list, 'go')).toBe('Accept'); expect(wordFor(list, 'no_go')).toBe('Not accepted'); expect(wordFor(list, 'not_applicable')).toBe('Not applicable')
    expect(standing(allChecks(list)[0], list)).toBe('Accept')
  })
  it('say the headline in the list\'s words', () => {
    expect(headline(handover())).toBe('4 of 16 answered · 1 Not accepted · overall: Accept')
  })
})

describe('the panel', () => {
  it('shows the list\'s own title, group and wording and nothing of Deploy\'s', () => {
    const out = panel(handover())
    expect(out).toContain('aria-label="Handover sign-off"'); expect(out).toContain('>Handover sign-off</h3>'); expect(out).toContain('What support has been given')
    expect(out).toContain('>Accept</button>'); expect(out).toContain('>Not accepted</button>')
    expect(out).toContain('Choose Accept, Not accepted or Not applicable for each')
    expect(out).toContain('A Not accepted does not stop you approving the phase')
    expect(out).not.toContain('Deployment checklist'); expect(out).not.toContain('>Go</button>'); expect(out).not.toContain('No-go')
  })
  it('writes who answered how in the list\'s words, for an answered check', () => {
    const out = panel(handover())
    expect(out).toMatch(/Accept · Demo Person · /); expect(out).not.toMatch(/>Go · /)
  })
  it('points the report links at its own phase', () => {
    const out = panel(handover())
    expect(out).toContain('/api/projects/p1/handover/checklist/report?format=md'); expect(out).toContain('/api/projects/p1/handover/checklist/report?format=docx'); expect(out).not.toContain('/deploy/checklist/report')
  })
})

describe('the addresses', () => {
  it('carry the phase, Deploy by default', () => {
    expect(reportPath('p1', 'md')).toBe('/api/projects/p1/deploy/checklist/report?format=md')
    expect(reportPath('p1', 'docx', 'handover')).toBe('/api/projects/p1/handover/checklist/report?format=docx')
    expect(reportPath('p1', 'md', 'a/b')).toBe('/api/projects/p1/a%2Fb/checklist/report?format=md')
  })
  it('are used by the client for reading and for saving an answer', async () => {
    const seen: { url: string }[] = []
    const client = makeClient(async (url) => { seen.push({ url: String(url) }); return json(answered) })
    await client.checklist('p1'); await client.checklist('p1', 'handover'); await client.answerCheck('p1', 'CHK-001', 'Ann', 'go', '', 'handover'); await client.answerCheck('p1', 'CHK-001', 'Ann', 'go', '')
    expect(seen.map((s) => s.url)).toEqual(['/api/projects/p1/deploy/checklist', '/api/projects/p1/handover/checklist', '/api/projects/p1/handover/checklist/CHK-001', '/api/projects/p1/deploy/checklist/CHK-001'])
  })
  it('are given the phase by the screen\'s answering function, Deploy by default', async () => {
    const client = { answerCheck: vi.fn(async () => handover()) }
    const ui = { setBusy: vi.fn(), setError: vi.fn(), setList: vi.fn(), refresh: vi.fn(async () => {}) }
    await answerCheckWith(client, ui, 'p1', 'CHK-001', 'Ann', 'go', 'n', 'handover')
    expect(client.answerCheck).toHaveBeenCalledWith('p1', 'CHK-001', 'Ann', 'go', 'n', 'handover')
    await answerCheckWith(client, ui, 'p1', 'CHK-001', 'Ann', 'go', 'n')
    expect(client.answerCheck).toHaveBeenLastCalledWith('p1', 'CHK-001', 'Ann', 'go', 'n', 'deploy')
  })
})

describe('the screen asks for, and answers into, the phase it is showing', () => {
  it('loads the checklist of that phase, and nothing for a phase without one', async () => {
    const client = { checklist: vi.fn(async () => handover()) }
    expect(await loadChecklistWith(client, 'p1', 'deploy')).toBeTruthy(); expect(client.checklist).toHaveBeenCalledWith('p1', 'deploy')
    expect(loadChecklistWith(client, 'p1', 'design')).toBeNull(); expect(client.checklist).toHaveBeenCalledTimes(1)
  })
  it('answers into the phase it was made for', async () => {
    const client = { answerCheck: vi.fn(async () => handover()) }
    const ui = { setBusy: vi.fn(), setError: vi.fn(), setList: vi.fn(), refresh: vi.fn(async () => {}) }
    await answerForPhase(client, ui, 'p1', 'handover', 'Ann')('CHK-002', 'no_go', 'why')
    expect(client.answerCheck).toHaveBeenCalledWith('p1', 'CHK-002', 'Ann', 'no_go', 'why', 'handover')
  })
})

describe('which phases load a checklist', () => {
  it('is Deploy and handover, and no other', () => {
    expect(checklistWanted('deploy')).toBe(true); expect(checklistWanted('handover')).toBe(true)
    for (const key of ['setup', 'requirements', 'design', 'architecture', 'build', '']) expect(checklistWanted(key), key).toBe(false)
  })
})
