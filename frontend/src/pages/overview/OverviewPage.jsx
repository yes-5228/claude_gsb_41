import { useCallback } from 'react'
import { Link } from 'react-router-dom'
import { overview } from '../../api/meta.js'
import BarChart from '../../components/common/BarChart.jsx'
import { SectionCard } from '../../components/common/Card.jsx'
import DataTable from '../../components/common/DataTable.jsx'
import { Alert, ErrorState, Loading } from '../../components/common/Feedback.jsx'
import StatCard from '../../components/common/StatCard.jsx'
import Tag from '../../components/common/Tag.jsx'
import {
  EXCEEDANCE_LEVEL_TONE,
  INSPECTION_TASK_STATUS_TONE,
  WORK_ORDER_STATUS_TONE
} from '../../constants/index.js'
import { useAsyncData } from '../../hooks/useAsyncData.js'
import { formatDate, formatDateTime, formatNumber, formatPercent, formatRatio } from '../../utils/format.js'

export default function OverviewPage() {
  const loader = useCallback(() => overview(), [])
  const { data, loading, error, reload } = useAsyncData(loader)

  if (loading && !data) return <Loading text="正在加载运行概览..." />
  if (error && !data) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  const {
    stations,
    measurements,
    exceedances,
    trend,
    pending_exceedances: pending,
    inspections,
    work_orders: workOrders,
    todo_tasks: todoTasks,
    active_work_orders: activeOrders
  } = data

  const pendingColumns = [
    { key: 'measured_at', title: '监测时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.measured_at) },
    { key: 'station_name', title: '监测点', render: (row) => row.station_name },
    { key: 'pollutant_label', title: '因子' },
    {
      key: 'value',
      title: '监测值 / 限值',
      render: (row) => `${formatNumber(row.value)} / ${formatNumber(row.limit_value)}`
    },
    { key: 'exceed_ratio', title: '超标倍数', render: (row) => formatRatio(row.exceed_ratio) },
    {
      key: 'level',
      title: '等级',
      render: (row) => <Tag tone={EXCEEDANCE_LEVEL_TONE[row.level]}>{row.level_label}</Tag>
    }
  ]

  const todoTaskColumns = [
    { key: 'code', title: '任务单号', className: 'cell-nowrap mono' },
    { key: 'station_name', title: '监测点' },
    { key: 'due_date', title: '应检日期', className: 'cell-nowrap', render: (row) => formatDate(row.due_date) },
    { key: 'inspector', title: '巡检人', render: (row) => row.inspector || '-' },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={INSPECTION_TASK_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    }
  ]

  const activeOrderColumns = [
    { key: 'code', title: '工单号', className: 'cell-nowrap mono' },
    { key: 'title', title: '故障内容' },
    { key: 'station_name', title: '监测点' },
    { key: 'assignee', title: '负责人', render: (row) => row.assignee || '待派单' },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={WORK_ORDER_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    }
  ]

  const typeRows = (stations.by_type || []).map((item) => ({
    id: item.key,
    label: item.label,
    count: item.count,
    ratio: stations.total ? item.count / stations.total : 0
  }))

  return (
    <>
      <div className="stat-grid">
        <StatCard
          label="监测点总数"
          value={stations.total}
          foot={(stations.by_status || [])
            .map((item) => `${item.label} ${item.count}`)
            .join(' · ')}
        />
        <StatCard
          label="监测数据总量"
          value={measurements.total}
          foot={`覆盖 ${measurements.station_count} 个监测点 · 均值 ${formatNumber(measurements.avg_value)}`}
        />
        <StatCard
          label="巡检待办"
          value={inspections.todo}
          tone={inspections.todo ? 'warning' : undefined}
          foot={`今日到期 ${inspections.due_today} · 逾期/待执行/执行中见工作台`}
        />
        <StatCard
          label="维修中工单"
          value={workOrders.active}
          tone={workOrders.active ? 'danger' : undefined}
          foot={
            <Link to="/inspections">前往运维巡检处理 →</Link>
          }
        />
      </div>

      <div className="grid-2">
        <SectionCard title="近 7 日数据量趋势" hint="按日统计录入条数, 红色代表当日存在超标">
          <BarChart items={trend.items || []} precision={0} danger={false} />
        </SectionCard>

        <SectionCard title="监测点类型分布" hint="台账中各类站点的数量占比">
          <div className="stack">
            {typeRows.map((row) => (
              <div key={row.id}>
                <div className="inline" style={{ justifyContent: 'space-between' }}>
                  <span>{row.label}</span>
                  <span className="muted small">
                    {row.count} 个 · {formatPercent(row.ratio)}
                  </span>
                </div>
                <div className="meter" style={{ marginTop: 6 }}>
                  <div className="meter-fill" style={{ width: `${Math.max(row.ratio * 100, 2)}%` }} />
                </div>
              </div>
            ))}
            <div className="inline">
              <Link className="btn btn-sm" to="/stations">
                管理监测点台账
              </Link>
              <Link className="btn btn-sm" to="/measurements">
                录入监测数据
              </Link>
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="grid-2">
        <SectionCard
          title="巡检待办 (最近 5 条)"
          hint="待执行 / 执行中 / 已逾期的巡检任务, 逐项登记结果"
          actions={<Link className="btn btn-sm btn-primary" to="/inspections">去巡检</Link>}
        >
          {todoTasks.length === 0 ? (
            <Alert tone="success">当前没有待办巡检任务 ✅</Alert>
          ) : (
            <DataTable columns={todoTaskColumns} rows={todoTasks} emptyText="暂无待办" emptyIcon="✅" />
          )}
        </SectionCard>

        <SectionCard
          title="维修中工单 (最近 5 张)"
          hint="处理完成后自动回写台账运行状态"
          actions={<Link className="btn btn-sm btn-primary" to="/inspections">处理工单</Link>}
        >
          {activeOrders.length === 0 ? (
            <Alert tone="success">没有进行中的维修工单, 设备运行正常 ✅</Alert>
          ) : (
            <DataTable columns={activeOrderColumns} rows={activeOrders} emptyText="暂无维修工单" emptyIcon="🛠️" />
          )}
        </SectionCard>
      </div>

      <SectionCard
        title="数据质量概览"
        hint={`超标记录 ${exceedances.total} 条 (超标率 ${formatPercent(measurements.exceed_rate)} · 最大超标 ${formatRatio(exceedances.max_ratio)}), 待标注 ${exceedances.pending} 条`}
        actions={
          <Link className="btn btn-sm" to="/exceedances">
            处理超标标注
          </Link>
        }
      >
        {exceedances.pending === 0 ? (
          <Alert tone="success">当前没有待标注的超标记录, 数据复核已完成 ✅</Alert>
        ) : (
          <DataTable
            columns={pendingColumns}
            rows={pending}
            loading={loading}
            emptyText="暂无待标注记录"
            emptyIcon="✅"
          />
        )}
      </SectionCard>
    </>
  )
}
