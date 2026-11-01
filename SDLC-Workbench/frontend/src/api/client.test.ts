import { describe, expect, it } from 'vitest'
import { BackendUnreachable, ContractError, makeClient, ServerRefused } from './index'
import modes from '../contract/modes.json'
import projectCreated from '../contract/project_created.json'
import projectsList from '../contract/projects_list.json'
import error422 from '../contract/error_422.json'

const reply = (body: unknown, status = 200) => async () => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('api client', () => {
  it('a 2xx reply is decoded', async () => {
    const client = makeClient(reply(modes))
    expect((await client.mode()).mode).toBe('replay')
    expect((await makeClient(reply(projectsList)).listProjects())[0].name).toBe('Meeting Room Booking')
  })
  it('a refusal shows the server\'s own sentence', async () => {
    const error = await makeClient(reply(error422, 422)).previewPlan({ requirements: ['personas'] }).catch((e) => e)
    expect(error).toBeInstanceOf(ServerRefused)
    expect(error.status).toBe(422)
    expect(error.message).toMatch(/required and cannot be switched off/)
  })
  it('a network failure says the backend is unreachable and how to start it', async () => {
    const error = await makeClient(async () => { throw new TypeError('Failed to fetch') }).listProjects().catch((e) => e)
    expect(error).toBeInstanceOf(BackendUnreachable)
    expect(error.message).toMatch(/Start it with \.\/start\.sh/)
  })
  it('a reply that is not JSON is reported, not crashed on', async () => {
    const html = async () => new Response('<html>oops</html>', { status: 200 })
    expect(await makeClient(html).mode().catch((e) => e)).toBeInstanceOf(ContractError)
    const broken = async () => new Response('<html>oops</html>', { status: 502 })
    const error = await makeClient(broken).mode().catch((e) => e)
    expect(error).toBeInstanceOf(ServerRefused)
    expect(error.message).toMatch(/502/)
  })
  it('a reply of the wrong shape is a contract problem that names the field', async () => {
    const error = await makeClient(reply({ mode: 'sideways', meaning: 'x' })).mode().catch((e) => e)
    expect(error).toBeInstanceOf(ContractError)
    expect(error.message).toMatch(/mode\.mode/)
    expect(error.message).toMatch(/bug, not something you did/)
  })
  it('creating a project sends the name in X-Actor and the payload as JSON, and decodes the project', async () => {
    let seen: { url: string; init?: RequestInit } | null = null
    const client = makeClient(async (url, init) => { seen = { url: String(url), init }; return new Response(JSON.stringify(projectCreated), { status: 201 }) })
    const made = await client.createProject({ name: 'P', brief: '', selection: {}, connectors: [] }, 'Parag')
    expect(made.name).toBe('Meeting Room Booking')
    expect(seen!.url).toBe('/api/projects')
    expect(seen!.init!.method).toBe('POST')
    expect((seen!.init!.headers as Record<string, string>)['X-Actor']).toBe('Parag')
    expect(JSON.parse(String(seen!.init!.body))).toEqual({ name: 'P', brief: '', selection: {}, connectors: [] })
  })
  it('reading sends no actor, and an id is escaped in the path', async () => {
    let seenUrl = ''
    let seenInit: RequestInit | undefined
    const client = makeClient(async (url, init) => { seenUrl = String(url); seenInit = init; return new Response(JSON.stringify(projectCreated)) })
    await client.getProject('a/b c')
    expect(seenUrl).toBe('/api/projects/a%2Fb%20c')
    expect(seenInit).toBeUndefined()
  })
})
