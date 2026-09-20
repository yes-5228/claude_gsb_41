import { useCallback, useState } from 'react'
import { inspectionOptions, inspectionSummary } from '../../api/inspections.js'
import { repairOptions } from '../../api/repairs.js'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { useToast } from '../../components/common/ToastProvider.jsx'
import SummaryCards from './components/SummaryCards.jsx'
import TodoPanel from './components/TodoPanel.jsx'
import TasksPanel from './components/TasksPanel.jsx'
import RepairsPanel from './components/RepairsPanel.jsx'
import PlansPanel from './components/PlansPanel.jsx'
import ExecuteTaskDrawer from './components/ExecuteTaskDrawer.jsx'
import ResolveRepairModal from './components/ResolveRepairModal.jsx'

const TABS = [
  { key: 'todo', label: '待办中心' },
  { key: 'tasks', label: '巡检任务' },
  { key: 'repairs', label: '维修工单' },
  { key: 'plans', label: '巡检计划' }
]

export default function InspectionsPage() {
  const toast = useToast()
  const [tab, setTab] = useState('todo')
  const [refreshKey, setRefreshKey] = useState(0)
  const [executeId, setExecuteId] = useState(null)
  const [resolveId, setResolveId] = useState(null)

  const summaryLoader = useCallback(() => inspectionSummary(), [])
  const summary = useAsyncData(summaryLoader)
  const { reload: reloadSummary } = summary
  const optionsLoader = useCallback(async () => {
    const [inspection, repair] = await Promise.all([inspectionOptions(), repairOptions()])
    return { ...inspection, ...repair }
  }, [])
  const options = useAsyncData(optionsLoader)

  /** 任何状态变更后统一刷新: 统计卡片 + 当前列表, 保证待办与台账一致 */
  const refresh = useCallback(() => {
    setRefreshKey((key) => key + 1)
    reloadSummary().catch(() => {})
  }, [reloadSummary])

  const handleError = useCallback(
    (error) => toast.error(error.message || '操作失败'),
    [toast]
  )

  const openExecute = useCallback((task) => setExecuteId(task.id), [])
  const openResolve = useCallback((repair) => setResolveId(repair.id), [])

  const data = summary.data
  const todoCount = (data?.task_open ?? 0) + (data?.repair?.open ?? 0)
  const badgeOf = (key) => {
    if (key === 'todo') return todoCount || null
    if (key === 'tasks') return data?.task_open || null
    if (key === 'repairs') return data?.repair?.open || null
    return null
  }

  return (
    <>
      <SummaryCards summary={data} loading={summary.loading && !data} />

      <div className="tabs">
        {TABS.map((item) => {
          const badge = badgeOf(item.key)
          return (
            <button
              key={item.key}
              type="button"
              className={`tab-btn ${tab === item.key ? 'active' : ''}`}
              onClick={() => setTab(item.key)}
            >
              {item.label}
              {badge ? (
                <span className={`tab-badge ${item.key === 'todo' ? 'warning' : ''}`}>{badge}</span>
              ) : null}
            </button>
          )
        })}
      </div>

      {tab === 'todo' ? (
        <TodoPanel
          refreshKey={refreshKey}
          onExecute={openExecute}
          onResolve={openResolve}
          onChanged={refresh}
          onError={handleError}
        />
      ) : null}
      {tab === 'tasks' ? (
        <TasksPanel
          refreshKey={refreshKey}
          options={options.data}
          onExecute={openExecute}
          onChanged={refresh}
          onError={handleError}
        />
      ) : null}
      {tab === 'repairs' ? (
        <RepairsPanel
          refreshKey={refreshKey}
          options={options.data}
          onResolve={openResolve}
          onChanged={refresh}
          onError={handleError}
        />
      ) : null}
      {tab === 'plans' ? (
        <PlansPanel
          refreshKey={refreshKey}
          options={options.data}
          onChanged={refresh}
          onError={handleError}
        />
      ) : null}

      <ExecuteTaskDrawer
        taskId={executeId}
        options={options.data}
        onClose={() => setExecuteId(null)}
        onCompleted={() => {
          setExecuteId(null)
          refresh()
        }}
        onError={handleError}
      />

      <ResolveRepairModal
        repairId={resolveId}
        options={options.data}
        onClose={() => setResolveId(null)}
        onResolved={() => {
          setResolveId(null)
          refresh()
        }}
        onError={handleError}
      />
    </>
  )
}
