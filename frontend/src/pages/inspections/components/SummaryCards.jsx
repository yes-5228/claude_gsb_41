import StatCard from '../../../components/common/StatCard.jsx'

export default function SummaryCards({ summary, loading }) {
  if (loading || !summary) {
    return (
      <div className="stat-grid">
        <StatCard label="待办巡检任务" value="-" />
        <StatCard label="逾期未检" value="-" />
        <StatCard label="待处理工单" value="-" />
        <StatCard label="启用巡检计划" value="-" />
      </div>
    )
  }
  const repair = summary.repair || {}
  return (
    <div className="stat-grid">
      <StatCard
        label="待办巡检任务"
        value={summary.task_open}
        tone={summary.task_open ? 'warning' : undefined}
        foot={`任务总数 ${summary.task_total} · 异常完成 ${summary.task_abnormal}`}
      />
      <StatCard
        label="逾期未检"
        value={summary.task_overdue}
        tone={summary.task_overdue ? 'danger' : undefined}
        foot="超过应完成日期仍未执行的巡检任务"
      />
      <StatCard
        label="待处理工单"
        value={repair.open ?? 0}
        tone={repair.open ? 'warning' : undefined}
        foot={`高优先级未结 ${repair.urgent_open ?? 0} 单 · 工单总数 ${repair.total ?? 0}`}
      />
      <StatCard
        label="启用巡检计划"
        value={summary.plan_active}
        foot={`计划总数 ${summary.plan_total} · 按周期自动去重派发`}
      />
    </div>
  )
}
