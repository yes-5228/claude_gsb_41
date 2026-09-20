import { useState } from 'react'
import { claimRepair, closeRepair, listRepairs } from '../../../api/repairs.js'
import { FilterPanel, SectionCard } from '../../../components/common/Card.jsx'
import ConfirmDialog from '../../../components/common/ConfirmDialog.jsx'
import DataTable from '../../../components/common/DataTable.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import Modal from '../../../components/common/Modal.jsx'
import Pagination from '../../../components/common/Pagination.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import {
  REPAIR_PRIORITY_TONE,
  REPAIR_STATUS_TONE,
  STATION_STATUS_TONE
} from '../../../constants/index.js'
import { useListQuery } from '../../../hooks/useListQuery.js'
import { useStationOptions } from '../../../hooks/useOptions.js'
import { useRefreshKey } from '../../../hooks/useRefreshKey.js'
import { formatDateTime } from '../../../utils/format.js'
import RepairFormModal from './RepairFormModal.jsx'

const INITIAL_FILTERS = { keyword: '', status: '', priority: '', station_id: '' }

export default function RepairsPanel({ refreshKey, options, onResolve, onChanged, onError }) {
  const toast = useToast()
  const query = useListQuery(listRepairs, INITIAL_FILTERS)
  const stations = useStationOptions()
  const [draft, setDraft] = useState(INITIAL_FILTERS)
  const [formOpen, setFormOpen] = useState(false)
  const [claiming, setClaiming] = useState(null)
  const [handler, setHandler] = useState('')
  const [closing, setClosing] = useState(null)
  const [busy, setBusy] = useState(false)

  const { reload } = query
  useRefreshKey(refreshKey, reload)

  const set = (key) => (event) => setDraft((prev) => ({ ...prev, [key]: event.target.value }))

  const submitClaim = async () => {
    if (!claiming) return
    if (!handler.trim()) {
      toast.warning('请填写处理人')
      return
    }
    setBusy(true)
    try {
      await claimRepair(claiming.id, { handler: handler.trim() })
      toast.success(`工单 ${claiming.code} 已接单`)
      setClaiming(null)
      setHandler('')
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const submitClose = async () => {
    if (!closing) return
    setBusy(true)
    try {
      await closeRepair(closing.id, {})
      toast.success(`工单 ${closing.code} 已关闭`)
      setClosing(null)
      onChanged()
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  const columns = [
    {
      key: 'code',
      title: '工单号',
      className: 'cell-nowrap',
      render: (row) => <span className="mono small">{row.code}</span>
    },
    {
      key: 'title',
      title: '工单标题',
      render: (row) => (
        <div>
          <div>{row.title}</div>
          <div className="small muted">
            {row.inspection_task_title ? `巡检转入: ${row.inspection_task_title}` : '手工报修'}
          </div>
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
    { key: 'reporter', title: '报修人', render: (row) => row.reporter || '-' },
    { key: 'handler', title: '处理人', render: (row) => row.handler || '-' },
    {
      key: 'created_at',
      title: '报修时间',
      className: 'cell-nowrap',
      render: (row) => formatDateTime(row.created_at)
    },
    {
      key: 'actions',
      title: '操作',
      render: (row) => {
        const open = row.status === 'open' || row.status === 'processing'
        if (!open) return <span className="small muted">已办结</span>
        return (
          <div className="btn-group">
            {row.status === 'open' ? (
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setClaiming(row)
                  setHandler(row.handler || '')
                }}
              >
                接单
              </button>
            ) : null}
            <button type="button" className="btn btn-sm btn-primary" onClick={() => onResolve(row)}>
              处理完成
            </button>
            <button type="button" className="btn btn-sm btn-danger" onClick={() => setClosing(row)}>
              关闭
            </button>
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
          <Input value={draft.keyword} onChange={set('keyword')} placeholder="工单号 / 标题 / 监测点" />
        </Field>
        <Field label="工单状态">
          <Select
            value={draft.status}
            onChange={set('status')}
            placeholder="全部状态"
            options={options?.statuses ?? []}
          />
        </Field>
        <Field label="优先级">
          <Select
            value={draft.priority}
            onChange={set('priority')}
            placeholder="全部优先级"
            options={options?.priorities ?? []}
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
      </FilterPanel>

      {query.error ? <Alert tone="error">{query.error.message}</Alert> : null}

      <SectionCard
        title="维修工单列表"
        hint="处理完成后回写台账运行状态, 保持台账与待办一致"
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setFormOpen(true)}>
            + 手工报修
          </button>
        }
      >
        <DataTable
          columns={columns}
          rows={query.items}
          loading={query.loading}
          emptyText="暂无维修工单"
          emptyIcon="🧰"
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

      <RepairFormModal
        open={formOpen}
        options={options}
        stations={stations.data?.items ?? []}
        onClose={() => setFormOpen(false)}
        onCreated={() => {
          setFormOpen(false)
          onChanged()
        }}
        onError={onError}
      />

      <Modal
        open={Boolean(claiming)}
        title="工单接单"
        onClose={() => setClaiming(null)}
        footer={
          <>
            <button type="button" className="btn" onClick={() => setClaiming(null)} disabled={busy}>
              取消
            </button>
            <button type="button" className="btn btn-primary" onClick={submitClaim} disabled={busy}>
              {busy ? '提交中...' : '确认接单'}
            </button>
          </>
        }
      >
        <div className="stack">
          <div>
            工单 <span className="mono">{claiming?.code}</span>「{claiming?.title}」接单后进入处理中。
          </div>
          <Field label="处理人" required>
            <Input
              value={handler}
              onChange={(event) => setHandler(event.target.value)}
              placeholder="负责处理该工单的人员"
            />
          </Field>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(closing)}
        danger
        busy={busy}
        title="关闭维修工单"
        message={`确认关闭工单 ${closing?.code || ''}「${closing?.title || ''}」吗?`}
        detail="关闭适用于误报或无需维修的场景; 如需恢复台账运行状态, 请使用“处理完成”并选择回写状态。"
        confirmText="确认关闭"
        onConfirm={submitClose}
        onCancel={() => setClosing(null)}
      />
    </>
  )
}
