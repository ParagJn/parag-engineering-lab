import { FONT, TYPE } from './theme'
import { snap4, textWidth, wrapText } from './measure'

// ---------- sequence ----------

export function layoutSequence(spec) {
  const people = spec.participants
  const index = new Map(people.map((p, i) => [p.id, i]))
  const boxes = people.map((p) => {
    const labelW = textWidth(p.label, TYPE.node, FONT.sans, 500)
    const subW = p.sublabel ? textWidth(p.sublabel, TYPE.sub, FONT.mono) : 0
    return { w: snap4(Math.max(112, labelW + 32, subW + 32)), h: p.sublabel ? 52 : 40 }
  })
  const boxH = Math.max(...boxes.map((b) => b.h))

  // Space between lifelines grows until every message label fits.
  const gaps = Array.from({ length: people.length - 1 }, (_, i) => (boxes[i].w + boxes[i + 1].w) / 2 + 24)
  let tailFromCenter = 0
  for (const message of spec.messages) {
    const a = index.get(message.from)
    const b = index.get(message.to)
    const labelW = textWidth(message.label, TYPE.edge, FONT.mono)
    if (a === b) {
      const need = 52 + labelW
      if (a < gaps.length) gaps[a] = Math.max(gaps[a], need + boxes[a + 1].w / 2)
      else tailFromCenter = Math.max(tailFromCenter, need)
      continue
    }
    const lo = Math.min(a, b)
    const hi = Math.max(a, b)
    const share = (labelW + 40) / (hi - lo)
    for (let g = lo; g < hi; g += 1) gaps[g] = Math.max(gaps[g], share)
  }

  const centers = [boxes[0].w / 2]
  gaps.forEach((gap, i) => centers.push(centers[i] + Math.min(gap, 340)))
  const last = people.length - 1
  const width = Math.ceil(centers[last] + Math.max(boxes[last].w / 2, tailFromCenter))

  let cursor = boxH + 36
  const messages = spec.messages.map((message) => {
    const a = index.get(message.from)
    const b = index.get(message.to)
    const row = { ...message, y: cursor, x1: centers[a], x2: centers[b], self: a === b }
    cursor += a === b ? 60 : 44
    return row
  })

  return {
    kind: 'sequence',
    participants: people.map((p, i) => ({ ...p, cx: centers[i], w: boxes[i].w, h: boxes[i].h })),
    boxH,
    messages,
    lifelineEnd: cursor,
    width,
    height: Math.ceil(cursor + 8),
  }
}

// ---------- timeline ----------

const COL = 188
const LABEL_LINE = 17
const DETAIL_LINE = 15

export function layoutTimeline(spec) {
  const inner = COL - 28
  const axisY = 44
  const events = spec.events.map((event, i) => {
    const labelLines = wrapText(event.label, inner, TYPE.node, FONT.sans, 500, 3)
    const detailLines = event.detail ? wrapText(event.detail, inner, 11.5, FONT.sans, 400, 4) : []
    return { ...event, cx: COL * i + COL / 2, labelLines, detailLines }
  })
  const tallest = Math.max(...events.map((e) => e.labelLines.length * LABEL_LINE + (e.detailLines.length ? 8 + e.detailLines.length * DETAIL_LINE : 0)))
  return {
    kind: 'timeline',
    axisY,
    events,
    width: COL * events.length,
    height: Math.ceil(axisY + 32 + tallest + 8),
    labelLine: LABEL_LINE,
    detailLine: DETAIL_LINE,
  }
}

// ---------- quadrant ----------

const PLOT_W = 560
const PLOT_H = 440

export function layoutQuadrant(spec) {
  const yLabelW = Math.max(textWidth(spec.y_axis.low, TYPE.sub, FONT.mono), textWidth(spec.y_axis.high, TYPE.sub, FONT.mono))
  const left = Math.ceil(30 + yLabelW + 12)
  const top = 8
  const bottom = 56

  const placed = []
  const items = [...spec.items]
    .map((item) => ({ ...item, cx: left + item.x * PLOT_W, cy: top + (1 - item.y) * PLOT_H }))
    .sort((a, b) => a.cy - b.cy)
    .map((item) => {
      const labelW = textWidth(item.label, 12, FONT.sans, item.focal ? 600 : 500)
      const side = item.x > 0.68 ? 'left' : 'right'
      const x0 = side === 'right' ? item.cx + 12 : item.cx - 12 - labelW
      let ly = item.cy
      const clash = () => placed.some((p) => Math.abs(p.y - ly) < 15 && x0 < p.x1 && x0 + labelW > p.x0)
      for (let guard = 0; clash() && guard < 20; guard += 1) ly += 15
      placed.push({ x0, x1: x0 + labelW, y: ly })
      return { ...item, side, labelY: ly }
    })

  return {
    kind: 'quadrant',
    left,
    top,
    plotW: PLOT_W,
    plotH: PLOT_H,
    items,
    xAxis: spec.x_axis,
    yAxis: spec.y_axis,
    quadrants: spec.quadrants,
    width: left + PLOT_W + 16,
    height: top + PLOT_H + bottom,
  }
}
