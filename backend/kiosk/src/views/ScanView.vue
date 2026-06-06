<template>
  <div class="kiosk" @click="refocus">
    <input
      ref="hiddenInput"
      class="hidden-input"
      v-model="buffer"
      @keydown.enter.prevent="onEnter"
      autocomplete="off"
      autocorrect="off"
    />

    <transition name="fade" mode="out-in">
      <div v-if="state === 'idle'" key="idle" class="screen idle">
        <div class="icon">📦</div>
        <p class="big-text">请扫描包裹条码</p>
        <p class="hint">将扫码枪对准包裹条形码</p>
      </div>

      <div v-else-if="state === 'loading'" key="loading" class="screen loading">
        <div class="spinner"></div>
        <p class="big-text">处理中…</p>
      </div>

      <!-- 已匹配员工：格子号最显眼 -->
      <div v-else-if="state === 'success'" key="success" class="screen success">
        <div class="icon">✅</div>
        <p class="label-hint">请放到格子</p>
        <p class="slot-number">{{ String(lastSlot).padStart(2, '0') }}</p>
        <p class="courier-text">{{ lastCourier }}</p>
        <p class="hint">取出打印标签贴到包裹上</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <!-- 待认领：格子号同样显眼，方便工作人员放置 -->
      <div v-else-if="state === 'unclaimed'" key="unclaimed" class="screen unclaimed">
        <div class="icon">⚠️</div>
        <p class="label-hint">无法识别收件人，放到格子</p>
        <p class="slot-number">{{ String(lastSlot).padStart(2, '0') }}</p>
        <p class="hint">已打「待认领」标签，放对应格子即可</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <div v-else-if="state === 'error'" key="error" class="screen error">
        <div class="icon">❌</div>
        <p class="big-text">扫描失败</p>
        <p class="hint">{{ errorMsg }}</p>
        <p class="hint small">{{ RESET_MS / 1000 }} 秒后自动重试…</p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue"
import { submitBarcode } from "../api/scan.js"

const RESET_MS = 4000

const state       = ref("idle")
const buffer      = ref("")
const lastSlot    = ref(0)
const lastCourier = ref("")
const errorMsg    = ref("")
const hiddenInput = ref(null)
let resetTimer = null

function refocus() { hiddenInput.value?.focus() }
function onVisibility() { if (!document.hidden) refocus() }

onMounted(() => {
  refocus()
  document.addEventListener("visibilitychange", onVisibility)
})
onUnmounted(() => {
  document.removeEventListener("visibilitychange", onVisibility)
  clearTimeout(resetTimer)
})

async function onEnter() {
  const barcode = buffer.value.trim()
  buffer.value = ""
  if (!barcode) { refocus(); return }

  state.value = "loading"
  clearTimeout(resetTimer)

  try {
    const data    = await submitBarcode(barcode)
    lastSlot.value    = data.slot
    lastCourier.value = data.courier
    state.value = data.matched ? "success" : "unclaimed"
  } catch (e) {
    errorMsg.value = e.message || "请求失败"
    state.value = "error"
  }

  resetTimer = setTimeout(() => { state.value = "idle"; refocus() }, RESET_MS)
}
</script>

<style scoped>
.kiosk {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100dvh;
  background: #0f172a;
  color: #f1f5f9;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  user-select: none;
}

.hidden-input {
  position: fixed; opacity: 0; width: 1px; height: 1px;
  top: 0; left: 0; pointer-events: none;
}

.screen {
  display: flex; flex-direction: column;
  align-items: center; gap: 0.75rem;
  padding: 2rem; text-align: center;
}

.icon       { font-size: 4rem; line-height: 1; }
.big-text   { font-size: clamp(2rem, 5vw, 3rem); font-weight: 700; }
.label-hint { font-size: 1.5rem; color: #94a3b8; }

/* 格子号：超大，远距离也看得清 */
.slot-number {
  font-size: clamp(6rem, 20vw, 12rem);
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0.05em;
  font-variant-numeric: tabular-nums;
}

.courier-text { font-size: 1.5rem; color: #7dd3fc; }
.hint         { font-size: 1.1rem; color: #94a3b8; }
.small        { font-size: 0.95rem; }

.idle     { color: #cbd5e1; }
.success  .slot-number { color: #86efac; }
.unclaimed .slot-number { color: #fde68a; }
.error    { color: #fca5a5; }

.spinner {
  width: 4rem; height: 4rem;
  border: 6px solid #334155; border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.countdown-bar {
  width: min(400px, 80vw); height: 6px;
  background: #1e293b; border-radius: 3px;
  overflow: hidden; margin-top: 0.5rem;
}
.countdown-fill {
  height: 100%; background: #38bdf8;
  border-radius: 3px;
  animation: countdown linear forwards;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from,   .fade-leave-to     { opacity: 0; }

@keyframes spin     { to { transform: rotate(360deg); } }
@keyframes countdown { from { width: 100%; } to { width: 0%; } }
</style>
