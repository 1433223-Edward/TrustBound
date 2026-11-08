// Emit directory rows before their files and keep paths relative to the snapshot.
export function fileTreeRows(paths, explicitDirectories = []) {
  const directories = new Set()
  const rows = []
  for (const path of [...paths, ...explicitDirectories.map(path => path + '/')].sort((left, right) => left.localeCompare(right))) {
    const parts = path.split('/')
    for (let depth = 0; depth < parts.length - 1; depth++) {
      const directory = parts.slice(0, depth + 1).join('/')
      if (!directories.has(directory)) {
        rows.push({ path: directory, name: parts[depth], depth, directory: true })
        directories.add(directory)
      }
    }
    if (parts.at(-1)) rows.push({ path, name: parts.at(-1), depth: parts.length - 1, directory: false })
  }
  return rows
}

// Folder pickers include caches and unrelated assets; import only supported source documents.
export function importableProjectFile(file) {
  const path = file.webkitRelativePath || file.name
  return !path.split('/').some(part => part.startsWith('.') || ['node_modules', '__pycache__'].includes(part)) &&
    (/\.(py|md|txt)$/.test(file.name) || file.name === 'TRUSTBOUND_PLAN.json')
}
