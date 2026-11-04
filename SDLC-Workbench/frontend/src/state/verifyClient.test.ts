import { describe, expect, it } from 'vitest'
import { ContractError, ServerRefused, makeClient } from '../api'
import run from '../contract/verify_run.json'
import list from '../contract/verify_list.json'
import error422 from '../contract/error_422_verify.json'

const reply = (body: unknown, status = 200) => async () => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('the Build Verify calls', () => {
  it('start a check with a POST to the project\'s verify address, in the person\'s name, with the backend folder only', async () => {
    const seen: { url: string; init: RequestInit }[] = []
    const client = makeClient(async (url, init) => { seen.push({ url: String(url), init: init ?? {} }); return new Response(JSON.stringify(run), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    const made = await client.runVerify('p001', 'Ann', '/x/back')
    expect(made.id).toBe(1)
    expect(seen[0].url).toBe('/api/projects/p001/verify'); expect(seen[0].init.method).toBe('POST')
    expect(JSON.parse(String(seen[0].init.body))).toEqual({ backend_path: '/x/back' }); expect(new Headers(seen[0].init.headers).get('X-Actor')).toBe('Ann')
    await client.runVerify('p001', 'Ann', '/x/other')
    expect(JSON.parse(String(seen[1].init.body))).toEqual({ backend_path: '/x/other' })                      // no frontend_path is ever sent: the server refuses it
  })
  it('send exactly the backend folder and nothing else, whatever the caller passes', async () => {
    const seen: string[] = []
    const client = makeClient(async (_url, init) => { seen.push(String(init?.body)); return new Response(JSON.stringify(run), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    await (client.runVerify as (...a: unknown[]) => Promise<unknown>)('p001', 'Ann', '/x/back', '/x/front')
    expect(Object.keys(JSON.parse(seen[0]))).toEqual(['backend_path'])
  })
  it('read the list and one run from their own addresses', async () => {
    const urls: string[] = []
    const client = makeClient(async (url) => { urls.push(String(url)); return new Response(JSON.stringify(String(url).endsWith('/verify') ? list : run), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    expect((await client.verifyRuns('p001')).runs).toHaveLength(1); expect((await client.verifyRun('p001', 7)).id).toBe(1)
    expect(urls).toEqual(['/api/projects/p001/verify', '/api/projects/p001/verify/7'])
  })
  it('carry the server\'s sentence when a folder cannot be read, and refuse an answer in the wrong shape', async () => {
    const refused = await makeClient(reply(error422, 422)).runVerify('p001', 'Ann', '/nope').catch((e) => e)
    expect(refused).toBeInstanceOf(ServerRefused); expect(refused.message).toContain('there is no folder at')
    const bad = await makeClient(reply({ id: 1 })).verifyRun('p001', 1).catch((e) => e)
    expect(bad).toBeInstanceOf(ContractError)
  })
  it('do not let a project ID escape the address', async () => {
    const urls: string[] = []
    const client = makeClient(async (url) => { urls.push(String(url)); return new Response(JSON.stringify(list), { status: 200, headers: { 'Content-Type': 'application/json' } }) })
    await client.verifyRuns('../x?y')
    expect(urls[0]).toBe('/api/projects/..%2Fx%3Fy/verify')
  })
})
