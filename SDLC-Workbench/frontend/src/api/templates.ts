// Word templates (S23 Part C): one .docx per document type per project. The server stores them and says whether each has a table of contents; the screen only shows that.
import { arr, bool, nullable, num, obj, str } from './decode'

export interface TemplateInfo { category: string; label: string; size: number; uploaded_at: string; has_toc: boolean; toc_note: string }
export interface TemplateSlot { category: string; label: string; template: TemplateInfo | null }
export interface TemplatesView {
  categories: TemplateSlot[]
  can_change: boolean
  max_mb: number
  note: string
  /** Present on the answer to an upload: the template that was just stored. */
  saved?: TemplateInfo
}

export function decodeTemplateInfo(value: unknown, w = 'template'): TemplateInfo {
  const o = obj(value, w)
  return {
    category: str(o.category, `${w}.category`), label: str(o.label, `${w}.label`), size: num(o.size, `${w}.size`), uploaded_at: str(o.uploaded_at, `${w}.uploaded_at`),
    has_toc: bool(o.has_toc, `${w}.has_toc`), toc_note: str(o.toc_note, `${w}.toc_note`),
  }
}

export function decodeTemplates(value: unknown): TemplatesView {
  const o = obj(value, 'templates')
  const view: TemplatesView = {
    categories: arr(o.categories, 'templates.categories').map((c, i) => {
      const co = obj(c, `templates.categories[${i}]`)
      return { category: str(co.category, `templates.categories[${i}].category`), label: str(co.label, `templates.categories[${i}].label`),
               template: nullable(co.template, `templates.categories[${i}].template`, (t, w) => decodeTemplateInfo(t, w)) }
    }),
    can_change: bool(o.can_change, 'templates.can_change'), max_mb: num(o.max_mb, 'templates.max_mb'), note: str(o.note, 'templates.note'),
  }
  if ('saved' in o) view.saved = decodeTemplateInfo(o.saved, 'templates.saved')
  return view
}
