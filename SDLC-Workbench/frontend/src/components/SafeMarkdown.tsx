import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { DISALLOWED_ELEMENTS, safeHref } from '../lib/markdown'
import { markPlugin, type Marks } from '../lib/reviewMarks'
import { CodeBlock } from './CodeBlock'
import { WireframeBlock } from './WireframeBlock'
import { filePathBefore } from '../lib/codeFiles'

/** Model-written Markdown, rendered as untrusted text: no raw HTML, no images, links only to http, https and mailto and never carrying the opener. */
/** `marks` colour-codes the places a review pointed at (red high, amber medium, blue low). Without it, or with none, the output is exactly as before. */
export function SafeMarkdown({ children, marks, collapseCode = false }: { children: string; marks?: Marks; collapseCode?: boolean }) {
  return (
    <div className="markdown">
      <Markdown
        remarkPlugins={[remarkGfm, markPlugin(marks)]}          // with no marks the plugin changes nothing
        disallowedElements={[...DISALLOWED_ELEMENTS]}
        unwrapDisallowed
        urlTransform={(url) => safeHref(url) ?? ''}
        components={{
          a: ({ href, children: inner }) => (href ? <a href={href} target="_blank" rel="noopener noreferrer nofollow">{inner}</a> : <span>{inner}</span>),
          // A fenced block tagged `svg` is a drawing (S13): cleaned and shown as a picture, with its source one click away. Every other code block is text.
          pre: ({ node, children: inner }) => {
            const code = node?.children?.[0]
            if (code && code.type === 'element' && code.tagName === 'code') {
              const classes = Array.isArray(code.properties?.className) ? code.properties.className.map(String) : []
              if (classes.includes('language-svg')) {
                const text = code.children.map((c) => (c.type === 'text' ? c.value : '')).join('')
                return <WireframeBlock source={text.replace(/\n$/, '')} />
              }
            }
            // Code in a Build artefact is collapsed and downloadable (S18). Elsewhere a code block is exactly what it always was.
            if (collapseCode && code && code.type === 'element' && code.tagName === 'code') {
              const classes = Array.isArray(code.properties?.className) ? code.properties.className.map(String) : []
              const language = classes.find((c) => c.startsWith('language-'))?.slice('language-'.length) ?? null
              const text = code.children.map((c) => (c.type === 'text' ? c.value : '')).join('')
              const start = node?.position?.start.line
              return <CodeBlock code={text} language={language} path={start ? filePathBefore(children, start) : null}><pre>{inner}</pre></CodeBlock>
            }
            return <pre>{inner}</pre>
          },
        }}
      >
        {children}
      </Markdown>
    </div>
  )
}
