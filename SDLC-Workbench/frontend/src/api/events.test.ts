import { describe, expect, it } from 'vitest'
import { ContractError, decodeEvent, followEvents, parseFrame, type RunEvent, type SourceLike } from '../api'
import events from '../contract/events.json'

const example = (type: string) => (events as Record<string, unknown>)[type]      // a fixture name: `type`, or `type.shape` for a second shape

describe('reading one stream frame', () => {
  const frame = (id: number, type: string, data: unknown) => `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify(data)}\n\n`

  it('a frame becomes the event it describes', () => {
    const e = parseFrame(frame(7, 'artefact.started', example('artefact.started')))
    expect(e).toMatchObject({ id: 7, type: 'artefact.started' })
  })
  it('a comment (the heartbeat and the live marker) is ignored', () => {
    expect(parseFrame(': live\n\n')).toBeNull()
    expect(parseFrame(': heartbeat\n\n')).toBeNull()
  })
  it('a frame with no data is ignored', () => {
    expect(parseFrame('id: 3\nevent: run.started\n\n')).toBeNull()
  })
  it('the dropped marker is recognised', () => {
    expect(parseFrame('event: dropped\ndata: {"reason":"too slow"}\n\n')).toEqual({ dropped: true })
  })
  it.each([['0'], ['-1'], ['1.5'], ['abc'], ['']])('an id of "%s" is refused', (id) => {
    expect(() => parseFrame(`id: ${id}\nevent: artefact.started\ndata: ${JSON.stringify(example('artefact.started'))}\n\n`)).toThrow(ContractError)
  })
  it('data that is not JSON is refused with a plain message', () => {
    expect(() => parseFrame('id: 1\nevent: artefact.started\ndata: {nope\n\n')).toThrow(/not JSON/)
  })
  it('an unknown event name is refused', () => {
    expect(() => decodeEvent(1, 'something.else', {})).toThrow(ContractError)
  })
  it('multi-line data is joined', () => {
    const json = JSON.stringify(example('artefact.started'), null, 1).split('\n')
    expect(parseFrame(`id: 2\nevent: artefact.started\n${json.map((l) => `data: ${l}`).join('\n')}\n\n`)).toMatchObject({ id: 2 })
  })
})

class FakeSource implements SourceLike {
  onmessage = null
  onerror: ((e: unknown) => void) | null = null
  closed = false
  listeners = new Map<string, (e: { data: string; lastEventId: string }) => void>()
  constructor(public url: string) {}
  addEventListener(type: string, listener: (e: { data: string; lastEventId: string }) => void) { this.listeners.set(type, listener) }
  close() { this.closed = true }
  emit(type: string, id: number, data: unknown) { this.listeners.get(type)!({ data: typeof data === 'string' ? data : JSON.stringify(data), lastEventId: String(id) }) }
}

function follow(afterId = 0) {
  const seen: RunEvent[] = []
  const log = { dropped: 0, problems: [] as string[], connected: [] as boolean[] }
  let source!: FakeSource
  const handle = followEvents('p1', afterId, {
    onEvent: (e) => seen.push(e), onDropped: () => { log.dropped += 1 }, onProblem: (m) => log.problems.push(m), onConnectionChange: (c) => log.connected.push(c),
  }, (url) => (source = new FakeSource(url)))
  return { seen, log, handle, source }
}

describe('following a project\'s events', () => {
  it('opens the stream after the id it already has, with the project id encoded', () => {
    const { source } = follow(41)
    expect(source.url).toBe('/api/projects/p1/events?after=41')
    let other!: FakeSource
    followEvents('a b/c', 0, { onEvent() {}, onDropped() {}, onProblem() {} }, (url) => (other = new FakeSource(url)))
    expect(other.url).toBe('/api/projects/a%20b%2Fc/events?after=0')
  })
  it('a negative or fractional starting id is made safe', () => {
    expect(follow(-5).source.url).toContain('after=0')
    expect(follow(3.9).source.url).toContain('after=3')
  })
  it('listens for every event name the server can send', () => {
    const { source } = follow()
    for (const name of ['run.started', 'artefact.finished', 'review.paused', 'run.stopped', 'dropped']) expect(source.listeners.has(name), name).toBe(true)
  })
  it('delivers a decoded event with the id the server gave it', () => {
    const { source, seen } = follow()
    source.emit('artefact.started', 12, example('artefact.started'))
    expect(seen).toHaveLength(1)
    expect(seen[0]).toMatchObject({ id: 12, type: 'artefact.started' })
  })
  it('a bad event is reported as a problem and does not stop the next one', () => {
    const { source, seen, log } = follow()
    source.emit('artefact.started', 1, { nonsense: true })
    source.emit('artefact.started', 2, example('artefact.started'))
    expect(log.problems).toHaveLength(1)
    expect(seen.map((e) => e.id)).toEqual([2])
  })
  it('the dropped marker asks the screen to catch up', () => {
    const { source, log } = follow()
    source.emit('dropped', 1, { reason: 'too slow' })
    expect(log.dropped).toBe(1)
  })
  it('nothing is delivered after close, and the source is closed', () => {
    const { source, seen, handle } = follow()
    handle.close()
    source.emit('artefact.started', 1, example('artefact.started'))
    expect(source.closed).toBe(true)
    expect(seen).toEqual([])
  })
  it('an error says "not connected" and the next event says "connected" again', () => {
    const { source, log } = follow()
    source.onerror!({})
    source.emit('artefact.started', 1, example('artefact.started'))
    expect(log.connected).toEqual([false, true])
  })
})
