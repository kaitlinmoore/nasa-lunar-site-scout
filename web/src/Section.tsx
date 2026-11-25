// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// A titled card on the site page that can be collapsed and expanded (the project author's idea).
// Collapsing applies only on the site page itself (`CollapsibleSections` = true there); cards
// inside a section (e.g. an NL answer's dashboard) stay plain. Defaults and memory: sections.ts.
import { type ReactNode, useContext, useId, useState } from 'react'
import { CollapsibleSections, initialOpen, type SectionId, storeSection } from './sections'

/**
 * A card with an `<h2>` title. On the site page the title is a button that collapses the body;
 * a collapsed body isn't mounted until first opened (so e.g. the terrain map loads on demand),
 * and stays mounted, hidden, after it's closed again (keeping its state).
 */
export default function Section({
  id,
  title,
  className,
  children,
}: {
  id: SectionId
  title: ReactNode
  className?: string
  children: ReactNode
}) {
  const collapsible = useContext(CollapsibleSections)
  const bodyId = useId()
  const [open, setOpen] = useState(() => !collapsible || initialOpen(id))
  const [opened, setOpened] = useState(open)
  const cls = ['card', className].filter(Boolean).join(' ')
  if (!collapsible) {
    return (
      <section className={cls}>
        <h2>{title}</h2>
        {children}
      </section>
    )
  }
  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next) setOpened(true)
    storeSection(id, next)
  }
  return (
    <section className={`${cls} collapsible${open ? '' : ' is-collapsed'}`}>
      <h2>
        <button type="button" className="section-toggle" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
          <span className="section-chevron" aria-hidden="true" />
          {title}
        </button>
      </h2>
      <div id={bodyId} className="section-body" hidden={!open}>
        {/* Cards inside a section (e.g. an NL answer's dashboard) don't collapse. */}
        <CollapsibleSections.Provider value={false}>{opened && children}</CollapsibleSections.Provider>
      </div>
    </section>
  )
}
