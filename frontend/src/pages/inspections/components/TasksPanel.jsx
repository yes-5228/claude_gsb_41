import { useState } from 'react'
import { cancelTask, dispatchAll, listTasks } from '../../../api/inspections.js'
import { FilterPanel, SectionCard } from '../../../components/common/Card.jsx'
import ConfirmDialog from '../../../components/common/ConfirmDialog.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import Pagination from '../../../components/common/Pagination.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { INSPECTION_RESULT_TONE, INSPECTION_TASK_STATUS_TONE } from '../../../constants/index.js'
import { useListQuery } from '../../../hooks/useListQuery.js'
import { useStationOptions } from '../../../hooks/useOptions.js'
import { useRefreshKey } from '../../../hooks/useRefreshKey.js'
import { formatDate } from '../../../utils/format.js'
import DispatchTaskModal from './DispatchTaskModal.jsx'

const INITIAL_FILTERS = { keyword: '', status: '', cycle: '', station_id: '', overdue: '' }

function isOverdue(row) {
  if (!row.due_date) return false
  const open = row.status === 'pending' || row.status === 'in_progress'
  return open && row.due_date < new Date().toISOString().slice(0, 10)
}

export default function TasksPanel({ refreshKey, options, onExecute, onChanged, onError }) {
  const toast = useToast()
  const query = useListQuery(listTasks, INITIAL_FILTERS)
  const stations = useStationOptions()
  const [draft, setDraft] = useState(INITIAL_FILTERS)
  const [dispatchOpen, setDispatchOpen] = useState(false)
  const [cancelling, setCancelling] = useState(null)
  const [busy, setBusy] = useState(false)

  const { reload } = query
  useRefreshKey(refreshKey, reload)

  const set = (key) => (event) => setDraft((prev) => ({ ...prev, [key]: event.target.value }))

  const runDispatchAll = async () => {
    setBusy(true)
    try {
      const result = await dispatchAll()
      if (result.created_count > 0) {
        toast.success(`已派发 ${result.created_count} 条本期巡检任务, 跳过已派发 ${result.skipped_count} 条`)
      } else {
        toast.info(`本期任务均已派发, 跳过 ${result.skipped_count} 条`)
      }
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const confirmCancel = async () => {
    if (!cancelling) return
    setBusy(true)
    try {
      await cancelTask(cancelling.id, { reason: '人工取消' })
      toast.success(`任务「${cancelling.title}」已取消`)
      setCancelling(null)
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    {
      key: 'title',
      title: '任务标题',
      render: (row) => (
        <div>
          <div>{row.title}</div>
          <div className="small muted">{row.plan_name ? `计划: ${row.plan_name}` : '手工临时派发'}</div>
        </div>
      )
    },
    {
      key: 'station_name',
      title: '监测点',
      render: (row) => (
        <div>
          <div>{row.station_name}</div>
          <div className="small muted">{row.station_code}</div>
        </div>
      )
    },
    { key: 'cycle_label', title: '周期' },
    {
      key: 'due_date',
      title: '应完成',
      className: 'cell-nowrap',
      render: (row) =>
        isOverdue(row) ? (
          <span className="danger-text">{formatDate(row.due_date)} 逾期</span>
        ) : (
          formatDate(row.due_date)
        )
    },
    {
      key: 'status',
      title: '状态',
      render: (row) => <Tag tone={INSPECTION_TASK_STATUS_TONE[row.status]}>{row.status_label}</Tag>
    },
    {
      key: 'result',
      title: '巡检结论',
      render: (row) =>
        row.result ? (
          <Tag tone={INSPECTION_RESULT_TONE[row.result]}>
            {row.result_label}
            {row.abnormal_count ? ` (${row.abnormal_count} 项)` : ''}
          </Tag>
        ) : (
          '-'
        )
    },
    { key: 'assignee', title: '巡检人', render: (row) => row.executor || row.assignee || '-' },
    {
      key: 'actions',
      title: '操作',
      render: (row) => {
        const open = row.status === 'pending' || row.status === 'in_progress'
        return (
          <div className="btn-group">
            <button
              type="button"
              className={`btn btn-sm ${open ? 'btn-primary' : ''}`}
              onClick={() => onExecute(row)}
            >
              {open ? '执行' : '详情'}
            </button>
            {open ? (
              <button type="button" className="btn btn-sm btn-danger" onClick={() => setCancelling(row)}>
                取消
              </button>
            ) : null}
          </div>
        )
      }
    }
  ]

  return (
    <>
      <FilterPanel
        loading={query.loading}
        onSearch={() => query.setFilters(draft)}
        onReset={() => {
          setDraft(INITIAL_FILTERS)
          query.setFilters(INITIAL_FILTERS)
        }}
      >
        <Field label="关键字">
          <Input value={draft.keyword} onChange={set('keyword')} placeholder="任务标题 / 监测点" />
        </Field>
        <Field label="任务状态">
          <Select
            value={draft.status}
            onChange={set('status')}
            placeholder="全部状态"
            options={options?.task_statuses ?? []}
          />
        </Field>
        <Field label="巡检周期">
          <Select
            value={draft.cycle}
            onChange={set('cycle')}
            placeholder="全部周期"
            options={options?.cycles ?? []}
          />
        </Field>
        <Field label="监测点">
          <Select
            value={draft.station_id}
            onChange={set('station_id')}
            placeholder="全部监测点"
            options={(stations.data?.items ?? []).map((item) => ({
              value: String(item.id),
              label: `${item.code} ${item.name}`
            }))}
          />
        </Field>
        <Field label="是否逾期">
          <Select
            value={draft.overdue}
            onChange={set('overdue')}
            placeholder="全部"
            options={[{ value: 'true', label: '仅看逾期' }]}
          />
        </Field>
      </FilterPanel>

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="巡检任务列表"
        hint="按周期派发, 逐项记录结果; 异常可直接转维修工单"
        actions={
          <>
            <button type="button" className="btn" onClick={() => setDispatchOpen(true)}>
              + 临时派发
            </button>
            <button type="button" className="btn btn-primary" onClick={runDispatchAll} disabled={busy}>
              {busy ? '派发中...' : '一键派发本期任务'}
            </button>
          </>
        }
      >
        <DataTable
          columns={columns}
          rows={query.items}
          loading={query.loading}
          emptyText="暂无巡检任务, 可点击右上角派发"
          emptyIcon="🧭"
        />
        <Pagination
          page={query.page}
          pages={query.pages}
          total={query.total}
          pageSize={query.pageSize}
          onPageChange={query.setPage}
          onPageSizeChange={query.setPageSize}
        />
      </SectionCard>

      <DispatchTaskModal
        open={dispatchOpen}
        options={options}
        stations={stations.data?.items ?? []}
        onClose={() => setDispatchOpen(false)}
        onCreated={() => {
          setDispatchOpen(false)
          onChanged()
        }}
        onError={onError}
      />

      <ConfirmDialog
        open={Boolean(cancelling)}
        danger
        busy={busy}
        title="取消巡检任务"
        message={`确认取消任务「${cancelling?.title || ''}」吗?`}
        detail="取消后任务不再出现在待办列表, 如需巡检请重新派发。"
        confirmText="确认取消"
        onConfirm={confirmCancel}
        onCancel={() => setCancelling(null)}
      />
    </>
  )
}
