// Small, strict decoders. A server response is untrusted input until proven otherwise: if a field is missing or the wrong type, the
// screen says the backend and the app disagree (a contract problem), rather than rendering undefined or crashing.

export class ContractError extends Error {
  constructor(where: string, what: string) {
    super(`The backend sent something this screen does not understand (${where}: ${what}). This is a bug, not something you did.`)
    this.name = 'ContractError'
  }
}

export type Json = Record<string, unknown>

export function obj(value: unknown, where: string): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new ContractError(where, 'expected an object')
  return value as Json
}

export function arr(value: unknown, where: string): unknown[] {
  if (!Array.isArray(value)) throw new ContractError(where, 'expected a list')
  return value
}

export function str(value: unknown, where: string): string {
  if (typeof value !== 'string') throw new ContractError(where, 'expected text')
  return value
}

export function num(value: unknown, where: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new ContractError(where, 'expected a number')
  return value
}

export function bool(value: unknown, where: string): boolean {
  if (typeof value !== 'boolean') throw new ContractError(where, 'expected true or false')
  return value
}

export function nullable<T>(value: unknown, where: string, inner: (v: unknown, w: string) => T): T | null {
  return value === null ? null : inner(value, where)
}

export function strings(value: unknown, where: string): string[] {
  return arr(value, where).map((v, i) => str(v, `${where}[${i}]`))
}

export function oneOf<T extends string>(value: unknown, where: string, allowed: readonly T[]): T {
  const text = str(value, where)
  if (!(allowed as readonly string[]).includes(text)) throw new ContractError(where, `unexpected value "${text}"`)
  return text as T
}
