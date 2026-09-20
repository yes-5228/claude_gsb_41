import { useCallback, useState } from 'react'
import {
  deletePlan,
  dispatchDue,
  dispatchPlan,
  inspectionCatalog,
  inspectionOptions,
  listPlans,
  listTasks,
  updatePlan
} from '../../api/inspections.js'
import { listWorkOrders } from '../../api/workOrders.js'
import ConfirmDialog from '../../components/common/ConfirmDialog.jsx'
import Pagination from '../../components/common/Pagination.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import { Alert } from '../../components/common/Feedback.jsx'
import { useToast } from '../../components/common/ToastProvider.jsx'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { useListQuery } from '../../hooks/useListQuery.js'
import TaskFilters from './components/TaskFilters.jsx'
import TaskStatusTabs from './components/TaskStatusTabs.jsx'
import TaskTable from './components/TaskTable.jsx'
import TaskExecuteDrawer from './components/TaskExecuteDrawer.jsx'
import PlanTable from './components/PlanTable.jsx'
import PlanFormModal from './components/PlanFormModal.jsx'
import ManualTaskModal from './components/ManualTaskModal.jsx'
import WorkOrderTable from './workorders/WorkOrderTable.jsx'
import WorkOrderFilters from './workorders/WorkOrderFilters.jsx'
import WorkOrderFormModal from './workorders/WorkOrderFormModal.jsx'
import WorkOrderDetailModal from './workorders/WorkOrderDetailModal.jsx'

const TABS = [
  { key: 'tasks', label: '巡检任务' },
  { key: 'plans', label: '巡检计划' },
  { key: 'orders', label: '维修工单' }
]

const TASK_FILTERS = { keyword: '', station_id: '', area: '', status: '', date_from: '', date_to: '' }
const ORDER_FILTERS = { keyword: '', area: '', status: '', priority: '' }

export default function InspectionsPage() {
  const toast = useToast()
  const [tab, setTab] = useState('tasks')

  const optionsState = useAsyncData(useCallback(async () => {
    const [options, catalogData] = await Promise.all([inspectionOptions(), inspectionCatalog()])
    return { ...options, catalog: catalogData.items || [] }
  }, []))
  const options = optionsState.data || { items: [], stations: [], areas: [], catalog: [] }

  // ---- 巡检任务 ----
  const taskQuery = useListQuery(listTasks, TASK_FILTERS)
  const [executeId, setExecuteId] = useState(null)
  const [manualOpen, setManualOpen] = useState(false)

  // ---- 巡检计划 ----
  const planQuery = useListQuery(listPlans, {}, { enabled: false })
  const [planForm, setPlanForm] = useState({ open: false, plan: null })
  const [pendingDeletePlan, setPendingDeletePlan] = useState(null)
  const [dispatching, setDispatching] = useState(false)

  // ---- 维修工单 ----
  const orderQuery = useListQuery(listWorkOrders, ORDER_FILTERS, { enabled: false })
  const [orderFormOpen, setOrderFormOpen] = useState(false)
  const [orderDetailId, setOrderDetailId] = useState(null)

  const switchTab = (key) => {
    setTab(key)
    if (key === 'plans') planQuery.reload()
    if (key === 'orders') orderQuery.reload()
  }

  const reloadAll = useCallback(() => {
    taskQuery.reload()
    if (tab === 'plans') planQuery.reload()
    if (tab === 'orders') orderQuery.reload()
  }, [tab, taskQuery, planQuery, orderQuery])

  const runDispatchDue = async () => {
    setDispatching(true)
    try {
      const result = await dispatchDue()
      if (result.task_count === 0) {
        toast.info('当前没有到期需要派发的周期计划')
      } else {
        toast.success(`已按到期计划派发 ${result.task_count} 条巡检任务 (计划 ${result.dispatched_plan_count} 个)`)
      }
      reloadAll()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDispatching(false)
    }
  }

  const handleDispatchPlan = async (plan) => {
    try {
      const result = await dispatchPlan(plan.id)
      if (result.task_count === 0) {
        toast.warning('覆盖点位今日已派发或均已停用, 未生成新任务')
      } else {
        toast.success(`计划「${plan.name}」已派发 ${result.task_count} 条任务`)
      }
      planQuery.reload()
      if (tab === 'tasks') taskQuery.reload()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleTogglePlan = async (plan) => {
    try {
      await updatePlan(plan.id, { enabled: !plan.enabled })
      toast.success(plan.enabled ? '计划已停用' : '计划已启用')
      planQuery.reload()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleDeletePlan = async () => {
    if (!pendingDeletePlan) return
    const plan = pendingDeletePlan
    try {
      await deletePlan(plan.id)
      toast.success('计划已删除, 已生成的历史巡检任务保留可查')
      setPendingDeletePlan(null)
      planQuery.reload()
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <>
      <div className="card">
        <div className="card-body tight">
          <div className="status-tabs">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`status-tab ${tab === item.key ? 'active' : ''}`}
                onClick={() => switchTab(item.key)}
              >
                {item.label}
              </button>
            ))}
            <span className="spacer" />
            <button type="button" className="btn btn-sm" onClick={runDispatchDue} disabled={dispatching}>
              {dispatching ? '派发中...' : '⏰ 执行到期派发'}
            </button>
            {tab === 'tasks' ? (
              <button type="button" className="btn btn-sm btn-primary" onClick={() => setManualOpen(true)}>
                + 手动派发
              </button>
            ) : null}
            {tab === 'plans' ? (
              <button type="button" className="btn btn-sm btn-primary"
                onClick={() => setPlanForm({ open: true, plan: null })}>
                + 新建巡检计划
              </button>
            ) : null}
            {tab === 'orders' ? (
              <button type="button" className="btn btn-sm btn-primary" onClick={() => setOrderFormOpen(true)}>
                + 人工建单
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {tab === 'tasks' ? (
        <>
          <TaskStatusTabs
            counts={taskQuery.summary?.by_status ? { ...taskQuery.summary } : null}
            active={taskQuery.filters.status || ''}
            onChange={(status) => taskQuery.setFilters({ ...taskQuery.filters, status })}
          />
          <TaskFilters
            value={taskQuery.filters}
            areas={options.areas}
            stations={options.stations}
            loading={taskQuery.loading}
            onSubmit={(next) => taskQuery.setFilters(next)}
            onReset={() => taskQuery.setFilters(TASK_FILTERS)}
          />
          {taskQuery.error ? <Alert tone="error">{taskQuery.error.message}</Alert> : null}
          <SectionCard title="巡检任务待办" hint="逐项登记巡检结果, 异常项可直接转维修工单; 逾期未开始的任务自动标记为“已逾期”">
            <TaskTable rows={taskQuery.items} loading={taskQuery.loading} onOpen={(row) => setExecuteId(row.id)} />
            <Pagination
              page={taskQuery.page}
              pages={taskQuery.pages}
              total={taskQuery.total}
              pageSize={taskQuery.pageSize}
              onPageChange={taskQuery.setPage}
              onPageSizeChange={taskQuery.setPageSize}
            />
          </SectionCard>
        </>
      ) : null}

      {tab === 'plans' ? (
        <>
          {planQuery.error ? <Alert tone="error">{planQuery.error.message}</Alert> : null}
          <SectionCard
            title="巡检计划"
            hint="按周期 (每日/每周/每月) 自动为覆盖点位派发任务; 也可随时“立即派发”一次"
            actions={
              <button type="button" className="btn btn-sm" onClick={() => planQuery.reload()} disabled={planQuery.loading}>
                刷新
              </button>
            }
          >
            <PlanTable
              rows={planQuery.items}
              loading={planQuery.loading}
              onEdit={(row) => setPlanForm({ open: true, plan: row })}
              onDispatch={handleDispatchPlan}
              onToggle={handleTogglePlan}
              onDelete={(row) => setPendingDeletePlan(row)}
            />
            <Pagination
              page={planQuery.page}
              pages={planQuery.pages}
              total={planQuery.total}
              pageSize={planQuery.pageSize}
              onPageChange={planQuery.setPage}
              onPageSizeChange={planQuery.setPageSize}
            />
          </SectionCard>
        </>
      ) : null}

      {tab === 'orders' ? (
        <>
          <WorkOrderFilters
            value={orderQuery.filters}
            areas={options.areas}
            loading={orderQuery.loading}
            onSubmit={(next) => orderQuery.setFilters(next)}
            onReset={() => orderQuery.setFilters(ORDER_FILTERS)}
          />
          {orderQuery.error ? <Alert tone="error">{orderQuery.error.message}</Alert> : null}
          <SectionCard title="维修工单" hint="工单处理中台账自动置为“维护中”, 维修办结后自动回写“运行中”, 保持三处状态一致">
            <WorkOrderTable rows={orderQuery.items} loading={orderQuery.loading} onOpen={(row) => setOrderDetailId(row.id)} />
            <Pagination
              page={orderQuery.page}
              pages={orderQuery.pages}
              total={orderQuery.total}
              pageSize={orderQuery.pageSize}
              onPageChange={orderQuery.setPage}
              onPageSizeChange={orderQuery.setPageSize}
            />
          </SectionCard>
        </>
      ) : null}

      <TaskExecuteDrawer
        taskId={executeId}
        onClose={() => setExecuteId(null)}
        onChanged={() => {
          reloadAll()
        }}
      />

      <ManualTaskModal
        open={manualOpen}
        catalog={options.catalog}
        stations={options.stations}
        onClose={() => setManualOpen(false)}
        onCreated={(task) => {
          setManualOpen(false)
          toast.success('巡检任务已创建')
          setTab('tasks')
          taskQuery.reload()
          setExecuteId(task.id)
        }}
      />

      {planForm.open ? (
        <PlanFormModal
          key={planForm.plan?.id || 'new'}
          open
          plan={planForm.plan}
          catalog={options.catalog}
          stations={options.stations}
          onClose={() => setPlanForm({ open: false, plan: null })}
          onSaved={() => {
            setPlanForm({ open: false, plan: null })
            planQuery.reload()
          }}
        />
      ) : null}

      <ConfirmDialog
        open={Boolean(pendingDeletePlan)}
        danger
        title="删除巡检计划"
        message={`确认删除计划「${pendingDeletePlan?.name || ''}」吗?`}
        detail="删除后不再自动派发, 已生成的历史巡检任务会保留, 但与计划解除关联。"
        confirmText="确认删除"
        onConfirm={handleDeletePlan}
        onCancel={() => setPendingDeletePlan(null)}
      />

      <WorkOrderFormModal
        open={orderFormOpen}
        stations={options.stations}
        onClose={() => setOrderFormOpen(false)}
        onCreated={(order) => {
          setOrderFormOpen(false)
          toast.success(`工单 ${order.code} 已创建, 台账已置为“维护中”`)
          orderQuery.reload()
          setOrderDetailId(order.id)
        }}
      />

      <WorkOrderDetailModal
        orderId={orderDetailId}
        onClose={() => setOrderDetailId(null)}
        onChanged={() => {
          orderQuery.reload()
          taskQuery.reload()
        }}
      />
    </>
  )
}
