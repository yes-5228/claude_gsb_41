import Tag from '../../../components/common/Tag.jsx'
import {
  INSPECTION_TASK_STATUS_LABELS
} from '../../../constants/index.js'
import { formatDate } from '../../../utils/format.js'

const TABS = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待执行' },
  { key: 'in_progress', label: '执行中' },
  { key: 'overdue', label: '已逾期' },
  { key: 'abnormal', label: '巡检异常' },
  { key: 'completed', label: '已完成' }
]

export default function TaskStatusTabs({ counts = {}, active, onChange }) {
  const map = Object.fromEntries((counts || []).map((item) => [item.key, item.count]))
  return (
    <div className="status-tabs">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`status-tab ${active === tab.key ? 'active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
          <span className="status-tab-count">{tab.key ? map[tab.key] ?? 0 : counts.total ?? 0}</span>
        </button>
      ))}
      <span className="spacer" />
      <span className="small muted">
        {INSPECTION_TASK_STATUS_LABELS[active] ? `当前: ${INSPECTION_TASK_STATUS_LABELS[active]}` : '全部任务'}
        <Tag tone="primary" >
          待办 {counts.todo ?? 0}
        </Tag>
      </span>
    </div>
  )
}
