import { useCallback, useEffect, useState } from 'react'
import {
  convertItemToWorkOrder,
  getTask,
  recordTaskItem,
  startTask,
  submitTask
} from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { Alert, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import { Field, Input, Textarea } from '../../../components/common/FormField.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import {
  INSPECTION_RESULT_LABELS,
  INSPECTION_RESULT_TONE,
  INSPECTION_TASK_STATUS_LABELS,
  INSPECTION_TASK_STATUS_TONE,
  WORK_ORDER_STATUS_LABELS,
  WORK_ORDER_STATUS_TONE
} from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'
import ConvertOrderModal from './ConvertOrderModal.jsx'
import WorkOrderDetailModal from '../workorders/WorkOrderDetailModal.jsx'

const READONLY_STATUSES = ['completed', 'abnormal']

export default function TaskExecuteDrawer({ taskId, onClose, onChanged }) {
  const toast = useToast()
  const loader = useCallback(() => getTask(taskId), [taskId])
  const { data, loading, error, reload } = useAsyncData(loader, { immediate: Boolean(taskId) })

  const [inspector, setInspector] = useState('')
  const [drafts, setDrafts] = useState({}) // itemId -> { result, remark }
  const [savingId, setSavingId] = useState(null)
  const [summary, setSummary] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)
  const [convertTarget, setConvertTarget] = useState(null)
  const [orderId, setOrderId] = useState(null)

  useEffect(() => {
    if (!data) return
    setInspector(data.inspector || '')
    setSummary(data.summary || '')
    setDrafts(
      Object.fromEntries(
        (data.items || []).map((item) => [
          item.id,
          { result: item.result || '', remark: item.remark || '' }
        ])
      )
    )
    setFormError(null)
  }, [data])

  if (!taskId) return null
  const readonly = data ? READONLY_STATUSES.includes(data.status) : false

  const updateDraft = (itemId, patch) =>
    setDrafts((prev) => ({ ...prev, [itemId]: { ...prev[itemId], ...patch } }))

  const ensureStarted = async () => {
    if (data.status === 'pending' || data.status === 'overdue') {
      await startTask(data.id, { inspector: inspector || null })
    }
  }

  const saveItem = async (item) => {
    const draft = drafts[item.id] || {}
    if (!draft.result) {
      toast.warning('请先选择巡检结果')
      return
    }
    setSavingId(item.id)
    setFormError(null)
    try {
      await ensureStarted()
      await recordTaskItem(data.id, item.id, {
        result: draft.result,
        remark: draft.remark || null,
        inspector: inspector || null
      })
      toast.success(`「${item.item_name}」已登记为${INSPECTION_RESULT_LABELS[draft.result]}`)
      await reload()
      onChanged?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSavingId(null)
    }
  }

  const handleSubmit = async () => {
    const unrecorded = (data.items || []).filter((item) => !item.result)
    if (unrecorded.length) {
      toast.warning(`还有 ${unrecorded.length} 个巡检项未登记结果`)
      return
    }
    setSubmitting(true)
    setFormError(null)
    try {
      await submitTask(data.id, { summary: summary || null, inspector: inspector || null })
      toast.success('巡检任务已提交')
      await reload()
      onChanged?.()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const progress = data?.progress || { total: 0, recorded: 0, abnormal: 0 }

  return (
    <Modal
      open={Boolean(taskId)}
      drawer
      title={data ? `巡检任务 · ${data.code}` : '巡检任务'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
          {data && !readonly ? (
            <button type="button" className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
              {submitting ? '提交中...' : '提交巡检任务'}
            </button>
          ) : null}
        </>
      }
    >
      {loading && !data ? <Loading /> : null}
      {error && !data ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="stack">
          <div className="inline">
            <h3 style={{ margin: 0 }}>{data.station_name}</h3>
            <Tag tone={INSPECTION_TASK_STATUS_TONE[data.status]}>
              {INSPECTION_TASK_STATUS_LABELS[data.status]}
            </Tag>
            {data.plan_name ? <Tag tone="outline">{data.plan_name}</Tag> : <Tag tone="outline">临时任务</Tag>}
          </div>

          <dl className="kv">
            <dt>点位编码</dt>
            <dd className="mono">{data.station_code} · {data.station_area}</dd>
            <dt>应检日期</dt>
            <dd>{formatDate(data.due_date)}</dd>
            <dt>检查进度</dt>
            <dd>
              {progress.recorded}/{progress.total} 项
              {progress.abnormal ? <span className="danger-text"> · 异常 {progress.abnormal} 项</span> : null}
            </dd>
            <dt>开始/完成</dt>
            <dd>
              {formatDateTime(data.started_at)} / {formatDateTime(data.finished_at)}
            </dd>
          </dl>

          {!readonly ? (
            <Field label="巡检人">
              <Input value={inspector} onChange={(e) => setInspector(e.target.value)} placeholder="如: 张三" />
            </Field>
          ) : (
            <Alert tone="info">
              该任务已办结(巡检人: {data.inspector || '-'})，巡检记录为只读，可查看异常项关联的维修工单。
            </Alert>
          )}

          {formError ? <Alert tone="error">{formError}</Alert> : null}

          <div className="inspection-item-list">
            {(data.items || []).map((item, index) => (
              <InspectionItemCard
                key={item.id}
                item={item}
                index={index}
                readonly={readonly}
                draft={drafts[item.id] || { result: item.result || '', remark: item.remark || '' }}
                saving={savingId === item.id}
                onChange={(patch) => updateDraft(item.id, patch)}
                onSave={() => saveItem(item)}
                onConvert={() => setConvertTarget(item)}
                onViewOrder={() => setOrderId(item.work_order_id)}
              />
            ))}
          </div>

          <Field label="巡检总结" hint="说明本次巡检的整体情况, 异常项建议在下方逐项描述">
            <Textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              disabled={readonly}
              placeholder="如: 整体运行正常, 采样系统异常已转维修"
            />
          </Field>
        </div>
      ) : null}

      {convertTarget ? (
        <ConvertOrderModal
          task={data}
          item={convertTarget}
          onClose={() => setConvertTarget(null)}
          onCreated={async () => {
            setConvertTarget(null)
            toast.success('已生成维修工单, 台账状态已更新为“维护中”')
            await reload()
            onChanged?.()
          }}
        />
      ) : null}
      {orderId ? (
        <WorkOrderDetailModal orderId={orderId} onClose={() => setOrderId(null)} onChanged={onChanged} />
      ) : null}
    </Modal>
  )
}

function InspectionItemCard({ item, index, readonly, draft, saving, onChange, onSave, onConvert, onViewOrder }) {
  const isAbnormal = item.result === 'abnormal'
  const hasActiveOrder = item.work_order_id && ['open', 'processing'].includes(item.work_order_status)
  return (
    <div className={`inspection-item ${item.result ? `is-${item.result}` : ''}`}>
      <div className="inspection-item-head">
        <div>
          <span className="muted small mono">{String(index + 1).padStart(2, '0')}</span>
          <span className="strong" style={{ marginLeft: 8 }}>{item.item_name}</span>
          <Tag tone="neutral">{item.category}</Tag>
        </div>
        <div className="inline">
          {item.result ? (
            <Tag tone={INSPECTION_RESULT_TONE[item.result]}>
              {INSPECTION_RESULT_LABELS[item.result] || item.result}
            </Tag>
          ) : (
            <Tag tone="warning">未检查</Tag>
          )}
          {item.checked_at ? <span className="small muted">{formatDateTime(item.checked_at)}</span> : null}
        </div>
      </div>

      {!readonly ? (
        <div className="stack" style={{ gap: 10 }}>
          <div className="inline">
            {Object.entries(INSPECTION_RESULT_LABELS).map(([value, label]) => (
              <label key={value} className="checkbox">
                <input
                  type="radio"
                  name={`result-${item.id}`}
                  checked={(draft.result || '') === value}
                  onChange={() => onChange({ result: value })}
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <Textarea
            value={draft.remark || ''}
            invalid={draft.result === 'abnormal' && !draft.remark}
            placeholder={
              draft.result === 'abnormal'
                ? '异常情况说明 (必填), 如: 采样泵异响, 流量偏低, 疑似管路堵塞'
                : '现场情况备注 (选填)'
            }
            onChange={(e) => onChange({ remark: e.target.value })}
          />
          <div className="inline">
            <button type="button" className="btn btn-sm btn-primary" onClick={onSave} disabled={saving}>
              {saving ? '保存中...' : '保存本项'}
            </button>
            {draft.result === 'abnormal' || isAbnormal ? (
              item.work_order_id ? (
                <button type="button" className="btn btn-sm" onClick={onViewOrder}>
                  查看维修工单
                  <Tag tone={WORK_ORDER_STATUS_TONE[item.work_order_status]}>
                    {WORK_ORDER_STATUS_LABELS[item.work_order_status]}
                  </Tag>
                </button>
              ) : (
                <button type="button" className="btn btn-sm btn-danger" onClick={onConvert}>
                  转为维修工单
                </button>
              )
            ) : null}
            {hasActiveOrder ? <span className="small warning-text">工单处理中, 点位台账为“维护中”</span> : null}
          </div>
        </div>
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          <div className="small">{item.remark || <span className="muted">无备注</span>}</div>
          <div className="small muted">登记人: {item.inspector || '-'}</div>
          {isAbnormal && item.work_order_id ? (
            <div>
              <button type="button" className="btn btn-sm" onClick={onViewOrder}>
                查看维修工单
                <Tag tone={WORK_ORDER_STATUS_TONE[item.work_order_status]}>
                  {WORK_ORDER_STATUS_LABELS[item.work_order_status]}
                </Tag>
              </button>
            </div>
          ) : null}
          {isAbnormal && !item.work_order_id ? (
            <div>
              <button type="button" className="btn btn-sm btn-danger" onClick={onConvert}>
                补转维修工单
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}
