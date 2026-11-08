import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agentNarration } from '../src/agentNarration.js'
import { language } from '../src/i18n.js'

test('narration uses actual counts and incomplete evidence never means failed', () => {
  language.value = 'en'
  const run = { run_id: 'actual-run', state: 'RUNNING', workspace_report: {
    agent_events: [{role:'executor',stage:'Proposal received',status:'COMPLETED'}],
    cases:[{phase:'acceptance',status:'MATCHED'},{phase:'acceptance',status:'INCONCLUSIVE'}] } }
  const rows = agentNarration({run})
  assert.equal(rows[0].role, 'executor')
  assert.match(rows[1].text, /1 matched, 0 mismatched, 1 incomplete/)
  assert.equal(rows[1].status, 'INCONCLUSIVE')
  assert.equal(rows[1].runId, 'actual-run')
  assert.equal(rows[1].tab, 'logs')
  assert.equal(rows.some(row => /All required/.test(row.text)),false)
  assert.deepEqual(agentNarration({run}), rows)
  language.value='zh-CN'
  assert.match(agentNarration({run})[1].text, /独立验收/)
})

test('confirmed challenges and recovery retain roles and evidence links', () => {
  language.value='en'
  const rows=agentNarration({run:{run_id:'retry',state:'COMPLETED',workspace_report:{
    status:'FAILED',retried_from:'parent',cases:[],adversarial_report:{challenges:[{status:'CONFIRMED'}]}}}})
  assert.equal(rows.find(row=>row.role==='recovery').tab,'recovery')
  assert.ok(rows.some(row=>row.role==='verifier' && /counterexample/.test(row.text)))
  assert.ok(rows.every(row=>row.runId==='retry'))
})

import { workspaceRoute } from '../src/workspaceConversation.js'
test('quick greetings, analysis and changes route directly while explicit execution stays gated', () => {
  for (const text of ['你好', 'Explain this code', 'Fix duplicate stock deductions']) {
    assert.equal(workspaceRoute(text,true).kind,'quick')
  }
  assert.equal(workspaceRoute('/run',true).kind,'run')
  assert.equal(workspaceRoute('/files',true).kind,'files')
  assert.equal(workspaceRoute('Fix stock',false).kind,'goal')
})

import { agentCards } from '../src/agentNarration.js'
test('cards update by role without duplicating statuses, preserving first role order', () => {
  const run={run_id:'one',state:'RUNNING',workspace_report:{cases:[],agent_events:[
    {role:'executor',stage:'Candidate generation',status:'RUNNING'},
    {role:'adversarial',stage:'Independent analysis',status:'RUNNING'},
    {role:'executor',stage:'Proposal received',status:'COMPLETED'},
  ]}}
  let cards=agentCards({run})
  assert.deepEqual(cards.map(row=>row.role),['executor','adversarial'])
  const executorKey=cards[0].key
  run.workspace_report.agent_events.push({role:'executor',stage:'Generation failed',status:'ERROR'})
  cards=agentCards({run})
  assert.equal(cards.length,2)
  assert.equal(cards[0].key,executorKey)
  assert.equal(cards[0].status,'ERROR')
})

test('model explanation is labeled and attached to the existing role card', () => {
  language.value='en'
  const run={run_id:'two',state:'COMPLETED',workspace_report:{status:'FAILED',artifact_hash:'a',frozen_hash:'f',cases:[],
    agent_events:[{role:'executor',stage:'Proposal received',status:'COMPLETED',model:'actual-model',explanation_source:'MODEL',
      explanation:{description:{en:'Proposed a correction',zh:'提出修正'},reason:{en:'To match the approved goal',zh:'符合批准目标'}}}]}}
  const cards=agentCards({run})
  assert.equal(cards[0].source,'MODEL')
  assert.equal(cards[0].reason,'To match the approved goal')
  assert.equal(cards[0].model,'actual-model')
  assert.equal(cards.filter(row=>row.role==='verifier').length,1)
  assert.equal(cards.at(-1).status,'FAILED')
})

test('security-only narration never describes execution as functional verification', () => {
  language.value='en'
  const cards=agentCards({run:{run_id:'security',state:'COMPLETED',workspace_report:{
    verification_mode:'SECURITY_ONLY',status:'EXECUTED_UNVERIFIED',cases:[{phase:'execution',status:'EXECUTED'}],
    agent_events:[{role:'verifier',stage:'Security execution',status:'RUNNING'}]}}})
  assert.equal(cards.length,1)
  assert.equal(cards[0].status,'EXECUTED_UNVERIFIED')
  assert.match(cards[0].text,/Functional correctness was not verified/)
  assert.equal(cards.some(row=>row.status==='VERIFIED'),false)
  language.value='zh-CN'
  assert.match(agentCards({run:{run_id:'security',state:'COMPLETED',workspace_report:{status:'EXECUTED_UNVERIFIED',cases:[]}}})[0].text,/未验证功能正确性/)
})
