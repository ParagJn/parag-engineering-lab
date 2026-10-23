import { useId } from 'react'
import { LINE, TYPE, TYPE_LABELS } from './theme'
import { makeAnim } from './animation'

const PAD = 40

function roundedPath(points, radius = 6) {
  if (points.length < 2) return ''
  let d = `M${points[0].x} ${points[0].y}`
  for (let i = 1; i < points.length - 1; i += 1) {
    const p0 = points[i - 1]
    const p1 = points[i]
    const p2 = points[i + 1]
    const l1 = Math.hypot(p1.x - p0.x, p1.y - p0.y)
    const l2 = Math.hypot(p2.x - p1.x, p2.y - p1.y)
    const r = Math.min(radius, l1 / 2, l2 / 2)
    if (l1 < 0.01 || l2 < 0.01 || r < 1) {
      d += ` L${p1.x} ${p1.y}`
      continue
    }
    const a = { x: p1.x + ((p0.x - p1.x) / l1) * r, y: p1.y + ((p0.y - p1.y) / l1) * r }
    const b = { x: p1.x + ((p2.x - p1.x) / l2) * r, y: p1.y + ((p2.y - p1.y) / l2) * r }
    d += ` L${a.x} ${a.y} Q${p1.x} ${p1.y} ${b.x} ${b.y}`
  }
  const last = points[points.length - 1]
  return `${d} L${last.x} ${last.y}`
}

// A paper-coloured outline behind text keeps labels legible where lines run underneath them.
const halo = (t) => ({ stroke: t.paper, strokeWidth: 4, paintOrder: 'stroke', strokeLinejoin: 'round' })

function Arrowhead({ id, t }) {
  return (
    <marker id={id} markerWidth="9" markerHeight="9" refX="7.5" refY="4.5" orient="auto-start-reverse" markerUnits="userSpaceOnUse">
      <path d="M1.5 1.5 L7.5 4.5 L1.5 7.5" fill="none" stroke={t.line} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </marker>
  )
}

// An accent outline around a node, used by the pulse and walkthrough effects. `props` carries the animation class.
function Outline({ node, pad, props }) {
  const { x, y, w, h, kind } = node
  if (kind === 'decision') {
    const cx = x + w / 2
    const cy = y + h / 2
    return <polygon {...props} points={`${cx},${y - pad} ${x + w + pad},${cy} ${cx},${y + h + pad} ${x - pad},${cy}`} />
  }
  const r = kind === 'start' || kind === 'end' ? h / 2 + pad : 10
  return <rect {...props} x={x - pad} y={y - pad} width={w + pad * 2} height={h + pad * 2} rx={r} />
}

// ---------- graph (architecture / flowchart / state) ----------

function GraphNode({ node, t, a }) {
  const { x, y, w, h, kind } = node
  const cx = x + w / 2
  let ink = t.ink
  let sub = t.muted
  let shape

  switch (kind) {
    case 'focal':
      shape = <rect x={x} y={y} width={w} height={h} rx={t.radius} fill={t.accentSoft} stroke={t.accent} strokeWidth="1" />
      break
    case 'muted':
      shape = <rect x={x} y={y} width={w} height={h} rx={t.radius} fill="none" stroke={t.rule} strokeWidth="1" />
      ink = t.muted
      break
    case 'external':
      shape = <rect x={x} y={y} width={w} height={h} rx={t.radius} fill={t.paper} stroke={t.line} strokeWidth="1" strokeDasharray="4 3" />
      break
    case 'store': {
      const rx = w / 2
      shape = (
        <g fill={t.paper} stroke={t.line} strokeWidth="1">
          <path d={`M${x} ${y + 6} a${rx} 6 0 0 1 ${w} 0 v${h - 12} a${rx} 6 0 0 1 ${-w} 0 z`} />
          <path d={`M${x} ${y + 6} a${rx} 6 0 0 0 ${w} 0`} fill="none" />
        </g>
      )
      break
    }
    case 'start':
      shape = <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={t.ink} stroke={t.ink} strokeWidth="1" />
      ink = t.paper
      sub = t.paper
      break
    case 'end':
      shape = <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={t.paper} stroke={t.ink} strokeWidth="1.5" />
      break
    case 'decision':
      shape = (
        <polygon
          points={`${cx},${y} ${x + w},${y + h / 2} ${cx},${y + h} ${x},${y + h / 2}`}
          fill={t.paper}
          stroke={t.line}
          strokeWidth="1"
          strokeLinejoin="round"
        />
      )
      break
    default:
      shape = <rect x={x} y={y} width={w} height={h} rx={t.radius} fill={t.paper} stroke={t.line} strokeWidth="1" />
  }

  // Text block (wrapped label lines, then wrapped sublabel lines) centred vertically in the shape.
  const labelLines = node.labelLines?.length ? node.labelLines : [node.label]
  const subLines = node.subLines || []
  const textH = labelLines.length * LINE.label + (subLines.length ? 6 + subLines.length * LINE.sub : 0)
  const top = y + (h - textH) / 2 + (kind === 'store' ? 3 : 0)
  const subTop = top + labelLines.length * LINE.label + 6
  const full = [node.label, node.sublabel].filter(Boolean).join(' - ')
  const ring = a.ring(node.id, kind === 'focal')
  const spot = a.spot(node.id)
  return (
    <g {...a.node(node.id)}>
      <title>{full}</title>
      {shape}
      {labelLines.map((line, i) => (
        <text key={i} x={cx} y={top + i * LINE.label + 12} textAnchor="middle" fontFamily={t.fonts.sans} fontSize={TYPE.node} fontWeight="500" fill={ink}>
          {line}
        </text>
      ))}
      {subLines.map((line, i) => (
        <text key={`s${i}`} x={cx} y={subTop + i * LINE.sub + 10} textAnchor="middle" fontFamily={t.fonts.mono} fontSize={TYPE.sub} fill={sub} opacity={kind === 'start' ? 0.8 : 1}>
          {line}
        </text>
      ))}
      {ring && <Outline node={node} pad={3} props={ring} />}
      {spot && <Outline node={node} pad={5} props={spot} />}
    </g>
  )
}

function GraphBody({ g, t, arrowId, a }) {
  return (
    <g>
      {g.groups.map((group) => (
        <g key={group.id} {...a.group(group.id)}>
          <rect
            x={group.x}
            y={group.y}
            width={group.w}
            height={group.h}
            rx={t.radius + 2}
            fill={group.depth % 2 === 0 ? t.panel : t.paper}
            stroke={t.rule}
            strokeWidth="1"
          />
          <text x={group.x + 14} y={group.y + 24} fontFamily={t.fonts.mono} fontSize={TYPE.group} letterSpacing="0.1em" fill={t.muted}>
            {group.label.toUpperCase()}
          </text>
        </g>
      ))}
      {g.edges.map((edge, i) => {
        const d = roundedPath(edge.points)
        const solid = edge.style !== 'dashed'
        const flow = a.flowEdge(i)
        return (
          <g key={i} {...a.edge(i)}>
            <path
              d={d}
              fill="none"
              stroke={t.line}
              strokeWidth="1"
              strokeDasharray={solid ? undefined : '4 3'}
              markerEnd={`url(#${arrowId})`}
              markerStart={edge.both ? `url(#${arrowId})` : undefined}
              {...a.draw(i, solid)}
            />
            {flow && <path d={d} {...flow} />}
          </g>
        )
      })}
      {g.nodes.map((node) => (
        <GraphNode key={node.id} node={node} t={t} a={a} />
      ))}
      {g.edges.map(
        (edge, i) =>
          edge.label && (
            <text
              key={`l${i}`}
              {...a.label(i)}
              x={edge.label.x + edge.label.w / 2}
              y={edge.label.y + edge.label.h / 2 + 3.5}
              textAnchor="middle"
              fontFamily={t.fonts.mono}
              fontSize={TYPE.edge}
              fill={t.muted}
              {...halo(t)}
            >
              {edge.label.text}
            </text>
          ),
      )}
    </g>
  )
}

// ---------- sequence ----------

function SequenceBody({ g, t, arrowId, a }) {
  return (
    <g>
      {g.participants.map((p) => (
        <line key={`ll${p.id}`} x1={p.cx} y1={g.boxH} x2={p.cx} y2={g.lifelineEnd} stroke={t.rule} strokeWidth="1" strokeDasharray="3 4" />
      ))}
      {g.participants.map((p) => {
        const ring = a.ring(p.id, false)
        return (
          <g key={p.id} {...a.part(p.id)}>
            <rect x={p.cx - p.w / 2} y={0} width={p.w} height={p.h} rx={t.radius} fill={t.paper} stroke={t.line} strokeWidth="1" />
            <text x={p.cx} y={p.sublabel ? 22 : p.h / 2 + 4.5} textAnchor="middle" fontFamily={t.fonts.sans} fontSize={TYPE.node} fontWeight="500" fill={t.ink}>
              {p.label}
            </text>
            {p.sublabel && (
              <text x={p.cx} y={38} textAnchor="middle" fontFamily={t.fonts.mono} fontSize={TYPE.sub} fill={t.muted}>
                {p.sublabel}
              </text>
            )}
            {ring && <rect {...ring} x={p.cx - p.w / 2 - 3} y={-3} width={p.w + 6} height={p.h + 6} rx={t.radius + 3} />}
          </g>
        )
      })}
      {g.messages.map((m, i) => {
        const dash = m.style === 'dashed' ? '4 3' : undefined
        const flow = a.flowMsg(i)
        const spot = a.spot(`m${i}`)
        if (m.self) {
          const d = `M${m.x1} ${m.y} h36 v20 h-36`
          return (
            <g key={i} {...a.msg(i)}>
              <path d={d} fill="none" stroke={t.line} strokeWidth="1" strokeDasharray={dash} markerEnd={`url(#${arrowId})`} />
              <text x={m.x1 + 46} y={m.y + 14} fontFamily={t.fonts.mono} fontSize={TYPE.edge} fill={t.muted} {...halo(t)}>
                {m.label}
              </text>
              {flow && <path d={d} {...flow} />}
              {spot && <path d={d} {...spot} />}
            </g>
          )
        }
        return (
          <g key={i} {...a.msg(i)}>
            <line x1={m.x1} y1={m.y} x2={m.x2} y2={m.y} stroke={t.line} strokeWidth="1" strokeDasharray={dash} markerEnd={`url(#${arrowId})`} />
            <text x={(m.x1 + m.x2) / 2} y={m.y - 7} textAnchor="middle" fontFamily={t.fonts.mono} fontSize={TYPE.edge} fill={t.muted} {...halo(t)}>
              {m.label}
            </text>
            {flow && <line x1={m.x1} y1={m.y} x2={m.x2} y2={m.y} {...flow} />}
            {spot && <line x1={m.x1} y1={m.y} x2={m.x2} y2={m.y} {...spot} />}
          </g>
        )
      })}
    </g>
  )
}

// ---------- timeline ----------

function TimelineBody({ g, t, a }) {
  return (
    <g>
      <line x1={0} y1={g.axisY} x2={g.width} y2={g.axisY} stroke={t.line} strokeWidth="1" />
      {g.events.map((event, i) => {
        const top = g.axisY + 32
        const detailTop = top + event.labelLines.length * g.labelLine + 8
        const dot = event.focal ? 6 : 4
        const ring = a.ring(`e${i}`, event.focal)
        const spot = a.spot(`e${i}`)
        return (
          <g key={i} {...a.event(i)}>
            {event.date && (
              <text x={event.cx} y={g.axisY - 16} textAnchor="middle" fontFamily={t.fonts.mono} fontSize={TYPE.sub} letterSpacing="0.04em" fill={event.focal ? t.accent : t.muted}>
                {event.date}
              </text>
            )}
            <circle cx={event.cx} cy={g.axisY} r={event.focal ? 6 : 4} fill={event.focal ? t.accent : t.paper} stroke={event.focal ? t.accent : t.line} strokeWidth="1" />
            {event.labelLines.map((line, j) => (
              <text key={j} x={event.cx} y={top + j * g.labelLine} textAnchor="middle" fontFamily={t.fonts.sans} fontSize={TYPE.node} fontWeight="500" fill={t.ink}>
                {line}
              </text>
            ))}
            {event.detailLines.map((line, j) => (
              <text key={`d${j}`} x={event.cx} y={detailTop + j * g.detailLine} textAnchor="middle" fontFamily={t.fonts.sans} fontSize="11.5" fill={t.muted}>
                {line}
              </text>
            ))}
            {ring && <circle {...ring} cx={event.cx} cy={g.axisY} r={dot + 3} />}
            {spot && <circle {...spot} cx={event.cx} cy={g.axisY} r={dot + 7} />}
          </g>
        )
      })}
    </g>
  )
}

// ---------- quadrant ----------

function QuadrantBody({ g, t, a }) {
  const { left, top, plotW, plotH } = g
  const midX = left + plotW / 2
  const midY = top + plotH / 2
  const corner = { fontFamily: t.fonts.mono, fontSize: TYPE.group, letterSpacing: '0.1em', fill: t.muted }
  const q = g.quadrants
  const mono = { fontFamily: t.fonts.mono, fontSize: TYPE.sub, fill: t.muted }
  return (
    <g>
      <rect x={left} y={top} width={plotW} height={plotH} rx={t.radius} fill="none" stroke={t.rule} strokeWidth="1" />
      <line x1={midX} y1={top} x2={midX} y2={top + plotH} stroke={t.rule} strokeWidth="1" strokeDasharray="3 4" />
      <line x1={left} y1={midY} x2={left + plotW} y2={midY} stroke={t.rule} strokeWidth="1" strokeDasharray="3 4" />
      {q.top_left && <text x={left + 14} y={top + 24} {...corner}>{q.top_left.toUpperCase()}</text>}
      {q.top_right && <text x={left + plotW - 14} y={top + 24} textAnchor="end" {...corner}>{q.top_right.toUpperCase()}</text>}
      {q.bottom_left && <text x={left + 14} y={top + plotH - 14} {...corner}>{q.bottom_left.toUpperCase()}</text>}
      {q.bottom_right && <text x={left + plotW - 14} y={top + plotH - 14} textAnchor="end" {...corner}>{q.bottom_right.toUpperCase()}</text>}

      <text x={left} y={top + plotH + 20} {...mono}>{g.xAxis.low}</text>
      <text x={left + plotW} y={top + plotH + 20} textAnchor="end" {...mono}>{g.xAxis.high}</text>
      {g.xAxis.label && (
        <text x={midX} y={top + plotH + 40} textAnchor="middle" fontFamily={t.fonts.sans} fontSize="12" fontWeight="500" fill={t.ink}>
          {g.xAxis.label}
        </text>
      )}
      <text x={left - 12} y={top + 12} textAnchor="end" {...mono}>{g.yAxis.high}</text>
      <text x={left - 12} y={top + plotH} textAnchor="end" {...mono}>{g.yAxis.low}</text>
      {g.yAxis.label && (
        <text transform={`translate(14 ${midY}) rotate(-90)`} textAnchor="middle" fontFamily={t.fonts.sans} fontSize="12" fontWeight="500" fill={t.ink}>
          {g.yAxis.label}
        </text>
      )}

      {g.items.map((item, i) => {
        const dot = item.focal ? 7 : 5
        const ring = a.ring(`i${i}`, item.focal)
        const spot = a.spot(`i${i}`)
        return (
        <g key={i} {...a.item(i)}>
          <circle cx={item.cx} cy={item.cy} r={dot} fill={item.focal ? t.accent : t.paper} stroke={item.focal ? t.accent : t.line} strokeWidth="1" />
          {ring && <circle {...ring} cx={item.cx} cy={item.cy} r={dot + 3} />}
          {spot && <circle {...spot} cx={item.cx} cy={item.cy} r={dot + 7} />}
          <text
            x={item.side === 'right' ? item.cx + 12 : item.cx - 12}
            y={item.labelY + 4}
            textAnchor={item.side === 'right' ? 'start' : 'end'}
            fontFamily={t.fonts.sans}
            fontSize="12"
            fontWeight={item.focal ? 600 : 500}
            fill={t.ink}
            {...halo(t)}
          >
            {item.label}
          </text>
        </g>
        )
      })}
    </g>
  )
}

// ---------- frame ----------

/** Natural pixel size of the whole framed diagram (title block + body + padding). */
export function frameSize(layout) {
  const bodyTop = PAD + (layout.subtitle ? 92 : 72)
  return {
    bodyTop,
    width: Math.ceil(Math.max(layout.width, layout.titleW, layout.subtitleW, 480) + PAD * 2),
    height: Math.ceil(bodyTop + layout.height + PAD),
  }
}

/** `plan` is an animation plan (see animation.js); without one the diagram is static. */
export default function Diagram({ layout, theme, plan = null }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '')
  const arrowId = `arrow-${uid}`
  const t = theme
  const a = makeAnim(layout, plan, uid, t)

  const hasSubtitle = Boolean(layout.subtitle)
  const { bodyTop, width, height } = frameSize(layout)
  const label = TYPE_LABELS[layout.type] || 'Diagram'

  let body = null
  if (layout.kind === 'graph') body = <GraphBody g={layout} t={t} arrowId={arrowId} a={a} />
  else if (layout.kind === 'sequence') body = <SequenceBody g={layout} t={t} arrowId={arrowId} a={a} />
  else if (layout.kind === 'timeline') body = <TimelineBody g={layout} t={t} a={a} />
  else if (layout.kind === 'quadrant') body = <QuadrantBody g={layout} t={t} a={a} />

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      data-diagram
      aria-labelledby={`${uid}t ${uid}d`}
      style={{ width: '100%', maxWidth: width, height: 'auto', display: 'block' }}
    >
      <title id={`${uid}t`}>{layout.title}</title>
      <desc id={`${uid}d`}>{`${label} diagram. ${layout.subtitle || ''}`.trim()}</desc>
      {a.css && <style data-anim-css>{a.css}</style>}
      <defs>
        <Arrowhead id={arrowId} t={t} />
      </defs>
      <rect width={width} height={height} fill={t.paper} />
      <text x={PAD} y={PAD + 8} fontFamily={t.fonts.mono} fontSize={TYPE.kicker} letterSpacing="0.14em" fill={t.muted}>
        {label.toUpperCase()}
      </text>
      <text x={PAD} y={PAD + 44} fontFamily={t.fonts.serif} fontSize={TYPE.title} fill={t.ink}>
        {layout.title}
      </text>
      {hasSubtitle && (
        <text x={PAD} y={PAD + 68} fontFamily={t.fonts.sans} fontSize={TYPE.subtitle} fill={t.muted}>
          {layout.subtitle}
        </text>
      )}
      <line x1={PAD} y1={bodyTop - 20} x2={width - PAD} y2={bodyTop - 20} stroke={t.rule} strokeWidth="1" />
      <g transform={`translate(${PAD} ${bodyTop})`}>{body}</g>
    </svg>
  )
}
