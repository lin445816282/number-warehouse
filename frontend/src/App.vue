<template>
  <div class="app">
    <div class="top-bar">
      <span class="tb-title">🔢 数字仓库</span>
      <span class="tb-date">{{ todayStr }} <button class="tb-logout" @click="doLogout">退出</button></span>
    </div>

    <!-- 视图切换 -->
    <div class="view-tabs">
      <button :class="{ active: view === 'collection' }" @click="view = 'collection'; loadCollections()">集合</button>
      <button :class="{ active: view === 'export' }" @click="view = 'export'">同步</button>
      <button :class="{ active: view === 'threshold' }" @click="view = 'threshold'; loadThreshold()">阈值</button>
      <button :class="{ active: view === 'vote' }" @click="view = 'vote'; loadVoteStores()">投票</button>
      <button :class="{ active: view === 'records' }" @click="view = 'records'; loadRecords(); loadYears()">记录</button>
      <button :class="{ active: view === 'analysis' }" @click="view = 'analysis'; loadProjects(); loadAnalysis()">分析</button>
      <button :class="{ active: view === 'sim' }" @click="view = 'sim'; loadSimRules(); loadSimQuery()">演算</button>
      <button :class="{ active: view === 'profit' }" @click="view = 'profit'; loadCollections(); loadProfit()">盈亏</button>
      <button :class="{ active: view === 'groupset' }" @click="view = 'groupset'; loadProjects(); loadSimRules()">组别</button>
      <button :class="{ active: view === 'rules' }" @click="view = 'rules'; loadDevRules(); loadMapping()">规则</button>
    </div>

    <!-- 数据记录视图 -->
    <div v-if="view === 'records'" class="records-view">
      <div class="rec-header">
        <span class="rec-title">📋 记录</span>
        <div class="rec-header-actions">
          <button class="rec-btn-analysis" @click="openAnalysis()">📊 分析</button>
          <button class="rec-btn-analysis" @click="openMissingNumbers()">🔢 最长号码</button>
          <button class="rec-btn-analysis" @click="openTracking()">🎯 最长跟踪</button>
          <select v-model="recYear" @change="loadRecords()" class="form-input" style="width:auto;padding:6px 10px;font-size:12px">
            <option value="">全部年份</option>
            <option v-for="y in recYears" :key="y" :value="y">{{ y }}</option>
          </select>
          <button class="btn-add" @click="openAdd">+ 新增</button>
        </div>
      </div>

      <!-- 可拖动悬浮新增按钮（记录页） -->
      <button
        class="fab-drag"
        :style="{ left: fabPos.x + 'px', top: fabPos.y + 'px' }"
        @pointerdown="onFabDown"
        @pointermove="onFabMove"
        @pointerup="onFabUp"
        @pointercancel="onFabUp"
        @click.stop="onFabTap"
        title="拖动移动 · 点击新增记录"
      >＋</button>

      <div class="sync-warning-bar">
        <span class="sync-warning-label">🔮 同步至号码系统</span>
        <input type="date" v-model="warnFromDate" class="form-input sync-date-input">
        <span class="sync-warning-sep">至</span>
        <input type="date" v-model="warnToDate" class="form-input sync-date-input">
        <button class="btn-add sync-warning-btn" @click="syncToNumberSystem" :disabled="warningSyncing">
          {{ warningSyncing ? '⏳ 同步中...' : '同步' }}
        </button>
      </div>
      <div v-if="records.length === 0" class="rec-empty">暂无记录，点击新增添加</div>
      <div class="rec-list">
        <div v-for="r in records" :key="r.id" class="rec-row">
          <div class="rec-info">
            <span class="rec-date">{{ r.date }}</span>
            <span class="rec-seq">#{{ r.day_seq }}</span>
            <span class="rec-draw">抽签 <b>{{ r.draw_number }}</b></span>
          </div>
          <div class="rec-actions">
            <button class="rec-btn edit" @click="openEdit(r)">✏️</button>
            <button class="rec-btn del" @click="doDelete(r.id)">🗑</button>
          </div>
        </div>
      </div>
      <!-- 分页 -->
      <div class="rec-pager" v-if="recTotalPages > 1">
        <button :disabled="recPage <= 1" @click="goPage(recPage-1)">上一页</button>
        <span>{{ recPage }} / {{ recTotalPages }} (共{{ recTotal }}条)</span>
        <button :disabled="recPage >= recTotalPages" @click="goPage(recPage+1)">下一页</button>
      </div>

      <!-- 新增/编辑弹窗 -->
      <div v-if="showForm" class="form-overlay" @click.self="showForm=false">
        <div class="form-card" style="max-width:340px">
          <div class="form-title">{{ editingId ? '编辑记录' : '新增记录' }}</div>
          <div class="form-fields">
            <label>日期</label>
            <div class="date-picker-field" @click="openDatePicker(form.date, v => form.date = v, $event)">
              <input v-model="form.date" readonly class="form-input" style="cursor:pointer">
            </div>
            <label style="margin-top:8px">抽签数字 (1-49)</label>
            <input v-model.number="form.draw_number" type="number" min="1" max="49" class="form-input">
            <div class="form-hint">第 {{ computedDaySeq }} 天</div>
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showForm=false">取消</button>
            <button class="btn-submit" @click="doSave">保存</button>
          </div>
        </div>
      </div>

      <!-- 尾数分析弹窗 -->
      <div v-if="showAnalysis" class="form-overlay" @click.self="showAnalysis=false">
        <div class="form-card" style="max-width:720px;max-height:85vh;overflow-y:auto">
          <div class="form-title">📊 尾数走势分析</div>
          <div v-if="analysisLoading" style="text-align:center;padding:20px">⏳ 分析中...</div>
          <div v-else-if="analysisData.error" style="color:#dc2626;padding:16px">{{ analysisData.error }}</div>
          <div v-else>
            <!-- 统计摘要 -->
            <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
              <div style="flex:1;min-width:140px;background:#f0fdf4;border-radius:10px;padding:10px;text-align:center">
                <div style="font-size:11px;color:#16a34a">0-4 尾数</div>
                <div style="font-size:20px;font-weight:700;color:#16a34a">{{ analysisData.stats.counts.total_04 }}次</div>
                <div style="font-size:10px;color:#64748b">连续 {{ analysisData.stats.current.streak_04 }} 天</div>
              </div>
              <div style="flex:1;min-width:140px;background:#fef2f2;border-radius:10px;padding:10px;text-align:center">
                <div style="font-size:11px;color:#dc2626">5-9 尾数</div>
                <div style="font-size:20px;font-weight:700;color:#dc2626">{{ analysisData.stats.counts.total_59 }}次</div>
                <div style="font-size:10px;color:#64748b">连续 {{ analysisData.stats.current.streak_59 }} 天</div>
              </div>
              <div style="flex:1;min-width:200px;background:linear-gradient(135deg,#eff6ff,#dbeafe);border-radius:10px;padding:10px;text-align:center">
                <div style="font-size:11px;color:#2563eb">📡 下期预测</div>
                <div style="font-size:18px;font-weight:700;color:#1e40af">{{ analysisData.prediction.range }}</div>
                <div style="font-size:10px;color:#3b82f6;margin-top:2px">{{ analysisData.prediction.hint }}</div>
                <div v-if="analysisData.prediction.empirical" style="font-size:10px;color:#1d4ed8;margin-top:4px;line-height:1.6">
                  📊 {{ analysisData.prediction.empirical.group }}尾连续{{ analysisData.prediction.empirical.current_streak }}天
                  · 延续 {{ analysisData.prediction.empirical.p_continue }}% / 反转 {{ analysisData.prediction.empirical.p_reverse }}%
                  <br><span style="color:#3b82f6">连续长度超 {{ analysisData.prediction.empirical.percentile }}% 历史（样本 {{ analysisData.prediction.empirical.samples }} 次）</span>
                </div>
                <div v-if="analysisNextDate" style="font-size:10px;color:#1d4ed8;margin-top:4px;font-weight:600">📅 {{ analysisNextDate }}</div>
              </div>
            </div>
            <!-- 连击记录卡片（按长度分组 Top10） -->
            <div v-if="analysisStreaks" class="tail-cards" style="margin-top:8px">
              <div class="tail-card tail-04">
                <div class="tail-card-hd">
                  <span class="tail-card-badge bg-green">0-4</span>
                  <span v-if="analysisStreaks.current && analysisStreaks.current['0-4'].streak>0" class="tail-card-streak">当前连续 <b>{{ analysisStreaks.current['0-4'].streak }}</b> 天</span>
                </div>
                <div class="tail-card-list">
                  <div v-for="(g,i) in (analysisStreaks.by_len_04||[])" :key="'a04-'+i" class="tail-streak-row">
                    <span class="tail-streak-num">{{ i+1 }}</span>
                    <span class="tail-streak-len">{{ g.len }}天</span>
                    <span class="tail-streak-count" @click.stop="showAnalysisPeriods('04',g)">{{ g.count }}次</span>
                  </div>
                </div>
              </div>
              <div class="tail-card tail-59">
                <div class="tail-card-hd">
                  <span class="tail-card-badge bg-red">5-9</span>
                  <span v-if="analysisStreaks.current && analysisStreaks.current['5-9'].streak>0" class="tail-card-streak">当前连续 <b>{{ analysisStreaks.current['5-9'].streak }}</b> 天</span>
                </div>
                <div class="tail-card-list">
                  <div v-for="(g,i) in (analysisStreaks.by_len_59||[])" :key="'a59-'+i" class="tail-streak-row">
                    <span class="tail-streak-num">{{ i+1 }}</span>
                    <span class="tail-streak-len">{{ g.len }}天</span>
                    <span class="tail-streak-count" @click.stop="showAnalysisPeriods('59',g)">{{ g.count }}次</span>
                  </div>
                </div>
              </div>
            </div>
            <!-- 策略回测 -->
            <div v-if="backtestData && backtestData.strategies" style="margin-top:12px;background:#0f172a;border:1px solid #334155;border-radius:10px;padding:12px">
              <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:2px">🧪 策略回测</div>
              <div style="font-size:10px;color:#64748b;margin-bottom:8px">截止 {{ backtestData.latest_date }} · 随机基线 50%</div>
              <div v-for="s in backtestData.strategies" :key="s.name" style="display:flex;align-items:center;gap:8px;padding:4px 0">
                <span style="width:150px;font-size:12px;color:#94a3b8;flex-shrink:0">{{ s.name }}</span>
                <div style="flex:1;height:6px;background:#1e293b;border-radius:3px;overflow:hidden">
                  <div :style="{width: s.rate+'%', background: s.rate>50?'#16a34a':'#475569', height:'100%'}"></div>
                </div>
                <span style="width:100px;text-align:right;font-size:12px;font-weight:700;flex-shrink:0" :style="{color: s.rate>50?'#4ade80':'#94a3b8'}">{{ s.rate }}%</span>
              </div>
              <details style="margin-top:8px">
                <summary style="font-size:11px;color:#3b82f6;cursor:pointer">📉 连续N天后延续概率（点击展开）</summary>
                <div v-for="row in backtestData.k_table" :key="row.group+'-'+row.k" style="display:flex;gap:6px;font-size:11px;color:#94a3b8;padding:2px 0">
                  <span style="width:40px">{{ row.group }}尾</span>
                  <span style="width:70px">连续{{ row.k }}天</span>
                  <span style="width:90px">延续 {{ row.p_continue }}%</span>
                  <span style="color:#64748b">{{ row.continue }}续/{{ row.reverse }}反</span>
                </div>
              </details>
              <div style="font-size:10px;color:#64748b;margin-top:6px">💡 命中率越接近 50% 越随机，>50% 才有预测价值</div>
            </div>
          </div>
          <!-- 时间段详情（弹窗内嵌弹窗） -->
          <div v-if="analysisPeriods" class="form-overlay" @click.self="analysisPeriods=null" style="position:fixed;top:0;left:0;z-index:2000">
            <div class="form-card" style="max-width:380px;margin:10vh auto">
              <div class="form-title">{{ analysisPeriods.label }} 连击 {{ analysisPeriods.len }}天 × {{ analysisPeriods.count }}次</div>
              <div style="max-height:50vh;overflow-y:auto">
                <div v-for="(p,i) in analysisPeriods.periods" :key="i"
                     style="display:flex;align-items:center;padding:10px 0;border-bottom:1px solid #1e293b;gap:10px">
                  <span style="background:#334155;color:#ffd700;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0">{{ i+1 }}</span>
                  <span style="flex:1;font-size:13px;color:#e2e8f0">
                    <span style="color:#64748b">{{ p.start }}</span>
                    <span style="margin:0 6px">→</span>
                    <span style="color:#64748b">{{ p.end }}</span>
                  </span>
                </div>
              </div>
              <div class="form-btns" style="margin-top:12px">
                <button class="btn-cancel" @click="analysisPeriods=null">关闭</button>
              </div>
            </div>
          </div>
          <div class="form-btns" style="margin-top:12px">
            <button class="btn-cancel" @click="showAnalysis=false">关闭</button>
          </div>
        </div>
      </div>

      <!-- 最长未出号码弹窗 -->
      <div v-if="showMissing" class="form-overlay" @click.self="showMissing=false">
        <div class="form-card" style="max-width:420px;max-height:90vh;overflow-y:auto">
          <div class="form-title">🔢 最长未出号码 TOP25</div>
          <div v-if="missingLoading" style="text-align:center;padding:20px">⏳ 分析中...</div>
          <div v-else-if="missingData.error" style="color:#dc2626;padding:16px">{{ missingData.error }}</div>
          <div v-else>
            <!-- 日期选择 -->
            <div style="display:flex;gap:6px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
              <span style="font-size:12px;color:#64748b">截止日期</span>
              <input type="date" v-model="missingDate" class="form-input" style="width:auto;padding:5px 8px;font-size:12px" @change="fetchMissing">
              <button class="btn-add" style="font-size:12px;padding:4px 10px" @click="fetchMissing">查询</button>
              <button class="btn-add" style="font-size:12px;padding:4px 10px" @click="missingDate='';fetchMissing()">最新</button>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <span style="font-size:12px;color:#64748b">截止 {{ missingData.latest_date }} · 共 {{ missingData.total_records }} 期</span>
              <button class="btn-add" style="font-size:12px;padding:4px 10px" @click="copyMissingNumbers">📋 复制25个号</button>
            </div>
            <!-- 表头 -->
            <div style="display:flex;align-items:center;padding:6px 0;border-bottom:2px solid #334155;font-size:11px;color:#94a3b8;font-weight:600">
              <span style="width:36px;text-align:center">#</span>
              <span style="width:42px;text-align:center">号码</span>
              <span style="flex:1;text-align:center">未出</span>
              <span style="flex:1;text-align:center">历史最长</span>
              <span style="width:80px;text-align:center">上次出现</span>
            </div>
            <div v-for="(n, i) in missingData.top25" :key="n.num"
                 style="display:flex;align-items:center;padding:8px 0;border-bottom:1px solid #1e293b;font-size:13px"
                 :style="i < 5 ? {background:'rgba(220,38,38,0.06)'} : {}">
              <span style="width:36px;text-align:center" :style="{color: i<3 ? '#f87171':'#64748b', fontWeight: i<3 ? '700':'400'}">{{ i+1 }}</span>
              <span style="width:42px;text-align:center;font-weight:700;font-size:15px"
                    :style="{color: n.current_gap >= 30 ? '#f87171' : n.current_gap >= 20 ? '#fbbf24' : '#e2e8f0'}">
                {{ n.num }}
              </span>
              <span style="flex:1;text-align:center" :style="{color: n.current_gap >= 30 ? '#f87171' : n.current_gap >= 20 ? '#fbbf24' : '#94a3b8'}">
                {{ n.current_gap }}期
              </span>
              <span style="flex:1;text-align:center;color:#64748b;font-size:11px">
                {{ n.max_gap_range || (n.max_gap + '期') }}
              </span>
              <span style="width:80px;text-align:center;font-size:11px;color:#64748b">{{ n.last_date }}</span>
            </div>
            <!-- 纯码展示（按号码排序） -->
            <div style="margin-top:12px;padding-top:10px;border-top:2px solid #334155">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <span style="font-size:12px;color:#64748b">🔢 纯码（按号码排序）</span>
                <button class="btn-add" style="font-size:12px;padding:4px 10px" @click="copyMissingSorted">📋 复制排序码</button>
              </div>
              <div style="font-size:14px;font-weight:600;color:#e2e8f0;word-break:break-all;line-height:1.9;font-family:ui-monospace,monospace">
                {{ missingSortedCode }}
              </div>
            </div>
          </div>
          <div class="form-btns" style="margin-top:12px">
            <button class="btn-cancel" @click="showMissing=false">关闭</button>
          </div>
        </div>
      </div>

    </div>

    <!-- 最长跟踪演算弹窗 -->
    <div v-if="showTracking" class="form-overlay" @click.self="showTracking=false">
      <div class="form-card" style="max-width:640px;max-height:92vh;overflow-y:auto">
        <div class="form-title">🎯 最长跟踪演算</div>

        <!-- 历史记录列表 -->
        <div v-if="trackingTab === 'list'">
          <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
            <button class="btn-add" style="font-size:13px" @click="trackingTab='new'">➕ 新建演算</button>
            <button class="btn-cancel" style="font-size:13px" @click="loadTrackingRuns()">🔄 刷新</button>
            <button class="btn-cancel" style="font-size:13px" @click="openAlgoDoc()">📚 算法文档</button>
            <button class="btn-cancel" style="font-size:13px" @click="openTrackingHold()">🎯 跟踪持有</button>
          </div>
          <div v-if="trackingRunsLoading" style="text-align:center;padding:20px">⏳ 加载中...</div>
          <div v-else-if="trackingRuns.length === 0" style="text-align:center;padding:24px;color:#64748b">
            暂无演算记录，点击「新建演算」开始
          </div>
          <div v-else>
            <div v-for="run in trackingRuns" :key="run.id"
                 class="tracking-run-card" @click="openTrackingRun(run.id)">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <div style="font-weight:700;color:#1a2a4a">
                    {{ run.name || ('演算 #' + run.id) }}
                    <span v-if="run.is_stale" class="tracking-stale-badge">🔄 有更新</span>
                  </div>
                  <div style="font-size:12px;color:#64748b;margin-top:3px">
                    N={{ run.min_n }}~{{ run.max_n }} · warmup={{ run.warmup }} · {{ run.total_records }}期
                    <span v-if="run.years > 0" style="margin-left:6px">· 近{{ run.years }}年</span>
                  </div>
                  <div style="font-size:12px;color:#64748b;margin-top:2px">
                    {{ run.date_from }} ~ {{ run.date_to }}
                  </div>
                </div>
                <div style="text-align:right">
                  <div style="font-size:12px;color:#64748b">{{ run.created_at }}</div>
                  <div style="margin-top:4px">
                    <span style="font-size:11px;color:#34d399">等额盈利 {{ run.eq_profitable }}</span>
                    <span style="font-size:11px;color:#fbbf24;margin-left:6px">倍投盈利 {{ run.bt_profitable }}</span>
                  </div>
                </div>
              </div>
              <div style="display:flex;gap:6px;margin-top:8px;align-items:center">
                <button class="btn-cancel" style="font-size:11px;padding:3px 8px"
                        @click.stop="recalcRun(run.id)"
                        :disabled="recalcRunId === run.id">
                  {{ recalcRunId === run.id ? '⏳ 演算中...' : '🔁 手动演算' }}
                </button>
                <span style="font-size:11px;color:#94a3b8">点击卡片查看详情</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 跟踪持有（锁定最冷号连续跟踪） -->
        <div v-else-if="trackingTab === 'hold'">
          <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap">
            <button class="btn-cancel" style="font-size:12px;padding:4px 10px" @click="trackingTab='list'">← 返回列表</button>
            <span style="font-size:13px;color:#1a2a4a;font-weight:700">🎯 跟踪持有（冷号回补）</span>
          </div>
          <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
            <div style="display:flex;gap:4px">
              <button class="btn-cancel" style="font-size:12px;padding:4px 10px"
                      :style="holdSignal==='gap' ? 'background:#2d6be0;color:#fff;border-color:#2d6be0' : ''"
                      @click="switchHoldSignal('gap')">遗漏期数</button>
              <button class="btn-cancel" style="font-size:12px;padding:4px 10px"
                      :style="holdSignal==='ratio' ? 'background:#2d6be0;color:#fff;border-color:#2d6be0' : ''"
                      @click="switchHoldSignal('ratio')">遗漏比</button>
              <button class="btn-cancel" style="font-size:12px;padding:4px 10px"
                      :style="holdSignal==='consensus' ? 'background:#2d6be0;color:#fff;border-color:#2d6be0' : ''"
                      @click="switchHoldSignal('consensus')">共识投票</button>
            </div>
            <div v-if="holdSignal !== 'consensus'" style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">{{ holdSignal === 'ratio' ? '进场阈值(遗漏比)' : '进场阈值(遗漏期数)' }}</span>
              <input type="number" v-model.number="holdTheta" class="form-input" style="width:64px;padding:5px 8px;font-size:13px"
                     :min="holdSignal==='ratio' ? 0.1 : 1" :step="holdSignal==='ratio' ? 0.1 : 1">
            </div>
            <div v-else style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">最少得票数</span>
              <input type="number" v-model.number="holdMinVotes" class="form-input" style="width:64px;padding:5px 8px;font-size:13px" min="2" max="7">
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">跟踪期数 K</span>
              <input type="number" v-model.number="holdK" class="form-input" style="width:64px;padding:5px 8px;font-size:13px" min="1">
            </div>
            <button class="btn-add" style="font-size:13px" @click="analyzeTrackingHold()" :disabled="holdLoading">
              {{ holdLoading ? '分析中...' : '🔍 分析' }}
            </button>
          </div>
          <div style="font-size:12px;color:#94a3b8;margin-bottom:12px;line-height:1.6">
            💡 锁定「最冷 1 号」（遗漏期数 ≥ 阈值即进场），连续跟踪 K 期直到命中即止盈，超 K 期止损。对比「每期重选」模式，本模型抓住「冷号回补」的正确语义。
          </div>
          <div v-if="holdLoading" style="text-align:center;padding:20px;color:#fbbf24">⏳ 分析中...</div>
          <div v-else-if="holdResult">
            <div style="display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap">
              <div class="tracking-stat" style="flex:1;min-width:110px">
                <div class="tracking-stat-value" :style="{color: holdResult.edge > 0 ? '#0f9f45' : '#ef4444'}">{{ holdResult.win_rate }}%</div>
                <div class="tracking-stat-label">命中率（基线 {{ holdResult.baseline }}%）</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:110px">
                <div class="tracking-stat-value" :style="{color: holdResult.edge > 0 ? '#0f9f45' : '#ef4444'}">{{ holdResult.edge > 0 ? '+' : '' }}{{ holdResult.edge }}%</div>
                <div class="tracking-stat-label">超随机基线</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:110px">
                <div class="tracking-stat-value" style="color:#1a2a4a">{{ holdResult.total_pnl }}</div>
                <div class="tracking-stat-label">总盈亏（{{ holdResult.rounds }} 轮）</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:110px">
                <div class="tracking-stat-value" style="color:#1a2a4a">{{ holdResult.avg_hit_delay }} 期</div>
                <div class="tracking-stat-label">平均命中期</div>
              </div>
            </div>
            <div v-if="holdResult.equity_curve && holdResult.equity_curve.length > 1" style="margin-bottom:12px">
              <div style="font-size:12px;color:#64748b;margin-bottom:6px">资金曲线（等额口径，最大回撤 {{ holdResult.max_drawdown }}）</div>
              <canvas ref="equityCanvas" style="width:100%;height:120px;border:1px solid #e0e0e0;border-radius:8px"></canvas>
            </div>
            <div style="font-size:12px;color:#64748b;margin-bottom:6px">真样本外验证（前段 vs 后段，无重叠）</div>
            <div style="display:flex;gap:10px;margin-bottom:12px">
              <div class="tracking-stat" style="flex:1">
                <div class="tracking-stat-value" :style="{color: holdResult.oos.front.total_pnl > 0 ? '#0f9f45' : '#ef4444'}">{{ holdResult.oos.front.win_rate }}%</div>
                <div class="tracking-stat-label">前段命中（盈亏 {{ holdResult.oos.front.total_pnl }}）</div>
              </div>
              <div class="tracking-stat" style="flex:1">
                <div class="tracking-stat-value" :style="{color: holdResult.oos.back.total_pnl > 0 ? '#0f9f45' : '#ef4444'}">{{ holdResult.oos.back.win_rate }}%</div>
                <div class="tracking-stat-label">后段命中（盈亏 {{ holdResult.oos.back.total_pnl }}）</div>
              </div>
            </div>
            <div style="font-size:11px;color:#94a3b8;line-height:1.6;margin-bottom:10px">
              ⚠️ 若前段/后段命中率都超基线 → 信号稳健；若仅后段超基线（前段反向）→ 信号可能受近期数据结构变化影响，需实盘小注验证。
            </div>
          </div>

          <!-- 实盘纸面跟踪 -->
          <div v-if="holdLive" style="margin-top:6px;border-top:1px dashed #e0e0e0;padding-top:12px">
            <div style="font-size:12px;color:#64748b;margin-bottom:8px">📊 实盘纸面跟踪（最新 {{ holdLive.latest_record_date }}）</div>
            <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" style="color:#1a2a4a">{{ holdLive.current.coldest_num }}</div>
                <div class="tracking-stat-label">当前最冷号</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" style="color:#1a2a4a">{{ holdLive.current.coldest_gap }} 期</div>
                <div class="tracking-stat-label">遗漏期数</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" :style="{color: holdLive.current.signal ? '#0f9f45' : '#64748b'}">{{ holdLive.current.signal ? '建议进场' : '等待信号' }}</div>
                <div class="tracking-stat-label">进场信号</div>
              </div>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-bottom:6px">最冷 5 号：<span v-for="t in holdLive.current.top_cold" :key="t.num" style="margin-right:8px">{{ t.num }}<span style="color:#64748b">({{ t.gap }}期)</span></span></div>
            <div style="font-size:11px;color:#64748b;line-height:1.8;max-height:96px;overflow-y:auto">
              最近轨迹：
              <span v-for="(t, i) in holdLive.trail" :key="i" style="margin-right:6px">
                {{ t.date.slice(5) }}·{{ t.num || '空' }}{{ t.event && t.event.type === 'hit' ? '✅' : (t.event && t.event.type === 'stop' ? '⛔' : '') }}
              </span>
            </div>
          </div>

          <!-- 实盘逐轮明细 -->
          <div v-if="holdRounds" style="margin-top:6px;border-top:1px dashed #e0e0e0;padding-top:12px">
            <div style="font-size:12px;color:#64748b;margin-bottom:8px">📋 实盘逐轮明细（共 {{ holdRounds.summary.total }} 轮）</div>
            <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" style="color:#1a2a4a">{{ holdRounds.summary.hit_rate }}%</div>
                <div class="tracking-stat-label">总命中率（{{ holdRounds.summary.hits }}/{{ holdRounds.summary.total }}）</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" :style="{color: holdRounds.summary.total_pnl >= 0 ? '#0f9f45' : '#ef4444'}">{{ holdRounds.summary.total_pnl }}</div>
                <div class="tracking-stat-label">总盈亏</div>
              </div>
              <div class="tracking-stat" style="flex:1;min-width:90px">
                <div class="tracking-stat-value" :style="{color: holdRounds.recent.total_pnl >= 0 ? '#0f9f45' : '#ef4444'}">{{ holdRounds.recent.hit_rate }}% / {{ holdRounds.recent.total_pnl }}</div>
                <div class="tracking-stat-label">近30轮（命中率/盈亏）</div>
              </div>
            </div>
            <div v-if="holdRounds.health" style="font-size:11px;color:#64748b;margin-bottom:8px;padding:6px 8px;background:#f8fafc;border-radius:6px">
              信号健康度：近20轮命中率 <span style="font-weight:700">{{ holdRounds.health.recent20_rate }}%</span> vs 全量 {{ holdRounds.health.full_rate }}%
              <span :style="{color: holdRounds.health.ratio >= 1 ? '#0f9f45' : '#ef4444', fontWeight:700}">
                {{ holdRounds.health.ratio >= 1 ? '· 信号偏强' : '· 信号偏弱/衰减' }}
              </span>
            </div>
            <div v-if="holdRounds.rolling && holdRounds.rolling.length" style="font-size:11px;color:#94a3b8;margin-bottom:8px">
              <div style="color:#64748b;margin-bottom:4px">滚动验证（每200期一段命中率，绿赚红亏）：</div>
              <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:4px">
                <div v-for="(s, i) in holdRounds.rolling" :key="i" style="padding:4px 6px;border-radius:6px;text-align:center"
                     :style="{background: s.pnl >= 0 ? 'rgba(15,159,69,0.08)' : 'rgba(239,68,68,0.08)'}">
                  <div :style="{color: s.pnl >= 0 ? '#0f9f45' : '#ef4444', fontWeight:700}">{{ s.start.slice(0,4) }}</div>
                  <div style="color:#64748b">{{ s.hit_rate }}%</div>
                </div>
              </div>
            </div>
            <div style="font-size:11px;color:#94a3b8;line-height:1.8;max-height:150px;overflow-y:auto">
              <div v-for="(r, i) in holdRounds.rounds.slice(-12).reverse()" :key="i" style="display:flex;align-items:center;padding:3px 0;border-bottom:1px dashed #f0f0f0;gap:8px">
                <span style="color:#64748b;flex:0 0 auto;white-space:nowrap">{{ r.enter_date.slice(5) }} 进{{ pad2(r.num) }}</span>
                <span style="color:#94a3b8;flex:1 1 auto;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">遗{{ r.enter_gap }}·跟{{ r.held }}期</span>
                <span :style="{color: r.result==='hit' ? '#0f9f45' : '#ef4444', flex:'0 0 auto', whiteSpace:'nowrap'}">{{ r.result==='hit' ? '✅' : '⛔' }}{{ r.pnl > 0 ? '+' : '' }}{{ r.pnl }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 新建演算 -->
        <div v-else-if="trackingTab === 'new'">
          <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center">
            <span style="font-size:12px;color:#64748b">名称</span>
            <input v-model="trackingName" class="form-input" style="flex:1;padding:6px 10px;font-size:13px" placeholder="如：冷号回补回测 2026-09">
          </div>
          <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">最小号数</span>
              <input type="number" v-model.number="trackingMinN" class="form-input" style="width:64px;padding:5px 8px;font-size:13px" min="1" max="49">
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">最大号数</span>
              <input type="number" v-model.number="trackingMaxN" class="form-input" style="width:64px;padding:5px 8px;font-size:13px" min="1" max="49">
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">预热期数</span>
              <input type="number" v-model.number="trackingWarmup" class="form-input" style="width:72px;padding:5px 8px;font-size:13px" min="10">
            </div>
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:12px;color:#64748b">日期范围(年)</span>
              <input type="number" v-model.number="trackingYears" class="form-input" style="width:64px;padding:5px 8px;font-size:13px" min="0" max="20">
              <span style="font-size:11px;color:#94a3b8">0=全部</span>
            </div>
          </div>
          <div style="font-size:12px;color:#94a3b8;margin-bottom:12px;line-height:1.6">
            💡 从最长未出号码（冷号）中，按 {{ algoDoc.algo_count || 67 }} 种算法各拆分 {{ trackingMinN }}~{{ trackingMaxN }} 个号，回测历史命中与盈利。
            命中率基线 = N/49（随机选号），盈利需命中率超过 N/47（等额口径盈亏平衡点）。
          </div>
          <div v-if="trackingRunning" style="text-align:center;padding:20px;color:#fbbf24">
            ⏳ 演算中（约 50 秒）... 请稍候
          </div>
          <div class="form-btns" style="margin-top:8px">
            <button class="btn-cancel" @click="trackingTab='list'">返回</button>
            <button class="btn-add" @click="runTracking()" :disabled="trackingRunning">
              {{ trackingRunning ? '演算中...' : '🚀 开始演算' }}
            </button>
          </div>
        </div>

        <!-- 演算详情 -->
        <div v-else-if="trackingTab === 'detail'">
          <div style="display:flex;gap:8px;margin-bottom:10px;align-items:center;flex-wrap:wrap">
            <button class="btn-cancel" style="font-size:12px;padding:4px 10px" @click="trackingTab='list';loadTrackingRuns()">← 返回列表</button>
            <span style="font-size:13px;color:#1a2a4a;font-weight:700">{{ trackingDetail.name || ('演算 #' + trackingDetail.id) }}</span>
            <span style="font-size:11px;color:#64748b">N={{ trackingDetail.min_n }}~{{ trackingDetail.max_n }}</span>
          </div>

          <!-- 有更新提示 -->
          <div v-if="trackingDetail.is_stale" style="display:flex;align-items:center;gap:8px;margin-bottom:10px;padding:8px 10px;background:#fef3c7;border-radius:8px">
            <span style="font-size:12px;color:#92400e">🔄 数据有更新，结果可能过期</span>
            <label style="font-size:12px;color:#92400e;display:flex;align-items:center;gap:4px;cursor:pointer">
              <input type="checkbox" v-model="trackingAutoRecalc" style="margin:0"> 切换口径自动重算
            </label>
            <button class="btn-add" style="font-size:12px;padding:3px 10px" @click="recalcRun(trackingDetail.id)" :disabled="recalcRunId === trackingDetail.id">
              {{ recalcRunId === trackingDetail.id ? '⏳ 演算中...' : '🔁 重新演算' }}
            </button>
          </div>

          <!-- 口径切换 -->
          <div style="display:flex;gap:6px;margin-bottom:10px">
            <button :class="['tracking-tab', {active: trackingSortBy==='eq_pnl'}]" @click="switchTrackingSort('eq_pnl')">💰 等额口径</button>
            <button :class="['tracking-tab', {active: trackingSortBy==='bt_pnl'}]" @click="switchTrackingSort('bt_pnl')">📈 倍投口径</button>
          </div>

          <!-- 摘要 -->
          <div style="display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap" v-if="trackingDetail.results">
            <div class="tracking-stat">
              <div class="tracking-stat-value" style="color:#1a2a4a">{{ trackingDetail.results.length }}</div>
              <div class="tracking-stat-label">方案总数</div>
            </div>
            <div class="tracking-stat">
              <div class="tracking-stat-value" :style="{color: eqProfitCount > 0 ? '#34d399' : '#f87171'}">{{ eqProfitCount }}</div>
              <div class="tracking-stat-label">等额盈利方案</div>
            </div>
            <div class="tracking-stat">
              <div class="tracking-stat-value" :style="{color: btProfitCount > 0 ? '#34d399' : '#f87171'}">{{ btProfitCount }}</div>
              <div class="tracking-stat-label">倍投盈利方案</div>
            </div>
            <div class="tracking-stat">
              <div class="tracking-stat-value" style="color:#d97706">{{ bestEqPnl }}</div>
              <div class="tracking-stat-label">最佳等额盈利</div>
            </div>
          </div>

          <!-- 结果表 -->
          <div v-if="trackingDetail.results && trackingDetail.results.length" style="margin-bottom:12px">
            <div style="font-size:12px;color:#94a3b8;margin-bottom:6px">
              {{ trackingSortBy === 'eq_pnl' ? '💰 等额口径' : '📈 倍投口径' }} 盈利排名 TOP 30
              <span style="color:#64748b">（命中率基线 = 随机选 N/49）</span>
            </div>
            <div class="tracking-table-wrap">
              <table class="tracking-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>算法</th>
                    <th>N</th>
                    <th>命中率</th>
                    <th>基线</th>
                    <th>累计盈利</th>
                    <th>单期均值</th>
                    <th>最大回撤</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in trackingDetail.results.slice(0, 30)" :key="r.id"
                      :class="{ 'tracking-row-win': (trackingSortBy==='eq_pnl' ? r.eq_pnl : r.bt_pnl) > 0 }">
                    <td>{{ i + 1 }}</td>
                    <td class="tracking-algo-name">{{ r.algo_name }}</td>
                    <td>{{ r.n }}</td>
                    <td>{{ r.hit_rate.toFixed(1) }}%</td>
                    <td style="color:#64748b">{{ (trackingDetail.baseline && trackingDetail.baseline[r.n]) || '—' }}%</td>
                    <td :style="{color: (trackingSortBy==='eq_pnl' ? r.eq_pnl : r.bt_pnl) > 0 ? '#34d399' : '#f87171', fontWeight:700}">
                      {{ (trackingSortBy==='eq_pnl' ? r.eq_pnl : r.bt_pnl).toLocaleString() }}
                    </td>
                    <td>{{ (trackingSortBy==='eq_pnl' ? r.eq_avg : (r.bt_pnl / (r.total || 1))).toFixed(2) }}</td>
                    <td style="color:#f87171">{{ r.max_drawdown.toLocaleString() }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="trackingDetail.results && trackingDetail.results.length" style="font-size:11px;color:#64748b;line-height:1.7;margin-bottom:10px">
            ⚠️ <b>诚实提示</b>：命中率接近随机基线说明冷号回补信号弱；47 赔率 < 49 号码，等额口径长期负期望。
            倍投口径盈利数字大是因投入额随遗漏指数增长（杠杆放大），不可与等额口径直接比较。
          </div>

          <div class="form-btns">
            <button class="btn-cancel" @click="deleteTrackingRun(trackingDetail.id)">🗑 删除本次演算</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 算法文档弹窗 -->
    <div v-if="showAlgoDoc" class="form-overlay" @click.self="showAlgoDoc=false">
      <div class="form-card" style="max-width:640px;max-height:92vh;overflow-y:auto">
        <div class="form-title">📚 算法文档（共 {{ algoDoc.algo_count }} 种）</div>
        <div v-for="cat in algoDoc.categories" :key="cat.category" style="margin-bottom:14px">
          <div style="font-weight:700;color:#1a2a4a;font-size:13px;margin-bottom:4px">{{ cat.category }}</div>
          <div style="font-size:11px;color:#94a3b8;margin-bottom:6px">{{ cat.note }}</div>
          <table class="tracking-table" style="min-width:0">
            <thead>
              <tr><th style="width:40px">ID</th><th>算法</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in cat.algorithms" :key="a.id">
                <td style="color:#64748b">{{ a.id }}</td>
                <td class="tracking-algo-name">{{ a.name }}</td>
                <td style="color:#64748b;font-size:11px">{{ a.desc }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="font-size:11px;color:#64748b;line-height:1.7;margin-top:4px">
          ⚠️ 命中率基线 = N/49（随机选号）；等额口径盈亏平衡点 = N/47；47 赔率 &lt; 49 号码，等额口径长期负期望。
          倍投口径盈利是杠杆放大，不可与等额口径直接比较。
        </div>
        <div class="form-btns" style="margin-top:10px">
          <button class="btn-cancel" @click="showAlgoDoc=false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 组别设置视图 -->
    <div v-if="view === 'groupset'" class="groupset-view">
      <div class="gs-header">
        <span class="gs-title">⚙️ 组别</span>
        <button class="btn-add" @click="openAddProject">+ 项目</button>
      </div>
      <!-- 集合筛选 → 汇总筛选 → 记录筛选 -->
      <div style="padding:0 12px 8px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">
        <select v-model="gsColFilter" @change="onGsColChange" class="form-input" style="width:auto;padding:5px 8px;font-size:12px">
          <option value="">📁 全部集合</option>
          <option v-for="c in collections" :key="'gsf'+c.id" :value="c.id">📁 {{ c.name }}</option>
        </select>
        <select v-if="gsColFilter" v-model="gsSumFilter" @change="onGsSumChange" class="form-input" style="width:auto;padding:5px 8px;font-size:12px">
          <option value="">📊 全部汇总</option>
          <option v-for="s in gsScopeSummaries" :key="'gss'+s.id" :value="s.id">📊 {{ s.name }}</option>
        </select>
        <select v-if="gsSumFilter" v-model="gsRgFilter" @change="onGsRgChange" class="form-input" style="width:auto;padding:5px 8px;font-size:12px">
          <option value="">📋 全部记录</option>
          <option v-for="r in gsScopeRunGroups" :key="'gsr'+r.id" :value="r.id">📋 {{ r.name }}</option>
        </select>
      </div>
      <!-- 项目切换 -->
      <div class="gs-projects">
        <span v-for="p in projects" :key="p.id"
              :class="['gs-pill',{active:selPid===p.id}]"
              @click="selectProject(p.id)">
          {{ p.name }}
        </span>
      </div>

      <div v-if="!selPid" class="gs-empty">请选择一个项目</div>

      <div v-if="selPid" class="gs-groups">
        <div class="gs-group-header">
          <span>📋 默认通用组别 ({{ gsGroups.length }})</span>
          <button class="btn-add-sm" @click="openAddGroup">+ 组</button>
        </div>
        <div v-for="g in gsGroups" :key="g.id" class="gs-group-row" @click="editGroup(g)">
          <span class="gs-gname">{{ g.group_name }}组</span>
          <span class="gs-gnums">{{ g.numbers.join(', ') }}</span>
          <button class="gs-del" @click.stop="delGroup(g.id)">🗑</button>
        </div>
        <!-- 分时段组别 -->
        <div class="gs-group-header" style="margin-top:16px;border-top:1px solid #e8ecf1;padding-top:14px">
          <span>📅 分时段组别 ({{ periodGroups.length }})</span>
          <button class="btn-add-sm" @click="openAddPeriod">+</button>
        </div>
        <div class="gs-hint" style="font-size:11px;color:#8899b0;padding:4px 0 8px">优先取分时段组别，未配置时段则用默认通用</div>
        <div v-for="pg in periodGroups" :key="pg.id" class="gs-group-row" @click="editPeriod(pg)">
          <span class="gs-gname">{{ pg.start_date }} ~ {{ pg.end_date }}</span>
          <button class="gs-del" @click.stop="delPeriod(pg.id)">🗑</button>
        </div>
        <!-- 规则管理 -->
        <div class="gs-group-header" style="margin-top:14px">
          <span>左移规则 ({{ rulesByProject[selPid]?.length || 0 }})</span>
          <button class="btn-add-sm" @click="openAddSimRule">+</button>
        </div>
        <div v-for="r in (rulesByProject[selPid] || [])" :key="r.id" class="gs-group-row">
          <span class="gs-gname">{{ r.shift_amount }}位</span>
          <span class="gs-gnums">{{ r.name }}</span>
          <button class="gs-del" @click.stop="delSimRule(r.id)">🗑</button>
        </div>
        <!-- 删除项目 -->
        <div class="gs-actions">
          <button class="btn-del-proj" @click="editProjectName">✏️ 项目名</button>
          <button class="btn-del-proj danger" @click="delProject">🗑 删除项目</button>
        </div>
      </div>

      <!-- 弹窗：新增/编辑项目 -->
      <div v-if="showProjForm" class="form-overlay" @click.self="showProjForm=false">
        <div class="form-card">
          <div class="form-title">{{ editingProjId ? '编辑项目' : '新增项目' }}</div>
          <label>项目名称</label>
          <input v-model="projForm.name" class="form-input" placeholder="如：主项目4" />
          <div class="form-btns">
            <button class="btn-cancel" @click="showProjForm=false">取消</button>
            <button class="btn-submit" @click="saveProject">保存</button>
          </div>
        </div>
      </div>

      <!-- 弹窗：新增/编辑组 -->
      <div v-if="showGroupForm" class="form-overlay" @click.self="showGroupForm=false">
        <div class="form-card">
          <div class="form-title">{{ editingGid ? '编辑组别' : '新增组别' }}</div>
          <label>组名 (A-L)</label>
          <input v-model="groupForm.group_name" class="form-input" placeholder="A" maxlength="1" />
          <label>数字列表 (逗号分隔)</label>
          <input v-model="groupForm.numbersStr" class="form-input" placeholder="3,12,25,38" />
          <div class="form-btns">
            <button class="btn-cancel" @click="showGroupForm=false">取消</button>
            <button class="btn-submit" @click="saveGroup">保存</button>
          </div>
        </div>
      </div>

      <!-- 弹窗：新增/编辑分时段 -->
      <div v-if="showPeriodForm" class="form-overlay" @click.self="showPeriodForm=false">
        <div class="form-card" style="max-width:400px">
          <div class="form-title">{{ editingPeriodId ? '编辑分时段' : '新增分时段' }}</div>
          <label>起始日期</label>
          <div class="date-picker-field" @click="openDatePicker(periodForm.start_date, v => periodForm.start_date = v, $event)">
            {{ periodForm.start_date || '点击选择日期' }}
            <span class="date-arrow">📅</span>
          </div>
          <label>结束日期</label>
          <div class="date-picker-field" @click="openDatePicker(periodForm.end_date, v => periodForm.end_date = v, $event)">
            {{ periodForm.end_date || '点击选择日期' }}
            <span class="date-arrow">📅</span>
          </div>
          <div class="gs-group-header" style="margin-top:8px">
            <span>A-L 组数字</span>
          </div>
          <div v-for="g in gsGroups" :key="g.id" class="gs-group-row" style="cursor:default">
            <span class="gs-gname">{{ g.group_name }}组</span>
            <input v-model="periodNums[g.group_name]" class="form-input" style="flex:1;font-size:12px;padding:6px" :placeholder="g.numbers.join(',')" />
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showPeriodForm=false">取消</button>
            <button class="btn-submit" @click="savePeriod">保存</button>
          </div>
        </div>
      </div>

      <!-- 弹窗：新增左移规则 -->
      <div v-if="showSimRuleForm" class="form-overlay" @click.self="showSimRuleForm=false">
        <div class="form-card">
          <div class="form-title">新增左移规则</div>
          <label>左移位数</label>
          <select v-model.number="simRuleForm.shift" class="form-input">
            <option v-for="n in 12" :key="n" :value="n">左{{ n }}</option>
          </select>
          <div class="form-btns">
            <button class="btn-cancel" @click="showSimRuleForm=false">取消</button>
            <button class="btn-submit" @click="saveSimRule">保存</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 开发规则视图 -->
    <div v-if="view === 'rules'" class="rules-view">
      <div class="gs-header">
        <span class="gs-title">🔧 规则</span>
        <button class="btn-add" @click="openAddRule">+ 规则</button>
      </div>
      <div v-if="devRules.length === 0" class="gs-empty">暂无规则</div>
      <div v-for="r in devRules" :key="r.id" class="rule-card"
           :class="{ locked: r.is_locked, active: r.is_active }">
        <div class="rule-info">
          <div class="rule-top">
            <span class="rule-name">{{ r.name }}</span>
            <span class="rule-type">{{ r.rule_type === 'rotation' ? '🔄轮换' : '📊映射' }}</span>
          </div>
          <div class="rule-tags">
            <span v-if="r.is_locked" class="tag locked">🔒 锁定</span>
            <span v-if="r.is_active" class="tag active">✅ 启用</span>
            <span v-if="!r.is_active" class="tag inactive">⏸ 停用</span>
          </div>
        </div>
        <div class="rule-actions">
          <button class="r-btn" @click="toggleLock(r)">{{ r.is_locked ? '🔓' : '🔒' }}</button>
          <button class="r-btn" @click="toggleActive(r)">{{ r.is_active ? '⏸' : '✅' }}</button>
          <button class="r-btn" @click="openEditRule(r)" :disabled="r.is_locked">✏️</button>
          <button class="r-btn del" @click="delRule(r.id)" :disabled="r.is_locked">🗑</button>
        </div>
      </div>

      <div v-if="showRuleForm" class="form-overlay" @click.self="showRuleForm=false">
        <div class="form-card">
          <div class="form-title">{{ editingRuleId ? '编辑规则' : '新增规则' }}</div>
          <label>规则名称</label>
          <input v-model="ruleForm.name" class="form-input" placeholder="如：我的轮换规则" />
          <label>类型</label>
          <select v-model="ruleForm.rule_type" class="form-input">
            <option value="rotation">🔄 轮换规则</option>
            <option value="mapping">📊 映射规则</option>
          </select>
          <label>配置 (JSON)</label>
          <textarea v-model="ruleForm.config_json" class="form-input rule-ta" rows="4" placeholder='{"desc":"说明","config":{}}'></textarea>
          <div class="form-btns">
            <button class="btn-cancel" @click="showRuleForm=false">取消</button>
            <button class="btn-submit" @click="saveRule">保存</button>
          </div>
        </div>
      </div>

      <!-- 次数映射折叠区 -->
      <div class="mapping-section">
        <div class="mapping-header" @click="showMapping=!showMapping">
          <span>📊 次数→值映射</span>
          <span class="mapping-arrow">{{ showMapping ? '▼' : '▶' }}</span>
        </div>
        <div v-if="showMapping" class="mapping-body">
          <div class="mapping-grid">
            <div v-for="m in mappingList" :key="m.count_n" class="mapping-item" @click="editMapping(m)">
              <span class="m-count">{{ m.count_n }}</span>
              <span class="m-arrow">→</span>
              <span class="m-value">{{ m.value }}</span>
            </div>
          </div>
          <div class="mapping-add-row">
            <input v-model.number="mapCountN" type="number" placeholder="次数" class="form-input" style="width:70px" />
            <input v-model.number="mapValue" type="number" placeholder="值" class="form-input" style="width:80px" />
            <button class="btn-add-sm" @click="saveMapping">保存</button>
            <button v-if="editingMapN" class="btn-add-sm" style="background:#ee0a24;color:#fff" @click="delMapping">删除</button>
          </div>
        </div>
      </div>

      <!-- 清理控制 -->
      <div class="mapping-section" style="margin-top:12px">
        <div class="mapping-header" @click="showClearControl=!showClearControl">
          <span>🧹 清理控制</span>
          <span class="mapping-arrow">{{ showClearControl ? '▼' : '▶' }}</span>
        </div>
        <div v-if="showClearControl" class="mapping-body">
          <div style="display:flex;align-items:center;gap:10px;padding:8px 0;flex-wrap:wrap">
            <span style="font-size:13px;color:#8899b0">分析/演算清空 + 集合删除：</span>
            <button class="btn-add-sm"
              :style="{background:allowClear?'#22c55e':'#ccc',color:'#fff'}"
              @click="allowClear=!allowClear">
              {{ allowClear ? '✅ 已开启' : '⛔ 已关闭' }}
            </button>
            <span style="font-size:11px;color:#8899b0">{{ allowClear ? '清空/删除按钮可用' : '清空/删除按钮已锁定（防误触）' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 导出视图 -->
    <div v-if="view === 'export'" class="export-view">
      <iframe :src="exportSrc" class="export-iframe" @load="onExportLoad"></iframe>
    </div>

    <!-- 阈值视图 -->
    <div v-if="view === 'threshold'" class="threshold-view">
      <div class="sim-header">
        <span class="sim-title">🎯 复制25/24</span>
        <div style="display:flex;align-items:center;gap:6px">
          <a href="api-doc.html" target="_blank" class="th-doc-link" title="API 文档">📋</a>
          <button class="btn-add" @click="computeThreshold" :disabled="thComputing">
            <span v-if="thComputing" class="btn-spin"></span>
            {{ thComputing ? '计算中' : '计算' }}
          </button>
        </div>
      </div>
      <!-- 日期选择 -->
      <div class="th-date-row">
        <label style="display:flex;align-items:center;gap:4px;font-size:11px;color:#8899b0;cursor:pointer;white-space:nowrap">
          <input type="checkbox" v-model="thRange" style="width:14px;height:14px" />
          时间段
        </label>
        <template v-if="!thRange">
          <input type="date" v-model="thDate" @change="loadThreshold" class="th-date-input" />
        </template>
        <template v-else>
          <input type="date" v-model="thFromDate" class="th-date-input" style="flex:1;min-width:0" />
          <span style="color:#8899b0;font-size:12px">→</span>
          <input type="date" v-model="thToDate" class="th-date-input" style="flex:1;min-width:0" />
        </template>
        <span v-if="thCol19?.length && !thRange" class="th-draw">🎲 {{ thCol19[0].draw_number || '—' }}</span>
      </div>
      <div v-if="thMsg" class="th-msg" :class="thMsgType">{{ thMsg }}</div>
      <!-- col19 汇总明细 -->
      <div v-if="thCol19?.length" class="th-col19-block">
        <div class="th-col19-title">📊 集合19 汇总</div>
        <div class="th-col19-grid">
          <div v-for="s in thCol19" :key="s.name" class="th-col19-item">
            <span class="th-col19-name">{{ s.name }}</span>
            <span class="th-col19-val">{{ fmtW(s.total_value) }}</span>
          </div>
        </div>
      </div>
      <!-- 阈值结果 -->
      <div v-if="thItems.length === 0 && !thComputing" class="gs-empty">暂无数据，点击「计算」</div>
      <template v-for="grp in thGrouped" :key="grp.key">
        <div class="th-block" :class="grp.collection_id < 0 ? 'th-summary' : 'th-collection'">
          <div class="th-block-title">{{ grp.label }}<span v-if="grp.col19_val != null" class="th-summary-val"> {{ fmtW(grp.col19_val) }}</span></div>
          <div v-for="th in [25,24]" :key="th" style="margin-bottom:6px">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
              <div class="th-label" style="margin-bottom:0">复制{{ th }}：</div>
              <button class="th-copy-btn" @click="copyThNumbers(grp, th)" title="复制号码列表">📋</button>
            </div>
            <div class="th-nums">
              <span v-for="n in 49" :key="n" class="th-num" :class="grp.thresholds[th]?.numbers?.includes(n) ? 'hit' : 'miss'">{{ pad2(n) }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- 多门店投票（已迁移） -->
      <div v-if="thGrouped.length > 0" class="th-block vote-block">
        <div class="th-block-title">🗳️ 多门店投票</div>
        <div style="font-size:12px;color:#8899b0;padding:8px 0">
          已迁移至顶部「投票」tab（含投注单号码注数累计功能）。
        </div>
      </div>
    </div>

    <!-- 投票视图 -->
    <div v-if="view === 'vote'" class="threshold-view">
      <div class="sim-header">
        <span class="sim-title">🗳️ 多门店投票</span>
        <div style="display:flex;align-items:center;gap:6px">
          <input type="date" v-model="voteDate" @change="loadVoteStores" class="th-date-input">
          <button class="btn-add" @click="loadVoteStores">刷新</button>
        </div>
      </div>
      <div v-if="voteMsg" class="th-msg" :class="voteMsgType">{{ voteMsg }}</div>

      <!-- 门店选择 + 投票 -->
      <div class="th-block vote-block" style="margin-top:0">
        <div class="th-block-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>🏪 门店</span>
          <div style="display:flex;gap:6px">
            <button class="vote-tgl-btn" :class="{ on: allStoresSelected }" @click="voteSelectedStores = allStoresSelected ? [] : voteStores.map(s=>s.id)">全选</button>
            <button class="vote-tgl-btn" :class="{ on: voteSelectedStores.length === 0 }" @click="voteSelectedStores = []">清空</button>
          </div>
        </div>
        <div class="vote-store-row">
          <label v-for="s in voteStores" :key="s.id" class="vote-store-cb" :class="{ active: voteSelectedStores.includes(s.id) }">
            <input type="checkbox" :value="s.id" v-model="voteSelectedStores" @change="onVoteStoreChange">
            {{ s.name }}
          </label>
        </div>
        <div class="vote-ctrl-bar">
          <div class="vote-ctrl-row">
            <div class="vote-mode-btns">
              <button :class="{ active: voteDirection === 'positive' }" @click="voteDirection='positive'; loadVote()">📈 正 (25)</button>
              <button :class="{ active: voteDirection === 'negative' }" @click="voteDirection='negative'; loadVote()">📉 负 (24)</button>
            </div>
            <select v-model.number="voteThreshold" @change="loadVote" class="vote-select">
              <option v-for="n in voteOptions" :key="n" :value="n">{{ n }}/{{ voteSelectedStores.length }} 共识</option>
            </select>
          </div>
          <button class="vote-submit-btn" @click="loadVote">
            <span class="vote-submit-icon">🔍</span>
            执行投票
          </button>
        </div>
        <!-- 共识号码 -->
        <div v-if="voteResult" style="margin-top:8px">
          <div style="font-size:12px;color:#8899b0;margin-bottom:6px">
            共识：<b>{{ voteResult.consensus?.length || 0 }}</b> 个号码（{{ voteResult.total_stores }}店{{ voteResult.vote_threshold }}选 · {{ voteResult.direction === 'positive' ? '正25' : '负24' }}）
          </div>
          <div class="th-nums">
            <span v-for="n in 49" :key="n" class="th-num" :class="voteResult.consensus?.includes(n) ? 'hit' : 'miss'" :title="voteResult.frequencies?.[n] ? '出现'+voteResult.frequencies[n]+'次' : ''">{{ pad2(n) }}</span>
          </div>
          <div v-if="voteResult.consensus?.length" style="margin-top:8px;display:flex;gap:6px;align-items:flex-start">
            <button class="th-copy-btn" @click="copyVoteResult()" title="复制共识号码" style="flex-shrink:0">📋 复制</button>
            <span style="font-size:11px;color:#8899b0;word-break:break-all;line-height:1.6;min-width:0">{{ voteResult.consensus?.map(n => pad2(n)).join('.') }}</span>
          </div>
        </div>
      </div>

      <!-- 投注单（新功能：号码注数累计） -->
      <div v-if="voteResult?.consensus?.length || betGroups.length" class="th-block" style="border-left:3px solid #10b981 !important">
        <div class="th-block-title">🧾 投注单（号码注数累计）</div>
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <label style="font-size:11px;color:#8899b0;white-space:nowrap">注数</label>
          <input v-model.number="betNum" type="number" step="0.1" min="0" class="form-input" style="width:80px;padding:5px 8px;font-size:12px">
          <label style="font-size:11px;color:#8899b0;white-space:nowrap">号码</label>
          <input v-model="betManualNums" class="form-input" style="flex:1;min-width:140px;padding:5px 8px;font-size:12px" placeholder="留空=当前共识号码，或手动填 03.05.12">
          <button class="btn-add" @click="addBetGroup" :disabled="!betNum">➕ 添加</button>
        </div>

        <!-- 已添加组 -->
        <div v-if="betGroups.length" style="margin-bottom:8px">
          <div v-for="(g,i) in betGroups" :key="g.id" style="display:flex;align-items:flex-start;gap:6px;padding:5px 0;border-bottom:1px solid #e0e0e0;font-size:12px">
            <span style="color:#64748b;flex-shrink:0">#{{ i+1 }}</span>
            <span style="font-weight:700;color:#000;flex-shrink:0">{{ g.num }}</span>
            <span style="color:#000;word-break:break-all;flex:1;min-width:0">{{ g.numbers.map(n => pad2(n)).join('.') }}</span>
            <button @click="removeBetGroup(g.id)" style="color:#dc2626;flex-shrink:0;background:none;border:none;cursor:pointer">🗑</button>
          </div>
        </div>

        <!-- 累计分配（1-49 金额） -->
        <div v-if="betGroups.length">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:12px;color:#64748b">累计分配（1-49 金额）</span>
            <div style="display:flex;gap:6px">
              <button class="th-copy-btn" @click="copyBetExcel()">📋 号码+金额</button>
              <button class="th-copy-btn" @click="copyBetAmounts()">📋 仅金额</button>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">
            <div v-for="it in betFull49" :key="it.num" style="text-align:center;border:1px solid #e0e0e0;border-radius:6px;padding:3px 2px;background:#fff">
              <div style="font-size:10px;color:#94a3b8">{{ pad2(it.num) }}</div>
              <div style="font-size:12px;font-weight:700" :style="{color: it.total > 0 ? '#000' : '#cbd5e1'}">{{ it.total }}</div>
            </div>
          </div>
        </div>
        <div v-else style="font-size:11px;color:#64748b">添加组后，相同号码的注数会自动累加汇总</div>
      </div>
    </div>

    <!-- 演算视图 -->
    <div v-if="view === 'sim'" class="sim-view">
      <div class="sim-header">
        <span class="sim-title">🚀 演算</span>
        <button class="btn-add" @click="runSimDialog=!runSimDialog"
                :class="{ running: running }" :disabled="running">
          <span v-if="running" class="btn-spin"></span>
          {{ running ? '演算中' : '运行' }}
        </button>
        <button class="btn-add" @click="allowClear ? clearAllSimData() : null"
          :style="{background:allowClear?'#ee0a24':'#ccc',color:'#fff',marginLeft:'8px',cursor:allowClear?'pointer':'not-allowed',opacity:allowClear?1:0.5}">
          🗑️ 清空
        </button>
      </div>

      <!-- 查询栏 -->
      <div class="sim-query card">
        <div class="sim-param-row">
          <div class="date-picker-field date-picker-sm" @click="openDatePicker(simQStart, v => simQStart = v, $event)" style="flex:1">
            {{ simQStart ? simQStart : '起始日' }}
            <span class="date-arrow">📅</span>
          </div>
          <span class="sim-hint">~</span>
          <div class="date-picker-field date-picker-sm" @click="openDatePicker(simQEnd, v => simQEnd = v, $event)" style="flex:1">
            {{ simQEnd ? simQEnd : '结束日' }}
            <span class="date-arrow">📅</span>
          </div>
          <button class="btn-add-sm" @click="simQPage=1;loadSimQuery()">🔍 查询</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <select v-model="simQL3" class="form-input" @change="onSimQL3Change">
            <option value="all">全部项目</option>
            <option v-for="c in collections" :key="'qc'+c.id" :value="'c'+c.id">📁 {{ c.name }}</option>
          </select>
          <select v-if="simQCID" v-model="simQL2" class="form-input" @change="onSimQL2Change">
            <option value="">📁 整个集合</option>
            <option v-for="s in simQScopeSummaries" :key="'qs'+s.id" :value="'s'+s.id">📊 {{ s.name }}</option>
          </select>
          <select v-if="simQSID" v-model="simQL1" class="form-input" @change="onSimQL1Change">
            <option value="">📊 整个汇总</option>
            <option v-for="rg in simQScopeRunGroups" :key="'qrg'+rg.id" :value="'r'+rg.id">📋 {{ rg.name }} ({{ rg.project_count }}项)</option>
          </select>
        </div>
      </div>

      <!-- 运行参数 -->
      <div v-if="runSimDialog" class="sim-params card">
        <div class="sim-subtitle-sm">📅 日期范围</div>
        <div class="sim-param-row">
          <div class="date-picker-field" @click="openDatePicker(simStart, v => simStart = v, $event)" style="flex:1">
            {{ simStart || '开始日期' }}
            <span class="date-arrow">📅</span>
          </div>
          <span class="sim-hint" style="margin:0 6px">~</span>
          <div class="date-picker-field" @click="openDatePicker(simEnd, v => simEnd = v, $event)" style="flex:1">
            {{ simEnd || '结束日期' }}
            <span class="date-arrow">📅</span>
          </div>
        </div>
        <div class="sim-subtitle-sm" style="display:flex;justify-content:space-between;align-items:center">
          <span>📦 项目 & 规则</span>
          <div style="display:flex;gap:4px">
            <button class="btn-add-sm" @click="selectAllProjects">全选</button>
            <button class="btn-add-sm" style="background:#f5f7fa;color:#8899b0" @click="deselectAllProjects">取消</button>
          </div>
        </div>
        <div v-for="p in projects" :key="p.id" class="sim-proj-row"
             :class="{ active: simProjectIds.includes(p.id) }">
          <label class="sim-cb">
            <input type="checkbox" :value="p.id" v-model="simProjectIds" @change="onProjCheck(p)" />
            <span>{{ p.name }}</span>
          </label>
          <template v-if="simProjectIds.includes(p.id)">
            <select v-if="(rulesByProject[p.id]||[]).length"
                    v-model="simProjectRules[p.id]" class="form-input" style="flex:1">
              <option v-for="r in rulesByProject[p.id]" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
            <span v-else class="sim-hint" style="color:#ee0a24">⚠ 请先在组别中设置规则</span>
          </template>
        </div>
        <button class="btn-submit sim-run-btn" @click="runSimulation"
                :disabled="!canRun||running">
          <span v-if="running" class="btn-spin"></span>
          {{ running ? '演算中...' : '▶️ 开始演算' }}
        </button>
      </div>

      <!-- 历史列表 -->
      <div class="sim-history" v-if="simQItems.length">
        <div class="sim-subtitle">📜 运行记录 ({{ simQTotal }})</div>
        <div v-for="run in simQItems" :key="run.id" class="sim-run-card"
             :class="{ active: simRunId === run.id }">
          <div class="sim-run-main" @click="loadSimRun(run.id)">
            <div class="sim-run-top">
              <span class="sim-run-pill">{{ run.project_name || 'P'+run.project_id }}</span>
              <span class="sim-run-name">{{ run.rule_name }}</span>
              <span class="sim-run-hit" :style="{color: run.hit_count===run.total_days?'#22c55e':'#f59e0b'}">
                {{ run.hit_count }}/{{ run.total_days }}
              </span>
            </div>
            <div class="sim-run-date">{{ run.start_date }} ~ {{ run.end_date }}</div>
          </div>
          <button class="sim-del-btn" @click.stop="delSimRun(run.id)" title="删除">🗑</button>
        </div>
        <div class="sim-pager" v-if="simQPages > 1">
          <button :disabled="simQPage<=1" @click="simQPage--;loadSimQuery()">‹</button>
          <span>{{ simQPage }} / {{ simQPages }}</span>
          <button :disabled="simQPage>=simQPages" @click="simQPage++;loadSimQuery()">›</button>
        </div>
      </div>

      <!-- 运行结果（默认展开最后一天） -->
      <div v-if="simResult">
        <div class="sim-subtitle" style="display:flex;justify-content:space-between;align-items:center">
          <span>📊 {{ simResult.run.project_name || '' }} {{ simResult.run.rule_name }}</span>
          <div style="display:flex;gap:6px">
            <button class="btn-add-sm" v-if="!simShowAll" @click="simShowAll=true;simLast30=false">
              📖 展开全部
            </button>
            <button class="btn-add-sm" v-if="simShowAll" @click="simShowAll=false;simLast30=true"
                    style="background:#f0f4f8;color:#8899b0">
              📕 收起
            </button>
          </div>
        </div>
        <div class="sim-summary card">
          <span>📅 {{ simResult.run.start_date }} ~ {{ simResult.run.end_date }}</span>
          <span>🎯 {{ simResult.run.hit_count }}/{{ simResult.run.total_days }}</span>
        </div>
        <div v-for="day in simDisplayDays" :key="day.date" class="sim-day card">
          <div class="sim-day-head">
            <span class="sim-day-date">{{ day.date }}</span>
            <span class="sim-day-draw">抽签 <b>{{ day.draw_number || '—' }}</b></span>
            <span class="sim-hit-tag" v-if="day.hit_group">{{ day.hit_group }}组命中</span>
            <span class="sim-hit-tag pending" v-else-if="!day.draw_number">⏳待开奖</span>
            <span class="sim-hit-tag miss" v-else>未命中</span>
          </div>
          <div class="sim-day-grid">
            <div v-for="g in ['A','B','C','D','E','F','G','H','I','J','K','L']" :key="g"
                 class="sim-gcell" :class="{ hit: day.hit_group === g }">
              <div class="sim-gname">{{ g }}</div>
              <div class="sim-gcount">{{ day.groups[g]?.count_n }}</div>
              <div class="sim-gvalue">¥{{ day.groups[g]?.value }}</div>
              <div class="sim-gnums">{{ (day.groups[g]?.numbers||[]).join(',') }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!simQItems.length && !simResult" class="gs-empty">
        选择日期范围查询已有运行记录，或点击「运行」
      </div>
    </div>

    <!-- 盈亏视图 -->
    <div v-if="view === 'profit'" class="profit-view">
      <div class="sim-header">
        <span class="sim-title">💰 盈亏</span>
      </div>
      <div class="sim-query card">
        <div class="sim-param-row">
          <div class="date-picker-field date-picker-sm" @click="openDatePicker(pfDate, v => pfDate = v, $event)" style="flex:1">
            {{ pfRange ? '起始：' : '' }}{{ pfDate || '选择日期' }}
            <span class="date-arrow">📅</span>
          </div>
          <div v-if="pfRange" class="date-picker-field date-picker-sm" @click="openDatePicker(pfEnd, v => pfEnd = v, $event)" style="flex:1">
            {{ pfEnd || '结束日' }}
            <span class="date-arrow">📅</span>
          </div>
          <button class="btn-add-sm" @click="pfRange=!pfRange" :style="{background:pfRange?'#4da6ff':'#f0f4f8',color:pfRange?'#fff':'#8899b0'}">{{ pfRange ? '📆 段' : '📅 日' }}</button>
          <button class="btn-add-sm" @click="pfPage=1;loadProfit()">🔍 查询</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <select v-model="pfL3" class="form-input" @change="onPfL3Change">
            <option value="all">全部项目</option>
            <option v-for="c in collections" :key="'pc'+c.id" :value="'c'+c.id">📁 {{ c.name }}</option>
          </select>
          <select v-if="pfCID" v-model="pfL2" class="form-input" @change="onPfL2Change">
            <option value="">📁 整个集合</option>
            <option v-for="s in pfSummaries" :key="'ps'+s.id" :value="'s'+s.id">📊 {{ s.name }}</option>
          </select>
          <select v-if="pfSID" v-model="pfL1" class="form-input" @change="onPfL1Change">
            <option value="">📊 整个汇总</option>
            <option v-for="rg in pfRunGroups" :key="'prg'+rg.id" :value="'r'+rg.id">📋 {{ rg.name }} ({{ rg.project_count }}项)</option>
          </select>
        </div>
      </div>

      <!-- 汇总层：集合→汇总列表 -->
      <div v-if="pfItems.length && pfLevel==='summaries'" class="pf-table-wrap card">
        <div style="font-size:12px;color:#8899b0;padding:4px 0">📁 {{ collections.find(c=>'c'+c.id===pfL3)?.name }} → 所有汇总{{ pfRange ? ' · '+pfDate+'~'+pfEnd : ' · 抽签'+pfItems[0]?.draw }}</div>
        <table class="pf-table">
          <thead><tr>
            <th>汇总</th><th>项目</th><th>时间</th>
            <template v-if="pfRange"><th>总结果</th></template>
            <template v-else><th>联合49格值</th><th>排位</th><th>总结果</th></template>
            <th>正负</th>
          </tr></thead>
          <tbody>
            <tr v-for="it in sortedPfSummaries" :key="'s'+it.id" class="pf-clickable" @click="pfL2='s'+it.id; onPfL2Change()">
              <td style="font-weight:600">📊 {{ it.name }}</td>
              <td>{{ it.project_count }}</td>
              <td style="font-size:12px;color:#8899b0">{{ it.date || pfDate }}</td>
              <template v-if="pfRange">
                <td class="pf-num">{{ it.total_result.toLocaleString() }} <button class="pf-copy-inline" @click.stop="copyNum(it.total_result)" title="复制" style="background:none;border:none;cursor:pointer;font-size:11px;margin-left:2px;opacity:0.5">📋</button></td>
              </template>
              <template v-else>
                <td class="pf-num">{{ (it.draw_value||0).toLocaleString() }}</td>
                <td>{{ it.rank ? '第'+it.rank+'位' : '-' }}</td>
                <td class="pf-num">{{ it.total_result.toLocaleString() }} <button class="pf-copy-inline" @click.stop="copyNum(it.total_result)" title="复制" style="background:none;border:none;cursor:pointer;font-size:11px;margin-left:2px;opacity:0.5">📋</button></td>
              </template>
              <td class="pf-result" :class="{neg:(it.total_result||0)<0,pos:(it.total_result||0)>=0}">{{ (it.total_result||0)>=0?'✅ 正':'❌ 负' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 记录组层：汇总→记录组列表 -->
      <div v-if="pfItems.length && pfLevel==='run_groups'" class="pf-table-wrap card">
        <div style="font-size:12px;color:#8899b0;padding:4px 0">📊 {{ pfSummaries.find(s=>'s'+s.id===pfL2)?.name }} → 所有记录组{{ pfRange ? ' · '+pfDate+'~'+pfEnd : ' · 抽签'+pfItems[0]?.draw }}</div>
        <table class="pf-table">
          <thead><tr>
            <th>记录组</th><th>项目</th>
            <template v-if="pfRange"><th>日期</th><th>总结果</th></template>
            <template v-else><th>联合49格值</th><th>排位</th><th>总结果</th></template>
            <th>正负</th>
          </tr></thead>
          <tbody>
            <tr v-for="it in pfItems" :key="'rg'+it.id" class="pf-clickable" @click="pfL1='r'+it.id; onPfL1Change()">
              <td style="font-weight:600">📋 {{ it.name }}</td>
              <td>{{ it.project_count }}</td>
              <template v-if="pfRange">
                <td>{{ it.date }}</td>
                <td class="pf-num">{{ it.total_result.toLocaleString() }} <button class="pf-copy-inline" @click.stop="copyNum(it.total_result)" title="复制" style="background:none;border:none;cursor:pointer;font-size:11px;margin-left:2px;opacity:0.5">📋</button></td>
              </template>
              <template v-else>
                <td class="pf-num">{{ (it.draw_value||0).toLocaleString() }}</td>
                <td>{{ it.rank ? '第'+it.rank+'位' : '-' }}</td>
                <td class="pf-num">{{ it.total_result.toLocaleString() }} <button class="pf-copy-inline" @click.stop="copyNum(it.total_result)" title="复制" style="background:none;border:none;cursor:pointer;font-size:11px;margin-left:2px;opacity:0.5">📋</button></td>
              </template>
              <td class="pf-result" :class="{neg:(it.total_result||0)<0,pos:(it.total_result||0)>=0}">{{ (it.total_result||0)>=0?'✅ 正':'❌ 负' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- 项目层：记录组→项目明细 -->
      <div v-if="pfItems.length && pfLevel==='projects'" class="pf-table-wrap card">
        <table class="pf-table">
          <thead><tr>
            <th>日期</th><th>项目</th><th>抽签</th><th>排位</th><th>对应值</th><th>累计</th><th>结果</th>
          </tr></thead>
          <tbody>
            <tr v-if="pfSummary" class="pf-summary">
              <td colspan="2" style="font-weight:700">📊 合计 ({{ pfSummary.project_count }}项)</td>
              <td>-</td><td>-</td>
              <td class="pf-num" style="font-weight:700">{{ pfSummary.total_value.toLocaleString() }}</td>
              <td>-</td>
              <td class="pf-result" :class="{neg:pfSummary.total_result<0,pos:pfSummary.total_result>=0}" style="font-weight:700">
                {{ pfSummary.total_result.toLocaleString() }}
                <button class="pf-copy-btn" @click.stop="copyTotalResult" title="复制总结果" style="background:none;border:none;cursor:pointer;font-size:14px;margin-left:4px;opacity:0.6">📋</button>
              </td>
            </tr>
            <tr v-for="it in pfItems" :key="it.date+it.id">
              <td>{{ it.date }}</td>
              <td>{{ it.name }}</td>
              <td style="color:#4da6ff;font-weight:700">{{ it.draw || '-' }}</td>
              <td>{{ it.rank ? '第'+it.rank+'位' : '-' }}</td>
              <td class="pf-num">{{ (it.draw_value||0).toLocaleString() }}</td>
              <td class="pf-num">{{ (it.cumulative||0).toLocaleString() }}</td>
              <td class="pf-result" :class="{neg:it.result<0,pos:it.result>=0}">{{ it.result != null ? it.result.toLocaleString() : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="pfSearched" class="gs-empty">无数据</div>

      <div class="sim-pager" v-if="pfPages > 1">
        <button :disabled="pfPage<=1" @click="pfPage=1;loadProfit()">«</button>
        <button :disabled="pfPage<=1" @click="pfPage--;loadProfit()">‹</button>
        <span>{{ pfPage }} / {{ pfPages }}</span>
        <button :disabled="pfPage>=pfPages" @click="pfPage++;loadProfit()">›</button>
        <button :disabled="pfPage>=pfPages" @click="pfPage=pfPages;loadProfit()">»</button>
      </div>
    </div>

    <!-- 数据分析视图 -->
    <div v-if="view === 'analysis'" class="analysis-view">
      <div class="sim-header">
        <span class="sim-title">📈 分析</span>
        <div style="display:flex;gap:6px">
          <button class="btn-add-sm" @click="allowClear ? clearAnalysis() : null"
            :style="{background:allowClear?'#ee0a24':'#ccc',color:'#fff',cursor:allowClear?'pointer':'not-allowed',opacity:allowClear?1:0.5}">🗑 清空</button>
        </div>
      </div>
      <div class="sim-query card">
        <div class="sim-param-row">
          <div class="date-picker-field date-picker-sm" @click="openDatePicker(anStart, v => anStart = v, $event)" style="flex:1">
            {{ anStart ? anStart : '起始日' }}
            <span class="date-arrow">📅</span>
          </div>
          <span class="sim-hint">~</span>
          <div class="date-picker-field date-picker-sm" @click="openDatePicker(anEnd, v => anEnd = v, $event)" style="flex:1">
            {{ anEnd ? anEnd : '结束日' }}
            <span class="date-arrow">📅</span>
          </div>
          <button class="btn-add-sm" @click="anPage=1;loadAnalysis()">🔍 查询</button>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <select v-model="anL3" class="form-input" @change="onAnL3Change">
            <option value="all">全部项目</option>
            <option v-for="c in collections" :key="'ac'+c.id" :value="'c'+c.id">📁 {{ c.name }}</option>
          </select>
          <select v-if="anCID" v-model="anL2" class="form-input" @change="onAnL2Change">
            <option value="">📁 整个集合</option>
            <option v-for="s in anScopeSummaries" :key="'as'+s.id" :value="'s'+s.id">📊 {{ s.name }}</option>
          </select>
          <select v-if="anSID" v-model="anL1" class="form-input" @change="onAnL1Change">
            <option value="">📊 整个汇总</option>
            <option v-for="rg in anScopeRunGroups" :key="'arg'+rg.id" :value="'r'+rg.id">📋 {{ rg.name }} ({{ rg.project_count }}项)</option>
          </select>
        </div>
      </div>

      <!-- 汇总 -->
      <div class="an-summary card" v-if="anCumulative != null">
        <span>累计求和</span>
        <b>{{ anCumulative.toLocaleString() }}</b>
        <span style="margin-left:16px">结果合计</span>
        <b :style="{color: totalResult>=0?'#22c55e':'#ee0a24'}">{{ totalResult.toLocaleString() }}</b>
      </div>

      <!-- 表格 -->
      <div class="an-table-wrap" v-if="anItems.length">
        <div class="an-table">
          <div class="an-tr an-th">
            <span>日期</span><span>序号</span><span>项目</span><span>抽签</span><span>次数</span><span>值</span><span>×47</span><span>累计求和</span><span>结果</span><span>命中</span>
          </div>
          <div v-for="it in anItems" :key="it.date+it.project_id" class="an-tr">
            <span>{{ it.date }}</span>
            <span>{{ it.day_seq }}</span>
            <span>{{ it.project_name }}</span>
            <span>{{ it.draw }}</span>
            <span>{{ it.count_n }}</span>
            <span class="an-num">{{ it.value }}</span>
            <span class="an-num">{{ it.value_x_47.toLocaleString() }}</span>
            <span class="an-num">{{ it.cumulative_sum.toLocaleString() }}</span>
            <span class="an-result" :class="{ neg: it.result < 0 }">{{ it.result.toLocaleString() }}</span>
            <span class="an-hit" v-if="it.hit_rules">{{ it.hit_rules.join(',') }}</span>
            <span v-else style="color:#aaa">-</span>
          </div>
        </div>
      </div>

      <div class="sim-pager" v-if="anPages > 1">
        <button :disabled="anPage<=1" @click="anPage=1;loadAnalysis()">«</button>
        <button :disabled="anPage<=1" @click="anPage--;loadAnalysis()">‹</button>
        <select v-model.number="anPage" @change="loadAnalysis()" class="pager-select">
          <option v-for="p in anPages" :key="p" :value="p">{{ p }}</option>
        </select>
        <span>/ {{ anPages }}</span>
        <button :disabled="anPage>=anPages" @click="anPage++;loadAnalysis()">›</button>
        <button :disabled="anPage>=anPages" @click="anPage=anPages;loadAnalysis()">»</button>
      </div>
    </div>

    <!-- 日期选择器浮层（全局） -->
    <div v-if="showDatePicker" class="cal-dropdown" :style="calStyle" @click.self="cancelDatePicker">
      <div class="cal-body">
        <div class="cal-header">
          <button class="btn-cancel" @click="cancelDatePicker">取消</button>
          <span class="cal-title">选择日期</span>
          <button class="btn-submit" @click="confirmDatePicker">确定</button>
        </div>
        <div class="cal-ym">
          <select v-model.number="pickerYear" class="cal-select">
            <option v-for="y in pickerYears" :key="y" :value="y">{{ y }}年</option>
          </select>
          <select v-model.number="pickerMonth" class="cal-select">
            <option v-for="m in 12" :key="m" :value="m">{{ m }}月</option>
          </select>
        </div>
        <div class="cal-weekdays">
          <span v-for="w in weekDays" :key="w">{{ w }}</span>
        </div>
        <div class="cal-grid">
          <div v-for="(d, i) in calDays" :key="i"
            :class="['cal-day', {
              empty: !d,
              active: d === pickerDay,
              today: d === todayDay && pickerYear === todayYear && pickerMonth === todayMonth
            }]"
            @click="d && (pickerDay = d)">
            {{ d || '' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 集合管理视图 -->
    <div v-if="view === 'collection'" class="col-view">
      <div class="sim-header">
        <span class="sim-title">📁 集合</span>
        <div style="display:flex;gap:6px">
          <button class="btn-add" style="background:linear-gradient(135deg,#22c55e,#0ea5e9)" @click="openTodayRun">⚡ 演算当天</button>
          <button class="btn-add" @click="openAddCollection">+ 集合</button>
        </div>
      </div>
      <div class="col-crumb" v-if="colSel">
        <span @click="backTo('collections')">📁 集合</span>
        <template v-if="sumSel || activeRecordId">
          <span class="crumb-sep">›</span>
          <span @click="backTo('summaries')">{{ colSel?.name }}</span>
          <template v-if="activeRecordId">
            <span class="crumb-sep">›</span>
            <span @click="clearActiveRecord">{{ sumSel?.name }}</span>
            <span class="crumb-sep">›</span>
            <span class="crumb-end">{{ activeRecordName }}</span>
          </template>
          <template v-else-if="rgSel">
            <span class="crumb-sep">›</span>
            <span @click="backTo('run_groups')">{{ sumSel?.name }}</span>
            <span class="crumb-sep">›</span>
            <span class="crumb-end">{{ rgSel?.name }}</span>
          </template>
        </template>
      </div>
      <div v-if="grid49" class="grid49-section card">
        <div class="grid49-hd">
          <span>📅 {{ grid49.last_date || '无数据' }}</span>
          <span v-if="grid49.draw_number" style="font-size:12px;color:#1a2a4a;display:flex;align-items:center;gap:4px;flex-wrap:wrap">
            抽<b style="font-size:16px;color:#4da6ff">{{ grid49.draw_number }}</b> →
            <b style="color:#f59e0b">{{ gridDrawVal?.toLocaleString() }}</b> × 47 −
            <b style="color:#8899b0">{{ gridTotalSum.toLocaleString() }}</b> =
            <b :style="{color:gridResult>=0?'#22c55e':'#ee0a24',fontSize:'16px'}">{{ gridResult?.toLocaleString() }}</b>
          </span>
          <span class="grid49-sum" :style="{color:gridTotalSum>=0?'#22c55e':'#ee0a24'}">累计 ¥{{ gridTotalSum.toLocaleString() }}</span>
          <div style="display:flex;gap:6px;align-items:center">
            <div class="date-picker-field date-picker-sm" style="width:110px" @click="openDatePicker(gridDate, v => gridDate = v, $event)">
              {{ gridDate || '选择日期' }}
              <span class="date-arrow">📅</span>
            </div>
            <button class="btn-add-sm" @click="queryGridDate">🔍</button>
            <button class="btn-add-sm" @click="copyGrid">📋</button>
            <button class="btn-add-sm" @click="copyTop25" title="复制前25号码(值最大→小)">📋25</button>
            <button class="btn-add-sm" @click="copyBottom24" title="复制后24号码(值最大→小后24)">📋24</button>
          </div>
        </div>
        <div v-if="summaries.length && !sumSel" class="sum-chips">
          <span v-for="s in summaries" :key="s.id" class="sum-chip"
                :class="{active: selectedSummaryIds.includes(s.id)}"
                @click="toggleSummary(s.id)">{{ stripGrade(s.name) }}</span>
        </div>
        <div v-if="runGroups.length && sumSel && !activeRecordId && !rgSel" class="grid49-range">
          <span v-for="rg in runGroups" :key="rg.id" class="rg-pill"
                :class="{active: selectedRunGroupIds.includes(rg.id)}"
                @click="toggleRunGroup(rg.id)">{{ rg.name }}</span>
        </div>
        <div v-if="showRecordProjects && recordProjects.length">
          <div class="grid49-range">
            <span v-for="p in recordProjects" :key="p.project_id" class="rg-pill"
                  :class="{active: selectedProjectIds.includes(p.project_id)}"
                  @click="toggleProject(p.project_id)"
                  @dblclick="openProjGridFromG49(p)">{{ p.project_name }}</span>
          </div>
        </div>
        <div class="grid49-table">
          <div v-for="g in grid49.grid" :key="g.n" class="grid49-cell" :class="{zero:g.value===0}">
            <span class="g49-n">{{ g.n }}</span>
            <span class="g49-v">{{ g.value }}</span>
          </div>
        </div>
        <div class="grid49-proj" v-if="!showRecordProjects && grid49.projects?.length">
          <div class="g49-proj-title" @click="showGridProj=!showGridProj">
            各项目最新值 ({{ grid49.projects.length }}) {{ showGridProj ? '▼' : '▶' }}
          </div>
          <div v-if="showGridProj" class="g49-proj-list">
            <div v-for="p in grid49.projects" :key="p.project_id" class="g49-proj-row" @click="openProjGridFromG49(p)" style="cursor:pointer">
              <span>{{ p.project_name }}</span>
              <span style="font-size:11px;color:#8899b0">{{ p.last_date }}</span>
              <span class="g49-pv">¥{{ p.value.toLocaleString() }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="!colSel">
        <div v-if="collections.length === 0"></div>
        <div v-for="c in collections" :key="c.id" class="col-card" @click="selectCollection(c)">
          <div class="col-card-left">
            <span class="col-card-name">📁 {{ c.name }}</span>
          </div>
          <button class="col-del" @click.stop="delCollection(c.id)" :disabled="!allowClear" :style="{opacity:allowClear?1:0.3,cursor:allowClear?'pointer':'not-allowed'}">🗑</button>
          <span class="col-card-arrow">›</span>
        </div>
      </div>
      <div v-if="colSel && !sumSel">
        <!-- 汇总列表 -->
        <div class="col-section-hd">
          <span class="col-section-tl">{{ colSel?.name }} · 汇总列表</span>
          <button class="btn-add-sm" @click="openAddSummary">+ 汇总</button>
        </div>
        <div v-if="!summaries.length" class="gs-empty">暂无汇总，点击 + 创建</div>
        <div v-for="s in summaries" :key="s.id" class="col-card" @click="selectSummary(s)">
          <div class="col-card-left">
            <span class="col-card-name">📊 {{ s.name }}</span>
            <span class="col-card-tags">
              <span class="col-tag">{{ s.run_count || 0 }}记录</span>
              <span class="col-tag hit">{{ s.hit_rate || 0 }}%</span>
              <span class="col-tag days">{{ s.total_days || 0 }}天</span>
            </span>
          </div>
          <span class="col-card-value" style="color:#22c55e;font-weight:700">¥{{ (s.total_value||0).toLocaleString() }}</span>
          <button class="col-copy-btn" @click.stop="copyValue(s.total_value)" title="复制累计值">📋</button>
          <span class="col-card-arrow">›</span>
        </div>
      </div>
      <div v-if="sumSel && !rgSel">
        <div class="col-section-hd">
          <span class="col-section-tl">{{ sumSel?.name }} · 记录列表</span>
          <button class="btn-add-sm" @click="openAddRunGroup">+ 记录</button>
        </div>
        <div v-if="!runGroups.length" class="gs-empty">暂无记录，点击 + 创建</div>
        <div v-for="rg in runGroups" :key="rg.id" class="col-card" @click="selectRunGroup(rg)">
          <div class="col-card-left">
            <span class="col-card-name">📋 {{ rg.name }}</span>
            <span class="col-card-tags">
              <span class="col-tag">{{ rg.project_count || '-' }}项目</span>
              <span class="col-tag hit">{{ rg.hit_rate || 0 }}%</span>
            </span>
          </div>
          <span class="col-card-value" style="color:#22c55e;font-weight:700">¥{{ (rg.total_value||0).toLocaleString() }}</span>
          <button class="col-del" @click.stop="delRunGroup(rg.id)" :disabled="!allowClear" :style="{opacity:allowClear?1:0.3,cursor:allowClear?'pointer':'not-allowed'}">🗑</button>
        </div>
      </div>
      <div v-if="rgSel">
        <div class="col-section-hd">
          <span class="col-section-tl">{{ rgSel?.name }} · 项目明细</span>
          <div style="display:flex;gap:6px">
            <button class="btn-add-sm" @click="openEditItems">✏️ 修改</button>
            <button class="btn-add-sm" @click="openRunDialog">🚀 运行</button>
          </div>
        </div>
        <div class="col-summary card">
          <span>📅 {{ rgSel?.created_at?.slice(0,10) }}</span>
          <span>{{ rgSel?.project_count || 0 }} 项目</span>
          <span v-if="rgSel?.hit_rate">🎯 {{ rgSel?.hit_rate }}%</span>
        </div>
        <div v-if="!rgItems.length" class="gs-empty">暂无项目，点击 🚀 运行</div>
        <div v-for="it in rgItems" :key="it.id" class="col-card" style="cursor:pointer;flex-wrap:wrap" @click="openProjGrid(it)">
          <div class="col-card-left">
            <span class="col-card-name">{{ it.project_name }}</span>
            <span class="col-card-tags">
              <span class="col-tag days" v-if="getProjGrid(it.project_id).date">{{ getProjGrid(it.project_id).date }}</span>
            </span>
          </div>
          <span class="col-card-value" style="color:#22c55e;font-weight:700">¥{{ (getProjGrid(it.project_id).value||0).toLocaleString() }}</span>
        </div>
      </div>
        <div v-if="showRunDialog" class="form-overlay" @click.self="showRunDialog=false">
        <div class="form-card" style="max-width:380px">
          <div class="form-title">运行模拟</div>
          <label>日期范围</label>
          <div class="sim-param-row">
            <div class="date-picker-field date-picker-sm" @click="openDatePicker(runForm.start_date, v => runForm.start_date = v, $event)" style="flex:1">
              {{ runForm.start_date || '起始日' }}
              <span class="date-arrow">📅</span>
            </div>
            <span class="sim-hint">~</span>
            <div class="date-picker-field date-picker-sm" @click="openDatePicker(runForm.end_date, v => runForm.end_date = v, $event)" style="flex:1">
              {{ runForm.end_date || '结束日' }}
              <span class="date-arrow">📅</span>
            </div>
          </div>
          <div v-if="editItemsForm.project_ids.length" style="margin-top:12px">
            <div class="scope-toggle" @click="runProjectsExpanded=!runProjectsExpanded">
              <span>已选 {{ editItemsForm.project_ids.length }} 个项目</span>
              <span class="scope-toggle-arrow" :class="{open:runProjectsExpanded}">▶</span>
            </div>
            <div v-if="runProjectsExpanded" class="scope-proj-wrap">
              <div v-for="pid in editItemsForm.project_ids" :key="pid" class="scope-proj-row">
                <span>{{ getProjectName(pid) }}</span>
              </div>
            </div>
          </div>
          <div v-else-if="rgItems.length" style="margin-top:12px">
            <div class="scope-toggle" @click="runProjectsExpanded=!runProjectsExpanded">
              <span>将运行 {{ rgItems.length }} 个项目</span>
              <span class="scope-toggle-arrow" :class="{open:runProjectsExpanded}">▶</span>
            </div>
            <div v-if="runProjectsExpanded" class="scope-proj-wrap">
              <div v-for="it in rgItems" :key="it.project_id" class="scope-proj-row">
                <span>{{ it.project_name }}</span>
                <span class="scope-rule-tag" v-if="it.rule_name">{{ it.rule_name }}</span>
              </div>
            </div>
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showRunDialog=false">取消</button>
            <button class="btn-submit" @click="execRunGroup" :disabled="runRunning">
              <span v-if="runRunning" class="btn-spin"></span>
              {{ runRunning ? '运行中...' : '开始运行' }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="showColForm" class="form-overlay" @click.self="showColForm=false">
        <div class="form-card">
          <div class="form-title">{{ editingColId ? '编辑集合' : '新增集合' }}</div>
          <label>集合名称</label>
          <input v-model="colForm.name" class="form-input" placeholder="如：测试集合1" />
          <div class="form-btns">
            <button class="btn-cancel" @click="showColForm=false">取消</button>
            <button class="btn-submit" @click="saveCollection">保存</button>
          </div>
        </div>
      </div>
      <div v-if="showSumForm" class="form-overlay" @click.self="showSumForm=false">
        <div class="form-card">
          <div class="form-title">新增汇总</div>
          <label>汇总名称</label>
          <input v-model="sumForm.name" class="form-input" placeholder="如：汇总1" />
          <div class="form-btns">
            <button class="btn-cancel" @click="showSumForm=false">取消</button>
            <button class="btn-submit" @click="saveSummary">保存</button>
          </div>
        </div>
      </div>
      <div v-if="showRgForm" class="form-overlay" @click.self="showRgForm=false">
        <div class="form-card" style="max-width:380px">
          <div class="form-title">新增记录组</div>
          <label>记录名称</label>
          <input v-model="rgForm.name" class="form-input" placeholder="如：主项目1-15" />
          <label>选择项目 ({{ rgForm.project_ids.length }})</label>
          <div class="rg-proj-grid">
            <div v-for="p in projects" :key="p.id"
                 :class="['rg-proj-pill', {active:rgForm.project_ids.includes(p.id)}]"
                 @click="toggleRgProject(p.id)">
              {{ p.name }}
            </div>
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showRgForm=false">取消</button>
            <button class="btn-submit" @click="saveRunGroup">创建</button>
          </div>
        </div>
      </div>
      <div v-if="showEditItems" class="form-overlay" @click.self="showEditItems=false">
        <div class="form-card" style="max-width:380px">
          <div class="form-title">修改项目 ({{ editItemsForm.project_ids.length }})</div>
          <label>选择项目</label>
          <div class="rg-proj-grid">
            <div v-for="p in projects" :key="p.id"
                 :class="['rg-proj-pill', {active:editItemsForm.project_ids.includes(p.id)}]"
                 @click="toggleEditProject(p.id)">
              {{ p.name }}
            </div>
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showEditItems=false">取消</button>
            <button class="btn-submit" @click="saveEditItems">保存</button>
          </div>
        </div>
      </div>
    </div>
    <!-- 弹窗：演算当天 -->
    <div v-if="showTodayRun" class="form-overlay" @click.self="showTodayRun=false">
      <div class="form-card" style="max-width:380px">
        <div class="form-title">⚡ 演算当天</div>
        <label>日期</label>
        <div class="date-picker-field" style="text-align:left" @click="openDatePicker(todayRunDate, v => todayRunDate = v, $event)">
          {{ todayRunDate || '点击选择日期' }}
          <span class="date-arrow">📅</span>
        </div>
        <label>范围</label>
        <select v-model="trL3" class="form-input" @change="onTrL3Change">
          <option value="all">全部项目</option>
          <option v-for="c in collections" :key="'c'+c.id" :value="'c'+c.id">📁 {{ c.name }}</option>
        </select>
        <select v-if="trCID" v-model="trL2" class="form-input" style="margin-top:8px" @change="onTrL2Change">
          <option value="">📁 整个集合</option>
          <option v-for="s in scopeSummaries" :key="'s'+s.id" :value="'s'+s.id">📊 {{ s.name }}</option>
        </select>
        <select v-if="trSID" v-model="trL1" class="form-input" style="margin-top:8px" @change="onTrL1Change">
          <option value="">📊 整个汇总</option>
          <option v-for="rg in scopeRunGroups" :key="'rg'+rg.id" :value="'r'+rg.id">📋 {{ rg.name }} ({{ rg.project_count }}项)</option>
        </select>
        <div v-if="scopeProjects.length" style="margin-top:12px">
          <div class="scope-toggle" @click="trProjectsExpanded=!trProjectsExpanded">
            <span>将演算 {{ scopeProjects.length }} 个项目</span>
            <span class="scope-toggle-arrow" :class="{open:trProjectsExpanded}">▶</span>
          </div>
          <div v-if="trProjectsExpanded" class="scope-proj-wrap">
            <div v-for="p in scopeProjects" :key="p.project_id" class="scope-proj-row">
              <span>{{ p.project_name }}</span>
              <span class="scope-rule-tag">{{ p.rule_name || '⚠ 无规则' }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="trL3 !== 'all'" class="gs-empty" style="padding:16px 0">所选范围下无项目</div>
        <div class="form-btns">
          <button class="btn-cancel" @click="showTodayRun=false">取消</button>
          <button class="btn-submit" @click="execTodayRun" :disabled="!canTodayRun||todayRunRunning">
            <span v-if="todayRunRunning" class="btn-spin"></span>
            {{ todayRunRunning ? '运行中...' : '▶️ 演算今天' }}
          </button>
        </div>
      </div>
    </div>
    <!-- 弹窗：演算进度 -->
    <div v-if="trProgress.show" class="form-overlay" style="z-index:1001">
      <div class="form-card" style="max-width:340px;text-align:center">
        <div class="form-title">⚡ 演算中 · 步骤 {{ trProgress.step }}/{{ trProgress.totalSteps }}</div>
        <div style="padding:8px 0;color:#5a6b85;font-size:13px">{{ trProgress.msg }}</div>
        <div v-if="trProgress.errors" style="font-size:11px;color:#dc2626;margin-top:4px">{{ trProgress.errors }}</div>
        <div style="background:#f0f3f8;border-radius:8px;height:10px;margin:12px 0 4px;overflow:hidden">
          <div :style="{width:(trProgress.step/trProgress.totalSteps*100)+'%',height:'100%',background:'linear-gradient(90deg,#22c55e,#0ea5e9)',transition:'width .3s'}"></div>
        </div>
        <div style="font-size:11px;color:#8899b0">{{ trProgress.done }}/{{ trProgress.total }} 个项目完成</div>
        <div v-if="trProgress.step === trProgress.totalSteps" class="form-btns" style="margin-top:12px">
          <button class="btn-submit" @click="trProgress.show=false">关闭</button>
        </div>
      </div>
    </div>
    <div v-if="showProjDetail" class="form-overlay" @click.self="showProjDetail=false">
      <div class="form-card" style="max-width:420px">
        <div class="form-title">{{ projDetail?.project_name }} · 49格明细</div>
        <div style="font-size:12px;color:#8899b0;margin-bottom:8px">📅 {{ projDetail?.last_date || '无数据' }} · 累计 ¥{{ (projDetail?.total||0).toLocaleString() }}</div>
        <div v-if="projDetail?.draw_number" style="font-size:12px;color:#1a2a4a;margin-bottom:8px;display:flex;align-items:center;gap:4px;flex-wrap:wrap">
          抽<b style="font-size:16px;color:#4da6ff">{{ projDetail.draw_number }}</b> →
          <b style="color:#f59e0b">{{ projDrawVal?.toLocaleString() }}</b> × 47 −
          <b style="color:#8899b0">{{ (projDetail.total||0).toLocaleString() }}</b> =
          <b :style="{color:projResult>=0?'#22c55e':'#ee0a24',fontSize:'16px'}">{{ projResult?.toLocaleString() }}</b>
        </div>
        <div class="grid49-table" v-if="projDetail?.grid?.length">
          <div v-for="g in projDetail.grid" :key="g.n" class="grid49-cell" :class="{zero:g.value===0}">
            <span class="g49-n">{{ g.n }}</span>
            <span class="g49-v">{{ g.value }}</span>
          </div>
        </div>
        <div v-else class="gs-empty" style="margin:12px 0">该项目尚未运行，无数据</div>
        <div class="form-btns">
          <button class="btn-cancel" @click="showProjDetail=false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="confirmDialog.show" class="form-overlay" @click.self="confirmDialog.cancel()">
      <div class="form-card" style="max-width:300px;text-align:center">
        <div style="font-size:15px;padding:16px 0 8px;color:#1a2a4a">{{ confirmDialog.msg }}</div>
        <div class="form-btns">
          <button class="btn-cancel" @click="confirmDialog.cancel()">取消</button>
          <button class="btn-submit" style="background:#ee0a24" @click="confirmDialog.ok()">确定</button>
        </div>
      </div>
    </div>

    <!-- Toast 通知 -->
    <div v-if="toast.show" class="toast" :class="{ error: toast.isError }">{{ toast.msg }}</div>

  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick } from 'vue'

const API = '/number-warehouse/api'

// 全局 fetch 包装：自动处理 session 过期返回 HTML 的情况
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts)
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    // session 过期，跳转到首页让认证中间件显示登录页
    window.location.href = '/number-warehouse/'
    throw new Error('登录已过期，正在刷新...')
  }
  return res
}

// 自定义确认弹窗（平板兼容）
const confirmDialog = reactive({
  show: false,
  msg: '',
  _resolve: null,
  ok() { this.show = false; if (this._resolve) this._resolve(true) },
  cancel() { this.show = false; if (this._resolve) this._resolve(false) },
})
function $confirm(msg) {
  return new Promise(resolve => {
    confirmDialog.msg = msg
    confirmDialog._resolve = resolve
    confirmDialog.show = true
  })
}

// Toast 通知（替代原生 alert）
const toast = reactive({ show: false, msg: '', isError: false, _timer: null })
function $notify(msg, isError = false) {
  clearTimeout(toast._timer)
  toast.msg = msg
  toast.isError = isError
  toast.show = true
  toast._timer = setTimeout(() => { toast.show = false }, 3000)
}
const todayStr = new Date().toISOString().slice(0, 10)
const tomorrowStr = new Date(Date.now() + 86400000).toISOString().slice(0, 10)

function doLogout() {
  fetch('/number-warehouse/auth/logout', { method: 'POST' })
    .then(r => r.json())
    .then(d => { if (d.ok) location.href = '/number-warehouse/' })
}

const view = ref('collection')

// ===== 尾数记录分析 =====
const tailData = reactive({
  latest_date: '', latest_draw: null,
  current: { '0-4': {streak:0}, '5-9': {streak:0} },
  by_len_04: [], by_len_59: [],
  prediction: null,
})
const tailPeriods = ref(null)

function showTailPeriods(group, g) {
  tailPeriods.value = {
    label: group === '04' ? '🟢 0-4' : '🔴 5-9',
    len: g.len,
    count: g.count,
    periods: g.periods,
  }
}

async function loadTailStreaks() {
  try {
    const r = await apiFetch('/draw-analysis/streaks')
    const data = await r.json()
    if (data.error) { $notify(data.error, true); return }
    Object.assign(tailData, data)
  } catch(e) { $notify('加载失败', true) }
}

// ===== 导出页签 =====
const exportSrc = ref('')
const onExportLoad = () => {}; // placeholder
watch(view, (v) => {
  if (v === 'export' && !exportSrc.value) {
    exportSrc.value = 'export.html'
  }
})

// ===== 阈值（复制25/24） =====
const thItems = ref([])
const thComputing = ref(false)
const thMsg = ref('')
const thMsgType = ref('')
const thDate = ref('')  // 由后端自动确定（最新抽签+1）
const thCol19 = ref([])
const thRange = ref(false)  // 时间段模式
const thFromDate = ref('')
const thToDate = ref('')

function fmtW(v) { return v != null ? (v / 10000).toFixed(1) + '万' : '—' }

const thGrouped = computed(() => {
  const valMap = {}
  thCol19.value.forEach(s => { valMap[s.name] = s.total_value })
  return [...thItems.value]
    .map(it => ({
      ...it,
      col19_val: it.collection_id < 0 ? valMap[it.summary_name] : null,
      _sort: it.collection_id < 0 ? -it.collection_id : it.collection_id + 1000
    }))
    .sort((a, b) => a._sort - b._sort)
})

async function loadThreshold() {
  try {
    const q = thDate.value ? '?date=' + thDate.value : ''
    const r = await fetch('api/threshold/results' + q, { credentials: 'include' })
    if (!r.ok) throw new Error('加载失败')
    const d = await r.json()
    thItems.value = d.items || []
    thCol19.value = d.col19_summaries || []
    thDate.value = d.date || thDate.value
  } catch(e) {
    thItems.value = []
    thCol19.value = []
  }
}

async function computeThreshold() {
  thComputing.value = true
  thMsg.value = '计算中...'
  thMsgType.value = ''
  try {
    let q = ''
    if (thRange.value && thFromDate.value && thToDate.value) {
      q = '?from_date=' + thFromDate.value + '&to_date=' + thToDate.value
    } else if (thDate.value) {
      q = '?date=' + thDate.value
    }
    const r = await fetch('api/threshold/compute' + q, { method: 'POST', credentials: 'include' })
    const d = await r.json()
    if (d.ok) {
      if (d.mode === 'range') {
        thMsg.value = '✅ ' + d.dates_count + '天完成 (' + d.elapsed_sec + 's)'
        thMsgType.value = 'ok'
        if (d.errors?.length) {
          thMsg.value += ' | ⚠️ ' + d.errors.length + '错'
        }
        if (d.dates?.length) {
          thDate.value = d.dates[d.dates.length - 1]
          thFromDate.value = d.from
          thToDate.value = d.to
        }
      } else {
        thMsg.value = '✅ 计算完成'
        thMsgType.value = 'ok'
        thDate.value = d.date
      }
      await loadThreshold()
    } else {
      thMsg.value = '❌ ' + (d.error || '计算失败')
      thMsgType.value = 'err'
    }
  } catch(e) {
    thMsg.value = '❌ ' + e.message
    thMsgType.value = 'err'
  }
  thComputing.value = false
  setTimeout(() => { thMsg.value = '' }, 3000)
}

function copyThNumbers(grp, th) {
  const nums = grp.thresholds[th]?.numbers
  if (!nums || nums.length === 0) return
  navigator.clipboard.writeText(nums.map(n => pad2(n)).join('.'))
    .then(() => $notify(`已复制${th}个号码`), () => $notify('复制失败', true))
}

// ===== 多门店投票 =====
const voteStores = ref([])
const voteSelectedStores = ref([])
const voteDirection = ref('positive')
const voteThreshold = ref(2)
const voteResult = ref(null)
const voteDate = ref('')
const voteMsg = ref('')
const voteMsgType = ref('')
const allStoresSelected = computed(() => voteStores.value.length > 0 && voteSelectedStores.value.length === voteStores.value.length)
const voteOptions = computed(() => {
  const n = voteSelectedStores.value.length
  if (n < 2) return []
  const min = Math.ceil(n / 2)
  const opts = []
  for (let i = min; i <= n; i++) opts.push(i)
  return opts
})

function initVoteStores() {
  // 从 thGrouped 提取门店：summary级(cid<0) + 集合14/16
  const summaryStores = thGrouped.value
    .filter(g => g.collection_id < 0)
    .map(g => ({ id: -g.collection_id, name: g.label }))
    .sort((a, b) => a.id - b.id)
  const colStores = thGrouped.value
    .filter(g => g.collection_id === 14 || g.collection_id === 16)
    .map(g => ({ id: g.collection_id, name: g.label }))
    .sort((a, b) => a.id - b.id)
  voteStores.value = [...summaryStores, ...colStores]
  voteSelectedStores.value = voteStores.value.map(s => s.id)
  if (voteOptions.value.length > 0) {
    voteThreshold.value = voteOptions.value[0]
  }
  loadVote()
}

async function loadVoteStores() {
  // 从独立接口获取门店列表（投票tab专用）
  voteMsg.value = ''; voteMsgType.value = ''
  try {
    const q = voteDate.value ? '?date=' + voteDate.value : ''
    const r = await fetch('api/vote/stores' + q, { credentials: 'include' })
    const d = await r.json()
    if (d.ok) {
      voteStores.value = d.stores || []
      voteDate.value = d.date || voteDate.value
      voteSelectedStores.value = voteStores.value.map(s => s.id)
      if (voteOptions.value.length > 0) voteThreshold.value = voteOptions.value[0]
      loadVote()
    } else {
      voteMsg.value = '⚠️ ' + (d.error || '无数据')
      voteMsgType.value = 'err'
      voteStores.value = []
      voteResult.value = null
    }
  } catch (e) {
    voteMsg.value = '❌ ' + e.message
    voteMsgType.value = 'err'
  }
}

function onVoteStoreChange() {
  if (voteOptions.value.length > 0) {
    voteThreshold.value = voteOptions.value[0]
  }
  loadVote()
}

async function loadVote() {
  if (voteSelectedStores.value.length < 2) { voteResult.value = null; return }
  try {
    const params = new URLSearchParams({
      direction: voteDirection.value,
      vote: voteThreshold.value,
      stores: voteSelectedStores.value.join(','),
      date: voteDate.value
    })
    const r = await fetch('api/threshold/vote?' + params, { credentials: 'include' })
    const d = await r.json()
    voteResult.value = d.ok ? d : null
  } catch(e) { voteResult.value = null }
}

function pad2(n) { return String(n).padStart(2, '0') }

function copyVoteResult() {
  const nums = voteResult.value?.consensus
  if (!nums?.length) return
  navigator.clipboard.writeText(nums.map(n => pad2(n)).join('.'))
    .then(() => $notify(`已复制${nums.length}个号码`), () => $notify('复制失败', true))
}

// ===== 投注单（号码注数累计） =====
const betNum = ref(1)
const betManualNums = ref('')
const betGroups = ref([])
const BET_KEY = 'nw_bet_groups'

function parseNums(s) {
  return s.split(/[.\s,，、]+/).map(x => parseInt(x, 10)).filter(n => n >= 1 && n <= 49)
}

function saveBetGroups() {
  try { localStorage.setItem(BET_KEY, JSON.stringify(betGroups.value)) } catch(e) {}
}

function loadBetGroups() {
  try {
    const d = JSON.parse(localStorage.getItem(BET_KEY) || '[]')
    if (Array.isArray(d)) betGroups.value = d
  } catch(e) {}
}

const betSummary = computed(() => {
  const map = {}
  for (const g of betGroups.value) {
    for (const n of g.numbers) {
      map[n] = (map[n] || 0) + g.num
    }
  }
  return map
})

const betSummaryList = computed(() => {
  return Object.entries(betSummary.value)
    .map(([num, total]) => ({ num: Number(num), total }))
    .sort((a, b) => a.num - b.num)
})

const betFull49 = computed(() => {
  const list = []
  for (let n = 1; n <= 49; n++) {
    list.push({ num: n, total: betSummary.value[n] || 0 })
  }
  return list
})

function addBetGroup() {
  const num = betNum.value
  if (!num || num <= 0) return alert('请填写注数（大于0）')
  let numbers
  if (betManualNums.value.trim()) {
    numbers = parseNums(betManualNums.value)
  } else {
    numbers = voteResult.value?.consensus || []
  }
  if (!numbers.length) return alert('无号码可添加（请先投票或手动填号码）')
  betGroups.value.push({ id: Date.now(), num, numbers: [...new Set(numbers)].sort((a, b) => a - b) })
  betManualNums.value = ''
  saveBetGroups()
}

function removeBetGroup(id) {
  betGroups.value = betGroups.value.filter(g => g.id !== id)
  saveBetGroups()
}

function copyBetSummary() {
  if (!betSummaryList.value.length) return
  const text = betSummaryList.value.map(it => `${pad2(it.num)}: ${it.total}`).join('\n')
  navigator.clipboard.writeText(text)
    .then(() => $notify('已复制投注单'), () => $notify('复制失败', true))
}

function copyBetExcel() {
  const text = betFull49.value.map(it => `${pad2(it.num)}\t${it.total}`).join('\n')
  navigator.clipboard.writeText(text)
    .then(() => $notify('已复制（号码+金额，Tab分隔，可直接粘贴Excel）'), () => $notify('复制失败', true))
}

function copyBetAmounts() {
  const text = betFull49.value.map(it => it.total).join('\n')
  navigator.clipboard.writeText(text)
    .then(() => $notify('已复制49个金额（换行分隔，可粘贴Excel一列）'), () => $notify('复制失败', true))
}

loadBetGroups()

// ===== 数据记录 =====
const records = ref([])
const recPage = ref(1)
const recTotal = ref(0)
const recTotalPages = ref(1)
const recYear = ref('')
const recYears = ref([])
const showForm = ref(false)
const editingId = ref(null)
const form = ref({ date: todayStr, draw_number: null })
const warnFromDate = ref('')
const warnToDate = ref('')
const warningSyncing = ref(false)

// ===== 数据记录 增删改查 =====
const computedDaySeq = computed(() => {
  if (!form.value.date) return '-'
  const d = new Date(form.value.date)
  const yearStart = new Date(d.getFullYear(), 0, 1)
  return Math.floor((d - yearStart) / 86400000) + 1
})

async function loadRecords() {
  try {
    const params = new URLSearchParams({ page: recPage.value, page_size: 30 })
    if (recYear.value) params.set('year', recYear.value)
    const res = await fetch(`${API}/records?${params}`)
    const data = await res.json()
    records.value = data.items
    recTotal.value = data.total
    recTotalPages.value = data.total_pages
    recPage.value = data.page
  } catch (e) { console.error(e) }
}

function goPage(p) { recPage.value = p; loadRecords() }

async function loadYears() {
  try {
    const res = await fetch(`${API}/records/years`)
    recYears.value = await res.json()
  } catch (e) { console.error(e) }
}

async function syncToNumberSystem() {
  if (!warnFromDate.value || !warnToDate.value) { $notify('请选择起止日期', true); return }
  if (warnFromDate.value > warnToDate.value) { $notify('开始日期不能晚于结束日期', true); return }
  warningSyncing.value = true
  try {
    const res = await apiFetch(`/export/push-warning-range?start_date=${warnFromDate.value}&end_date=${warnToDate.value}`, { method: 'POST' })
    const data = await res.json()
    if (data.ok) {
      const parts = [`新增 ${data.synced} 条`]
      if (data.updated) parts.push(`覆盖 ${data.updated} 条`)
      if (data.failed) parts.push(`失败 ${data.failed} 条`)
      $notify(parts.join('，') + `（共 ${data.total} 条）`)
    } else {
      $notify(data.error || '同步失败', true)
    }
  } catch (e) {
    $notify('网络错误', true)
  } finally {
    warningSyncing.value = false
  }
}

function openAdd() {
  editingId.value = null
  form.value = { date: todayStr, draw_number: null }
  showForm.value = true
}

// ===== 可拖动悬浮新增按钮（记录页） =====
const fabPos = reactive({ x: 9999, y: 9999 })
let fabDrag = null
let fabMoved = false
const FAB_SIZE = 52

function fabReset() {
  const s = FAB_SIZE
  fabPos.x = Math.max(8, window.innerWidth - s - 16)
  fabPos.y = Math.max(8, window.innerHeight - s - 130)
}

// 记录页显示时重置到右下角（处理窗口尺寸变化后出屏）
watch(view, (v) => { if (v === 'records') fabReset() })

function onFabDown(e) {
  if (e.button !== undefined && e.button !== 0) return
  e.preventDefault()
  // 先钳制到视口内（防止 resize 后出屏点不到）
  const s = FAB_SIZE
  fabPos.x = Math.max(8, Math.min(window.innerWidth - s - 8, fabPos.x))
  fabPos.y = Math.max(8, Math.min(window.innerHeight - s - 8, fabPos.y))
  fabDrag = { sx: e.clientX, sy: e.clientY, ox: fabPos.x, oy: fabPos.y }
  fabMoved = false
  if (e.target && e.target.setPointerCapture) {
    try { e.target.setPointerCapture(e.pointerId) } catch (_) {}
  }
}

function onFabMove(e) {
  if (!fabDrag) return
  const dx = e.clientX - fabDrag.sx
  const dy = e.clientY - fabDrag.sy
  if (Math.abs(dx) > 5 || Math.abs(dy) > 5) fabMoved = true
  const s = FAB_SIZE
  fabPos.x = Math.max(8, Math.min(window.innerWidth - s - 8, fabDrag.ox + dx))
  fabPos.y = Math.max(8, Math.min(window.innerHeight - s - 8, fabDrag.oy + dy))
}

function onFabUp() { fabDrag = null }

function onFabTap() {
  if (fabMoved) { fabMoved = false; return }
  openAdd()
}

function openEdit(r) {
  editingId.value = r.id
  form.value = { date: r.date, draw_number: r.draw_number }
  showForm.value = true
}

async function doSave() {
  if (!form.value.date || !form.value.draw_number) return alert('请填写日期和抽签数')
  const payload = { date: form.value.date, draw_number: form.value.draw_number }
  try {
    const url = editingId.value ? `${API}/records/${editingId.value}` : `${API}/records`
    const method = editingId.value ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '保存失败')
    showForm.value = false
    loadRecords()
  } catch (e) { alert(e.message) }
}

async function doDelete(id) {
  const ok = await $confirm('确定删除此记录？'); if (!ok) return
  try {
    await fetch(`${API}/records/${id}`, { method: 'DELETE' })
    loadRecords()
  } catch (e) { console.error(e) }
}

// ===== 最长未出号码 =====
const showMissing = ref(false)
const missingLoading = ref(false)
const missingData = ref({})
const missingDate = ref('')

async function fetchMissing() {
  missingLoading.value = true; missingData.value = {}
  try {
    const q = missingDate.value ? `?date=${missingDate.value}` : ''
    const res = await fetch(`${API}/missing-numbers${q}`)
    missingData.value = await res.json()
    if (!missingDate.value && missingData.value.latest_date) {
      missingDate.value = missingData.value.latest_date
    }
  } catch (e) {
    missingData.value = { error: e.message }
  } finally {
    missingLoading.value = false
  }
}

async function openMissingNumbers() {
  showMissing.value = true
  missingDate.value = ''
  await fetchMissing()
}

const missingSortedCode = computed(() => {
  const nums = (missingData.value.top25 || []).map(n => n.num).slice().sort((a, b) => a - b)
  return nums.length ? nums.join('.') : ''
})

function copyMissingNumbers() {
  const nums = (missingData.value.top25 || []).map(n => n.num).join('.')
  navigator.clipboard.writeText(nums).then(() => {
    alert('已复制: ' + nums)
  }).catch(() => {
    prompt('复制以下号码:', nums)
  })
}

function copyMissingSorted() {
  const code = missingSortedCode.value
  if (!code) return alert('暂无数据')
  navigator.clipboard.writeText(code).then(() => {
    alert('已复制: ' + code)
  }).catch(() => {
    prompt('复制以下号码:', code)
  })
}

// ===== 最长跟踪演算 =====
const showTracking = ref(false)
const trackingTab = ref('list')   // list | new | detail
const trackingRuns = ref([])
const trackingRunsLoading = ref(false)
const trackingName = ref('')
const trackingMinN = ref(3)
const trackingMaxN = ref(25)
const trackingWarmup = ref(100)
const trackingRunning = ref(false)
const trackingDetail = ref({})
const trackingSortBy = ref('eq_pnl')
const trackingYears = ref(2)          // 日期范围：最近 N 年（0=全部）
const trackingAutoRecalc = ref(true)  // 切换算法/口径时，若有更新自动重算
const recalcRunId = ref(null)         // 正在重算的 run id
const showAlgoDoc = ref(false)        // 算法文档弹窗
const algoDoc = ref({ algo_count: 0, categories: [] })
const holdTheta = ref(10)             // 跟踪持有：进场阈值（遗漏期数）
const holdK = ref(12)                 // 跟踪持有：跟踪期数
const holdSignal = ref('gap')         // 进场信号：gap(遗漏期数) / ratio(遗漏比) / consensus(共识投票)
const holdMinVotes = ref(4)           // 共识投票：最少得票数
const holdResult = ref(null)          // 跟踪持有分析结果
const holdLoading = ref(false)
const holdLive = ref(null)            // 实盘纸面跟踪（当前最冷号 + 最近轨迹）
const holdRounds = ref(null)          // 实盘逐轮明细 + 汇总
const equityCanvas = ref(null)        // 资金曲线 Canvas

async function openTracking() {
  showTracking.value = true
  trackingTab.value = 'list'
  await loadTrackingRuns()
}

async function loadTrackingRuns() {
  trackingRunsLoading.value = true
  try {
    const res = await apiFetch('/longest-tracking/runs')
    const data = await res.json()
    trackingRuns.value = data.runs || []
  } catch (e) {
    trackingRuns.value = []
  } finally {
    trackingRunsLoading.value = false
  }
}

async function runTracking() {
  if (trackingMinN.value < 1 || trackingMaxN.value > 49 || trackingMinN.value > trackingMaxN.value) {
    alert('号数范围无效（1~49，且最小 ≤ 最大）')
    return
  }
  trackingRunning.value = true
  try {
    const res = await apiFetch('/longest-tracking/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: trackingName.value,
        min_n: trackingMinN.value,
        max_n: trackingMaxN.value,
        warmup: trackingWarmup.value,
        years: trackingYears.value,
      }),
    })
    const data = await res.json()
    if (data.ok) {
      $notify(`演算完成！共 ${data.total_results} 个方案，等额盈利 ${data.eq_profitable} 个，倍投盈利 ${data.bt_profitable} 个`)
      await openTrackingRun(data.run_id)
    } else {
      $notify('演算失败：' + (data.detail || JSON.stringify(data)), true)
    }
  } catch (e) {
    $notify('演算失败：' + e.message, true)
  } finally {
    trackingRunning.value = false
  }
}

async function openTrackingRun(runId) {
  trackingTab.value = 'detail'
  trackingDetail.value = { id: runId }
  await loadTrackingDetail()
}

async function loadTrackingDetail() {
  const runId = trackingDetail.value.id
  if (!runId) return
  try {
    const res = await apiFetch(`/longest-tracking/runs/${runId}?sort_by=${trackingSortBy.value}`)
    const data = await res.json()
    // 后端返回 { run: {id,name,min_n,...}, results, baseline, algorithms, is_stale }
    // 平铺 run 元数据到顶层，否则 name/id/min_n 取不到
    trackingDetail.value = { ...data.run, ...data }
  } catch (e) {
    $notify('加载演算详情失败：' + e.message, true)
  }
}

// 切换口径（等额/倍投）：若数据有更新且开启自动重算，先重算再加载
async function switchTrackingSort(sortBy) {
  if (trackingSortBy.value === sortBy && trackingDetail.value.results) {
    return
  }
  trackingSortBy.value = sortBy
  if (trackingDetail.value.is_stale && trackingAutoRecalc.value) {
    $notify('检测到数据更新，自动重算中...')
    const ok = await doRecalc(trackingDetail.value.id)
    if (ok) { await loadTrackingDetail() }
    return
  }
  await loadTrackingDetail()
}

// 执行重算（返回是否成功），不弹完成提示
async function doRecalc(runId) {
  if (recalcRunId.value) return false
  recalcRunId.value = runId
  try {
    const res = await apiFetch(`/longest-tracking/runs/${runId}/recalc`, { method: 'POST' })
    const data = await res.json()
    if (data.ok) return true
    $notify('重算失败：' + (data.detail || '未知'), true)
    return false
  } catch (e) {
    $notify('重算失败：' + e.message, true)
    return false
  } finally {
    recalcRunId.value = null
  }
}

// 卡片「手动演算」按钮：重算后刷新列表 + 若正在看该详情则刷新详情
async function recalcRun(runId) {
  $notify('正在重新演算...（约 30~60 秒）')
  const ok = await doRecalc(runId)
  if (ok) {
    $notify('重算完成，结果已更新')
    await loadTrackingRuns()
    if (trackingDetail.value.id === runId) await loadTrackingDetail()
  }
}

// 算法文档
async function openAlgoDoc() {
  try {
    const res = await apiFetch('/longest-tracking/algorithms/doc')
    algoDoc.value = await res.json()
    showAlgoDoc.value = true
  } catch (e) {
    $notify('加载算法文档失败：' + e.message, true)
  }
}

// 跟踪持有：锁定最冷 1 号，gap≥theta 进场，跟踪 K 期直到命中/止损
function openTrackingHold() {
  trackingTab.value = 'hold'
  if (!holdResult.value) analyzeTrackingHold()
  loadHoldLive()
}
async function analyzeTrackingHold() {
  holdLoading.value = true
  try {
    const res = await apiFetch(`/tracking-hold/analyze?theta=${holdTheta.value}&K=${holdK.value}&signal=${holdSignal.value}&min_votes=${holdMinVotes.value}`)
    holdResult.value = await res.json()
  } catch (e) {
    $notify('跟踪持有分析失败：' + e.message, true)
  } finally {
    holdLoading.value = false
  }
  loadHoldLive()
  loadHoldRounds()
}
async function loadHoldLive() {
  try {
    const res = await apiFetch(`/tracking-hold/live?theta=${holdTheta.value}&K=${holdK.value}&signal=${holdSignal.value}&min_votes=${holdMinVotes.value}&tail=20`)
    holdLive.value = await res.json()
  } catch (e) {
    holdLive.value = null
  }
}
async function loadHoldRounds() {
  try {
    const res = await apiFetch(`/tracking-hold/rounds?theta=${holdTheta.value}&K=${holdK.value}&signal=${holdSignal.value}&min_votes=${holdMinVotes.value}`)
    holdRounds.value = await res.json()
  } catch (e) {
    holdRounds.value = null
  }
}
// 切换进场信号：自动调整阈值默认值
function switchHoldSignal(s) {
  if (holdSignal.value === s) return
  holdSignal.value = s
  if (s === 'ratio') holdTheta.value = 0.8
  else if (s === 'gap') holdTheta.value = 10
  holdResult.value = null
  holdLive.value = null
  analyzeTrackingHold()
}
// 资金曲线 Canvas 绘制
function drawEquityCurve(canvas, curve) {
  if (!canvas || !curve || curve.length < 2) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  const W = canvas.clientWidth || 600
  const H = canvas.clientHeight || 120
  canvas.width = W * dpr
  canvas.height = H * dpr
  ctx.scale(dpr, dpr)
  ctx.clearRect(0, 0, W, H)
  const min = Math.min(...curve)
  const max = Math.max(...curve)
  const range = (max - min) || 1
  const pad = 8
  const x = i => pad + (W - pad * 2) * i / (curve.length - 1)
  const y = v => H - pad - (H - pad * 2) * (v - min) / range
  // 零轴
  if (min < 0 && max > 0) {
    const y0 = y(0)
    ctx.strokeStyle = '#e0e0e0'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(pad, y0); ctx.lineTo(W - pad, y0); ctx.stroke()
  }
  // 曲线
  ctx.strokeStyle = curve[curve.length - 1] >= 0 ? '#0f9f45' : '#ef4444'
  ctx.lineWidth = 1.5
  ctx.beginPath()
  curve.forEach((v, i) => { i === 0 ? ctx.moveTo(x(i), y(v)) : ctx.lineTo(x(i), y(v)) })
  ctx.stroke()
  // 面积
  ctx.fillStyle = 'rgba(15,159,69,0.08)'
  ctx.beginPath()
  ctx.moveTo(x(0), y(0)); curve.forEach((v, i) => ctx.lineTo(x(i), y(v)))
  ctx.lineTo(x(curve.length - 1), y(0)); ctx.closePath(); ctx.fill()
}
// 分析结果变化后绘制资金曲线
watch(holdResult, async (v) => {
  if (!v || !v.equity_curve) return
  await nextTick()
  drawEquityCurve(equityCanvas.value, v.equity_curve)
})

const eqProfitCount = computed(() => {
  const r = trackingDetail.value.results
  return r ? r.filter(x => x.eq_pnl > 0).length : 0
})
const btProfitCount = computed(() => {
  const r = trackingDetail.value.results
  return r ? r.filter(x => x.bt_pnl > 0).length : 0
})
const bestEqPnl = computed(() => {
  const r = trackingDetail.value.results
  if (!r || !r.length) return 0
  return Math.max(...r.map(x => x.eq_pnl)).toLocaleString()
})

async function deleteTrackingRun(runId) {
  if (!confirm('确认删除本次演算记录？')) return
  try {
    await apiFetch(`/longest-tracking/runs/${runId}`, { method: 'DELETE' })
    trackingTab.value = 'list'
    await loadTrackingRuns()
  } catch (e) {
    $notify('删除失败：' + e.message, true)
  }
}

// ===== 尾数分析 =====
const showAnalysis = ref(false)
const analysisLoading = ref(false)
const analysisData = ref({})
const analysisTable = ref([])
const analysisNextDate = ref('')
const analysisStreaks = ref(null)
const backtestData = ref(null)

function showAnalysisPeriods(group, g) {
  const periods = (g.periods || []).map(p => ({
    start: p.start_date || p.start,
    end: p.end_date || p.end,
  }))
  analysisPeriods.value = {
    label: group === '04' ? '🟢 0-4' : '🔴 5-9',
    len: g.len, count: g.count,
    periods: periods.reverse(),
  }
}
const analysisPeriods = ref(null)

async function openAnalysis() {
  showAnalysis.value = true; analysisLoading.value = true; analysisData.value = {}
  analysisStreaks.value = null; analysisNextDate.value = ''; backtestData.value = null
  try {
    const params = recYear.value ? `?year=${recYear.value}` : ''
    const [res1, res2, res3] = await Promise.all([
      fetch(`${API}/tail-analysis${params}`),
      apiFetch('/draw-analysis/streaks'),
      fetch(`${API}/tail-backtest`),
    ])
    analysisData.value = await res1.json()
    analysisTable.value = analysisData.value.table || []
    // compute next date
    const ld = analysisData.value.latest_date
    if (ld) {
      const d = new Date(ld)
      d.setDate(d.getDate() + 1)
      analysisNextDate.value = d.toISOString().slice(0, 10)
    }
    // streaks
    const sdata = await res2.json()
    if (!sdata.error) analysisStreaks.value = sdata
    // backtest
    const bdata = await res3.json()
    if (!bdata.error) backtestData.value = bdata
  } catch (e) { analysisData.value = { error: e.message } }
  finally { analysisLoading.value = false }
}

// ===== 组别设置 =====
const projects = ref([])
const selPid = ref(null)
const gsColFilter = ref('')
const gsSumFilter = ref('')
const gsRgFilter = ref('')
const gsScopeSummaries = ref([])
const gsScopeRunGroups = ref([])
const gsGroups = ref([])
const showProjForm = ref(false)
const editingProjId = ref(null)
const projForm = ref({ name: '' })
const showGroupForm = ref(false)
const editingGid = ref(null)
const groupForm = ref({ group_name: '', numbersStr: '' })

// 分时段分组表单
const periodGroups = ref([])
const showPeriodForm = ref(false)
const editingPeriodId = ref(null)
const periodForm = ref({ start_date: '', end_date: '' })
const periodNums = reactive({})  // {A:"1,2,3", B:"4,5,6", ...}

// 日期选择器
const showDatePicker = ref(false)
const datePickerSetter = ref(null)  // (val: string) => void
const pickerYear = ref(2024)
const pickerMonth = ref(1)
const pickerDay = ref(1)
const pickerYears = Array.from({length: 21}, (_, i) => 2020 + i)
const calStyle = ref({})  // { top, left, width } 动态定位

// 今天
const now = new Date()
const todayYear = now.getFullYear()
const todayMonth = now.getMonth() + 1
const todayDay = now.getDate()

const weekDays = ['日', '一', '二', '三', '四', '五', '六']

const calDays = computed(() => {
  const firstDay = new Date(pickerYear.value, pickerMonth.value - 1, 1).getDay()
  const daysInMonth = new Date(pickerYear.value, pickerMonth.value, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  return cells
})

function openDatePicker(curVal, setter, event) {
  datePickerSetter.value = setter
  // 定位：获取触发元素的屏幕位置
  const trigger = event.currentTarget || event.target.closest('.date-picker-field')
  if (trigger) {
    const rect = trigger.getBoundingClientRect()
    calStyle.value = {
      position: 'fixed',
      top: rect.bottom + 4 + 'px',
      left: '0',
      right: '0',
      width: '100%',
      maxWidth: '480px',
      margin: '0 auto',
    }
  }
  if (curVal && /^\d{4}-\d{2}-\d{2}$/.test(curVal)) {
    const [y, m, d] = curVal.split('-').map(Number)
    pickerYear.value = y
    pickerMonth.value = m
    pickerDay.value = d
  } else {
    pickerYear.value = todayYear
    pickerMonth.value = todayMonth
    pickerDay.value = todayDay
  }
  showDatePicker.value = true
}

function confirmDatePicker() {
  const mm = String(pickerMonth.value).padStart(2, '0')
  const dd = String(pickerDay.value).padStart(2, '0')
  const dateStr = `${pickerYear.value}-${mm}-${dd}`
  datePickerSetter.value(dateStr)
  showDatePicker.value = false
}

function cancelDatePicker() {
  showDatePicker.value = false
}

// 左移规则表单
const showSimRuleForm = ref(false)
const simRuleForm = ref({ shift: 1 })

function openAddSimRule() {
  simRuleForm.value.shift = 1
  showSimRuleForm.value = true
}

async function saveSimRule() {
  const desc = {1:'L',2:'K',3:'J',4:'I',5:'H',6:'G',7:'F',8:'E',9:'D',10:'C',11:'B',12:'A'}
  const name = `左${simRuleForm.value.shift} (A←${desc[simRuleForm.value.shift]})`
  try {
    // 1. 从API获取该项目当前所有规则并逐一删除
    const oldRes = await fetch(`${API}/sim/rules?project_id=${selPid.value}`)
    const oldRules = await oldRes.json()
    await Promise.all(oldRules.map(r => fetch(`${API}/sim/rules/${r.id}`, { method: 'DELETE' })))
    // 2. 创建新规则
    const res = await fetch(`${API}/sim/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, shift_amount: simRuleForm.value.shift, project_id: selPid.value }),
    })
    if (!res.ok) throw new Error((await res.json()).detail)
    showSimRuleForm.value = false
    loadSimRules()
  } catch (e) { alert(e.message) }
}

async function delSimRule(rid) {
  const ok = await $confirm('确定删除此左移规则？'); if (!ok) return
  try {
    await fetch(`${API}/sim/rules/${rid}`, { method: 'DELETE' })
    loadSimRules()
  } catch (e) { alert('删除失败: ' + e.message) }
}

async function delGroup(gid) {
  const ok = await $confirm('确定删除此组？'); if (!ok) return
  try {
    await fetch(`${API}/groups/${gid}`, { method: 'DELETE' })
    loadGsGroups()
  } catch (e) { console.error(e) }
}

// ===== 分时段分组 =====
async function loadPeriodGroups() {
  if (!selPid.value) return
  try {
    const res = await fetch(`${API}/projects/${selPid.value}/period-groups`)
    periodGroups.value = await res.json()
  } catch (e) { console.error(e) }
}

function openAddPeriod() {
  editingPeriodId.value = null
  periodForm.value = { start_date: '', end_date: '' }
  for (const k of Object.keys(periodNums)) delete periodNums[k]
  showPeriodForm.value = true
}

function editPeriod(pg) {
  editingPeriodId.value = pg.id
  periodForm.value = { start_date: pg.start_date, end_date: pg.end_date }
  for (const k of Object.keys(periodNums)) delete periodNums[k]
  const gj = pg.groups_json || {}
  for (const [g, nums] of Object.entries(gj)) { periodNums[g] = nums.join(',') }
  showPeriodForm.value = true
}

async function savePeriod() {
  try {
    const groupsObj = {}
    for (const [g, ns] of Object.entries(periodNums)) {
      if (ns && ns.trim()) groupsObj[g] = ns.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    }
    const p = {
      project_id: selPid.value,
      start_date: periodForm.value.start_date,
      end_date: periodForm.value.end_date,
      groups_json: JSON.stringify(groupsObj)
    }
    if (editingPeriodId.value) {
      await fetch(`${API}/period-groups/${editingPeriodId.value}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p)
      })
    } else {
      await fetch(`${API}/projects/${selPid.value}/period-groups`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p)
      })
    }
    showPeriodForm.value = false
    loadPeriodGroups()
  } catch (e) { alert('保存失败: ' + e.message) }
}

async function delPeriod(pgid) {
  const ok = await $confirm('确定删除此时段？'); if (!ok) return
  try {
    await fetch(`${API}/period-groups/${pgid}`, { method: 'DELETE' })
    loadPeriodGroups()
  } catch (e) { console.error(e) }
}

async function loadProjects(cid = null) {
  try {
    const url = cid != null ? `${API}/projects?collection_id=${cid}` : `${API}/projects`
    const res = await fetch(url)
    projects.value = await res.json()
    if (projects.value.length && !selPid.value) {
      selPid.value = projects.value[0].id
      loadGsGroups()
    }
  } catch (e) { console.error(e) }
}

async function onGsColChange() {
  gsSumFilter.value = ''
  gsScopeSummaries.value = []
  if (gsColFilter.value) {
    // 加载该集合的汇总列表
    try {
      const r = await fetch(`${API}/collections/${gsColFilter.value}/summaries`)
      gsScopeSummaries.value = await r.json()
    } catch(e) { gsScopeSummaries.value = [] }
  }
  loadProjects(gsColFilter.value || undefined)
}

async function onGsSumChange() {
  gsRgFilter.value = ''
  gsScopeRunGroups.value = []
  if (gsSumFilter.value) {
    // 加载该汇总的记录组列表
    try {
      const r = await fetch(`${API}/summaries/${gsSumFilter.value}/run-groups`)
      gsScopeRunGroups.value = await r.json()
    } catch(e) { gsScopeRunGroups.value = [] }
    // 按汇总筛选项目
    try {
      const r = await fetch(`${API}/scope/projects?summary_id=${gsSumFilter.value}`)
      const data = await r.json()
      projects.value = data.map(p => ({ id: p.project_id, name: p.project_name }))
      if (projects.value.length && !selPid.value) {
        selPid.value = projects.value[0].id
        loadGsGroups()
      }
    } catch(e) { console.error(e) }
  } else {
    // 回到集合级筛选
    loadProjects(gsColFilter.value || undefined)
  }
}

async function onGsRgChange() {
  if (gsRgFilter.value) {
    // 按记录组筛选项目
    try {
      const r = await fetch(`${API}/scope/projects?run_group_id=${gsRgFilter.value}`)
      const data = await r.json()
      projects.value = data.map(p => ({ id: p.project_id, name: p.project_name }))
      if (projects.value.length && !selPid.value) {
        selPid.value = projects.value[0].id
        loadGsGroups()
      }
    } catch(e) { console.error(e) }
  } else {
    // 回到汇总级筛选
    onGsSumChange()
  }
}

function selectProject(pid) {
  selPid.value = pid
  loadGsGroups()
  loadSimRules()
  loadPeriodGroups()
}

async function loadGsGroups() {
  if (!selPid.value) return
  try {
    const res = await fetch(`${API}/projects/${selPid.value}/groups`)
    gsGroups.value = await res.json()
  } catch (e) { console.error(e) }
}

function openAddProject() {
  editingProjId.value = null
  projForm.value = { name: '' }
  showProjForm.value = true
}

function openAddColProject() {
  editingProjId.value = null
  projForm.value = { name: '', collection_id: colSel.value?.id || null }
  showProjForm.value = true
}

function editProjectName() {
  const p = projects.value.find(x => x.id === selPid.value)
  if (!p) return
  editingProjId.value = p.id
  projForm.value = { name: p.name }
  showProjForm.value = true
}

async function saveProject() {
  if (!projForm.value.name) return alert('请输入项目名')
  try {
    const url = editingProjId.value ? `${API}/projects/${editingProjId.value}` : `${API}/projects`
    const method = editingProjId.value ? 'PUT' : 'POST'
    const body = { name: projForm.value.name }
    if (projForm.value.collection_id != null) body.collection_id = projForm.value.collection_id
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
    showProjForm.value = false
    loadProjects()
    if (colSel.value) loadColProjects(colSel.value.id)
  } catch (e) { alert(e.message) }
}

async function delProject() {
  const ok = await $confirm('确定删除此项目？组也将被删除')
  if (!ok) return
  try {
    await fetch(`${API}/projects/${selPid.value}`, { method: 'DELETE' })
    selPid.value = null
    gsGroups.value = []
    loadProjects()
  } catch (e) { console.error(e) }
}

function openAddGroup() {
  editingGid.value = null
  groupForm.value = { group_name: '', numbersStr: '' }
  showGroupForm.value = true
}

function editGroup(g) {
  editingGid.value = g.id
  groupForm.value = { group_name: g.group_name, numbersStr: g.numbers.join(',') }
  showGroupForm.value = true
}

async function saveGroup() {
  if (!groupForm.value.group_name) return alert('请输入组名')
  const nums = groupForm.value.numbersStr.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  if (!nums.length) return alert('请输入有效的数字列表')
  try {
    const url = editingGid.value ? `${API}/groups/${editingGid.value}` : `${API}/groups`
    const method = editingGid.value ? 'PUT' : 'POST'
    const body = editingGid.value
      ? { numbers: nums, group_name: groupForm.value.group_name }
      : { project_id: selPid.value, group_name: groupForm.value.group_name, numbers: nums }
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
    showGroupForm.value = false
    loadGsGroups()
  } catch (e) { alert(e.message) }
}

// ===== 开发规则 =====
const devRules = ref([])
const showRuleForm = ref(false)
const editingRuleId = ref(null)
const ruleForm = ref({ name: '', rule_type: 'rotation', config_json: '{}' })

async function loadDevRules() {
  try {
    const res = await fetch(`${API}/dev-rules`)
    devRules.value = await res.json()
  } catch (e) { console.error(e) }
}

function openAddRule() {
  editingRuleId.value = null
  ruleForm.value = { name: '', rule_type: 'rotation', config_json: '{}' }
  showRuleForm.value = true
}

function openEditRule(r) {
  if (r.is_locked) return alert('规则已锁定，请先解锁')
  editingRuleId.value = r.id
  ruleForm.value = { name: r.name, rule_type: r.rule_type, config_json: r.config_json }
  showRuleForm.value = true
}

async function saveRule() {
  if (!ruleForm.value.name) return alert('请输入规则名称')
  try {
    const url = editingRuleId.value ? `${API}/dev-rules/${editingRuleId.value}` : `${API}/dev-rules`
    const method = editingRuleId.value ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ruleForm.value),
    })
    if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
    showRuleForm.value = false
    loadDevRules()
  } catch (e) { alert(e.message) }
}

async function toggleLock(r) {
  try {
    await fetch(`${API}/dev-rules/${r.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_locked: r.is_locked ? 0 : 1 }),
    })
    loadDevRules()
  } catch (e) { alert((await e.response?.json?.())?.detail || '操作失败') }
}

async function toggleActive(r) {
  try {
    await fetch(`${API}/dev-rules/${r.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: r.is_active ? 0 : 1 }),
    })
    loadDevRules()
  } catch (e) { console.error(e) }
}

async function delRule(id) {
  const ok = await $confirm('确定删除此规则？'); if (!ok) return
  try {
    const res = await fetch(`${API}/dev-rules/${id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error((await res.json()).detail || '删除失败')
    loadDevRules()
  } catch (e) { alert(e.message) }
}

// ===== 次数映射管理 =====
const showMapping = ref(false)
const showClearControl = ref(false)
const allowClear = ref(false)
const mappingList = ref([])
const mapCountN = ref(null)
const mapValue = ref(null)
const editingMapN = ref(null)

async function loadMapping() {
  try {
    const res = await fetch(`${API}/mapping`)
    mappingList.value = await res.json()
  } catch (e) { console.error(e) }
}

function editMapping(m) {
  mapCountN.value = m.count_n
  mapValue.value = m.value
  editingMapN.value = m.count_n
}

async function saveMapping() {
  if (!mapCountN.value || mapValue.value == null) return alert('请填写次数和值')
  try {
    await fetch(`${API}/mapping`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count_n: mapCountN.value, value: mapValue.value }),
    })
    mapCountN.value = null
    mapValue.value = null
    editingMapN.value = null
    loadMapping()
  } catch (e) { alert(e.message) }
}

async function delMapping() {
  const ok = await $confirm(`确定删除次数 ${editingMapN.value} 的映射？`); if (!ok) return
  try {
    await fetch(`${API}/mapping/${editingMapN.value}`, { method: 'DELETE' })
    mapCountN.value = null
    mapValue.value = null
    editingMapN.value = null
    loadMapping()
  } catch (e) { alert(e.message) }
}

// ===== 规则运行 =====
const simRules = ref([])  // all rules
const rulesByProject = ref({})  // {projectId: [rule, ...]}
const simRunId = ref(null)
const simResult = ref(null)
const runSimDialog = ref(false)
const running = ref(false)

// 运行参数
const simProjectIds = ref([])
const simProjectRules = ref({})  // {projectId: ruleId}
const simStart = ref(todayStr)
const simEnd = ref(tomorrowStr)

// 查询参数
const simQProject = ref(null)
const simQStart = ref('2026-01-01')
const simQEnd = ref(todayStr)
const simQPage = ref(1)
const simQItems = ref([])
const simQTotal = ref(0)
const simQPages = ref(1)

const canRun = computed(() => {
  const sel = simProjectIds.value.filter(pid => simProjectRules.value[pid])
  return sel.length > 0 && simStart.value && simEnd.value
})

function onProjCheck(p) {
  // 勾选时自动匹配该项目第一条规则
  if (simProjectIds.value.includes(p.id)) {
    const rules = rulesByProject.value[p.id] || []
    if (rules.length) {
      simProjectRules.value[p.id] = rules[0].id
    }
  } else {
    delete simProjectRules.value[p.id]
  }
}

// 展示天数：默认近30天，可切换展开全部/收起
const simShowAll = ref(false)
const simLast30 = ref(true)

function cycleSimDisplay() {
  if (simShowAll.value) {
    simShowAll.value = false
    simLast30.value = true
  } else if (simLast30.value) {
    simLast30.value = false
    simShowAll.value = true
  } else {
    simLast30.value = true
    simShowAll.value = false
  }
}

const simDisplayDays = computed(() => {
  if (!simResult.value) return []
  let d = simResult.value.daily
  if (!d.length) return []
  // 按查询日期范围过滤
  if (simQStart.value || simQEnd.value) {
    d = d.filter(day => {
      if (simQStart.value && day.date < simQStart.value) return false
      if (simQEnd.value && day.date > simQEnd.value) return false
      return true
    })
  }
  if (!d.length) return []
  if (simShowAll.value) return d
  if (simLast30.value) return d.slice(0, 30)
  return [d[0]]
})

async function loadSimRules() {
  try {
    const [rRes, pRes] = await Promise.all([
      fetch(`${API}/sim/rules`),
      fetch(`${API}/projects`),
    ])
    simRules.value = await rRes.json()
    projects.value = await pRes.json()
    // 按项目分组
    const byP = {}
    for (const r of simRules.value) {
      if (!byP[r.project_id]) byP[r.project_id] = []
      byP[r.project_id].push(r)
    }
    rulesByProject.value = byP
    // 默认全选项目
    if (!simProjectIds.value.length && projects.value.length) {
      simProjectIds.value = projects.value.map(p => p.id)
      projects.value.forEach(p => { if ((byP[p.id]||[]).length) simProjectRules.value[p.id] = byP[p.id][0].id })
    }
    // 默认日期范围
    if (!simStart.value) simStart.value = todayStr
    if (!simEnd.value) simEnd.value = tomorrowStr
    loadSimQuery()
  } catch (e) { console.error(e) }
}

async function loadSimQuery() {
  const params = new URLSearchParams()
  if (simQScope.cachedIds.length) params.set('project_ids', simQScope.cachedIds.join(','))
  if (simQStart.value) params.set('start_date', simQStart.value)
  if (simQEnd.value) params.set('end_date', simQEnd.value)
  params.set('page', simQPage.value)
  params.set('page_size', '15')
  const url = `${API}/sim/results/query?${params}`

  try {
    const res = await fetch(url)
    const data = await res.json()
    simQItems.value = data.items
    simQTotal.value = data.total
    simQPages.value = data.total_pages
    simQPage.value = data.page
  } catch (e) { console.error('查询失败', e) }
}

async function runSimulation() {
  if (!canRun.value) return
  running.value = true
  try {
    const ruleIds = []
    const projIds = []
    for (const pid of simProjectIds.value) {
      if (simProjectRules.value[pid]) {
        projIds.push(pid)
        ruleIds.push(simProjectRules.value[pid])
      }
    }
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 120000)
    const res = await fetch(`${API}/sim/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rule_ids: ruleIds,
        project_ids: projIds,
        start_date: simStart.value,
        end_date: simEnd.value,
      }),
      signal: controller.signal,
    })
    clearTimeout(timeout)
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail) }
    const data = await res.json()
    const runs = data.runs || []
    const skipped = runs.filter(r => r.skipped)
    const generated = runs.filter(r => !r.skipped)
    const totalHits = runs.reduce((s, r) => s + (r.hit_count||0), 0)
    const totalDays = runs.reduce((s, r) => s + (r.total_days||0), 0)
    const pendingTotal = runs.reduce((s, r) => s + (r.pending_count||0), 0)

    let msg = ''
    if (generated.length) {
      msg += `✅ ${generated.length}项目生成完成`
      generated.forEach(r => {
        const tag = r.continued ? '(续)' : '(新)'
        msg += `\n${r.project_name}${tag}: +${r.new_days}天`
      })
    }
    if (skipped.length) {
      msg += `\n⚠️ ${skipped.length}项目已有数据，跳过`
    }
    msg += `\n命中 ${totalHits}/${totalDays - pendingTotal}`
    if (pendingTotal) msg += ` +${pendingTotal}天待开奖`
    $notify(msg)
    runSimDialog.value = false
    simShowAll.value = false
    simLast30.value = true
    if (data.last_run_id) await loadSimRun(data.last_run_id)
    loadSimQuery()
  } catch (e) { $notify(e.message, true) }
  finally { running.value = false }
}

async function loadSimRun(runId) {
  simRunId.value = runId
  simShowAll.value = false
  simLast30.value = true
  try {
    const res = await fetch(`${API}/sim/runs/${runId}`)
    simResult.value = await res.json()
  } catch (e) { console.error(e) }
}

async function delSimRun(runId) {
  const ok = await $confirm('确定删除？'); if (!ok) return
  try {
    await fetch(`${API}/sim/runs/${runId}`, { method: 'DELETE' })
    if (simRunId.value === runId) { simRunId.value = null; simResult.value = null }
    loadSimQuery()
  } catch (e) { console.error(e) }
}

// ===== 数据分析 =====
const anStart = ref(new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10))
const anEnd = ref(todayStr)
const anProject = ref(null)
const anPage = ref(1)
const anPages = ref(1)
const anItems = ref([])
const anCumulative = ref(null)

const totalResult = computed(() => {
  return anItems.value.reduce((sum, it) => sum + (it.result || 0), 0)
})

async function clearAnalysis() {
  const ok = await $confirm('确定清空分析数据？（不影响原始数据记录）'); if (!ok) return
  try {
    await fetch(`${API}/analysis/clear`, { method: 'DELETE' })
    anItems.value = []
    anCumulative.value = null
    alert('已清空')
  } catch (e) { alert('清空失败: ' + e.message) }
}

async function loadAnalysis() {
  const params = new URLSearchParams({
    start_date: anStart.value,
    end_date: anEnd.value,
    page: anPage.value,
    page_size: '50',
  })
  if (anScope.cachedIds.length) params.set('project_ids', anScope.cachedIds.join(','))
  try {
    const res = await fetch(`${API}/analysis?${params}`)
    const data = await res.json()
    anItems.value = data.items
    anPages.value = data.total_pages
    anPage.value = data.page
    anCumulative.value = data.cumulative_sum
  } catch (e) { console.error(e) }
}


// ===== 集合管理 =====
const collections = ref([])
const colSel = ref(null)
const colSubTab = ref('summary')  // 'summary' | 'project'
const colProjects = ref([])

// 初始加载 + 切换时懒加载
watch(view, (v) => {
  if (v === 'collection' && !collections.value.length) loadCollections()
}, { immediate: true })
const sumSel = ref(null)
const rgSel = ref(null)
const summaries = ref([])
const runGroups = ref([])
const rgItems = ref([])
const allSimRules = ref([])

const showColForm = ref(false)
const editingColId = ref(null)
const colForm = ref({ name: '' })

const showSumForm = ref(false)
const sumForm = ref({ name: '' })

const showRgForm = ref(false)
const rgForm = ref({ name: '', project_ids: [] })

const showRunDialog = ref(false)
const runRunning = ref(false)
const runProjectsExpanded = ref(false)
const runForm = ref({ start_date: '2020-03-18', end_date: todayStr })

// Helper: get project name by ID (for editItemsForm project_ids)
function getProjectName(pid) {
  const it = rgItems.value.find(i => i.project_id === pid)
  if (it) return it.project_name
  // fallback: check all projects cache
  const p = allProjects.value.find(p => p.id === pid)
  return p ? p.name : `项目#${pid}`
}

const grid49 = ref(null)
const gridDate = ref('')
const showGridProj = ref(false)
let gridRequestId = 0   // 请求序号，防止竞态
const gridLevel = ref('')
const gridId = ref(null)
const selectedSummaryIds = ref([])  // 选中的汇总ID

function stripGrade(name) {
  return name.replace(/^[A-Z]级\s*/, '')
}
const gridTotalSum = ref(0)
const gridDrawVal = ref(null)
const gridResult = ref(null)

// 记录选择（汇总级：勾选哪些 runGroup 参与 1-49 格计算）
const selectedRunGroupIds = ref([])
const activeRecordId = ref(null)
const recordProjects = ref([])
const showRecordProjects = ref(false)
const selectedProjectIds = ref([])
watch(runGroups, (newVal) => {
  selectedRunGroupIds.value = newVal.map(r => r.id)
  activeRecordId.value = null
  recordProjects.value = []
  showRecordProjects.value = false
})

function toggleRunGroup(id) {
  const idx = selectedRunGroupIds.value.indexOf(id)
  if (idx >= 0) {
    // 至少保留一个
    if (selectedRunGroupIds.value.length <= 1) return
    selectedRunGroupIds.value.splice(idx, 1)
  } else {
    selectedRunGroupIds.value = [...selectedRunGroupIds.value, id]
  }
  // 重新加载汇总级49格（按选中记录组过滤）
  if (sumSel.value) {
    const ids = selectedRunGroupIds.value.join(',')
    loadGrid('summary', sumSel.value.id, gridDate.value, ids ? `run_group_ids=${ids}` : 'run_group_ids=')
  }
}

const activeRecordName = computed(() => {
  const rg = runGroups.value.find(r => r.id === activeRecordId.value)
  return rg?.name || ''
})

function clearActiveRecord() {
  activeRecordId.value = null
  recordProjects.value = []
  showRecordProjects.value = false
  rgSel.value = null
}

async function loadRecordProjects(rgId) {
  // 从已加载的 grid49 同步项目列表（loadGrid 已请求过）
  const g = grid49.value
  if (g?.projects?.length) {
    recordProjects.value = g.projects
    showRecordProjects.value = true
    selectedProjectIds.value = g.projects.map(p => p.project_id)
  } else {
    recordProjects.value = []
    showRecordProjects.value = false
    selectedProjectIds.value = []
  }
}

function toggleProject(pid) {
  const idx = selectedProjectIds.value.indexOf(pid)
  if (idx >= 0) {
    if (selectedProjectIds.value.length <= 1) return
    selectedProjectIds.value.splice(idx, 1)
  } else {
    selectedProjectIds.value = [...selectedProjectIds.value, pid]
  }
  // 重新加载 1-49 格（仅聚合选中项目）
  const rgId = rgSel.value?.id || activeRecordId.value
  if (!rgId) return
  const ids = selectedProjectIds.value.join(',')
  loadGrid('run_group', rgId, gridDate.value, ids ? `project_ids=${ids}` : 'project_ids=')
}

function recalcFormula() {
  const g = grid49.value
  if (!g?.grid?.length) { gridTotalSum.value = 0; gridDrawVal.value = null; gridResult.value = null; return }
  gridTotalSum.value = g.grid.reduce((s, c) => s + (c.value || 0), 0)
  const dn = g.draw_number
  if (dn) {
    const cell = g.grid.find(c => c.n === dn)
    gridDrawVal.value = cell ? cell.value : null
    gridResult.value = gridDrawVal.value != null ? gridDrawVal.value * 47 - gridTotalSum.value : null
  } else {
    gridDrawVal.value = null
    gridResult.value = null
  }
}
watch(grid49, recalcFormula, { deep: true })

// 数字归属：1-49 → 汇总名
const numSummaryMap = ref(null)
const showNumSum = ref(false)
const summaryColorList = ref([])  // [{name, color}]
const SUM_COLORS = [
  '#4da6ff', '#22c55e', '#f59e0b', '#ee0a24', '#8b5cf6', '#06b6d4',
  '#f97316', '#ec4899', '#14b8a6', '#6366f1'
]
function getSumColor(sname) {
  if (!sname) return '#888'
  const idx = summaryColorList.value.findIndex(s => s.name === sname)
  return idx >= 0 ? summaryColorList.value[idx].color : '#888'
}
async function loadNumSummaryMap(cid) {
  try {
    const res = await fetch(API + '/collections/' + cid + '/num-summary-map')
    const data = await res.json()
    numSummaryMap.value = data.map
    if (data.summaries?.length) {
      summaryColorList.value = data.summaries.map((s, i) => ({
        name: s, color: SUM_COLORS[i % SUM_COLORS.length]
      }))
    }
    showNumSum.value = true
  } catch (e) {
    numSummaryMap.value = null
  }
}

const showEditItems = ref(false)
const editItemsForm = ref({ project_ids: [] })
const showProjDetail = ref(false)
const projDetail = ref(null)
const projDrawVal = computed(() => {
  const dn = projDetail.value?.draw_number
  if (!dn || !projDetail.value?.grid) return null
  const cell = projDetail.value.grid.find(g => g.n === dn)
  return cell ? cell.value : null
})
const projResult = computed(() => {
  if (projDrawVal.value == null) return null
  return projDrawVal.value * 47 - (projDetail.value?.total || 0)
})

async function loadCollections() {
  try {
    const res = await fetch(`${API}/collections`)
    collections.value = await res.json()
  } catch (e) { console.error(e) }
}

async function loadColProjects(cid) {
  try {
    const res = await fetch(`${API}/projects?collection_id=${cid}`)
    colProjects.value = await res.json()
  } catch (e) { colProjects.value = [] }
}

async function loadAllSimRules() {
  try {
    const res = await fetch(`${API}/sim/rules`)
    allSimRules.value = await res.json()
  } catch (e) { console.error(e) }
}

async function loadGrid(level, id, date = '', extraParams = '') {
  const reqId = ++gridRequestId
  try {
    let url = level === 'collection' ? `${API}/collections/${id}/grid`
            : level === 'summary' ? `${API}/summaries/${id}/grid`
            : `${API}/run-groups/${id}/grid`
    const params = []
    if (date) params.push(`date=${encodeURIComponent(date)}`)
    if (extraParams) params.push(extraParams)
    if (params.length) url += '?' + params.join('&')
    const res = await fetch(url)
    const data = await res.json()
    if (reqId !== gridRequestId) return  // 已被更新的请求取代，丢弃
    console.log('loadGrid', level, id, 'cells:', data.grid?.length, 'proj:', data.projects?.length)
    grid49.value = data
    gridLevel.value = level
    gridId.value = id
    gridDate.value = date || grid49.value?.last_date || ''
    // run_group 级别：同步项目列表，默认全选
    if (level === 'run_group' && data.projects?.length) {
      // 仅在首次加载（非 toggleProject 过滤时）更新项目列表
      if (!extraParams) {
        recordProjects.value = data.projects
        selectedProjectIds.value = data.projects.map(p => p.project_id)
      }
      showRecordProjects.value = true
    }
  } catch (e) { grid49.value = null }
}

function queryGridDate() {
  if (!gridDate.value || !gridLevel.value || !gridId.value) return
  loadGrid(gridLevel.value, gridId.value, gridDate.value)
}

function copyGrid() {
  if (!grid49.value?.grid?.length) return
  const vals = grid49.value.grid.map(g => g.value).join('\t')
  navigator.clipboard.writeText(vals).then(() => $notify('49值已复制(可粘贴到Excel)'), () => $notify('复制失败', true))
}

function copyTop25() {
  if (!grid49.value?.grid?.length) return
  const sorted = [...grid49.value.grid].sort((a, b) => b.value - a.value)
  const nums = sorted.slice(0, 25).map(g => g.n).join('.')
  navigator.clipboard.writeText(nums).then(() => $notify('前25号码已复制'), () => $notify('复制失败', true))
}

function copyBottom24() {
  if (!grid49.value?.grid?.length) return
  const sorted = [...grid49.value.grid].sort((a, b) => b.value - a.value)
  const nums = sorted.slice(25).map(g => g.n).join('.')
  navigator.clipboard.writeText(nums).then(() => $notify('后24号码已复制'), () => $notify('复制失败', true))
}

function copyValue(val) {
  if (val === null || val === undefined) return
  navigator.clipboard.writeText(String(val)).then(() => $notify(`已复制: ¥${val.toLocaleString()}`))
}

function getValueColor(val) {
  return { color: (val || 0) >= 0 ? '#22c55e' : '#ee0a24', fontWeight: '700' }
}

function getProjGrid(pid) {
  if (!grid49.value?.projects) return {}
  const p = grid49.value.projects.find(p => p.project_id === pid)
  return p ? { date: p.last_date, value: p.value } : {}
}

function backTo(level) {
  // 清除项目选择状态
  activeRecordId.value = null
  recordProjects.value = []
  showRecordProjects.value = false
  selectedProjectIds.value = []
  if (level === 'collections') {
    colSel.value = null; sumSel.value = null; rgSel.value = null; grid49.value = null
  } else if (level === 'summaries') {
    sumSel.value = null; rgSel.value = null; loadGrid('collection', colSel.value.id)
  } else {
    rgSel.value = null; loadGrid('summary', sumSel.value.id)
  }
}

async function selectCollection(c) {
  colSel.value = c; sumSel.value = null; rgSel.value = null; colSubTab.value = 'summary'
  await loadSummaries(c.id)
  selectedSummaryIds.value = summaries.value.map(s => s.id)  // 默认全选
  loadColProjects(c.id)
  loadGrid('collection', c.id)
  loadNumSummaryMap(c.id)
}

function toggleSummary(sid) {
  const found = selectedSummaryIds.value.includes(sid)
  if (found) {
    if (selectedSummaryIds.value.length <= 1) return
    selectedSummaryIds.value = selectedSummaryIds.value.filter(id => id !== sid)
  } else {
    selectedSummaryIds.value = [...selectedSummaryIds.value, sid]
  }
  const ids = selectedSummaryIds.value
  const params = ids.length === 0 ? '' : 'summary_ids=' + ids.join(',')
  loadGrid('collection', colSel.value.id, gridDate.value, params)
}

function selectSummary(s) {
  sumSel.value = s; rgSel.value = null
  loadRunGroups(s.id); loadGrid('summary', s.id)
}

function selectRunGroup(rg) {
  rgSel.value = rg; loadRgItems(rg.id); loadGrid('run_group', rg.id)
  activeRecordId.value = rg.id
}

async function loadSummaries(cid) {
  try {
    const res = await fetch(`${API}/collections/${cid}/summaries`)
    summaries.value = await res.json()
  } catch (e) { console.error(e) }
}

async function loadRunGroups(sid) {
  try {
    const res = await fetch(`${API}/summaries/${sid}/run-groups`)
    runGroups.value = await res.json()
  } catch (e) { console.error(e) }
}

async function loadRgItems(rgid) {
  try {
    const res = await fetch(`${API}/run-groups/${rgid}/items`)
    rgItems.value = await res.json()
  } catch (e) { console.error(e) }
}

function openAddCollection() {
  editingColId.value = null; colForm.value = { name: '' }; showColForm.value = true
}

async function saveCollection() {
  if (!colForm.value.name) return $notify('请输入集合名', true)
  try {
    const url = editingColId.value ? `${API}/collections/${editingColId.value}` : `${API}/collections`
    const method = editingColId.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(colForm.value) })
    if (!res.ok) throw new Error((await res.json()).detail)
    showColForm.value = false; loadCollections()
  } catch (e) { $notify(e.message, true) }
}

async function delCollection(cid) {
  const ok = await $confirm('删除集合将同时删除其下所有汇总和记录组，确定？'); if (!ok) return
  try {
    await fetch(`${API}/collections/${cid}`, { method: 'DELETE' })
    loadCollections(); colSel.value = null; sumSel.value = null; rgSel.value = null; grid49.value = null
  } catch (e) { $notify(e.message, true) }
}

function openAddSummary() {
  sumForm.value = { name: '' }; showSumForm.value = true
}

async function saveSummary() {
  if (!sumForm.value.name) return $notify('请输入汇总名', true)
  try {
    const res = await fetch(`${API}/collections/${colSel.value.id}/summaries`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sumForm.value) })
    if (!res.ok) throw new Error((await res.json()).detail)
    showSumForm.value = false; loadSummaries(colSel.value.id)
  } catch (e) { $notify(e.message, true) }
}

function openAddRunGroup() {
  if (!projects.value.length) loadProjects()
  rgForm.value = { name: `记录${(runGroups.value.length||0)+1}`, project_ids: [] }; showRgForm.value = true
}

function toggleRgProject(pid) {
  const idx = rgForm.value.project_ids.indexOf(pid)
  if (idx >= 0) rgForm.value.project_ids.splice(idx, 1)
  else rgForm.value.project_ids.push(pid)
}

async function saveRunGroup() {
  if (!rgForm.value.name) return $notify('请输入记录名称', true)
  if (!rgForm.value.project_ids.length) return $notify('请选择至少一个项目', true)
  try {
    const res = await fetch(`${API}/summaries/${sumSel.value.id}/run-groups`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(rgForm.value) })
    if (!res.ok) throw new Error((await res.json()).detail)
    const data = await res.json()
    $notify('✅ 创建完成')
    showRgForm.value = false; loadRunGroups(sumSel.value.id)
    rgSel.value = { id: data.run_group_id, name: rgForm.value.name, project_count: rgForm.value.project_ids.length }
    loadRgItems(data.run_group_id)
  } catch (e) { $notify(e.message, true) }
}

async function delRunGroup(rgid) {
  const ok = await $confirm('确定删除此记录组？'); if (!ok) return
  try {
    await fetch(`${API}/run-groups/${rgid}`, { method: 'DELETE' })
    loadRunGroups(sumSel.value.id); rgSel.value = null; loadGrid('summary', sumSel.value.id)
  } catch (e) { $notify(e.message, true) }
}

function openEditItems() {
  if (!projects.value.length) loadProjects()
  editItemsForm.value = { project_ids: rgItems.value.map(it => it.project_id) }
  showEditItems.value = true
}

function toggleEditProject(pid) {
  const idx = editItemsForm.value.project_ids.indexOf(pid)
  if (idx >= 0) editItemsForm.value.project_ids.splice(idx, 1)
  else editItemsForm.value.project_ids.push(pid)
}

async function saveEditItems() {
  try {
    const oldPids = rgItems.value.map(it => it.project_id)
    const newPids = editItemsForm.value.project_ids
    const toAdd = newPids.filter(p => !oldPids.includes(p))
    const toDel = oldPids.filter(p => !newPids.includes(p))
    for (const pid of toDel) {
      const it = rgItems.value.find(x => x.project_id === pid)
      if (it) await fetch(`${API}/run-group-items/${it.id}`, { method: 'DELETE' })
    }
    for (const pid of toAdd) {
      const rule = allSimRules.value.find(r => r.project_id === pid && r.is_active)
      const simRunId = await getActiveSimRunId(pid)
      await fetch(`${API}/run-groups/${rgSel.value.id}/items`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: pid, sim_run_id: simRunId || 0, rule_id: rule?.id || 0 })
      })
    }
    showEditItems.value = false
    loadRgItems(rgSel.value.id)
    loadGrid('run_group', rgSel.value.id)
  } catch (e) { $notify(e.message, true) }
}

async function openProjGrid(it) {
  projDetail.value = null
  showProjDetail.value = true
  try {
    const res = await fetch(`${API}/run-group-items/${it.id}/grid`)
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '请求失败')
    projDetail.value = data
  } catch (e) { $notify('打开失败: ' + e.message, true); showProjDetail.value = false }
}

async function openProjGridFromG49(p) {
  projDetail.value = null
  showProjDetail.value = true
  try {
    const dateParam = gridDate.value ? `?date=${gridDate.value}` : ''
    const res = await fetch(`${API}/projects/${p.project_id}/grid${dateParam}`)
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '请求失败')
    projDetail.value = data
  } catch (e) { $notify('打开失败: ' + e.message, true); showProjDetail.value = false }
}

async function getActiveSimRunId(pid) {
  try {
    const res = await fetch(`${API}/sim/runs?project_id=${pid}`)
    const runs = await res.json()
    return runs.length ? runs[0].id : 0
  } catch (e) { return 0 }
}

async function execRunGroup() {
  if (!runForm.value.start_date || !runForm.value.end_date) return $notify('请选择日期范围', true)
  if (!allSimRules.value.length) await loadAllSimRules()
  runRunning.value = true
  try {
    const pids = editItemsForm.value.project_ids.length ? editItemsForm.value.project_ids : rgItems.value.map(it => it.project_id)
    const rule_ids = []
    for (const pid of pids) {
      const rule = allSimRules.value.find(r => r.project_id === pid && r.is_active)
      rule_ids.push(rule ? rule.id : 0)
    }
    const res = await fetch(`${API}/sim/run`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule_ids, project_ids: pids, start_date: runForm.value.start_date, end_date: runForm.value.end_date })
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '运行失败')

    // 更新项目关联
    for (const run of data.runs || []) {
      if (run.project_id) {
        const existingIt = rgItems.value.find(it => it.project_id === run.project_id)
        if (existingIt) {
          await fetch(`${API}/run-group-items/${existingIt.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sim_run_id: run.run_id })
          })
        }
      }
    }
    $notify(`✅ 运行完成 (${data.runs?.length || 0} 项目)`)
    showRunDialog.value = false
    loadRgItems(rgSel.value.id)
    loadGrid('run_group', rgSel.value.id)
  } catch (e) { $notify(e.message, true) }
  runRunning.value = false
}

function openRunDialog() {
  runForm.value = { start_date: '2020-03-18', end_date: todayStr }
  runProjectsExpanded.value = false
  showRunDialog.value = true
}

// ===== 演算当天 =====
const showTodayRun = ref(false)
const todayRunDate = ref(todayStr)
const todayRunRunning = ref(false)
const trProjectsExpanded = ref(false)
const trL3 = ref('all'), trL2 = ref(''), trL1 = ref('')
const trCID = computed(() => trL3.value !== 'all')
const trSID = computed(() => trCID.value && trL2.value !== '')
const scopeSummaries = ref([])
const scopeRunGroups = ref([])
const scopeProjects = ref([])
const trProgress = reactive({ show: false, step: 0, totalSteps: 0, msg: '', done: 0, total: 0, errors: '' })

const canTodayRun = computed(() => scopeProjects.value.length > 0 && todayRunDate.value)

function openTodayRun() {
  if (!collections.value.length) loadCollections()
  todayRunDate.value = todayStr
  trL3.value = 'all'; trL2.value = ''; trL1.value = ''
  scopeSummaries.value = []; scopeRunGroups.value = []; scopeProjects.value = []
  trProjectsExpanded.value = false
  showTodayRun.value = true
  // 初始即为全项目模式，手动触发加载
  onTrL3Change()
}

async function onTrL3Change() {
  trL2.value = ''; trL1.value = ''; scopeRunGroups.value = []; trProjectsExpanded.value = false
  if (trL3.value === 'all') { scopeSummaries.value = []; await loadTrAllProjects(); return }
  const cid = parseInt(trL3.value.slice(1))
  try { const r = await apiFetch(`/collections/${cid}/summaries`); scopeSummaries.value = await r.json() } catch(e) { scopeSummaries.value = [] }
  loadTrScopeProjects()
}
async function onTrL2Change() {
  trL1.value = ''; scopeRunGroups.value = []
  if (trL2.value) {
    const sid = parseInt(trL2.value.slice(1))
    try { const r = await apiFetch(`/summaries/${sid}/run-groups`); scopeRunGroups.value = await r.json() } catch(e) { scopeRunGroups.value = [] }
  }
  loadTrScopeProjects()
}
async function onTrL1Change() { loadTrScopeProjects() }

async function loadTrAllProjects() {
  try {
    const [pRes, rRes] = await Promise.all([
      apiFetch('/projects'),
      apiFetch('/sim/rules'),
    ])
    const projs = await pRes.json()
    const rules = await rRes.json()
    const byP = {}
    for (const r of rules) {
      if (!byP[r.project_id]) byP[r.project_id] = []
      byP[r.project_id].push(r)
    }
    scopeProjects.value = projs.map(p => ({
      project_id: p.id,
      project_name: p.name,
      rule_name: (byP[p.id] || [])[0]?.name || null,
      rule_id: (byP[p.id] || [])[0]?.id || 0,
    }))
  } catch(e) { scopeProjects.value = [] }
}

async function loadTrScopeProjects() {
  const params = new URLSearchParams()
  if (trL1.value && trL1.value.startsWith('r')) params.set('run_group_id', parseInt(trL1.value.slice(1)))
  else if (trL2.value && trL2.value.startsWith('s')) params.set('summary_id', parseInt(trL2.value.slice(1)))
  else if (trL3.value !== 'all') params.set('collection_id', parseInt(trL3.value.slice(1)))
  try {
    const res = await apiFetch(`/scope/projects?${params}`)
    scopeProjects.value = await res.json()
  } catch (e) { scopeProjects.value = [] }
}

async function execTodayRun() {
  if (!canTodayRun.value) return
  todayRunRunning.value = true
  try {
  // 预检：今天是否已完成
  const checkRes = await apiFetch(`/sim/today-ready?date=${todayRunDate.value}`)
  if (checkRes.ok) {
    const checkData = await checkRes.json()
    if (checkData.total > 0) {
      if (checkData.ready) {
        // 当天抽签数已出来 → 直接跑，不询问
        if (checkData.has_draw) {
          // 直接继续，跳过确认
        } else {
          // 抽签数还没出来，询问是否重新演算
          if (!confirm(`📌 今天已全部演算完成（${checkData.covered}/${checkData.total}）\n\n⚠️ 当天抽签数尚未出来\n\n是否重新演算？`)) {
            todayRunRunning.value = false
            return
          }
        }
      } else {
        // 部分覆盖：提示并确认
        const missingNames = checkData.missing_list || []
        const missingText = missingNames.length <= 3 ? missingNames.join('、') : `${missingNames.slice(0, 3).join('、')}等${missingNames.length}条`
        if (!confirm(`📌 ${checkData.covered}/${checkData.total} 已覆盖，差${checkData.missing}条门店\n\n缺失：${missingText}\n\n是否仍然执行演算？`)) {
          todayRunRunning.value = false
          return
        }
      }
    }
  }
  const pids = scopeProjects.value.map(p => p.project_id)
  const rids = scopeProjects.value.map(p => p.rule_id || 0)
  const total = pids.length
  const CHUNKS = 1
  const chunkSize = Math.ceil(total / CHUNKS)

  // 关掉表单弹窗，开进度弹窗
  showTodayRun.value = false
  Object.assign(trProgress, { show: true, step: 0, totalSteps: CHUNKS, msg: '准备中...', done: 0, total, errors: '' })

  let allRuns = [], allErrors = [], totalHits = 0, totalDays = 0, totalAdjusted = 0

  for (let i = 0; i < CHUNKS; i++) {
    const start = i * chunkSize
    const end = Math.min(start + chunkSize, total)
    if (start >= total) break

    const chunkPids = pids.slice(start, end)
    const chunkRids = rids.slice(start, end)
    const isLastChunk = (i === CHUNKS - 1 || end >= total)

    Object.assign(trProgress, {
      step: i + 1, msg: `正在演算第 ${start+1}-${end} 个项目（共 ${chunkPids.length} 项）...`, done: start
    })

    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 120000)
      const res = await apiFetch('/sim/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_ids: chunkRids,
          project_ids: chunkPids,
          start_date: todayRunDate.value,
          end_date: todayRunDate.value,
          skip_refresh: !isLastChunk  // 最后一批才刷新分析
        }),
        signal: controller.signal,
      })
      clearTimeout(timeout)
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '运行失败')

      const runs = data.runs || []
      const errs = data.errors || []
      totalHits += runs.reduce((s, r) => s + (r.hit_count || 0), 0)
      totalDays += runs.reduce((s, r) => s + (r.total_days || 0), 0)
      totalAdjusted += runs.filter(r => r.message && r.message.includes('调整')).length
      allRuns = allRuns.concat(runs)
      allErrors = allErrors.concat(errs)

      Object.assign(trProgress, { done: end })
      if (errs.length) {
        trProgress.errors = `⚠️ 第${i+1}批: ${errs.length}项失败`
      }
    } catch (e) {
      allErrors.push({ phase: `batch_${i+1}`, error: e.message })
      trProgress.errors = `❌ 第${i+1}批连接失败: ${e.message}`
    }
  }

  // 最后一批已做 refresh_analysis，这里直接显示结果
  let msg = `✅ 演算完成 ${allRuns.length}项目 · 命中 ${totalHits}/${totalDays}`
  if (allErrors.length) {
    if (allRuns.length === 0) {
      trProgress.errors = allErrors[0].error || '全部失败'
      return
    }
    msg += ` · ⚠️ ${allErrors.length}项失败`
  }
  if (totalAdjusted) msg += ` · ⚠️ ${totalAdjusted}项日期被自动调整`

  Object.assign(trProgress, { step: CHUNKS, done: total, msg, errors: '' })
  $notify(msg)
  if (allErrors.length) console.warn('演算失败项:', allErrors)
  } finally { todayRunRunning.value = false }
}

// ===== 一键清空模拟数据 =====
async function clearAllSimData() {
  if (!confirm('⚠️ 确认清空所有模拟运行数据？此操作不可恢复！')) return
  try {
    const res = await fetch(`${API}/sim/clear-all`, { method: 'DELETE' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '失败')
    $notify('✅ ' + data.message)
    // 刷新规则列表和查询
    loadSimRules()
    loadSimQuery()
  } catch (e) { $notify(e.message, true) }
}

// ===== 共享范围工具 =====
async function loadScopeProjectsCached(scope, cid, sid, rgid) {
  const params = new URLSearchParams()
  if (rgid) params.set('run_group_id', rgid)
  else if (sid) params.set('summary_id', sid)
  else if (cid) params.set('collection_id', cid)
  try {
    const res = await fetch(`${API}/scope/projects?${params}`)
    const data = await res.json()
    scope.cachedIds = data.map(p => p.project_id)
  } catch (e) { scope.cachedIds = [] }
}

// ===== 分析范围 (L3=集合 L2=汇总 L1=记录组) =====
const anL3 = ref('all'), anL2 = ref(''), anL1 = ref('')
const anCID = computed(() => anL3.value !== 'all')
const anSID = computed(() => anCID.value && anL2.value !== '')
const anScope = reactive({ cachedIds: [] })
const anScopeSummaries = ref([])
const anScopeRunGroups = ref([])

async function onAnL3Change() {
  anL2.value = ''; anL1.value = ''; anScopeRunGroups.value = []
  if (anL3.value === 'all') { anScopeSummaries.value = []; anScope.cachedIds = []; anPage.value = 1; loadAnalysis(); return }
  const cid = parseInt(anL3.value.slice(1))
  try { const r = await fetch(`${API}/collections/${cid}/summaries`); anScopeSummaries.value = await r.json() } catch(e) { anScopeSummaries.value = [] }
  await loadScopeProjectsCached(anScope, cid, null, null)
  anPage.value = 1; loadAnalysis()
}
async function onAnL2Change() {
  anL1.value = ''; anScopeRunGroups.value = []
  const cid = parseInt(anL3.value.slice(1))
  let sid = null
  if (anL2.value) {
    sid = parseInt(anL2.value.slice(1))
    try { const r = await fetch(`${API}/summaries/${sid}/run-groups`); anScopeRunGroups.value = await r.json() } catch(e) { anScopeRunGroups.value = [] }
  }
  await loadScopeProjectsCached(anScope, cid, sid, null)
  anPage.value = 1; loadAnalysis()
}
async function onAnL1Change() {
  const sid = anL2.value ? parseInt(anL2.value.slice(1)) : null
  const rgid = anL1.value ? parseInt(anL1.value.slice(1)) : null
  await loadScopeProjectsCached(anScope, null, sid, rgid)
  anPage.value = 1; loadAnalysis()
}

// ===== 演算查询范围 =====
const simQL3 = ref('all'), simQL2 = ref(''), simQL1 = ref('')
const simQCID = computed(() => simQL3.value !== 'all')
const simQSID = computed(() => simQCID.value && simQL2.value !== '')
const simQScope = reactive({ cachedIds: [] })
const simQScopeSummaries = ref([])
const simQScopeRunGroups = ref([])

async function onSimQL3Change() {
  simQL2.value = ''; simQL1.value = ''; simQScopeRunGroups.value = []
  if (simQL3.value === 'all') { simQScopeSummaries.value = []; simQScope.cachedIds = []; simQPage.value = 1; loadSimQuery(); return }
  const cid = parseInt(simQL3.value.slice(1))
  try { const r = await fetch(`${API}/collections/${cid}/summaries`); simQScopeSummaries.value = await r.json() } catch(e) { simQScopeSummaries.value = [] }
  await loadScopeProjectsCached(simQScope, cid, null, null)
  simQPage.value = 1; loadSimQuery()
}
async function onSimQL2Change() {
  simQL1.value = ''; simQScopeRunGroups.value = []
  const cid = parseInt(simQL3.value.slice(1))
  let sid = null
  if (simQL2.value) {
    sid = parseInt(simQL2.value.slice(1))
    try { const r = await fetch(`${API}/summaries/${sid}/run-groups`); simQScopeRunGroups.value = await r.json() } catch(e) { simQScopeRunGroups.value = [] }
  }
  await loadScopeProjectsCached(simQScope, cid, sid, null)
  simQPage.value = 1; loadSimQuery()
}
async function onSimQL1Change() {
  const sid = simQL2.value ? parseInt(simQL2.value.slice(1)) : null
  const rgid = simQL1.value ? parseInt(simQL1.value.slice(1)) : null
  await loadScopeProjectsCached(simQScope, null, sid, rgid)
  simQPage.value = 1; loadSimQuery()
}

// ===== 演算运行全选 =====
function selectAllProjects() {
  simProjectIds.value = projects.value.map(p => p.id)
  projects.value.forEach(p => { if (!simProjectRules.value[p.id] && (rulesByProject.value[p.id]||[]).length) simProjectRules.value[p.id] = rulesByProject.value[p.id][0].id })
}
function deselectAllProjects() {
  simProjectIds.value = []
  simProjectRules.value = {}
}

// 盈亏 — 单日 (v0704to)
const pfL3 = ref('all'), pfL2 = ref(''), pfL1 = ref('')
const pfCID = computed(() => pfL3.value !== 'all')
const pfSID = computed(() => pfCID.value && pfL2.value !== '')
const pfSummaries = ref([]), pfRunGroups = ref([])
const pfDate = ref(todayStr)
const pfEnd = ref(todayStr)
const pfRange = ref(false)
const pfPage = ref(1), pfPages = ref(1)
const pfItems = ref([])
const pfSummary = ref(null)
const pfLevel = ref('projects')
const pfSearched = ref(false)

const sortedPfSummaries = computed(() => {
  if (pfLevel.value !== 'summaries') return pfItems.value
  return [...pfItems.value].sort((a, b) => {
    const na = parseInt((a.name||'').match(/\d+/)?.[0] || '999')
    const nb = parseInt((b.name||'').match(/\d+/)?.[0] || '999')
    return na - nb
  })
})

function copyTotalResult() {
  if (pfSummary.value) {
    navigator.clipboard.writeText(String(pfSummary.value.total_result))
    $notify('✅ 已复制总结果')
  }
}

function copyNum(val) {
  navigator.clipboard.writeText(String(val))
  $notify('✅ 已复制 ' + val.toLocaleString())
}

async function loadProfit() {
  pfSearched.value = true
  // 根据选中层级自动判断 level
  let level = 'projects'
  if (pfL3.value !== 'all' && !pfL2.value) level = 'summaries'
  else if (pfL2.value && !pfL1.value) level = 'run_groups'
  pfLevel.value = level
  const params = new URLSearchParams({ level, page: pfPage.value, page_size: '30' })
  if (pfRange.value) { params.set('start_date', pfDate.value); params.set('end_date', pfEnd.value) }
  else params.set('date', pfDate.value)
  if (pfL1.value && pfL1.value.startsWith('r')) params.set('run_group_id', parseInt(pfL1.value.slice(1)))
  else if (pfL2.value && pfL2.value.startsWith('s')) params.set('summary_id', parseInt(pfL2.value.slice(1)))
  else if (pfL3.value !== 'all') params.set('collection_id', parseInt(pfL3.value.slice(1)))
  try {
    const res = await fetch(`${API}/scope/daily?${params}`)
    const data = await res.json()
    pfItems.value = data.items; pfPages.value = data.total_pages; pfPage.value = data.page; pfSummary.value = data.summary || null
  } catch (e) { console.error(e) }
}
async function onPfL3Change() {
  pfL2.value = ''; pfL1.value = ''; pfRunGroups.value = []
  if (pfL3.value === 'all') { pfSummaries.value = []; pfItems.value = []; pfSearched.value = false; return }
  const cid = parseInt(pfL3.value.slice(1))
  try { const r = await fetch(`${API}/collections/${cid}/summaries`); pfSummaries.value = await r.json() } catch(e) { pfSummaries.value = [] }
  pfPage.value = 1; loadProfit()
}
async function onPfL2Change() {
  pfL1.value = ''; pfRunGroups.value = []
  if (pfL2.value) {
    const sid = parseInt(pfL2.value.slice(1))
    try { const r = await fetch(`${API}/summaries/${sid}/run-groups`); pfRunGroups.value = await r.json() } catch(e) { pfRunGroups.value = [] }
  }
  pfPage.value = 1; loadProfit()
}
async function onPfL1Change() { pfPage.value = 1; loadProfit() }
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f0f4f8; }
.app { min-height: 100vh; padding-bottom: 40px; }
.top-bar {
  background: linear-gradient(135deg, #1a2a4a, #0a1628);
  color: #fff; padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: center;
}
.tb-title { font-size: 17px; font-weight: 700; }
.tb-date { font-size: 12px; color: #8899bb; display: flex; align-items: center; gap: 6px; }
.tb-logout { font-size: 11px; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,.2); background: transparent; color: #8899bb; cursor: pointer; transition: all .15s; }
.tb-logout:hover { border-color: #ff6b6b; color: #ff6b6b; }

.view-tabs {
  display: flex; gap: 3px; padding: 6px 8px;
  background: #f0f4f8; position: sticky; top: 0; z-index: 10;
}
.view-tabs button {
  flex: 1; min-width: 0; padding: 6px 0; border-radius: 16px;
  font-size: 12px; font-weight: 600; cursor: pointer; transition: all .2s;
  border: 1px solid #dde3ea; background: #fff; color: #66788a;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
  white-space: nowrap; font-family: inherit; text-align: center;
}
.view-tabs button:active:not(.active) {
  background: #e8ecf1; transform: scale(.96);
}
.view-tabs button.active {
  background: linear-gradient(135deg, #1a2a4a, #2d4a7a);
  color: #fff; border-color: #1a2a4a;
  box-shadow: 0 3px 8px rgba(26,42,74,.35), 0 0 0 2px rgba(77,166,255,.25);
  transform: translateY(-1px);
}

/* 卡片 */
.card { background: #fff; border-radius: 12px; padding: 14px; margin: 8px 12px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.card-title { font-size: 14px; font-weight: 700; color: #1a2a4a; margin-bottom: 10px; }

/* ===== 数据记录 ===== */
.records-view { padding: 0 12px 40px; }
.rec-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 4px 10px; flex-wrap: wrap; gap: 8px; }
.rec-header-actions { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.rec-title { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.fab-drag {
  position: fixed; z-index: 999;
  width: 52px; height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4da6ff, #1a2a4a);
  color: #fff; font-size: 28px; font-weight: 700; line-height: 1;
  border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(26, 42, 74, .4);
  touch-action: none;
  user-select: none; -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
}
.fab-drag:active { transform: scale(.92); }
.btn-add {
  padding: 8px 18px; background: linear-gradient(135deg, #4da6ff, #1a2a4a);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.rec-btn-analysis {
  padding: 6px 12px; background: linear-gradient(135deg, #8b5cf6, #6366f1);
  color: #fff; border: none; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
  white-space: nowrap;
}
.rec-btn-analysis:active { transform: scale(.95); }
.rec-empty { text-align: center; padding: 40px 0; color: #bbb; font-size: 14px; }
.sync-warning-bar { display: flex; align-items: center; gap: 8px; padding: 8px 4px 12px; flex-wrap: wrap; }
.sync-warning-label { font-size: 13px; font-weight: 600; color: #7c4dff; white-space: nowrap; }
.sync-date-input { width: auto; padding: 6px 8px; font-size: 12px; min-width: 118px; }
.sync-warning-sep { color: #999; font-size: 12px; }
.sync-warning-btn { padding: 6px 14px; font-size: 12px; }
.sync-warning-btn:disabled { opacity: .6; }
.rec-list { display: flex; flex-direction: column; gap: 6px; }
.rec-row {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-radius: 10px; padding: 12px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.rec-info { display: flex; align-items: center; gap: 12px; }
.rec-date { font-size: 13px; font-weight: 600; color: #1a2a4a; }
.rec-seq { font-size: 11px; color: #8899b0; background: #f0f4f8; padding: 2px 8px; border-radius: 6px; }
.rec-draw { font-size: 13px; color: #4da6ff; }
.rec-draw b { font-size: 16px; }
.rec-actions { display: flex; gap: 4px; }
.rec-btn { width: 34px; height: 34px; border-radius: 8px; border: none; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.rec-btn.edit { background: #eef3ff; }
.rec-btn.del { background: #fff0f0; }
.rec-btn:active { transform: scale(.92); }

.rec-pager { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 16px 0; }
.rec-pager button {
  padding: 8px 16px; border: 1px solid #dde3ea; border-radius: 8px;
  background: #fff; font-size: 13px; color: #1a2a4a; cursor: pointer;
}
.rec-pager button:disabled { opacity: .4; cursor: default; }
.rec-pager span { font-size: 12px; color: #8899b0; }

/* 弹窗 */
.form-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 100;
  display: flex; align-items: flex-start; justify-content: center;
  padding: 40px 12px; overflow-y: auto;
}
.form-card {
  width: min(92vw, 640px); background: #fff; border-radius: 16px; padding: 24px 20px 20px;
  box-shadow: 0 8px 40px rgba(0,0,0,.15); max-height: calc(100vh - 80px);
  overflow-y: auto; margin: auto;
}
/* Toast */
.toast {
  position: fixed; top: 60px; left: 50%; transform: translateX(-50%);
  background: #1a2a4a; color: #fff; padding: 12px 20px; border-radius: 10px;
  font-size: 13px; z-index: 2001; white-space: pre-line; text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,.2); max-width: 90vw; animation: toastIn .3s;
}
.toast.error { background: #ee0a24; }
@keyframes toastIn { from { opacity: 0; transform: translateX(-50%) translateY(-10px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
.form-title { font-size: 17px; font-weight: 700; color: #1a2a4a; margin-bottom: 16px; }
.form-fields label { display: block; font-size: 12px; color: #8899b0; margin-bottom: 4px; margin-top: 12px; }
.form-fields label:first-child { margin-top: 0; }
.form-hint { font-weight: 400; color: #ccc; }
.form-input {
  width: 100%; padding: 10px 12px; border: 1px solid #dde3ea; border-radius: 10px;
  font-size: 14px; background: #f8fafc; outline: none;
}
.form-input:focus { border-color: #4da6ff; background: #fff; }
.form-input:disabled { color: #999; }
.form-btns { display: flex; gap: 10px; margin-top: 20px; }
.btn-cancel, .btn-submit {
  flex: 1; padding: 12px; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; border: none;
}
.btn-cancel { background: #f5f7fa; color: #8899b0; }
.btn-submit { background: linear-gradient(135deg, #4da6ff, #1a2a4a); color: #fff; }

/* ===== 组别设置 ===== */
.groupset-view { padding: 0 12px 40px; }
.gs-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 4px 10px; }
.gs-title { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.gs-projects { display: flex; gap: 8px; padding: 0 4px 12px; flex-wrap: wrap; }
.gs-pill {
  padding: 6px 16px; border-radius: 16px; background: #f0f4f8;
  font-size: 13px; color: #8899b0; cursor: pointer; font-weight: 600;
  transition: all .2s;
}
.gs-pill.active { background: linear-gradient(135deg, #4da6ff, #1a2a4a); color: #fff; }
.gs-empty { text-align: center; padding: 40px 0; color: #bbb; font-size: 14px; }
.gs-groups { margin-top: 4px; }
.gs-group-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 4px; font-size: 13px; color: #8899b0; font-weight: 600; }
.btn-add-sm {
  padding: 4px 12px; border-radius: 8px; background: #eef3ff; color: #4da6ff;
  border: none; font-size: 12px; font-weight: 600; cursor: pointer;
}
.gs-group-row {
  display: flex; align-items: center; gap: 10px;
  background: #fff; border-radius: 10px; padding: 10px 12px; margin-bottom: 4px;
  box-shadow: 0 1px 2px rgba(0,0,0,.03); cursor: pointer;
}
.gs-gname { font-size: 14px; font-weight: 700; color: #1a2a4a; min-width: 28px; }
.gs-gnums { flex: 1; font-size: 12px; color: #4da6ff; }
.gs-del { background: none; border: none; font-size: 14px; cursor: pointer; padding: 4px; }
.gs-actions { display: flex; gap: 8px; margin-top: 14px; }
.btn-del-proj {
  flex: 1; padding: 10px; border-radius: 10px; border: none; font-size: 13px;
  font-weight: 600; cursor: pointer; background: #f0f4f8; color: #1a2a4a;
  min-height: 44px; /* 平板友好触摸区 */
}
.btn-del-proj.danger { background: #fff0f0; color: #ee0a24; }

/* ===== 开发规则 ===== */
.rules-view { padding: 0 12px 40px; }
.rule-card {
  display: flex; justify-content: space-between; align-items: center;
  background: #fff; border-radius: 10px; padding: 12px 14px; margin-bottom: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.rule-card.locked { background: #fffdf0; border-left: 3px solid #ffd700; }
.rule-card.active { border-left: 3px solid #22c55e; }
.rule-card.locked.active { border-left: 3px solid #22c55e; }
.rule-info { flex: 1; }
.rule-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.rule-name { font-size: 14px; font-weight: 700; color: #1a2a4a; }
.rule-type { font-size: 11px; background: #eef3ff; color: #4da6ff; padding: 2px 8px; border-radius: 6px; }
.rule-tags { display: flex; gap: 6px; }
.tag { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600; }
.tag.locked { background: #fff8e1; color: #f59e0b; }
.tag.active { background: #f0fdf4; color: #22c55e; }
.tag.inactive { background: #f5f5f5; color: #bbb; }
.rule-actions { display: flex; gap: 4px; flex-shrink: 0; }
.r-btn {
  width: 32px; height: 32px; border-radius: 8px; border: none;
  font-size: 14px; cursor: pointer; background: #f0f4f8;
  display: flex; align-items: center; justify-content: center;
}
.r-btn:disabled { opacity: .3; cursor: not-allowed; }
.r-btn.del { background: #fff0f0; }

.rule-ta { font-family: monospace; font-size: 12px; resize: vertical; }

/* ===== 规则模拟 ===== */
.sim-view { padding: 0 12px 40px; }
.sim-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 4px 10px; }
.sim-title { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.sim-params { padding: 14px; }
.sim-query { padding: 10px 14px; }
.sim-param-row { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.sim-param-row label { font-size: 12px; color: #8899b0; white-space: nowrap; min-width: 36px; }
.sim-subtitle { font-size: 14px; font-weight: 700; color: #1a2a4a; padding: 16px 4px 8px; }
.sim-subtitle-sm { font-size: 12px; font-weight: 700; color: #8899b0; padding: 8px 0 4px; }
.sim-history { margin-top: 4px; padding-bottom: 12px; }
.sim-proj-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 8px; margin-bottom: 6px;
  border: 1px solid #e8ecf1; transition: all .15s;
}
.sim-proj-row.active { border-color: #4da6ff; background: #eef3ff; }
.sim-cb { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #1a2a4a; cursor: pointer; white-space: nowrap; }
.sim-cb input[type=checkbox] { width: 18px; height: 18px; accent-color: #4da6ff; }
.sim-run-card {
  display: flex; align-items: center;
  background: #fff; border-radius: 10px; padding: 12px 14px; margin-bottom: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.sim-run-card.active { border-left: 3px solid #4da6ff; background: #eef3ff; }
.sim-run-main { flex: 1; cursor: pointer; }
.sim-run-top { display: flex; justify-content: space-between; align-items: center; }
.sim-run-pill {
  font-size: 11px; background: #eef3ff; color: #4da6ff;
  padding: 2px 8px; border-radius: 8px; font-weight: 700; white-space: nowrap;
}
.sim-run-name { font-size: 14px; font-weight: 600; color: #1a2a4a; }
.sim-run-hit { font-size: 16px; font-weight: 700; }
.sim-run-date { font-size: 11px; color: #8899b0; margin-top: 4px; }
.sim-summary { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.sim-day { padding: 12px; }
.sim-day-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.sim-day-date { font-size: 13px; font-weight: 700; color: #1a2a4a; }
.sim-day-draw { font-size: 13px; color: #4da6ff; }
.sim-day-draw b { font-size: 16px; }
.sim-hit-tag {
  font-size: 11px; background: #f0fdf4; color: #22c55e;
  padding: 2px 8px; border-radius: 8px; font-weight: 700;
}
.sim-hit-tag.miss { background: #fff0f0; color: #ee0a24; }
.sim-hit-tag.pending { background: #fff8e1; color: #f59e0b; }
.sim-day-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.sim-gcell {
  background: #f8fafc; border-radius: 8px; padding: 6px; text-align: center;
  border: 1.5px solid transparent; transition: all .15s;
}
.sim-gcell.hit { border-color: #22c55e; background: #f0fdf4; }
.sim-gname { font-size: 13px; font-weight: 700; color: #1a2a4a; }
.sim-gcount { font-size: 18px; font-weight: 700; color: #4da6ff; margin: 2px 0; }
.sim-gcell.hit .sim-gcount { color: #22c55e; }
.sim-gvalue { font-size: 13px; font-weight: 800; color: #f59e0b; margin-bottom: 2px; }
.sim-gcell.hit .sim-gvalue { color: #22c55e; }
.sim-gnums { font-size: 9px; color: #8899b0; word-break: break-all; }
.sim-hint { font-size: 13px; color: #8899b0; white-space: nowrap; }

.sim-del-btn {
  width: 32px; height: 32px; border-radius: 8px; border: none;
  font-size: 14px; cursor: pointer; background: #fff0f0;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-left: 8px;
}
.sim-del-btn:active { transform: scale(.9); }

.sim-pager { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 10px 0; }
.sim-pager button {
  padding: 6px 14px; border: 1px solid #dde3ea; border-radius: 8px;
  background: #fff; font-size: 13px; color: #1a2a4a; cursor: pointer;
}
.sim-pager button:disabled { opacity: .4; cursor: default; }
.sim-pager span { font-size: 12px; color: #8899b0; }
.pager-select {
  padding: 4px 8px; border: 1px solid #dde3ea; border-radius: 6px;
  background: #fff; font-size: 12px; color: #1a2a4a; max-width: 80px;
}

/* 按钮动画 */
.btn-add.running { opacity: 0.7; pointer-events: none; }
.btn-spin {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,.3); border-top-color: #fff;
  border-radius: 50%; animation: btn-spin .6s linear infinite;
  vertical-align: middle; margin-right: 4px;
}
@keyframes btn-spin { to { transform: rotate(360deg); } }
.sim-run-btn {
  width: 100%; margin-top: 10px; position: relative;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.sim-run-btn:disabled { opacity: 0.6; cursor: not-allowed; }

/* ===== 数据分析 ===== */
.analysis-view { padding: 0 12px 40px; }
.an-summary { display: flex; justify-content: space-between; align-items: center; }
.an-summary b { font-size: 22px; color: #4da6ff; }
.an-table-wrap { overflow-x: auto; margin-top: 8px; }
.an-table { min-width: 660px; }
.an-tr { display: grid; grid-template-columns: 80px 36px 55px 32px 36px 36px 48px 70px 60px 72px; gap: 2px; align-items: center; padding: 6px 4px; font-size: 12px; border-bottom: 1px solid #eef1f5; }
.an-th { font-weight: 700; color: #8899b0; font-size: 11px; background: #f8fafc; border-radius: 8px 8px 0 0; }
.an-tr span { text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.an-tr span:first-child { text-align: left; color: #1a2a4a; font-weight: 600; }
.an-num { color: #4da6ff; font-weight: 600; }
.an-result { font-weight: 700; color: #22c55e; }
.an-result.neg { color: #ee0a24; }

/* ===== 次数映射 ===== */
.mapping-section { margin-top: 16px; border: 1px solid #e8ecf1; border-radius: 12px; overflow: hidden; }
.mapping-header { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #f8fafc; cursor: pointer; font-size: 14px; font-weight: 600; color: #1a2a4a; }
.mapping-arrow { font-size: 11px; color: #8899b0; }
.mapping-body { padding: 10px 12px; background: #fff; }
.mapping-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 4px; max-height: 300px; overflow-y: auto; margin-bottom: 10px; }
.mapping-item { display: flex; align-items: center; gap: 3px; padding: 4px 6px; background: #f0f4f8; border-radius: 6px; font-size: 12px; cursor: pointer; }
.mapping-item:active { background: #dde3ea; }
.m-count { font-weight: 700; color: #1a2a4a; min-width: 18px; }
.m-arrow { color: #8899b0; font-size: 10px; }
.m-value { color: #4da6ff; font-weight: 600; }
.mapping-add-row { display: flex; gap: 8px; align-items: center; }

/* ===== 日历选择器 ===== */
.date-picker-field {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border: 1px solid #dde3ea; border-radius: 8px;
  background: #fff; font-size: 14px; color: #1a2a4a; cursor: pointer;
  min-height: 40px;
}
.date-picker-field:active { background: #f0f4f8; }
.date-picker-sm { padding: 6px 8px; font-size: 11px; min-height: 32px; border-radius: 6px; }
.date-arrow { font-size: 16px; color: #8899b0; }
.date-picker-overlay { display: none; }  /* 旧样式废弃 */
.cal-dropdown {
  position: fixed; z-index: 2000;
  /* top/left/width 由 JS calStyle 动态设置 */
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,.18);
  overflow: hidden;
}
.cal-body {
  padding-bottom: 12px;
}
@keyframes dp-slide-up { from { transform: translateY(100%); } to { transform: translateY(0); } }
.cal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #eef1f5;
}
.cal-title { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.cal-ym {
  display: flex; gap: 10px; padding: 14px 16px 10px;
}
.cal-select {
  flex: 1; padding: 8px 10px; border: 1px solid #dde3ea; border-radius: 8px;
  font-size: 15px; color: #1a2a4a; background: #f8fafc; appearance: auto;
  text-align: center;
}
.cal-weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr);
  padding: 0 16px; margin-bottom: 4px;
}
.cal-weekdays span {
  text-align: center; font-size: 12px; font-weight: 600;
  color: #8899b0; padding: 8px 0;
}
.cal-grid {
  display: grid; grid-template-columns: repeat(7, 1fr);
  padding: 0 16px; gap: 2px;
}
.cal-day {
  text-align: center; padding: 10px 0; font-size: 15px; color: #1a2a4a;
  border-radius: 8px; cursor: pointer; transition: all .12s;
}
.cal-day.empty { cursor: default; }
.cal-day:active:not(.empty) { background: #f0f4f8; }
.cal-day.today { color: #4da6ff; font-weight: 600; }
.cal-day.active {
  background: #4da6ff; color: #fff; font-weight: 700;
}
.cal-day.today.active { background: #4da6ff; color: #fff; }
</style>

<style scoped>
/* ===== 集合管理 ===== */
.col-view { padding: 0 12px 40px; }
.col-crumb { display: flex; align-items: center; gap: 6px; padding: 10px 4px; font-size: 13px; color: #8899b0; flex-wrap: wrap; }
.col-crumb span { cursor: pointer; color: #4da6ff; }
.col-crumb .crumb-sep { color: #ccc; cursor: default; }
.col-crumb .crumb-end { color: #1a2a4a; font-weight: 700; cursor: default; }
.col-section-hd { display: flex; justify-content: space-between; align-items: center; padding: 12px 4px 8px; }
.col-section-tl { font-size: 15px; font-weight: 700; color: #1a2a4a; }
.col-card { display: flex; align-items: center; justify-content: space-between; background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.04); cursor: pointer; transition: all .15s; }
.col-card:active { background: #f0f4f8; transform: scale(.98); }
.col-card-left { display: flex; flex-direction: column; gap: 6px; flex: 1; }
.col-card-name { font-size: 14px; font-weight: 700; color: #1a2a4a; }
.col-card-arrow { font-size: 20px; color: #ccc; }
.col-card-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.col-tag { font-size: 11px; padding: 2px 8px; border-radius: 6px; background: #eef3ff; color: #4da6ff; font-weight: 600; }
.col-tag.hit { background: #f0fdf4; color: #22c55e; }
.col-tag.days { background: #f0f4f8; color: #8899b0; }
.col-tag.rule { background: #fff8e1; color: #f59e0b; }
.col-card-hit { font-size: 14px; font-weight: 700; }
.col-card-value { font-size: 15px; flex-shrink: 0; margin: 0 4px; }
.col-del { display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; border: none; font-size: 14px; cursor: pointer; background: #fff0f0; flex-shrink: 0; margin-left: 8px; }
.col-copy-btn { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; border: none; font-size: 12px; cursor: pointer; background: #f0f4f8; flex-shrink: 0; transition: all .15s; }
.col-copy-btn:active { background: #4da6ff22; transform: scale(.9); }
.col-summary { display: flex; justify-content: space-between; align-items: center; font-size: 13px; flex-wrap: wrap; gap: 8px; }
.rg-proj-grid { display: flex; flex-wrap: wrap; gap: 6px; max-height: 200px; overflow-y: auto; padding: 4px 0; }
.rg-proj-pill { padding: 5px 14px; border-radius: 14px; font-size: 13px; background: #f0f4f8; color: #8899b0; cursor: pointer; font-weight: 600; transition: all .15s; }
.rg-proj-pill.active { background: linear-gradient(135deg, #4da6ff, #1a2a4a); color: #fff; }

/* 数字归属 */
.numsum-section { padding: 10px 12px; margin: 8px 0; }
.numsum-hd { font-size: 13px; font-weight: 600; color: #1a2a4a; cursor: pointer; user-select: none; }
.numsum-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; margin-top: 8px; }
.numsum-cell { padding: 6px 0; border-radius: 6px; font-size: 12px; text-align: center; }
.numsum-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.numsum-tag { padding: 2px 10px; border-radius: 10px; font-size: 11px; color: #fff; font-weight: 600; }
/* ===== 49值网格 ===== */
.grid49-section { padding: 12px; margin: 8px 0; }
.grid49-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 13px; flex-wrap: wrap; gap: 4px; }
.grid49-range { display: flex; flex-wrap: wrap; gap: 6px; padding: 2px 0 6px; }
.grid49-range .rg-pill {
  font-size: 12px; padding: 5px 14px; border-radius: 16px;
  background: #1a2035; color: #8899aa; cursor: pointer; font-weight: 500;
  border: 1px solid #243044; transition: all .15s;
}
.grid49-range .rg-pill.active {
  background: #0d3b66; color: #4da6ff; border-color: #4da6ff;
}
.rg-breadcrumb {
  font-size: 13px; color: #4da6ff; font-weight: 600; padding: 4px 0 6px;
}
.grid49-sum { font-weight: 700; font-size: 14px; }
.grid49-table { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
.grid49-cell { font-size: 10px; padding: 4px 2px; border-radius: 6px; background: #f8fafc; display: flex; flex-direction: column; align-items: center; }
.grid49-cell.zero { opacity: .3; }
.g49-n { color: #8899b0; font-size: 9px; }
.g49-v { color: #1a2a4a; font-weight: 700; font-size: 12px; }
.grid49-proj { margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px; }
.g49-proj-title { font-size: 12px; color: #8899b0; cursor: pointer; padding: 4px 0; }
.g49-proj-list { padding: 4px 0; }
.g49-proj-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; font-size: 12px; }
.g49-pv { font-weight: 700; color: #22c55e; }

/* ===== 演算当天 ===== */
.scope-toggle { display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#f0f4f8;border-radius:8px;cursor:pointer;font-size:13px;color:#1a2a4a;user-select:none }
.scope-toggle-arrow { font-size:10px;transition:transform .2s;color:#8899b0 }
.scope-toggle-arrow.open { transform:rotate(90deg) }
.scope-proj-wrap { margin-top:8px }
.scope-proj-row { display:flex;align-items:center;justify-content:space-between;padding:6px 10px;background:#f8fafc;border-radius:8px;margin-bottom:4px;font-size:13px }
.scope-rule-tag { font-size:11px;background:#eef3ff;color:#4da6ff;padding:2px 8px;border-radius:6px }

/* ===== 盈亏表格 ===== */
.pf-summary { background: linear-gradient(135deg, #eef3ff, #f0f4f8); border-bottom: 2px solid #4da6ff; }
.pf-summary td { padding: 10px 8px; }
.pf-clickable { cursor: pointer; transition: background .15s; }
.pf-clickable:hover { background: #f0f4f8; }
.pf-clickable:active { background: #e8ecf1; }
.profit-view { padding: 0 12px 40px; }
.pf-table-wrap { overflow-x: auto; padding: 8px 4px; }
.pf-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.pf-table th, .pf-table td { padding: 8px 6px; text-align: center; border-bottom: 1px solid #e8ecf1; white-space: nowrap; }
.pf-table th { color: #8899b0; font-weight: 600; font-size: 11px; }
.pf-table td:first-child, .pf-table td:nth-child(2) { text-align: left; }
.pf-num { font-weight: 600; color: #1a2a4a; }
.pf-result { font-weight: 700; }

/* ===== 多门店投票 ===== */
.vote-block { border-left: 3px solid #f59e0b !important; margin-top: 12px; }
.vote-store-row { display:flex; flex-wrap:wrap; gap:6px; margin:8px 0; }

/* 全选/清空 切换按钮 */
.vote-tgl-btn {
  padding: 4px 12px; border: 1px solid #e0e0e0; border-radius: 14px;
  background: #fff; color: #8899b0; font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all .2s;
}
.vote-tgl-btn:hover { border-color: #f59e0b; color: #f59e0b; }
.vote-tgl-btn.on { background: #fef3c7; border-color: #f59e0b; color: #b45309; font-weight: 700; }

/* 门店标签 */
.vote-store-cb {
  display:inline-flex; align-items:center; gap:3px;
  padding:3px 8px; border-radius:6px; font-size:12px;
  background:#f0f4f8; color:#8899b0; cursor:pointer;
  transition:all .2s; border:1px solid transparent;
}
.vote-store-cb input { display:none; }
.vote-store-cb.active { background:#fef3c7; color:#b45309; border-color:#f59e0b; font-weight:600; }

/* 控制栏 */
.vote-ctrl-bar {
  background: #fafbfc; border-radius: 10px; padding: 12px;
  margin-top: 10px; display: flex; flex-direction: column; gap: 10px;
}
.vote-ctrl-row {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}

/* 正/负 模式切换 */
.vote-mode-btns {
  display: flex; border-radius: 8px; overflow: hidden;
  border: 1px solid #e0e0e0; flex-shrink: 0;
}
.vote-mode-btns button {
  padding: 6px 14px; border: none; background: #fafafa;
  font-size: 12px; color: #999; cursor: pointer;
  transition: all .2s; font-weight: 500;
}
.vote-mode-btns button:first-child { border-right: 1px solid #e0e0e0; }
.vote-mode-btns button.active { background: #f59e0b; color: #fff; font-weight: 700; }
.vote-mode-btns button:not(.active):hover { background: #fef3c7; color: #b45309; }

/* 共识下拉 */
.vote-select {
  padding: 6px 10px; border: 1px solid #e0e0e0; border-radius: 8px;
  font-size: 12px; background: #fff; color: #555; outline: none;
  cursor: pointer; min-width: 100px;
}
.vote-select:focus { border-color: #f59e0b; }

/* 执行投票 主按钮 */
.vote-submit-btn {
  width: 100%; padding: 10px 0; border: none; border-radius: 10px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #fff; font-size: 14px; font-weight: 700;
  cursor: pointer; transition: all .2s;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  box-shadow: 0 2px 8px rgba(245,158,11,.25);
}
.vote-submit-btn:hover { box-shadow: 0 4px 14px rgba(245,158,11,.35); transform: translateY(-1px); }
.vote-submit-btn:active { transform: scale(.97); box-shadow: 0 1px 4px rgba(245,158,11,.2); }
.vote-submit-icon { font-size: 16px; }
.pf-result.pos { color: #22c55e; }
.pf-result.neg { color: #ee0a24; }
.pf-table tbody tr:hover { background: #f8fafc; }
.export-view { position:fixed; top:100px; left:0; right:0; bottom:0; z-index:10; }
.export-iframe { width:100%; height:100%; border:none; }

/* 汇总选择芯片 */
.sum-chips { display: flex; gap: 8px; flex-wrap: wrap; padding: 6px 0; }
.sum-chip { padding: 8px 18px; border-radius: 12px; font-size: 13px; font-weight: 600;
  background: #1a2035; color: #8899aa; cursor: pointer;
  transition: all .15s; border: 1px solid #243044; user-select: none; }
.sum-chip.active {
  background: #0d3b66; color: #4da6ff; border-color: #4da6ff;
}

/* ===== 阈值视图 ===== */
.th-date-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; margin: 8px 12px 0; }
.th-date-input { flex: 1; padding: 8px 12px; border-radius: 8px; border: 1px solid #d0d5dd; background: #fff; font-size: 14px; color: #1a2a4a; }
.th-draw { font-size: 15px; font-weight: 700; color: #e05a1e; white-space: nowrap; }
.th-doc-link { font-size: 16px; text-decoration: none; line-height: 1; transition: transform .15s; }
.th-doc-link:hover { transform: scale(1.15); }
.th-col19-block { background: #eef4ff; border-radius: 10px; padding: 10px 14px; margin: 8px 12px; }
.th-col19-title { font-size: 13px; font-weight: 600; color: #4da6ff; margin-bottom: 8px; }
.th-col19-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.th-col19-item { display: flex; flex-direction: column; align-items: center; background: #fff; border-radius: 8px; padding: 6px 12px; min-width: 72px; }
.th-col19-name { font-size: 12px; color: #8899b0; }
.th-col19-val { font-size: 14px; font-weight: 700; color: #1a2a4a; }
.th-date-bar { padding: 8px 14px; font-size: 14px; color: #4da6ff; text-align: center; background: #f0f6ff; border-radius: 8px; margin: 8px 12px 0; }
.th-msg { padding: 8px 14px; border-radius: 8px; font-size: 13px; text-align: center; margin: 8px 12px 0; }
.th-msg.ok { background: #0d3320; color: #5ce6a0; }
.th-msg.err { background: #3d1515; color: #e66060; }
.th-block { background: #f5f7fa; border-radius: 12px; padding: 14px; margin: 6px 12px; }
.th-block.th-collection { border-left: 3px solid #4da6ff; }
.th-block-title { font-size: 15px; font-weight: 700; color: #1a2a4a; margin-bottom: 4px; }
.th-summary-val { font-size: 12px; color: #8899b0; font-weight: 400; }
.th-label { font-size: 13px; color: #8899b0; }
.th-copy-btn { background: none; border: 1px solid #ccd5e0; border-radius: 6px; padding: 1px 6px; cursor: pointer; font-size: 12px; opacity: 0.6; transition: opacity .2s; }
.th-copy-btn:hover { opacity: 1; }
.th-copy-btn:active { background: #e8ecf1; }
.th-nums { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.th-num { aspect-ratio: 1; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: clamp(10px, 2.4vw, 13px); font-weight: 700; min-width: 0; }
.th-num.hit { background: #4da6ff; color: #fff; }
.th-num.miss { background: #e8ecf1; color: #8899b0; }

/* ===== 尾数记录分析 ===== */
.tail-view { padding: 0 12px 40px; }
.tail-latest { display: flex; align-items: center; justify-content: center; padding: 14px; margin-bottom: 10px; }
.tail-predict { padding: 14px; margin-bottom: 10px; }
.tail-cards { display: flex; gap: 10px; margin-bottom: 10px; }
.tail-card { flex: 1; background: rgba(255,255,255,0.04); border-radius: 14px; padding: 12px; cursor: pointer; transition: all .15s; border: 1px solid rgba(255,255,255,0.06); }
.tail-card:active { background: rgba(255,255,255,0.08); transform: scale(.98); }
.tail-card-hd { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.tail-card-badge { padding: 2px 10px; border-radius: 10px; font-size: 13px; font-weight: 700; color: #fff; }
.bg-green { background: #16a34a; }
.bg-red { background: #dc2626; }
.tail-card-streak { font-size: 11px; color: #94a3b8; }
.tail-card-list { display: flex; flex-direction: column; gap: 6px; }
.tail-streak-row { display: flex; align-items: center; gap: 6px; font-size: 11px; }
.tail-streak-num { background: rgba(255,255,255,0.08); color: #94a3b8; width: 18px; height: 18px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 600; }
.tail-streak-dates { flex: 1; color: #64748b; }
.tail-streak-len { color: #fbbf24; font-weight: 700; flex-shrink: 0; margin-right: 4px; }
.tail-streak-count { color: #38bdf8; font-weight: 700; cursor: pointer; flex-shrink: 0; padding: 2px 8px; background: rgba(56,189,248,0.12); border-radius: 10px; font-size: 11px; }
.tail-streak-count:hover { background: rgba(56,189,248,0.25); }

/* ===== 最长跟踪演算 ===== */
.tracking-run-card {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
  cursor: pointer;
  transition: all .15s;
  border-left: 3px solid #f59e0b;
}
.tracking-run-card:active { background: #f0f4f8; transform: scale(.98); }
.tracking-stale-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 10px;
  padding: 1px 7px;
  margin-left: 6px;
  vertical-align: middle;
}
.tracking-tab {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all .15s;
}
.tracking-tab.active {
  background: #4da6ff;
  border-color: #4da6ff;
  color: #fff;
}
.tracking-stat {
  flex: 1;
  min-width: 90px;
  background: #fff;
  border-radius: 10px;
  padding: 10px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.tracking-stat-value { font-size: 20px; font-weight: 800; line-height: 1.2; }
.tracking-stat-label { font-size: 11px; color: #8899b0; margin-top: 4px; }
.tracking-table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid #e2e8f0; }
.tracking-table { width: 100%; border-collapse: collapse; font-size: 12px; min-width: 520px; }
.tracking-table th {
  background: #f8fafc;
  color: #64748b;
  font-weight: 700;
  padding: 8px 6px;
  text-align: center;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}
.tracking-table td {
  padding: 7px 6px;
  text-align: center;
  border-bottom: 1px solid #f1f5f9;
  white-space: nowrap;
}
.tracking-table tbody tr:last-child td { border-bottom: none; }
.tracking-row-win { background: rgba(52, 211, 153, 0.06); }
.tracking-algo-name { text-align: left !important; font-weight: 600; color: #1a2a4a; white-space: normal !important; word-break: break-all; }
</style>
