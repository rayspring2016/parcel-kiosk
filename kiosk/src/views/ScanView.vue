<template>
  <div class="kiosk" @click="refocus">
    <input ref="hiddenInput" class="hidden-input" v-model="buffer"
           @keydown.enter.prevent="onBarcodeScan" autocomplete="off" autocorrect="off" />

    <div class="dev-bar">
      <input class="dev-input" v-model="devInput"
             placeholder="调试：输入条码后按回车"
             @keydown.enter.prevent="onDevSubmit" />
    </div>

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

      <!-- 已生成编号，等待输入手机尾号 -->
      <div v-else-if="state === 'scanned'" key="scanned" class="screen scanned">
        <p class="courier-tag">{{ courier }}</p>
        <p class="label-hint">取件编号（已打印）</p>
        <p class="code">{{ lastCode }}</p>
        <p class="big-text phone-prompt">请输入手机尾号</p>
        <div class="digit-display">
          <span v-for="i in 4" :key="i" class="digit-box">{{ phoneTail[i-1] || '_' }}</span>
        </div>
        <div class="numpad">
          <button v-for="n in [1,2,3,4,5,6,7,8,9]" :key="n"
                  class="num-btn" @click="appendDigit(String(n))">{{ n }}</button>
          <button class="num-btn del-btn" @click="deleteDigit">⌫</button>
          <button class="num-btn" @click="appendDigit('0')">0</button>
          <button class="num-btn skip-btn" @click="skipAssign">跳过</button>
        </div>
      </div>

      <!-- 输入姓氏消歧 -->
      <div v-else-if="state === 'surname_input'" key="surname" class="screen surname-input">
        <p class="code">{{ lastCode }}</p>
        <p class="big-text">匹配到多位收件人</p>
        <p class="hint">请输入收件人姓氏（如：张）</p>
        <input ref="surnameInput" class="surname-field" v-model="surname"
               maxlength="4" placeholder="姓氏"
               @keydown.enter.prevent="submitSurname" />
        <div class="row-btns">
          <button class="action-btn" @click="submitSurname">确认</button>
          <button class="action-btn skip-btn" @click="skipAssign">跳过→待认领</button>
        </div>
      </div>

      <!-- 匹配成功 -->
      <div v-else-if="state === 'success'" key="success" class="screen success">
        <div class="icon">✅</div>
        <p class="big-text">通知已发送</p>
        <p class="code">{{ lastCode }}</p>
        <p class="hint">员工已收到取件通知</p>
        <p class="courier">快递：{{ courier }}</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <!-- 待认领（无匹配 or 重复） -->
      <div v-else-if="state === 'unclaimed'" key="unclaimed" class="screen unclaimed">
        <div class="icon">⚠️</div>
        <p class="big-text">标签已打印</p>
        <p class="code">{{ lastCode }}</p>
        <p class="hint">{{ unclaimedMsg }}</p>
        <div class="countdown-bar">
          <div class="countdown-fill" :style="{ animationDuration: RESET_MS + 'ms' }"></div>
        </div>
      </div>

      <!-- 出错 -->
      <div v-else-if="state === 'error'" key="error" class="screen error">
        <div class="icon">❌</div>
        <p class="big-text">出错了</p>
        <p class="hint">{{ errorMsg }}</p>
        <p class="hint small">3 秒后重置…</p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from "vue"

const BASE_URL = import.meta.env.VITE_API_BASE || "http://localhost:8000"
const RESET_MS = 5000

const state       = ref("idle")
const buffer      = ref("")
const devInput    = ref("")
const courier     = ref("")
const phoneTail   = ref("")
const surname     = ref("")
const lastCode    = ref("")
const errorMsg    = ref("")
const unclaimedMsg= ref("")
const hiddenInput = ref(null)
const surnameInput= ref(null)

let currentPkgId = null
let resetTimer   = null

function refocus() {
  if (state.value === "idle") hiddenInput.value?.focus()
  if (state.value === "surname_input") nextTick(() => surnameInput.value?.focus())
}
function onVisibility() { if (!document.hidden) refocus() }
onMounted(() => { refocus(); document.addEventListener("visibilitychange", onVisibility) })
onUnmounted(() => { document.removeEventListener("visibilitychange", onVisibility); clearTimeout(resetTimer) })

async function onDevSubmit() {
  const bc = devInput.value.trim(); devInput.value = ""
  if (!bc) return
  buffer.value = bc; await onBarcodeScan()
}

// ── Step 1：扫码 → 立即入库+打印，返回编号 ──
async function onBarcodeScan() {
  const barcode = buffer.value.trim(); buffer.value = ""
  if (!barcode || state.value !== "idle") return
  state.value = "loading"; clearTimeout(resetTimer)
  try {
    const resp = await fetch(`${BASE_URL}/scan`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ barcode })
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    lastCode.value  = data.code
    courier.value   = data.courier
    currentPkgId    = data.pkg_id
    phoneTail.value = ""
    state.value     = "scanned"   // 显示编号 + 数字键盘
  } catch(e) {
    showError(e.message || "扫描失败")
  }
}

// ── Step 2：输入手机尾号 ──
function appendDigit(d) {
  if (phoneTail.value.length < 4) phoneTail.value += d
  if (phoneTail.value.length === 4) submitAssign()
}
function deleteDigit() { phoneTail.value = phoneTail.value.slice(0, -1) }

async function submitAssign(sur = null) {
  if (phoneTail.value.length !== 4) return
  state.value = "loading"
  try {
    const body = { phone_tail: phoneTail.value }
    if (sur) body.surname = sur
    const resp = await fetch(`${BASE_URL}/scan/${currentPkgId}/assign`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()

    if (data.status === "matched") {
      state.value = "success"
      scheduleReset()
    } else {
      unclaimedMsg.value = data.status === "ambiguous_notified"
        ? `已通知 ${data.count} 位候选员工，请放到对应位置`
        : "未匹配到员工，包裹放待认领区"
      state.value = "unclaimed"
      scheduleReset()
    }
  } catch(e) {
    showError(e.message || "匹配失败")
  }
}

function submitSurname() {
  if (!surname.value.trim()) return
  submitAssign(surname.value.trim())
}

async function skipAssign() {
  // 不做匹配，直接结束，包裹保持待认领状态
  unclaimedMsg.value = "已跳过匹配，包裹放待认领区"
  state.value = "unclaimed"
  scheduleReset()
}

function scheduleReset() {
  resetTimer = setTimeout(() => { state.value = "idle"; refocus() }, RESET_MS)
}
function showError(msg) {
  errorMsg.value = msg; state.value = "error"
  resetTimer = setTimeout(() => { state.value = "idle"; refocus() }, 3000)
}
</script>

<style scoped>
.kiosk {
  display: flex; justify-content: center; align-items: center;
  min-height: 100dvh; background: #0f172a; color: #f1f5f9;
  font-family: "PingFang SC", "Microsoft YaHei", sans-serif; user-select: none;
}
.hidden-input { position: fixed; opacity: 0; width: 1px; height: 1px; top: 0; left: 0; pointer-events: none; }
.dev-bar { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); z-index: 10; }
.dev-input { padding: .5rem 1rem; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #f1f5f9; font-size: 1rem; width: 320px; outline: none; }
.dev-input:focus { border-color: #38bdf8; }

.screen { display: flex; flex-direction: column; align-items: center; gap: .75rem; padding: 2rem; text-align: center; }
.icon      { font-size: 5rem; line-height: 1; }
.big-text  { font-size: clamp(1.6rem, 4vw, 2.8rem); font-weight: 700; letter-spacing: -.02em; }
.phone-prompt { font-size: clamp(1.2rem, 3vw, 1.8rem); color: #94a3b8; font-weight: 500; margin-top: .25rem; }
.label-hint { font-size: 1rem; color: #64748b; margin-bottom: -.5rem; }
.code      { font-size: clamp(2.8rem, 8vw, 5rem); font-weight: 900; letter-spacing: .05em; color: #38bdf8; font-variant-numeric: tabular-nums; }
.hint      { font-size: 1.2rem; color: #94a3b8; }
.small     { font-size: 1rem; }
.courier   { font-size: 1.4rem; color: #7dd3fc; }
.courier-tag { font-size: 1.3rem; color: #7dd3fc; background: #1e293b; padding: .3rem 1rem; border-radius: 999px; }

.idle      { color: #cbd5e1; }
.success   { color: #86efac; }
.unclaimed { color: #fde68a; }
.error     { color: #fca5a5; }

.digit-display { display: flex; gap: .75rem; margin: .25rem 0; }
.digit-box { width: 3.5rem; height: 4.5rem; border: 2px solid #334155; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 2.5rem; font-weight: 700; color: #38bdf8; font-variant-numeric: tabular-nums; }
.numpad { display: grid; grid-template-columns: repeat(3, 5rem); gap: .65rem; margin-top: .25rem; }
.num-btn { height: 4rem; border-radius: 12px; border: none; cursor: pointer; background: #1e293b; color: #f1f5f9; font-size: 1.75rem; font-weight: 600; transition: background .15s; }
.num-btn:active { background: #334155; transform: scale(.95); }
.del-btn  { background: #2d1b1b; color: #fca5a5; }
.skip-btn { background: #1a1f2e; color: #94a3b8; font-size: .95rem; }

.surname-field { font-size: 2rem; text-align: center; width: 200px; padding: .5rem; border: 2px solid #334155; border-radius: 12px; background: #1e293b; color: #f1f5f9; outline: none; }
.surname-field:focus { border-color: #38bdf8; }
.row-btns { display: flex; gap: 1rem; margin-top: .5rem; }
.action-btn { padding: .75rem 2rem; border-radius: 12px; border: none; cursor: pointer; background: #1e40af; color: #fff; font-size: 1.2rem; font-weight: 600; }
.action-btn.skip-btn { background: #1e293b; color: #94a3b8; }

.spinner { width: 4rem; height: 4rem; border: 6px solid #334155; border-top-color: #38bdf8; border-radius: 50%; animation: spin .8s linear infinite; }
.countdown-bar { width: min(400px,80vw); height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-top: .5rem; }
.countdown-fill { height: 100%; background: #38bdf8; border-radius: 3px; animation: countdown linear forwards; }

.fade-enter-active, .fade-leave-active { transition: opacity .25s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes countdown { from { width: 100%; } to { width: 0%; } }
</style>
