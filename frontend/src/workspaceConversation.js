// Only documented commands can request execution. Free text becomes a draft goal.
export function workspaceIntent(text) {
  const input = text.trim()
  const lower = input.toLowerCase()
  if (/^(?:hi|hello|hey|thanks|thank you|你好|您好|嗨|谢谢)[!！。.\s]*$/i.test(input)) return { kind: 'greeting' }
  if (/^(?:why\b|what\b|how\b|explain\b|can you explain\b|为什么|为何|什么是|怎么理解|解释|说明一下)/i.test(input)) {
    return { kind: 'question', text: input }
  }
  if (['/run', 'run', '运行', '执行', '运行测试'].includes(lower)) return { kind: 'run' }
  if (['/files', 'list files', '列出文件', '查看文件'].includes(lower)) return { kind: 'files' }
  if (['/plan', '计划书', '修改计划书'].includes(lower)) return { kind: 'plan' }
  const restore = /^\/restore ([a-f0-9]{32})$/i.exec(input)
  if (restore) return { kind: 'restore', id: restore[1].toLowerCase() }
  return { kind: 'goal', goal: input }
}

export function workspaceRoute(text, quickMode) {
  const intent = workspaceIntent(text)
  return quickMode && !['run', 'restore', 'files', 'plan'].includes(intent.kind)
    ? { kind: 'quick', text: text.trim() } : intent
}
