import Tag from '../../../components/common/Tag.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import {
  WORK_ORDER_PRIORITY_TONE,
  WORK_ORDER_SOURCE_LABELS,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_STATUS_TONE
} from '../../../constants/index.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'

export default function WorkOrderTable({ rows, loading, onOpen }) {
  const columns = [
    {
      key: 'code',
      title: '工单号',
      className: 'cell-nowrap mono',
      render: (row) => (
        <span>
          {row.code}
          <span className="small muted"> · {WORK_ORDER_SOURCE_LABELS[row.source]}</span>
        </span>
      )
    },
    { key: 'title', title: '故障 / 维修内容' },
    {
      key: 'station',
      title: '监测点',
      render: (row) => (
        <span>
          {row.station_name} <span className="small muted">· {row.station_area}</span>
        </span>
      )
    },
    { key: 'assignee', title: '负责人', render: (row) => row.assignee || '待派单' },
    {
      key: 'priority',
      title: '优先级',
      render: (row) => <Tag tone={WORK_ORDER_PRIORITY_TONE[row.priority]}>{row.priority_label}</Tag>
    },
    { key: 'reported_at', title: '报修时间', className: 'cell-nowrap', render: (row) => formatDateTime(row.reported_at) },
    { key: 'due_date', title: '要求完成', className: 'cell-nowrap', render: (row) => formatDate(row.due_date) },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={WORK_ORDER_STATUS_TONE[row.status]}>{WORK_ORDER_STATUS_LABELS[row.status]}</Tag>
    },
    {
      key: 'actions',
      title: '操作',
      className: 'cell-nowrap',
      render: (row) => (
        <button type="button" className="btn btn-sm btn-primary" onClick={() => onOpen(row)}>
          {['closed', 'cancelled'].includes(row.status) ? '查看' : '处理'}
        </button>
      )
    }
  ]
  return <DataTable columns={columns} rows={rows} loading={loading} onRowClick={onOpen} emptyText="暂无维修工单" emptyIcon="🛠️" />
}
