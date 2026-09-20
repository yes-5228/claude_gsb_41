import { useState } from 'react'
import { deletePlan, dispatchPlan, listPlans, updatePlan } from '../../../api/inspections.js'
import { SectionCard } from '../../../components/common/Card.jsx'
import ConfirmDialog from '../../../components/common/ConfirmDialog.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import Pagination from '../../../components/common/Pagination.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { useListQuery } from '../../../hooks/useListQuery.js'
import { useRefreshKey } from '../../../hooks/useRefreshKey.js'
import PlanFormModal from './PlanFormModal.jsx'

const INITIAL_FILTERS = {}

export default function PlansPanel({ refreshKey, options, onChanged, onError }) {
  const toast = useToast()
  const query = useListQuery(listPlans, INITIAL_FILTERS)
  const [formState, setFormState] = useState({ open: false, plan: null })
  const [deleting, setDeleting] = useState(null)
  const [busy, setBusy] = useState(false)

  const { reload } = query
  useRefreshKey(refreshKey, reload)

  const runDispatch = async (plan) => {
    setBusy(true)
    try {
      const result = await dispatchPlan(plan.id)
      if (result.created) {
        toast.success(`已派发任务「${result.title}」`)
      } else {
        toast.info(`本期任务已存在: 「${result.title}」, 无需重复派发`)
      }
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (plan) => {
    setBusy(true)
    try {
      await updatePlan(plan.id, { active: !plan.active })
      toast.success(plan.active ? `计划「${plan.name}」已停用` : `计划「${plan.name}」已启用`)
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      await deletePlan(deleting.id)
      toast.success(`计划「${deleting.name}」已删除`)
      setDeleting(null)
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    { key: 'name', title: '计划名称' },
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
    { key: 'cycle_label', title: '巡检周期' },
    {
      key: 'items',
      title: '巡检项',
      render: (row) => (
        <span title={row.items.join('、')}>{row.items.length} 项</span>
      )
    },
    { key: 'assignee', title: '默认巡检人', render: (row) => row.assignee || '-' },
    {
      key: 'active',
      title: '状态',
      render: (row) =>
        row.active ? <Tag tone="success">启用中</Tag> : <Tag tone="neutral">已停用</Tag>
    },
    {
      key: 'actions',
      title: '操作',
      render: (row) => (
        <div className="btn-group">
          <button
            type="button"
            className="btn btn-sm btn-primary"
            disabled={!row.active || busy}
            onClick={() => runDispatch(row)}
          >
            派发本期
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setFormState({ open: true, plan: row })}
          >
            编辑
          </button>
          <button type="button" className="btn btn-sm" disabled={busy} onClick={() => toggleActive(row)}>
            {row.active ? '停用' : '启用'}
          </button>
          <button
            type="button"
            className="btn btn-sm btn-danger"
            disabled={busy}
            onClick={() => setDeleting(row)}
          >
            删除
          </button>
        </div>
      )
    }
  ]

  return (
    <>
      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="巡检计划"
        hint="按周期为点位配置巡检项模板, 派发时自动生成本期任务并按周期去重"
        actions={
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setFormState({ open: true, plan: null })}
          >
            + 新建巡检计划
          </button>
        }
      >
        <DataTable
          columns={columns}
          rows={query.items}
          loading={query.loading}
          emptyText="暂无巡检计划, 点击右上角新建"
          emptyIcon="🗓️"
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

      <PlanFormModal
        open={formState.open}
        plan={formState.plan}
        options={options}
        onClose={() => setFormState({ open: false, plan: null })}
        onSaved={() => {
          setFormState({ open: false, plan: null })
          onChanged()
        }}
        onError={onError}
      />

      <ConfirmDialog
        open={Boolean(deleting)}
        danger
        busy={busy}
        title="删除巡检计划"
        message={`确认删除计划「${deleting?.name || ''}」吗?`}
        detail="已派发过任务的计划无法删除, 可改为停用。"
        confirmText="确认删除"
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
      />
    </>
  )
}
