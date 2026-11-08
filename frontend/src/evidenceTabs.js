import { t } from './i18n.js'

// Shared by Billing and Workspace, with the same identifiers and navigation order.
export function evidenceTabs() {
  return [
    { id: 'summary', label: t('Overview', '概览') },
    { id: 'diff', label: t('Raw diff', '原始差异') },
    { id: 'logs', label: t('Execution logs', '执行日志') },
    { id: 'adversarial', label: t('Adversarial', '对抗') },
    { id: 'recovery', label: t('Recovery', '恢复') },
  ]
}
