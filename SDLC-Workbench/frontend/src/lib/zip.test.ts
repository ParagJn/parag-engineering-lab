import { describe, expect, it } from 'vitest'
import { crc32, makeZip, uniqueNames } from './zip'

const u32 = (b: Uint8Array, at: number) => new DataView(b.buffer, b.byteOffset).getUint32(at, true)
const u16 = (b: Uint8Array, at: number) => new DataView(b.buffer, b.byteOffset).getUint16(at, true)
const WHEN = new Date(2026, 10, 5, 13, 45, 30)

/** Read a "stored" zip back with no library, the way any unzip tool would: the end record, the central directory, then each local file. */
function readZip(bytes: Uint8Array): { name: string; text: string; crc: number }[] {
  const end = bytes.length - 22
  expect(u32(bytes, end)).toBe(0x06054b50)
  const count = u16(bytes, end + 10), size = u32(bytes, end + 12), start = u32(bytes, end + 16)
  expect(start + size).toBe(end)
  const out = []
  let at = start
  for (let i = 0; i < count; i++) {
    expect(u32(bytes, at)).toBe(0x02014b50)
    const crc = u32(bytes, at + 16), csize = u32(bytes, at + 20), usize = u32(bytes, at + 24), nlen = u16(bytes, at + 28), local = u32(bytes, at + 42)
    const name = new TextDecoder().decode(bytes.slice(at + 46, at + 46 + nlen))
    expect(u32(bytes, local)).toBe(0x04034b50)
    const lname = u16(bytes, local + 26), extra = u16(bytes, local + 28)
    expect(csize).toBe(usize)
    const data = bytes.slice(local + 30 + lname + extra, local + 30 + lname + extra + csize)
    out.push({ name, text: new TextDecoder().decode(data), crc })
    at += 46 + nlen
  }
  return out
}

describe('the checksum', () => {
  it('is the standard CRC-32: the check value of "123456789" and of nothing', () => {
    expect(crc32(new TextEncoder().encode('123456789'))).toBe(0xcbf43926)
    expect(crc32(new Uint8Array())).toBe(0)
    expect(crc32(new TextEncoder().encode('a'))).toBe(0xe8b7be43)
  })
})

describe('a zip made in the browser', () => {
  const files = [{ name: '00-foundation.md', text: '# Foundation\n\nA service.\n' }, { name: 'UC-001-a.md', text: '# A\n' }, { name: 'empty.md', text: '' }]
  it('can be read back: every file with its name, its exact text and the right checksum, in the order given', () => {
    const back = readZip(makeZip(files, WHEN))
    expect(back.map((f) => [f.name, f.text])).toEqual(files.map((f) => [f.name, f.text]))
    for (const f of back) expect(f.crc).toBe(crc32(new TextEncoder().encode(f.text)))
  })
  it('holds text that is not plain ASCII, with the name and the content both as UTF-8', () => {
    const back = readZip(makeZip([{ name: 'café-ü.md', text: 'naïve — “quotes” 日本語\n' }], WHEN))
    expect(back[0]).toMatchObject({ name: 'café-ü.md', text: 'naïve — “quotes” 日本語\n' })
  })
  it('says in both headers that names are UTF-8 and that nothing is compressed', () => {
    const z = makeZip([{ name: 'a.md', text: 'x' }], WHEN)
    expect(u16(z, 6)).toBe(0x0800); expect(u16(z, 8)).toBe(0)
    const central = 30 + 4 + 1                                           // the local header, the name `a.md` and its one byte of data
    expect(u32(z, central)).toBe(0x02014b50); expect(u16(z, central + 8)).toBe(0x0800); expect(u16(z, central + 10)).toBe(0)
  })
  it('records the checksum and both sizes in the local header too, not only in the central directory', () => {
    const data = 'hello zip\n'
    const z = makeZip([{ name: 'a.md', text: data }], WHEN)
    expect(u32(z, 14)).toBe(crc32(new TextEncoder().encode(data))); expect(u32(z, 18)).toBe(data.length); expect(u32(z, 22)).toBe(data.length)
  })
  it('stamps the time it was given, in the zip\'s own date format', () => {
    const z = makeZip([{ name: 'a.md', text: 'x' }], WHEN)
    expect(u16(z, 10)).toBe((13 << 11) | (45 << 5) | 15); expect(u16(z, 12)).toBe(((2026 - 1980) << 9) | (11 << 5) | 5)
  })
  it('counts its files in the end record, and an empty list is a valid empty zip', () => {
    const z = makeZip(files, WHEN)
    expect(u16(z, z.length - 12)).toBe(3); expect(u16(z, z.length - 14)).toBe(3)
    const none = makeZip([], WHEN)
    expect(none.length).toBe(22); expect(u32(none, 0)).toBe(0x06054b50); expect(readZip(none)).toEqual([])
  })
  it('gives two files of the same name two different names rather than hiding one', () => {
    expect(readZip(makeZip([{ name: 'a.md', text: '1' }, { name: 'a.md', text: '2' }, { name: 'a.md', text: '3' }], WHEN)).map((f) => [f.name, f.text])).toEqual([['a.md', '1'], ['a-2.md', '2'], ['a-3.md', '3']])
  })
  it('makes the same bytes every time for the same input and time', () => {
    expect(Array.from(makeZip(files, WHEN))).toEqual(Array.from(makeZip(files, WHEN)))
  })
  it('is unchanged by a year before 1980, which a zip cannot hold', () => {
    const z = makeZip([{ name: 'a.md', text: 'x' }], new Date(1975, 0, 1))
    expect(u16(z, 12) >> 9).toBe(0)
  })
})

describe('unique names', () => {
  it('leaves names alone unless they repeat, and numbers a repeat before its extension', () => {
    expect(uniqueNames(['a.md', 'b.md'])).toEqual(['a.md', 'b.md'])
    expect(uniqueNames(['a.md', 'a.md', 'b.md', 'a.md'])).toEqual(['a.md', 'a-2.md', 'b.md', 'a-3.md'])
    expect(uniqueNames(['noext', 'noext'])).toEqual(['noext', 'noext-2']); expect(uniqueNames(['.hidden', '.hidden'])).toEqual(['.hidden', '.hidden-2'])
  })
})
