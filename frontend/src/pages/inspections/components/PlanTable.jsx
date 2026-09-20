import DataTable from '../../../components/common/DataTable.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { INSPECTION_CYCLE_LABELS } from '../../../constants/index.js'
import { formatDate } from '../../../utils/format.js'

export default function PlanTable({ rows, loading, onEdit, onDispatch, onToggle, onDelete }) {
  const columns = [
    { key: 'name', title: '计划名称', render: (row) => (
      <span>
        {row.name}
        {!row.enabled ? <Tag tone="neutral">已停用</Tag> : null}
      </span>
    ) },
    {
      key: 'cycle',
      title: '周期',
      render: (row) => <Tag tone="primary">{INSPECTION_CYCLE_LABELS[row.cycle]}</Tag>
    },
    {
      key: 'stations',
      title: '覆盖点位',
      align: 'right',
      render: (row) => `${(row.stations || []).length} 个`
    },
    {
      key: 'items',
      title: '巡检项',
      align: 'right',
      render: (row) => `${(row.items || []).length} 项`
    },
    { key: 'inspector', title: '默认巡检人', render: (row) => row.inspector || '-' },
    { key: 'next_run_date', title: '下次派发', className: 'cell-nowrap', render: (row) => formatDate(row.next_run_date) },
    {
      key: 'actions',
      title: '操作',
      className: 'cell-nowrap',
      render: (row) => (
        <div className="btn-group">
          <button type="button" className="btn btn-sm btn-primary" onClick={() => onDispatch(row)}>
            立即派发
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onEdit(row)}>
            编辑
          </button>
          <button type="button" className="btn btn-sm" onClick={() => onToggle(row)}>
            {row.enabled ? '停用' : '启用'}
          </button>
          <button type="button" className="btn btn-sm btn-danger" onClick={() => onDelete(row)}>
            删除
          </button>
        </div>
      )
    }
  ]
  return (
    <DataTable
      columns={columns}
      rows={rows}
      loading={loading}
      emptyText="还没有巡检计划, 点击“新建巡检计划”按周期自动派单"
      emptyIcon="📅"
    />
  )
}
