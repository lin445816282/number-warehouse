<template>
  <div class="app">
    <div class="top-bar">
      <span class="tb-title">🔢 数字仓库</span>
      <span class="tb-date">{{ todayStr }}</span>
    </div>

    <!-- 视图切换 -->
    <div class="view-tabs">
      <span :class="{ active: view === 'collection' }" @click="view = 'collection'; loadCollections()">📁 集合</span>
      <span :class="{ active: view === 'analysis' }" @click="view = 'analysis'; loadProjects(); loadAnalysis()">📈 分析</span>
      <span :class="{ active: view === 'sim' }" @click="view = 'sim'; loadSimRules(); loadSimQuery()">🚀 演算</span>
      <span :class="{ active: view === 'profit' }" @click="view = 'profit'; loadCollections(); loadProfit()">💰 盈亏</span>
      <span :class="{ active: view === 'records' }" @click="view = 'records'; loadRecords(); loadYears()">📋 记录</span>
      <span :class="{ active: view === 'groupset' }" @click="view = 'groupset'; loadProjects(); loadSimRules()">⚙ 组别</span>
      <span :class="{ active: view === 'rules' }" @click="view = 'rules'; loadDevRules(); loadMapping()">📐 规则</span>
    </div>

    <!-- 数据记录视图 -->
    <div v-if="view === 'records'" class="records-view">
      <div class="rec-header">
        <span class="rec-title">📋 记录</span>
        <div style="display:flex;gap:6px">
          <select v-model="recYear" @change="loadRecords()" class="form-input" style="width:auto;padding:6px 10px;font-size:12px">
            <option value="">全部年份</option>
            <option v-for="y in recYears" :key="y" :value="y">{{ y }}</option>
          </select>
          <button class="btn-add" @click="openAdd">+ 新增</button>
        </div>
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
        <div class="form-card">
          <div class="form-title">{{ editingId ? '编辑记录' : '新增记录' }}</div>
          <div class="form-fields">
            <label>日期</label>
            <div class="date-picker-field" @click="openDatePicker(form.date, v => form.date = v, $event)">
              {{ form.date || '点击选择日期' }}
              <span class="date-arrow">📅</span>
            </div>
            <label>日期序号 <span class="form-hint">(自动)</span></label>
            <input type="number" :value="computedDaySeq" class="form-input" disabled />
            <label>抽签数 (1-49)</label>
            <input type="number" v-model.number="form.draw_number" min="1" max="49" class="form-input" placeholder="1-49" />
          </div>
          <div class="form-btns">
            <button class="btn-cancel" @click="showForm=false">取消</button>
            <button class="btn-submit" @click="doSave">保存</button>
          </div>
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
            <span style="font-size:13px;color:#8899b0">分析 / 演算 清空按钮：</span>
            <button class="btn-add-sm"
              :style="{background:allowClear?'#22c55e':'#ccc',color:'#fff'}"
              @click="allowClear=!allowClear">
              {{ allowClear ? '✅ 已开启' : '⛔ 已关闭' }}
            </button>
            <span style="font-size:11px;color:#8899b0">{{ allowClear ? '清空按钮可用，可操作' : '清空按钮已锁定（防误触）' }}</span>
          </div>
        </div>
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
        <template v-if="sumSel">
          <span class="crumb-sep">›</span>
          <span @click="backTo('summaries')">{{ colSel?.name }}</span>
          <template v-if="rgSel">
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
        <div class="grid49-table">
          <div v-for="g in grid49.grid" :key="g.n" class="grid49-cell" :class="{zero:g.value===0}">
            <span class="g49-n">{{ g.n }}</span>
            <span class="g49-v">{{ g.value }}</span>
          </div>
        </div>
        <div class="grid49-proj" v-if="grid49.projects?.length">
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
          <button class="col-del" @click.stop="delCollection(c.id)">🗑</button>
          <span class="col-card-arrow">›</span>
        </div>
      </div>
      <div v-if="colSel && !sumSel">
        <!-- 子标签：汇总/项目 -->
        <div class="col-subtabs">
          <span :class="{active:colSubTab==='summary'}" @click="colSubTab='summary'">📊 汇总</span>
          <span :class="{active:colSubTab==='project'}" @click="colSubTab='project'">📁 项目</span>
        </div>
        <!-- 汇总列表 -->
        <template v-if="colSubTab==='summary'">
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
        </template>
        <!-- 项目列表 -->
        <template v-if="colSubTab==='project'">
        <div class="col-section-hd">
          <span class="col-section-tl">{{ colSel?.name }} · 项目列表</span>
          <button class="btn-add-sm" @click="openAddColProject">+ 项目</button>
        </div>
        <div v-if="!colProjects.length" class="gs-empty">暂无项目，点击 + 创建</div>
        <div v-for="p in colProjects" :key="'cp'+p.id" class="col-card" @click="selectProject(p.id); view='groupset'">
          <div class="col-card-left">
            <span class="col-card-name">📁 {{ p.name }}</span>
          </div>
          <span class="col-card-arrow">›</span>
        </div>
        </template>
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
          <button class="col-del" @click.stop="delRunGroup(rg.id)">🗑</button>
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
          <div class="sim-subtitle-sm">将演算 {{ scopeProjects.length }} 个项目：</div>
          <div v-for="p in scopeProjects" :key="p.project_id" class="scope-proj-row">
            <span>{{ p.project_name }}</span>
            <span class="scope-rule-tag">{{ p.rule_name || '⚠ 无规则' }}</span>
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
    <!-- 弹窗：单项目 49 格明细 -->
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
import { ref, reactive, computed, watch } from 'vue'

const API = '/number-warehouse/api'

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

const view = ref('collection')

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

function openAdd() {
  editingId.value = null
  form.value = { date: todayStr, draw_number: null }
  showForm.value = true
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
const simStart = ref('2020-03-18')
const simEnd = ref(todayStr)

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
    if (!simStart.value) simStart.value = '2020-03-18'
    if (!simEnd.value) simEnd.value = todayStr
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
    const res = await fetch(`${API}/sim/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rule_ids: ruleIds,
        project_ids: projIds,
        start_date: simStart.value,
        end_date: simEnd.value,
      }),
    })
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
const runForm = ref({ start_date: '2020-03-18', end_date: todayStr })

const grid49 = ref(null)
const gridDate = ref('')
const showGridProj = ref(false)
const gridLevel = ref('')
const gridId = ref(null)
const gridTotalSum = computed(() => {
  if (!grid49.value?.grid) return 0
  return grid49.value.grid.reduce((s, g) => s + (g.value || 0), 0)
})
const gridDrawVal = computed(() => {
  const dn = grid49.value?.draw_number
  if (!dn || !grid49.value?.grid) return null
  const cell = grid49.value.grid.find(g => g.n === dn)
  return cell ? cell.value : null
})
const gridResult = computed(() => {
  if (gridDrawVal.value == null) return null
  return gridDrawVal.value * 47 - gridTotalSum.value
})

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

async function loadGrid(level, id, date = '') {
  try {
    let url = level === 'collection' ? `${API}/collections/${id}/grid`
            : level === 'summary' ? `${API}/summaries/${id}/grid`
            : `${API}/run-groups/${id}/grid`
    if (date) url += `?date=${encodeURIComponent(date)}`
    const res = await fetch(url)
    const data = await res.json()
    console.log('loadGrid', level, id, 'cells:', data.grid?.length, 'proj:', data.projects?.length)
    grid49.value = data
    gridLevel.value = level
    gridId.value = id
    gridDate.value = date || grid49.value?.last_date || ''
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
  const nums = sorted.slice(0, 25).map(g => g.n).join(',')
  navigator.clipboard.writeText(nums).then(() => $notify('前25号码已复制'), () => $notify('复制失败', true))
}

function copyBottom24() {
  if (!grid49.value?.grid?.length) return
  const sorted = [...grid49.value.grid].sort((a, b) => b.value - a.value)
  const nums = sorted.slice(25).map(g => g.n).join(',')
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
  if (level === 'collections') {
    colSel.value = null; sumSel.value = null; rgSel.value = null; grid49.value = null
  } else if (level === 'summaries') {
    sumSel.value = null; rgSel.value = null; loadGrid('collection', colSel.value.id)
  } else {
    rgSel.value = null; loadGrid('summary', sumSel.value.id)
  }
}

function selectCollection(c) {
  colSel.value = c; sumSel.value = null; rgSel.value = null; colSubTab.value = 'summary'
  loadSummaries(c.id); loadColProjects(c.id); loadGrid('collection', c.id)
}

function selectSummary(s) {
  sumSel.value = s; rgSel.value = null
  loadRunGroups(s.id); loadGrid('summary', s.id)
}

function selectRunGroup(rg) {
  rgSel.value = rg; loadRgItems(rg.id); loadGrid('run_group', rg.id)
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
  showRunDialog.value = true
}

// ===== 演算当天 =====
const showTodayRun = ref(false)
const todayRunDate = ref(todayStr)
const todayRunRunning = ref(false)
const trL3 = ref('all'), trL2 = ref(''), trL1 = ref('')
const trCID = computed(() => trL3.value !== 'all')
const trSID = computed(() => trCID.value && trL2.value !== '')
const scopeSummaries = ref([])
const scopeRunGroups = ref([])
const scopeProjects = ref([])

const canTodayRun = computed(() => scopeProjects.value.length > 0 && todayRunDate.value)

function openTodayRun() {
  if (!collections.value.length) loadCollections()
  todayRunDate.value = todayStr
  trL3.value = 'all'; trL2.value = ''; trL1.value = ''
  scopeSummaries.value = []; scopeRunGroups.value = []; scopeProjects.value = []
  showTodayRun.value = true
  // 初始即为全项目模式，手动触发加载
  onTrL3Change()
}

async function onTrL3Change() {
  trL2.value = ''; trL1.value = ''; scopeRunGroups.value = []
  if (trL3.value === 'all') { scopeSummaries.value = []; await loadTrAllProjects(); return }
  const cid = parseInt(trL3.value.slice(1))
  try { const r = await fetch(`${API}/collections/${cid}/summaries`); scopeSummaries.value = await r.json() } catch(e) { scopeSummaries.value = [] }
  loadTrScopeProjects()
}
async function onTrL2Change() {
  trL1.value = ''; scopeRunGroups.value = []
  if (trL2.value) {
    const sid = parseInt(trL2.value.slice(1))
    try { const r = await fetch(`${API}/summaries/${sid}/run-groups`); scopeRunGroups.value = await r.json() } catch(e) { scopeRunGroups.value = [] }
  }
  loadTrScopeProjects()
}
async function onTrL1Change() { loadTrScopeProjects() }

async function loadTrAllProjects() {
  try {
    const [pRes, rRes] = await Promise.all([
      fetch(`${API}/projects`),
      fetch(`${API}/sim/rules`),
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
    const res = await fetch(`${API}/scope/projects?${params}`)
    scopeProjects.value = await res.json()
  } catch (e) { scopeProjects.value = [] }
}

async function execTodayRun() {
  if (!canTodayRun.value) return
  todayRunRunning.value = true
  try {
    const pids = scopeProjects.value.map(p => p.project_id)
    const rids = scopeProjects.value.map(p => p.rule_id || 0)
    const res = await fetch(`${API}/sim/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        rule_ids: rids,
        project_ids: pids,
        start_date: todayRunDate.value,
        end_date: todayRunDate.value,
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '运行失败')
    const runs = data.runs || []
    const errors = data.errors || []
    const hits = runs.reduce((s, r) => s + (r.hit_count || 0), 0)
    const days = runs.reduce((s, r) => s + (r.total_days || 0), 0)
    let msg = `✅ 演算完成 ${runs.length}项目 · 命中 ${hits}/${days}`
    if (errors.length) {
      if (runs.length === 0) {
        // 全部失败 → 显示红色错误
        $notify(errors[0].error, true)
        showTodayRun.value = false
        todayRunRunning.value = false
        return
      }
      msg += ` · ⚠️ ${errors.length}项失败`
    }
    const adjusted = runs.filter(r => r.message && r.message.includes('调整'))
    if (adjusted.length) msg += ` · ⚠️ ${adjusted.length}项日期被自动调整`
    $notify(msg)
    if (errors.length) console.warn('演算失败项:', errors)
    if (adjusted.length) console.warn('日期调整项:', adjusted.map(r => r.message))
    showTodayRun.value = false
  } catch (e) { $notify(e.message, true) }
  todayRunRunning.value = false
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
.tb-date { font-size: 12px; color: #8899bb; }

.view-tabs {
  display: flex; background: #fff; border-bottom: 1px solid #e8ecf1;
  position: sticky; top: 0; z-index: 10; overflow-x: auto;
}
.view-tabs span {
  flex: 1; text-align: center; padding: 12px 4px;
  font-size: 12px; color: #8899b0; cursor: pointer; transition: all .2s;
  border-bottom: 3px solid transparent; white-space: nowrap;
}
.view-tabs span.active {
  color: #4da6ff; font-weight: 700; font-size: 13px;
  border-bottom-color: #4da6ff; background: linear-gradient(to top, #eef3ff, transparent 60%);
}

/* 卡片 */
.card { background: #fff; border-radius: 12px; padding: 14px; margin: 8px 12px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
.card-title { font-size: 14px; font-weight: 700; color: #1a2a4a; margin-bottom: 10px; }

/* ===== 数据记录 ===== */
.records-view { padding: 0 12px 40px; }
.rec-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 4px 10px; }
.rec-title { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.btn-add {
  padding: 8px 18px; background: linear-gradient(135deg, #4da6ff, #1a2a4a);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.rec-empty { text-align: center; padding: 40px 0; color: #bbb; font-size: 14px; }
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
  display: flex; align-items: safe center; justify-content: center;
  padding: 40px 0; overflow-y: auto;
}
.form-card {
  width: 300px; background: #fff; border-radius: 16px; padding: 24px 20px 20px;
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

/* ===== 49值网格 ===== */
.grid49-section { padding: 12px; margin: 8px 0; }
.grid49-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 13px; flex-wrap: wrap; gap: 4px; }
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
.pf-result.pos { color: #22c55e; }
.pf-result.neg { color: #ee0a24; }
.pf-table tbody tr:hover { background: #f8fafc; }
.col-subtabs { display: flex; gap: 0; background: #f0f4f8; border-radius: 10px; padding: 3px; margin: 0 0 12px; }
.col-subtabs span { flex: 1; text-align: center; padding: 8px 0; border-radius: 8px; font-size: 13px; font-weight: 600; color: #8899b0; cursor: pointer; transition: all .2s; }
.col-subtabs span.active { background: #fff; color: #1a2a4a; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
</style>
