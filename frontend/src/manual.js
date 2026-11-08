// The public handbook uses a small Markdown subset. Render every value as text.
export function parseManual(markdown) {
  const blocks = []
  let fence = null
  let heading = 0
  const lines = markdown.split(/\r?\n/)
  const cells = row => row.trim().slice(1, -1).split('|').map(value => value.trim())
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    if (line.startsWith('```')) {
      if (fence) {
        blocks.push({ type: 'code', text: fence.join('\n') })
        fence = null
      } else fence = []
    } else if (fence) {
      fence.push(line)
    } else if (line) {
      const match = /^(#{1,3}) (.+)$/.exec(line)
      if (match) {
        blocks.push({ type: 'heading', level: match[1].length, text: match[2],
          id: `documentation/section-${++heading}` })
      } else if (line.startsWith('> ')) {
        blocks.push({ type: 'quote', text: line.slice(2) })
      } else if (line.startsWith('|') && line.endsWith('|') && /^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[index + 1] ?? '')) {
        const table = { type: 'table', headers: cells(line), rows: [] }
        index++
        while (lines[index + 1]?.startsWith('|') && lines[index + 1].endsWith('|')) {
          table.rows.push(cells(lines[++index]))
        }
        blocks.push(table)
      } else if (line.startsWith('- ')) {
        if (blocks.at(-1)?.type !== 'list') blocks.push({ type: 'list', items: [] })
        blocks.at(-1).items.push(line.slice(2))
      } else {
        blocks.push({ type: 'paragraph', text: line })
      }
    }
  }
  if (fence) blocks.push({ type: 'code', text: fence.join('\n') })
  return blocks
}
