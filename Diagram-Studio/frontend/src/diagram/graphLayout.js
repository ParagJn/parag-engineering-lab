import ELK from 'elkjs/lib/elk.bundled.js'
import { FONT, LINE, TYPE } from './theme'
import { snap4, textWidth, wrapText } from './measure'

const elk = new ELK()

const GROUP_PADDING = '[top=40,left=20,bottom=20,right=20]'

const widest = (lines, size, family, weight) => Math.max(0, ...lines.map((line) => textWidth(line, size, family, weight)))

/**
 * Wrap the text first, then size the shape to the wrapped text, so nothing can overflow its box.
 * A diamond is only as wide as its text allows at the corners, so it gets its own sizing and no sublabel.
 */
function nodeSize(node) {
  if (node.kind === 'decision') {
    const labelLines = wrapText(node.label, 120, TYPE.node, FONT.sans, 500, 3)
    const tw = widest(labelLines, TYPE.node, FONT.sans, 500)
    const textH = labelLines.length * LINE.label
    // Keep the text block inside the diamond: tw / w + textH / h <= ~0.9
    const h = snap4(Math.max(48, labelLines.length === 1 ? 48 : textH * 2.5))
    const ratio = textH / h
    const w = snap4(Math.max(120, tw / Math.max(0.9 - ratio, 0.3)))
    return { w, h, labelLines, subLines: [] }
  }
  const terminal = node.kind === 'start' || node.kind === 'end'
  const labelLines = wrapText(node.label, terminal ? 140 : 200, TYPE.node, FONT.sans, 500, 3)
  const subLines = node.sublabel ? wrapText(node.sublabel, 190, TYPE.sub, FONT.mono, 400, 2) : []
  const textW = Math.max(widest(labelLines, TYPE.node, FONT.sans, 500), widest(subLines, TYPE.sub, FONT.mono, 400))
  const textH = labelLines.length * LINE.label + (subLines.length ? 6 + subLines.length * LINE.sub : 0)
  return {
    w: snap4(Math.max(terminal ? 88 : 112, textW + 36)),
    h: snap4(Math.max(40, textH + 20)),
    labelLines,
    subLines,
  }
}

/** Arrow ends land on the bounding box; slide them along the last segment onto the diamond's edge. */
function clipToDiamond(p, neighbor, r) {
  const cx = r.x + r.w / 2
  const cy = r.y + r.h / 2
  if (Math.abs(p.x - neighbor.x) < 0.5) {
    const dx = Math.abs(p.x - cx)
    if (dx >= r.w / 2) return p
    const off = (r.h / 2) * (1 - dx / (r.w / 2))
    return { x: p.x, y: p.y < cy ? cy - off : cy + off }
  }
  if (Math.abs(p.y - neighbor.y) < 0.5) {
    const dy = Math.abs(p.y - cy)
    if (dy >= r.h / 2) return p
    const off = (r.w / 2) * (1 - dy / (r.h / 2))
    return { x: p.x < cx ? cx - off : cx + off, y: p.y }
  }
  return p
}

function groupDepth(group, byId) {
  let depth = 0
  let cursor = group.parent
  while (cursor && depth < 10) {
    depth += 1
    cursor = byId.get(cursor)?.parent
  }
  return depth
}

/** Distance from a point to a rectangle's outline (0 when it lies on the border). */
function outlineDistance(p, r) {
  const dx = Math.max(r.x - p.x, 0, p.x - (r.x + r.w))
  const dy = Math.max(r.y - p.y, 0, p.y - (r.y + r.h))
  if (dx > 0 || dy > 0) return Math.hypot(dx, dy)
  return Math.min(p.x - r.x, r.x + r.w - p.x, p.y - r.y, r.y + r.h - p.y)
}

export async function layoutGraph(spec) {
  const direction = spec.direction === 'LR' ? 'RIGHT' : 'DOWN'

  // Groups with nothing inside would collapse to a dot; drop them.
  const byGroupId = new Map(spec.groups.map((g) => [g.id, g]))
  const used = new Set()
  for (const node of spec.nodes) {
    let cursor = node.group
    while (cursor && !used.has(cursor)) {
      used.add(cursor)
      cursor = byGroupId.get(cursor)?.parent
    }
  }
  const groups = spec.groups.filter((g) => used.has(g.id))
  const groupIds = new Set(groups.map((g) => g.id))

  const elkGroups = new Map(
    groups.map((g) => [g.id, { id: `g:${g.id}`, children: [], layoutOptions: { 'elk.padding': GROUP_PADDING } }]),
  )
  const sizes = new Map()
  const root = { id: 'root', children: [], edges: [] }
  for (const group of groups) {
    const parent = group.parent && groupIds.has(group.parent) ? elkGroups.get(group.parent) : root
    parent.children.push(elkGroups.get(group.id))
  }
  for (const node of spec.nodes) {
    const size = nodeSize(node)
    sizes.set(node.id, size)
    const parent = node.group && groupIds.has(node.group) ? elkGroups.get(node.group) : root
    parent.children.push({ id: `n:${node.id}`, width: size.w, height: size.h })
  }
  spec.edges.forEach((edge, index) => {
    const item = { id: `e${index}`, sources: [`n:${edge.from}`], targets: [`n:${edge.to}`] }
    if (edge.label) {
      item.labels = [{ id: `e${index}:l`, text: edge.label, width: Math.ceil(textWidth(edge.label, TYPE.edge, FONT.mono)) + 12, height: 16 }]
    }
    root.edges.push(item)
  })

  root.layoutOptions = {
    'elk.algorithm': 'layered',
    'elk.direction': direction,
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.padding': '[top=0,left=0,bottom=0,right=0]',
    'elk.spacing.nodeNode': '36',
    'elk.spacing.edgeNode': '24',
    'elk.layered.spacing.nodeNodeBetweenLayers': '56',
    'elk.layered.spacing.edgeNodeBetweenLayers': '20',
    'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
  }

  const result = await elk.layout(root)

  // Absolute rectangles for every node and group (shape coordinates are relative to the parent).
  const rects = new Map()
  const walk = (children, ox, oy) => {
    for (const child of children || []) {
      const rect = { x: ox + (child.x || 0), y: oy + (child.y || 0), w: child.width || 0, h: child.height || 0 }
      rects.set(child.id, rect)
      walk(child.children, rect.x, rect.y)
    }
  }
  walk(result.children, 0, 0)

  const parentOf = new Map()
  for (const node of spec.nodes) parentOf.set(`n:${node.id}`, node.group && groupIds.has(node.group) ? `g:${node.group}` : 'root')
  for (const group of groups) parentOf.set(`g:${group.id}`, group.parent && groupIds.has(group.parent) ? `g:${group.parent}` : 'root')
  const ancestors = (id) => {
    const chain = []
    let cursor = parentOf.get(id)
    while (cursor) {
      chain.push(cursor)
      cursor = parentOf.get(cursor)
    }
    return chain
  }
  const commonAncestor = (a, b) => {
    const chainB = new Set(ancestors(b))
    return ancestors(a).find((id) => chainB.has(id)) || 'root'
  }

  const kinds = new Map(spec.nodes.map((n) => [n.id, n.kind]))
  const edges = []
  result.edges?.forEach((laid, index) => {
    const spec_ = spec.edges[index]
    const section = laid.sections?.[0]
    if (!section) return
    const raw = [section.startPoint, ...(section.bendPoints || []), section.endPoint]

    // Which origin the edge coordinates are relative to depends on how ELK exported the hierarchy.
    // Try the root first, then the common ancestor of the two ends, and keep whichever lands on the source node.
    const sourceRect = rects.get(`n:${spec_.from}`)
    const ancestorRect = rects.get(commonAncestor(`n:${spec_.from}`, `n:${spec_.to}`)) || { x: 0, y: 0 }
    const candidates = [
      { x: 0, y: 0 },
      { x: ancestorRect.x, y: ancestorRect.y },
    ]
    let origin = candidates[0]
    if (sourceRect) {
      origin = candidates.reduce((best, c) =>
        outlineDistance({ x: raw[0].x + c.x, y: raw[0].y + c.y }, sourceRect) < outlineDistance({ x: raw[0].x + best.x, y: raw[0].y + best.y }, sourceRect) ? c : best,
      )
    }
    const points = raw.map((p) => ({ x: p.x + origin.x, y: p.y + origin.y }))
    const last = points.length - 1
    if (kinds.get(spec_.from) === 'decision' && sourceRect) points[0] = clipToDiamond(points[0], points[1], sourceRect)
    const targetRect = rects.get(`n:${spec_.to}`)
    if (kinds.get(spec_.to) === 'decision' && targetRect) points[last] = clipToDiamond(points[last], points[last - 1], targetRect)

    const laidLabel = laid.labels?.[0]
    let label = null
    if (spec_.label) {
      label = laidLabel && laidLabel.x != null
        ? { text: spec_.label, x: laidLabel.x + origin.x, y: laidLabel.y + origin.y, w: laidLabel.width, h: laidLabel.height }
        : (() => {
            const mid = points[Math.floor(points.length / 2)]
            const w = Math.ceil(textWidth(spec_.label, TYPE.edge, FONT.mono)) + 12
            return { text: spec_.label, x: mid.x - w / 2, y: mid.y - 8, w, h: 16 }
          })()
    }
    edges.push({ ...spec_, points, label })
  })

  const nodes = spec.nodes.map((node) => {
    const size = sizes.get(node.id)
    const rect = rects.get(`n:${node.id}`) || { x: 0, y: 0, w: size.w, h: size.h }
    return { ...node, x: rect.x, y: rect.y, w: rect.w, h: rect.h, labelLines: size.labelLines, subLines: size.subLines }
  })

  const byId = new Map(groups.map((g) => [g.id, g]))
  const laidGroups = groups
    .map((group) => {
      const rect = rects.get(`g:${group.id}`) || { x: 0, y: 0, w: 0, h: 0 }
      return { ...group, x: rect.x, y: rect.y, w: rect.w, h: rect.h, depth: groupDepth(group, byId) }
    })
    .sort((a, b) => a.depth - b.depth)

  // Edge labels can poke out past the node bounding box.
  let maxX = result.width || 0
  let maxY = result.height || 0
  for (const edge of edges) {
    if (edge.label) {
      maxX = Math.max(maxX, edge.label.x + edge.label.w)
      maxY = Math.max(maxY, edge.label.y + edge.label.h)
    }
  }

  return { kind: 'graph', nodes, groups: laidGroups, edges, width: Math.ceil(maxX), height: Math.ceil(maxY) }
}
