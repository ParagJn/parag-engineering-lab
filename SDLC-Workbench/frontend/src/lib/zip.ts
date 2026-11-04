// A zip file made in the browser from text that is already on the page. No library: the "stored" method (no compression) is enough for a few Markdown files and is
// the simplest zip there is, so it is easy to check. File names are written as UTF-8. Nothing is sent anywhere.

const TABLE = (() => {
  const t = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c >>> 0
  }
  return t
})()

export function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff
  for (let i = 0; i < bytes.length; i++) c = TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

export interface ZipEntry { name: string; text: string }

/** Names must be unique inside a zip, or one file hides another. A repeat gets `-2`, `-3`, before its extension. */
export function uniqueNames(names: readonly string[]): string[] {
  const seen = new Map<string, number>()
  return names.map((name) => {
    const n = (seen.get(name) ?? 0) + 1
    seen.set(name, n)
    if (n === 1) return name
    const dot = name.lastIndexOf('.')
    return dot > 0 ? `${name.slice(0, dot)}-${n}${name.slice(dot)}` : `${name}-${n}`
  })
}

function dosTime(when: Date): { time: number; date: number } {
  const year = Math.max(1980, when.getFullYear())
  return { time: (when.getHours() << 11) | (when.getMinutes() << 5) | (when.getSeconds() >> 1), date: ((year - 1980) << 9) | ((when.getMonth() + 1) << 5) | when.getDate() }
}

/** The bytes of a zip holding the entries, in the order given. `when` is the time stamped on every file. */
export function makeZip(entries: readonly ZipEntry[], when: Date = new Date()): Uint8Array {
  const enc = new TextEncoder()
  const names = uniqueNames(entries.map((e) => e.name))
  const { time, date } = dosTime(when)
  const parts: Uint8Array[] = []
  const central: Uint8Array[] = []
  let offset = 0
  entries.forEach((entry, i) => {
    const name = enc.encode(names[i])
    const data = enc.encode(entry.text)
    const crc = crc32(data)
    const local = new DataView(new ArrayBuffer(30))
    local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true); local.setUint16(8, 0, true)
    local.setUint16(10, time, true); local.setUint16(12, date, true); local.setUint32(14, crc, true); local.setUint32(18, data.length, true); local.setUint32(22, data.length, true)
    local.setUint16(26, name.length, true); local.setUint16(28, 0, true)
    parts.push(new Uint8Array(local.buffer), name, data)
    const head = new DataView(new ArrayBuffer(46))
    head.setUint32(0, 0x02014b50, true); head.setUint16(4, 20, true); head.setUint16(6, 20, true); head.setUint16(8, 0x0800, true); head.setUint16(10, 0, true)
    head.setUint16(12, time, true); head.setUint16(14, date, true); head.setUint32(16, crc, true); head.setUint32(20, data.length, true); head.setUint32(24, data.length, true)
    head.setUint16(28, name.length, true); head.setUint16(30, 0, true); head.setUint16(32, 0, true); head.setUint16(34, 0, true); head.setUint16(36, 0, true)
    head.setUint32(38, 0, true); head.setUint32(42, offset, true)
    central.push(new Uint8Array(head.buffer), name)
    offset += 30 + name.length + data.length
  })
  const centralSize = central.reduce((n, p) => n + p.length, 0)
  const end = new DataView(new ArrayBuffer(22))
  end.setUint32(0, 0x06054b50, true); end.setUint16(4, 0, true); end.setUint16(6, 0, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true)
  end.setUint32(12, centralSize, true); end.setUint32(16, offset, true); end.setUint16(20, 0, true)
  const all = [...parts, ...central, new Uint8Array(end.buffer)]
  const out = new Uint8Array(all.reduce((n, p) => n + p.length, 0))
  let at = 0
  for (const p of all) { out.set(p, at); at += p.length }
  return out
}
