<script setup>
import { computed } from 'vue'
import { t } from '../i18n.js'

const capabilities = computed(() => [
  { icon: '⌑', title: 'Secure Sandbox', text: t('A restricted runner enforces write scope, resource limits and cleanup. Every run leaves evidence.', '受限 Runner 管理修改范围、资源和清理过程，保留可复查的执行证据。') },
  { icon: '◇', title: 'Adversarial Verification', text: t('An independent agent looks for counterexamples. The trusted verifier makes the decision.', '独立 Agent 寻找反例，可信 Verifier 根据实际证据裁决。') },
  { icon: '⌘', title: 'Semantic Context Reconstruction', text: t('A future plug-in will assemble relevant context while retaining mandatory requirements.', '未来插件将重组相关上下文，并始终保留硬性需求与约束。'), planned: true },
])
const flow = computed(() => [
  t('User goal', '用户目标'), t('Agent proposal', 'Agent 提案'), t('Permission gate', '权限检查'),
  t('Isolated runner', '独立 Runner'), t('Sandbox execution', '沙盒执行'),
  t('Trusted verifier', '可信验收'), t('Evidence report', '证据报告'),
])
</script>

<template>
  <section class="product-page product-home">
    <header class="home-hero">
      <div class="hero-copy">
        <span class="eyebrow product-kicker"><i></i>{{ $t('TRUSTBOUND / AGENT WORKSPACE', 'TRUSTBOUND / 智能开发工作区') }}</span>
        <h1>{{ $t('Give agents room to act.', '让 Agent 执行，') }}<br><em>{{ $t('Keep proof independent.', '让证据独立。') }}</em></h1>
        <p>{{ $t('A secure development workspace for AI-generated changes, isolated execution, and evidence you can inspect.', '面向开发者的安全工作区。让 AI 提案，在受限环境执行，并保留可以亲自检查的证据。') }}</p>
        <div class="product-actions">
          <a class="product-button primary" href="#demo">{{ $t('Try Demo Replay', '体验演示回放') }} <span aria-hidden="true">↗</span></a>
          <a class="product-button" href="#workspace">{{ $t('Open Workspace', '打开工作区') }} <span aria-hidden="true">→</span></a>
        </div>
        <p class="hero-principle">{{ $t('An agent that can act, but cannot certify its own success.', 'Agent 可以执行，可信验收器负责裁决。') }}</p>
      </div>
      <figure class="flow-board">
        <figcaption><span class="flow-lights" aria-hidden="true"><i></i><i></i><i></i></span>{{ $t('EXECUTION ARCHITECTURE', '执行架构') }}</figcaption>
        <ol class="product-flow">
          <li v-for="(step, index) in flow" :key="index" :class="{ boundary: index === 2 || index === 5 }">
            <span class="flow-index mono">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ step }}</strong><span v-if="index === 2 || index === 5" class="flow-tag">{{ $t('TRUSTED', '可信控制') }}</span>
          </li>
        </ol>
      </figure>
    </header>
    <section class="home-section">
      <div class="section-intro"><span class="eyebrow">{{ $t('PRODUCT PRINCIPLES', '产品理念') }}</span><h2>{{ $t('A proposal earns its verdict.', '让验收证据决定结果') }}</h2></div>
      <div class="capability-grid">
        <article v-for="item in capabilities" :key="item.title" class="product-card">
          <div class="capability-top"><span class="capability-icon" aria-hidden="true">{{ item.icon }}</span><span v-if="item.planned" class="product-chip">{{ $t('Future plug-in', '未来插件') }}</span></div>
          <h3>{{ item.title }}</h3><p>{{ item.text }}</p>
        </article>
      </div>
      <p class="scope-note">{{ $t('VERIFIED applies to the declared acceptance checks. User feedback, regression tests and evaluations help improve coverage over time.', 'VERIFIED 仅表示通过本次声明的验收范围。后续通过用户反馈、回归测试和评测改进覆盖。') }}</p>
    </section>
    <section class="home-section product-home-bottom">
      <article class="product-card demo-preview">
        <span class="eyebrow">{{ $t('GUIDED DEMO', '演示入口') }}</span><h2>Billing Rounding</h2>
        <p>{{ $t('Follow a real recorded run, compare the patch, and see how the independent verifier treats a false success.', '回看真实运行记录、对比补丁，并查看独立验收如何识别假成功。') }}</p>
        <a href="#demo">{{ $t('Open the recorded demo', '打开历史演示') }} →</a>
      </article>
      <article class="product-card">
        <span class="eyebrow">{{ $t('INFRASTRUCTURE', '运行基础') }}</span><h2>{{ $t('Built on Vultr', '基于 Vultr') }}</h2>
        <div class="stack-labels"><span>Vultr VM</span><span>Serverless Inference</span><span>Rootless Docker</span></div>
        <p>{{ $t('Review the architecture, deployment boundaries and known limits.', '查看架构、部署边界和已知限制。') }}</p>
        <a href="#documentation">{{ $t('Read the documentation', '阅读项目手册') }} →</a>
      </article>
    </section>
  </section>
</template>
