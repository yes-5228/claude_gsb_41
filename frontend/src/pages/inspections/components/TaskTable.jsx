import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import {
  INSPECTION_TASK_STATUS_LABELS,
  INSPECTION_TASK_STATUS_TONE
} from '../../../constants/index.js'
import { formatDate } from '../../../utils/format.js'

export default function TaskTable({ rows, loading, onOpen }) {
  const columns = [
    {
      key: 'code',
      title: '任务单号',
      className: 'cell-nowrap mono',
      render: (row) => (
        <span>
          {row.code}
          {row.plan_name ? <span className="small muted"> · {row.plan_name}</span> : null}
        </span>
      )
    },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <span>
          {row.station_name}
          <span className="small muted"> · {row.station_area}</span>
        </span>
      )
    },
    {
      key: 'due_date',
      title: '应检日期',
      className: 'cell-nowrap',
      render: (row) => {
        const overdue = ['pending', 'in_progress'].includes(row.status)
        return <span className={overdue ? 'warning-text' : ''}>{formatDate(row.due_date)}</span>
      }
    },
    { key: 'inspector', title: '巡检人', render: (row) => row.inspector || '-' },
    {
      key: 'progress',
      title: '检查进度',
      align: 'right',
      render: (row) => (
        <span>
          {row.progress.recorded}/{row.progress.total}
          {row.progress.abnormal ? <span className="danger-text"> · 异常 {row.progress.abnormal}</span> : null}
        </span>
      )
    },
    {
      key: 'status',
      title: '状态',
      render: (row) => (
        <Tag tone={INSPECTION_TASK_STATUS_TONE[row.status]}>
          {INSPECTION_TASK_STATUS_LABELS[row.status] || row.status}
        </Tag>
      )
    },
    {
      key: 'actions',
      title: '操作',
      className: 'cell-nowrap',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onOpen(row)}>
          {row.status === 'completed' || row.status === 'abnormal' ? '查看记录' : '去巡检'}
        </button>
      )
    }
  ]

  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      onRowClick={onOpen}
      emptyText="暂无巡检任务, 可在“巡检计划”页按周期派发或手动新建"
      emptyIcon="🔍"
    />
  )
}
