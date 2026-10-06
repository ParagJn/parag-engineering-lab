/** Normalise a relative path: collapse `.`/`..`, unify separators, drop a leading `./` or `/`. */
export function normalizePath(path: string): string {
  const out: string[] = [];
  for (const part of path.replace(/\\/g, "/").split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") out.pop();
    else out.push(part);
  }
  return out.join("/");
}

export function dirname(path: string): string {
  const norm = normalizePath(path);
  const i = norm.lastIndexOf("/");
  return i === -1 ? "" : norm.slice(0, i);
}

export function basename(path: string): string {
  const norm = normalizePath(path);
  return norm.slice(norm.lastIndexOf("/") + 1);
}

export function stem(path: string): string {
  const base = basename(path);
  const dot = base.lastIndexOf(".");
  return dot > 0 ? base.slice(0, dot) : base;
}

/** Resolve an image `src` written in `fromFile` to a key in the uploaded-files map. */
export function resolveLocal(src: string, fromFile: string): string {
  const clean = src.split(/[?#]/)[0];
  let decoded = clean;
  try {
    decoded = decodeURI(clean);
  } catch {
    // keep as-is
  }
  return decoded.startsWith("/") ? normalizePath(decoded) : normalizePath(`${dirname(fromFile)}/${decoded}`);
}

/**
 * Find an uploaded file for an image reference: exact relative path first, then
 * by file name when it is unambiguous (handles single files dropped without their folder).
 */
export function findAsset<T>(files: Map<string, T>, src: string, fromFile: string): T | undefined {
  const exact = files.get(resolveLocal(src, fromFile));
  if (exact) return exact;
  const name = basename(resolveLocal(src, fromFile)).toLowerCase();
  const matches = [...files.entries()].filter(([path]) => basename(path).toLowerCase() === name);
  return matches.length === 1 ? matches[0][1] : undefined;
}
