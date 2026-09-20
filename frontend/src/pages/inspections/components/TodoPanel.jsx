import { useCallback } from 'react'
import { inspectionTodo } from '../../../api/inspections.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import {
  INSPECTION_TASK_STATUS_TONE,
  REPAIR_PRIORITY_TONE,
  REPAIR_STATUS_TONE,
  STATION_STATUS_TONE
} from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { useRefreshKey } from '../../../hooks/useRefreshKey.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'

function isOverdue(row) {
  if (!row.due_date) return false
  return row.due_date < new Date().toISOString().slice(0, 10)
}

export default function TodoPanel({ refreshKey, onExecute, onResolve }) {
  const loader = useCallback(() => inspectionTodo(), [])
  const { data, loading, error, reload } = useAsyncData(loader)

  useRefreshKey(refreshKey, () => reload().catch(() => {}))

  const taskColumns = [
    {
      key: 'title',
      title: '巡检任务',
      render: (row) => (
        <div>
          <div>{row.title}</div>
          <div className="small muted">
            {row.station_code} {row.station_name} · {row.cycle_label}
          </div>
        </div>
      )
    },
    {
      key: 'due_date',
      title: '应完成',
      className: 'cell-nowrap',
      render: (row) =>
        isOverdue(row) ? (
          <span className="danger-text">{formatDate(row.due_date)} (已逾期)</span>
        ) : (
          formatDate(row.due_date)
        )
    },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={INSPECTION_TASK_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    { key: 'assignee', title: '巡检人', render: (row) => row.assignee || '-' },
    {
      key: 'actions',
      title: '操作',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onExecute(row)}>
          执行巡检
        </button>
      )
    }
  ]

  const repairColumns = [
    {
      key: 'title',
      title: '维修工单',
      render: (row) => (
        <div>
          <div>
            <span className="mono small muted">{row.code}</span> {row.title}
          </div>
          <div className="small muted">
            {row.station_code} {row.station_name}
            {row.inspection_task_title ? ` · 来源: ${row.inspection_task_title}` : ' · 手工报修'}
          </div>
        </div>
      )
    },
    {
      key: 'priority',
      title: '优先级',
      render: (row) => <Tag tone={REPAIR_PRIORITY_TONE[row.priority]}>{row.priority_label}</Tag>
    },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={REPAIR_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    {
      key: 'station_status',
      title: '台账状态',
      render: (row) => <Tag tone={STATION_STATUS_TONE[row.station_status]}>{row.station_status_label}</Tag>
    },
    {
      key: 'actions',
      title: '操作',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onResolve(row)}>
          处理工单
        </button>
      )
    }
  ]

  const tasks = data?.tasks ?? []
  const repairs = data?.repairs ?? []

  return (
    <>
      {error ? <Alert tone="error">{error.message}</Alert> : null}
      {!error && data && tasks.length === 0 && repairs.length === 0 ? (
        <Alert tone="success">当前没有待办事项: 巡检任务与维修工单均已处理完毕 ✅</Alert>
      ) : null}
      <div className="grid-2">
        <SectionCard
          title={`待办巡检任务 (${tasks.length})`}
          hint="按应完成日期升序, 点击“执行巡检”逐项记录结果"
        >
          <DataTable
            columns={taskColumns}
            rows={tasks}
            loading={loading}
            emptyText="暂无待办巡检任务"
            emptyIcon="🧭"
          />
        </SectionCard>
        <SectionCard
          title={`待处理维修工单 (${repairs.length})`}
          hint="处理完成后将按选择回写台账运行状态"
        >
          <DataTable
            columns={repairColumns}
            rows={repairs}
            loading={loading}
            emptyText="暂无待处理维修工单"
            emptyIcon="🧰"
          />
        </SectionCard>
      </div>
      {data ? (
        <div className="small muted">
          待办数据与巡检任务、维修工单实时同源; 台账运行状态随工单处理自动回写。
          最近刷新: {formatDateTime(new Date().toISOString())}
        </div>
      ) : null}
    </>
  )
}
