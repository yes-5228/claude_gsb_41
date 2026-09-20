import { useCallback, useState } from 'react'
import { getWorkOrder, updateWorkOrder } from '../../../api/workOrders.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { Alert, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import {
  WORK_ORDER_PRIORITY_LABELS,
  WORK_ORDER_PRIORITY_TONE,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_STATUS_TONE
} from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'

export default function WorkOrderDetailModal({ orderId, onClose, onChanged }) {
  const toast = useToast()
  const loader = useCallback(() => getWorkOrder(orderId), [orderId])
  const { data, loading, error, reload } = useAsyncData(loader, { immediate: Boolean(orderId) })
  const [busy, setBusy] = useState(false)
  const [action, setAction] = useState(null) // processing / resolved / closed / cancelled
  const [form, setForm] = useState({ assignee: '', resolution: '', restore_status: 'active' })
  const [formError, setFormError] = useState(null)

  const open = Boolean(orderId)

  const begin = (next) => {
    setAction(next)
    setFormError(null)
    if (data) setForm((prev) => ({ ...prev, assignee: prev.assignee || data.assignee || '' }))
  }

  const confirm = async () => {
    if (action === 'resolved' && !form.resolution.trim()) {
      setFormError('维修完成时必须填写处理说明')
      return
    }
    setBusy(true)
    setFormError(null)
    try {
      await updateWorkOrder(data.id, {
        status: action,
        assignee: form.assignee || null,
        resolution: form.resolution || null,
        restore_status: action === 'resolved' ? form.restore_status : null
      })
      toast.success(`工单已更新为“${WORK_ORDER_STATUS_LABELS[action]}”`)
      setAction(null)
      setForm((prev) => ({ ...prev, resolution: '' }))
      await reload()
      onChanged?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const terminal = data && ['closed', 'cancelled'].includes(data.status)

  return (
    <Modal
      open={open}
      title={data ? `维修工单 · ${data.code}` : '维修工单'}
      onClose={onClose}
      footer={
        data && !terminal ? (
          <>
            <button type="button" className="btn" onClick={onClose} disabled={busy}>
              关闭
            </button>
            {data.status === 'open' ? (
              <>
                <button type="button" className="btn" onClick={() => begin('cancelled')} disabled={busy}>
                  取消工单
                </button>
                <button type="button" className="btn btn-primary" onClick={() => begin('processing')} disabled={busy}>
                  开始维修 / 派单
                </button>
              </>
            ) : null}
            {data.status === 'processing' ? (
              <>
                <button type="button" className="btn" onClick={() => begin('cancelled')} disabled={busy}>
                  取消工单
                </button>
                <button type="button" className="btn btn-primary" onClick={() => begin('resolved')} disabled={busy}>
                  维修完成, 回写台账
                </button>
              </>
            ) : null}
            {data.status === 'resolved' ? (
              <button type="button" className="btn btn-primary" onClick={() => begin('closed')} disabled={busy}>
                关闭工单
              </button>
            ) : null}
          </>
        ) : null
      }
    >
      {loading && !data ? <Loading /> : null}
      {error && !data ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="stack">
          <div className="inline">
            <h3 style={{ margin: 0 }}>{data.title}</h3>
            <Tag tone={WORK_ORDER_STATUS_TONE[data.status]}>{data.status_label}</Tag>
            <Tag tone={WORK_ORDER_PRIORITY_TONE[data.priority]}>{data.priority_label}优先级</Tag>
            <Tag tone="outline">{data.source_label}</Tag>
          </div>

          <dl className="kv">
            <dt>监测点</dt>
            <dd>{data.station_name} <span className="muted mono">{data.station_code} · {data.station_area}</span></dd>
            <dt>来源巡检</dt>
            <dd>{data.inspection_task_code || '-'} {data.item_name ? `· ${data.item_name}` : ''}</dd>
            <dt>报修人</dt>
            <dd>{data.reporter || '-'}</dd>
            <dt>维修负责人</dt>
            <dd>{data.assignee || '待派单'}</dd>
            <dt>报修时间</dt>
            <dd>{formatDateTime(data.reported_at)}</dd>
            <dt>要求完成</dt>
            <dd>{formatDate(data.due_date)}</dd>
            <dt>开始维修</dt>
            <dd>{formatDateTime(data.started_at)}</dd>
            <dt>修复时间</dt>
            <dd>{formatDateTime(data.resolved_at)}</dd>
          </dl>

          {data.description ? (
            <div>
              <div className="field-label">故障描述</div>
              <div className="inspection-note">{data.description}</div>
            </div>
          ) : null}
          {data.resolution ? (
            <div>
              <div className="field-label">处理说明</div>
              <div className="inspection-note success">{data.resolution}</div>
            </div>
          ) : null}

          <Alert tone="info">
            {['open', 'processing'].includes(data.status)
              ? '工单处理期间, 台账运行状态保持“维护中”；维修完成提交后自动恢复为“运行中”。'
              : '工单已办结, 台账状态已同步。'}
          </Alert>

          {formError ? <Alert tone="error">{formError}</Alert> : null}

          {action ? (
            <div className="card" style={{ boxShadow: 'none' }}>
              <div className="card-body tight stack">
                <div className="strong">
                  {action === 'processing' && '开始维修 / 指派负责人'}
                  {action === 'resolved' && '维修完成处理'}
                  {action === 'closed' && '确认关闭工单'}
                  {action === 'cancelled' && '取消工单'}
                </div>
                {(action === 'processing') ? (
                  <Field label="维修负责人">
                    <Input
                      value={form.assignee}
                      onChange={(e) => setForm({ ...form, assignee: e.target.value })}
                      placeholder="如: 赵宇"
                    />
                  </Field>
                ) : null}
                {action === 'resolved' ? (
                  <>
                    <Field label="处理说明" required error={formError || undefined}>
                      <Textarea
                        value={form.resolution}
                        onChange={(e) => setForm({ ...form, resolution: e.target.value })}
                        placeholder="如: 已更换光源组件并重做跨度校准, 数据恢复正常"
                      />
                    </Field>
                    <Field label="完成后台账状态恢复为">
                      <Select
                        value={form.restore_status}
                        onChange={(e) => setForm({ ...form, restore_status: e.target.value })}
                        options={[
                          { value: 'active', label: '运行中' },
                          { value: 'maintenance', label: '维护中' }
                        ]}
                      />
                    </Field>
                  </>
                ) : null}
                {action === 'cancelled' ? (
                  <Field label="取消原因">
                    <Textarea
                      value={form.resolution}
                      onChange={(e) => setForm({ ...form, resolution: e.target.value })}
                      placeholder="如: 现场复测故障消失, 无需维修"
                    />
                  </Field>
                ) : null}
                <div className="inline">
                  <button type="button" className="btn btn-primary" onClick={confirm} disabled={busy}>
                    {busy ? '提交中...' : '确认'}
                  </button>
                  <button type="button" className="btn" onClick={() => setAction(null)} disabled={busy}>
                    返回
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  )
}
