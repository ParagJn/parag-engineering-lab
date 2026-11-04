"""Deliberate breaks for the run panel's downloads (one file, or all as a zip), frontend only.

Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s20e_download_all.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
MUTANTS: list = []

Z = "src/lib/zip.ts"
I = "src/lib/instructionSet.ts"
S = "src/state/useProjectScreen.ts"
R = "src/components/RunPanel.tsx"
D = "src/lib/download.ts"

FRONTEND = [
    # ---- the zip itself
    ("the checksum table is wrong", Z, "c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1", "c = c & 1 ? 0xedb88321 ^ (c >>> 1) : c >>> 1"),
    ("the checksum starts wrong", Z, "  let c = 0xffffffff\n  for (let i", "  let c = 0\n  for (let i"),
    ("the checksum is not finished", Z, "  return (c ^ 0xffffffff) >>> 0", "  return c >>> 0"),
    ("the local header mark is wrong", Z, "local.setUint32(0, 0x04034b50, true)", "local.setUint32(0, 0x04034b51, true)"),
    ("the central header mark is wrong", Z, "head.setUint32(0, 0x02014b50, true)", "head.setUint32(0, 0x02014b51, true)"),
    ("the end mark is wrong", Z, "end.setUint32(0, 0x06054b50, true)", "end.setUint32(0, 0x06054b51, true)"),
    ("names are not marked utf-8", Z, "local.setUint16(6, 0x0800, true)", "local.setUint16(6, 0, true)"),
    ("the central names are not marked utf-8", Z, "head.setUint16(8, 0x0800, true)", "head.setUint16(8, 0, true)"),
    ("the files are compressed in the header", Z, "local.setUint16(8, 0, true)", "local.setUint16(8, 8, true)"),
    ("the local checksum is lost", Z, "local.setUint32(14, crc, true)", "local.setUint32(14, 0, true)"),
    ("the central checksum is lost", Z, "head.setUint32(16, crc, true)", "head.setUint32(16, 0, true)"),
    ("the local size is wrong", Z, "local.setUint32(18, data.length, true); local.setUint32(22, data.length, true)", "local.setUint32(18, data.length, true); local.setUint32(22, 0, true)"),
    ("the central size is wrong", Z, "head.setUint32(20, data.length, true); head.setUint32(24, data.length, true)", "head.setUint32(20, data.length, true); head.setUint32(24, 0, true)"),
    ("the name length is wrong", Z, "local.setUint16(26, name.length, true)", "local.setUint16(26, name.length + 1, true)"),
    ("the central name length is wrong", Z, "head.setUint16(28, name.length, true)", "head.setUint16(28, name.length + 1, true)"),
    ("the central offset is wrong", Z, "head.setUint32(38, 0, true); head.setUint32(42, offset, true)", "head.setUint32(38, 0, true); head.setUint32(42, 0, true)"),
    ("the offset ignores the names", Z, "    offset += 30 + name.length + data.length", "    offset += 30 + data.length"),
    ("the offset ignores the data", Z, "    offset += 30 + name.length + data.length", "    offset += 30 + name.length"),
    ("the file count is wrong", Z, "end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true)", "end.setUint16(8, entries.length, true); end.setUint16(10, 0, true)"),
    ("the central size is not recorded", Z, "end.setUint32(12, centralSize, true)", "end.setUint32(12, 0, true)"),
    ("the central start is not recorded", Z, "end.setUint32(16, offset, true)", "end.setUint32(16, 0, true)"),
    ("the files come out in another order", Z, "  const all = [...parts, ...central, new Uint8Array(end.buffer)]", "  const all = [...central, ...parts, new Uint8Array(end.buffer)]"),
    ("the time is not stamped", Z, "local.setUint16(10, time, true); local.setUint16(12, date, true)", "local.setUint16(10, 0, true); local.setUint16(12, 0, true)"),
    ("the date is wrong", Z, "date: ((year - 1980) << 9) | ((when.getMonth() + 1) << 5) | when.getDate()", "date: ((year - 1980) << 9) | (when.getMonth() << 5) | when.getDate()"),
    ("a year before 1980 is kept", Z, "  const year = Math.max(1980, when.getFullYear())", "  const year = when.getFullYear()"),
    ("a repeated name hides the first", Z, "    if (n === 1) return name", "    return name"),
    ("a repeat is numbered after its extension", Z, "return dot > 0 ? `${name.slice(0, dot)}-${n}${name.slice(dot)}` : `${name}-${n}`", "return `${name}-${n}`"),
    ("a name without an extension is lost", Z, ": `${name}-${n}`\n  })", ": name\n  })"),
    # ---- what a download saves
    ("a file download saves the whole set", I, "return one ? { kind: 'file', ...downloadOf(one) } : null", "return one ? { kind: 'file', name: one.name, text: body } : null"),
    ("a missing file is saved anyway", I, "return one ? { kind: 'file', ...downloadOf(one) } : null", "return { kind: 'file', ...downloadOf(one ?? { name: file, text: '' }) }"),
    ("all files with none is saved", I, "  if (files.length === 0) return null\n", ""),
    ("the zip is not named for the version", I, "-v${version}.zip", ".zip"),
    ("the zip name keeps odd characters", I, "artefactId.replace(/[^A-Za-z0-9._-]+/g, '_')", "artefactId"),
    ("the zip keeps unsafe file names", I, "entries: files.map((f) => downloadOf(f)) }", "entries: files.map((f) => ({ name: f.name, text: f.text })) }"),
    ("the zip leaves a file out", I, "entries: files.map((f) => downloadOf(f)) }", "entries: files.slice(1).map((f) => downloadOf(f)) }"),
    # ---- fetching and saving
    ("the wrong version is fetched", S, "await client.getArtefact(projectId, artefactId, version ?? undefined)", "await client.getArtefact(projectId, artefactId)"),
    ("a failure to fetch is not said", S, "catch (e) { return message(e, 'The files could not be fetched, so nothing was saved.') }", "catch { return null }"),
    ("a missing file is not said", S, "  if (plan === null) return file === null ?", "  if (plan === null) return null ?"),
    ("a file is saved as a zip", S, "  if (plan.kind === 'file') save.text(plan.name, plan.text)\n  else save.zip(plan.name, makeZip(plan.entries))", "  save.zip(plan.name, makeZip(plan.entries))"),
    ("all files are saved as text", S, "  if (plan.kind === 'file') save.text(plan.name, plan.text)\n  else save.zip(plan.name, makeZip(plan.entries))", "  if (plan.kind === 'file') save.text(plan.name, plan.text)\n  else save.text(plan.name, plan.entries.map((e) => e.text).join('\\n'))"),
    ("the empty set message is lost", S, "'This version holds no files, so there is nothing to save.'", "''"),
    ("a note from an earlier try stays", S, "  setNote(null)\n  setNote(await run())", "  setNote(await run())"),
    ("a note is not set when a download fails", S, "  setNote(null)\n  setNote(await run())", "  setNote(null)\n  await run()"),
    ("the icon alone has no name", R, "aria-label={`Download ${x.file}`} title={`Download ${x.file}`}", "title={`Download ${x.file}`}"),
    ("the icon alone has no hover text", R, "aria-label={`Download ${x.file}`} title={`Download ${x.file}`}", "aria-label={`Download ${x.file}`}"),
    ("the word comes back", R, "                <Download size={13} aria-hidden />\n              </button>", "                <Download size={13} aria-hidden /> Download\n              </button>"),
    ("a zip is saved as text", D, "  saveBlob(filename, new Blob([bytes as BlobPart], { type }))", "  saveBlob(filename, new Blob([String(bytes)], { type: 'text/plain' }))"),
    # ---- the buttons
    ("there is no download all", R, "                  {onDownload && r.pieces.length > 0 && (", "                  {false && ("),
    ("a plain artefact gets a download all", R, "                  {onDownload && r.pieces.length > 0 && (", "                  {onDownload && ("),
    ("download all asks for one file", R, "onClick={() => onDownload(r.artefactId!, r.version, null)}", "onClick={() => onDownload(r.artefactId!, r.version, r.pieces[0].file)}"),
    ("download all asks for the wrong version", R, "onClick={() => onDownload(r.artefactId!, r.version, null)}", "onClick={() => onDownload(r.artefactId!, null, null)}"),
    ("download all is after Read it", R, "                  {onDownload && r.pieces.length > 0 && (\n                    <button", "                  {false && (\n                    <button"),
    ("Read it loses its place", R, "className={`${onDownload && r.pieces.length > 0 ? '' : 'ml-auto '}text-xs underline`}", "className=\"text-xs underline\""),
    ("every file has a download", R, "            {x.state === 'done' && onSave && (", "            {onSave && ("),
    ("no file has a download", R, "            {x.state === 'done' && onSave && (", "            {false && ("),
    ("a file download asks for another file", R, "<button type=\"button\" onClick={() => onSave(x.file)}", "<button type=\"button\" onClick={() => onSave(pieces[0].file)}"),
    ("a file button is not named", R, "aria-label={`Download ${x.file}`}", "aria-label=\"Download\""),
    ("the files are not given a save handler", R, "onSave={onDownload && r.artefactId ? (file) => onDownload(r.artefactId!, r.version, file) : undefined}", "onSave={undefined}"),
    ("the files save the wrong version", R, "(file) => onDownload(r.artefactId!, r.version, file)", "(file) => onDownload(r.artefactId!, null, file)"),
    ("the reason is not shown", R, "      {downloadNote && <Notice tone=\"warn\" title=\"Nothing was saved\">{downloadNote}</Notice>}", ""),
]
