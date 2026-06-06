<template>
  <div class="kiosk" @click="refocus">
    <!-- 隐藏 input 持续吸住焦点：USB HID 扫码枪模拟键盘，焦点丢失则数据丢失 -->
    <input
      ref="hiddenInput"
      class="hidden-input"
      v-model="buffer"
      @keydown.enter.prevent="onEnter"
      autocomplete="off"
      autocorrect="off"
    />

    <transition name="fade" mode="out-in">
      <!-- 待机 -->
      <div v-if="state === 'idle'" key="idle" class="screen idle">
        <div class="icon">📦</div>
        <p class="big-text">请扫描包裹条码</p>
        <p class="hint">将扫码枪对准包裹条形码</p>
      </div>

      <!-- 处理中 -->
      <div v-else-if="state === 'loading'" key="loading" class="screen loading">
        <div class="spinner"></div>
        <p class="big-text">处理中…</p>
      </div>

      <!-- 已匹配员工 -->
      <div v-else-if="state === 'success'" key="success" class="screen success">
        <div class="icon">✅</div>
        <p class="big-text">扫描成功</p>
        <p class="code">{{ lastCode }}</p>
        <p class="hint">请取出打印标签贴到包裹上</p>
        <p class="courier">快递：{{ lastCourier }}</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <!-- 未匹配（待认领） -->
      <div v-else-if="state === 'unclaimed'" key="unclaimed" class="screen unclaimed">
        <div class="icon">⚠️</div>
        <p class="big-text">无法识别收件人</p>
        <p class="code">{{ lastCode }}</p>
        <p class="hint">已贴「待认领」标签，请放到对应快递格</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <!-- 出错 -->
      <div v-else-if="state === 'error'" key="error" class="screen error">
        <div class="icon">❌</div>
        <p class="big-text">扫描失败</p>
        <p class="hint">{{ errorMsg }}</p>
        <p class="hint small">3 秒后自动重试…</p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue"
import { submitBarcode } from "../api/scan.js"

const RESET_MS = 4000   // 结果展示时长（ms）

const state       = ref("idle")
const buffer      = ref("")
const lastCode    = ref("")
const lastCourier = ref("")
const errorMsg    = ref("")
const hiddenInput = ref(null)

let resetTimer = null

function refocus() {
  hiddenInput.value?.focus()
}

function onVisibility() {
  if (!document.hidden) refocus()
}

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
    const data = await submitBarcode(barcode)
    lastCode.value    = data.code
    lastCourier.value = data.courier
    state.value = data.matched ? "success" : "unclaimed"
  } catch (e) {
    errorMsg.value = e.message || "请求失败"
    state.value = "error"
  }

  resetTimer = setTimeout(() => {
    state.value = "idle"
    refocus()
  }, RESET_MS)
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
  position: fixed;
  opacity: 0;
  width: 1px;
  height: 1px;
  top: 0; left: 0;
  pointer-events: none;
}

/* ── Screens ── */
.screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 2rem;
  text-align: center;
}

.icon  { font-size: 5rem; line-height: 1; }

.big-text {
  font-size: clamp(2rem, 5vw, 3.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.code {
  font-size: clamp(3rem, 8vw, 5rem);
  font-weight: 900;
  letter-spacing: 0.05em;
  color: #38bdf8;
  font-variant-numeric: tabular-nums;
}

.hint  { font-size: 1.25rem; color: #94a3b8; }
.small { font-size: 1rem; }

.courier { font-size: 1.5rem; color: #7dd3fc; }

/* ── Colors per state ── */
.idle     { color: #cbd5e1; }
.success  { color: #86efac; }
.unclaimed{ color: #fde68a; }
.error    { color: #fca5a5; }

/* ── Spinner ── */
.spinner {
  width: 4rem; height: 4rem;
  border: 6px solid #334155;
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Countdown bar ── */
.countdown-bar {
  width: min(400px, 80vw);
  height: 6px;
  background: #1e293b;
  border-radius: 3px;
  overflow: hidden;
  margin-top: 1rem;
}

.countdown-fill {
  height: 100%;
  background: #38bdf8;
  border-radius: 3px;
  animation: countdown linear forwards;
  animation-duration: 4000ms; /* overridden by :style binding */
}

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from,
.fade-leave-to     { opacity: 0; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes countdown {
  from { width: 100%; }
  to   { width: 0%; }
}
</style>
