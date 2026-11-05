import { describe, expect, it } from 'vitest'
import { decodeMe, decodeUsersList } from '../api/users'
import list from '../contract/users_list.json'
import architect from '../contract/users_me_architect.json'
import stranger from '../contract/users_me_stranger.json'
import { approveBlock, approversChanged, isLastAdministrator, rolesToAdd, showConfiguration, sortedUsers, toggleRole, whoLine } from './users'

const L = decodeUsersList(list), ann = decodeMe(architect), nobody = decodeMe(stranger)
const ROLES = L.roles

describe('the Approve button', () => {
  it('has no block when this person may approve the phase, and the server\'s own sentence when not', () => {
    expect(approveBlock(ann, 'requirements')).toBeNull(); expect(approveBlock(ann, 'design')).toBeNull()
    expect(approveBlock(ann, 'deploy')).toBe(ann.why_not.deploy); expect(approveBlock(ann, 'deploy')).toContain('Deployment Engineer')
  })
  it('has no block while nobody is on the list, or before the answer has loaded', () => {
    expect(approveBlock(null, 'setup')).toBeNull()
    expect(approveBlock({ ...ann, list_in_force: false, may_approve: [], why_not: {} }, 'setup')).toBeNull()
  })
  it('blocks a stranger on every phase and tells them to ask an Administrator', () => {
    for (const p of Object.keys(L.approvers)) expect(approveBlock(nobody, p), p).toContain('ask an Administrator')
  })
  it('has a plain fallback when the server gave no reason for a phase', () => {
    expect(approveBlock({ ...ann, may_approve: [], why_not: {} }, 'setup')).toBe('You are not allowed to approve this phase.')
  })
})

describe('who you are', () => {
  it('says what the app thinks of the typed name, in words', () => {
    expect(whoLine(ann)).toBe('Ann · Architect, Technical Lead')
    expect(whoLine(nobody)).toBe('Stranger is not on the Users list: you can work, but not approve.')
    expect(whoLine({ ...ann, list_in_force: false })).toBe('Nobody is on the Users list yet, so nothing is restricted.')
    expect(whoLine({ ...ann, roles: [] })).toBe('Ann · no role'); expect(whoLine(null)).toBe('')
  })
})

describe('roles', () => {
  it('toggles a role on and off keeping the fixed order and each role once', () => {
    expect(toggleRole(ROLES, ['Technical Lead'], 'Architect')).toEqual(['Architect', 'Technical Lead'])
    expect(toggleRole(ROLES, ['Architect', 'Technical Lead'], 'Architect')).toEqual(['Technical Lead'])
    expect(toggleRole(ROLES, ['Architect'], 'Wizard')).toEqual(['Architect'])
  })
  it('lists the roles not yet held', () => { expect(rolesToAdd(ROLES, ['Architect'])).not.toContain('Architect'); expect(rolesToAdd(ROLES, [])).toEqual(ROLES) })
})

describe('the list', () => {
  it('puts the active first, by name, and the switched-off after', () => {
    expect(sortedUsers(L.users).map((u) => u.name)).toEqual(['Ann', 'Root', 'Bo'])
  })
  it('knows when a phase\'s approvers were changed from the default', () => {
    expect(approversChanged(L, 'requirements')).toBe(true); expect(approversChanged(L, 'design')).toBe(false)
  })
  it('knows the last Administrator, and nobody else', () => {
    expect(isLastAdministrator(L.users, 'Root')).toBe(true); expect(isLastAdministrator(L.users, 'Ann')).toBe(false); expect(isLastAdministrator(L.users, 'Nobody')).toBe(false)
    expect(isLastAdministrator([...L.users, { ...L.users[0], name: 'Zed', roles: ['Administrator'] }], 'Root')).toBe(false)
  })
})

describe('the Configuration link', () => {
  it('shows on Setup and on no other phase', () => {
    expect(showConfiguration('setup')).toBe(true)
    for (const p of ['requirements', 'design', 'architecture', 'build', 'deploy', 'handover', '', 'Setup']) expect(showConfiguration(p), p).toBe(false)
  })
})
