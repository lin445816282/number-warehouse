<template>
  <div class="app">
    <div class="top-bar">
      <span class="tb-title">🔢 数字仓库</span>
      <span class="tb-date">{{ todayStr }}</span>
    </div>

    <!-- 视图切换 -->
    <div class="view-tabs">
      <span :class="{ active: view === 'records' }" @click="view = 'records'; loadRecords(); loadYears()">📋 数据记录</span>
      <span :class="{ active: view === 'groupset' }" @click="view = 'groupset'; loadProjects(); loadSimRules()">⚙ 组别设置</span>
      <span :class="{ active: view === 'rules' }" @click="view = 'rules'; loadDevRules(); loadMapping()">📐 开发规则</span>
      <span :class="{ active: view === 'sim' }" @click="view = 'sim'; loadSimRules(); loadSimQuery()">🚀 规则运行</span>
      <span :class="{ active: view === 'analysis' }" @click="view = 'analysis'; loadProjects(); loadAnalysis()">📈 数据分析</span>
    </div>

    <!-- 数据记录视图 -->
    <div v-if="view === 'records'" class="records-view">
      <div class="rec-header">
        <span class="rec-title">📋 数据记录</span>
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
        <span class="gs-title">⚙️ 组别设置</span>
        <button class="btn-add" @click="openAddProject">+ 项目</button>
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
        <span class="gs-title">🔧 开发规则</span>
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
    </div>

    <!-- 规则运行视图 -->
    <div v-if="view === 'sim'" class="sim-view">
      <div class="sim-header">
        <span class="sim-title">🚀 规则运行</span>
        <button class="btn-add" @click="runSimDialog=!runSimDialog"
                :class="{ running: running }" :disabled="running">
          <span v-if="running" class="btn-spin"></span>
          {{ running ? '演算中' : '运行' }}
        </button>
      </div>

      <!-- 查询栏 -->
      <div class="sim-query card">
        <div class="sim-param-row">
          <select v-model="simQProject" class="form-input" style="flex:1">
            <option :value="null">全部项目</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
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
        <div class="sim-subtitle-sm">📦 项目 & 规则</div>
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
            <span v-else class="sim-hint" style="color:#ee0a24">⚠ 请先在组别设置中设置规则</span>
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

    <!-- 数据分析视图 -->
    <div v-if="view === 'analysis'" class="analysis-view">
      <div class="sim-header">
        <span class="sim-title">📈 数据分析</span>
        <div style="display:flex;gap:6px">
          <button class="btn-add-sm" @click="clearAnalysis" style="background:#ee0a24;color:#fff">🗑 清空</button>
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
        <div class="sim-param-row">
          <select v-model="anProject" class="form-input" style="flex:1">
            <option :value="null">全部项目</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
      </div>

      <!-- 汇总 -->
      <div class="an-summary card" v-if="anCumulative != null">
        <span>累计求和</span>
        <b>{{ anCumulative.toLocaleString() }}</b>
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
import { ref, reactive, computed } from 'vue'

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

const view = ref('records')

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

async function loadProjects() {
  try {
    const res = await fetch(`${API}/projects`)
    projects.value = await res.json()
    if (projects.value.length && !selPid.value) {
      selPid.value = projects.value[0].id
      loadGsGroups()
    }
  } catch (e) { console.error(e) }
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
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: projForm.value.name }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || '保存失败')
    showProjForm.value = false
    loadProjects()
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
    // 默认日期范围
    if (!simStart.value) simStart.value = '2020-03-18'
    if (!simEnd.value) simEnd.value = todayStr
    loadSimQuery()
  } catch (e) { console.error(e) }
}

async function loadSimQuery() {
  const params = new URLSearchParams()
  if (simQProject.value) params.set('project_id', simQProject.value)
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
const anStart = ref('2020-03-01')
const anEnd = ref(todayStr)
const anProject = ref(null)
const anPage = ref(1)
const anPages = ref(1)
const anItems = ref([])
const anCumulative = ref(null)

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
  if (anProject.value) params.set('project_id', anProject.value)
  try {
    const res = await fetch(`${API}/analysis?${params}`)
    const data = await res.json()
    anItems.value = data.items
    anPages.value = data.total_pages
    anPage.value = data.page
    anCumulative.value = data.cumulative_sum
  } catch (e) { console.error(e) }
}

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
