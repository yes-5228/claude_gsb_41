import { useCallback, useEffect, useMemo, useState } from 'react'
import { completeTask, getTask, startTask } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Checkbox, Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert, ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import {
  INSPECTION_ITEM_RESULT_TONE,
  INSPECTION_TASK_STATUS_TONE,
  REPAIR_PRIORITY_TONE,
  REPAIR_STATUS_TONE
} from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDate, formatDateTime } from '../../../utils/format.js'

const RESULT_CHOICES = [
  { value: 'normal', label: '正常' },
  { value: 'abnormal', label: '异常' },
  { value: 'skipped', label: '未检' }
]

const PRIORITY_OPTIONS = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' }
]

export default function ExecuteTaskDrawer({ taskId, onClose, onCompleted, onError }) {
  const toast = useToast()
  const loader = useCallback(() => getTask(taskId), [taskId])
  const { data: task, loading, error, reload } = useAsyncData(loader, {
    immediate: Boolean(taskId)
  })

  const [results, setResults] = useState({})
  const [executor, setExecutor] = useState('')
  const [summary, setSummary] = useState('')
  const [withRepair, setWithRepair] = useState(true)
  const [repair, setRepair] = useState({ title: '', description: '', priority: 'high' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const open = Boolean(taskId)
  const editable = task && (task.status === 'pending' || task.status === 'in_progress')

  useEffect(() => {
    if (!task) return
    const initial = {}
    ;(task.items || []).forEach((item) => {
      initial[item.id] = { result: item.result === 'pending' ? '' : item.result, note: item.note || '' }
    })
    setResults(initial)
    setExecutor(task.executor || task.assignee || '')
    setSummary(task.summary || '')
    setWithRepair(true)
    setRepair({ title: '', description: '', priority: 'high' })
    setErrors({})
  }, [task])

  const abnormalItems = useMemo(
    () =>
      (task?.items || []).filter((item) => results[item.id]?.result === 'abnormal'),
    [task, results]
  )

  const filledCount = useMemo(
    () => Object.values(results).filter((entry) => entry.result).length,
    [results]
  )

  const setResult = (itemId, result) => {
    setResults((prev) => ({ ...prev, [itemId]: { ...prev[itemId], result } }))
    setErrors((prev) => ({ ...prev, items: undefined }))
  }
  const setNote = (itemId, note) =>
    setResults((prev) => ({ ...prev, [itemId]: { ...prev[itemId], note } }))

  const markAllNormal = () => {
    const next = {}
    ;(task.items || []).forEach((item) => {
      next[item.id] = { result: 'normal', note: '' }
    })
    setResults(next)
    setErrors({})
  }

  const validate = () => {
    const next = {}
    if (!executor.trim()) next.executor = '请填写巡检人'
    const unfilled = (task.items || []).filter((item) => !results[item.id]?.result)
    if (unfilled.length) next.items = `还有 ${unfilled.length} 个巡检项未记录结果`
    const noNote = abnormalItems.filter((item) => !results[item.id]?.note?.trim())
    if (!next.items && noNote.length) {
      next.items = `异常项「${noNote[0].item_name}」需要填写异常说明`
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const submit = async () => {
    if (!validate()) return
    setBusy(true)
    try {
      const payload = {
        items: (task.items || []).map((item) => ({
          id: item.id,
          result: results[item.id].result,
          note: results[item.id].note?.trim() || null
        })),
        executor: executor.trim(),
        summary: summary.trim() || null
      }
      if (withRepair && abnormalItems.length > 0) {
        payload.repair = {
          title: repair.title.trim() || null,
          description: repair.description.trim() || null,
          priority: repair.priority
        }
      }
      const result = await completeTask(task.id, payload)
      if (result.repair_order) {
        toast.warning(
          `巡检完成, 发现 ${result.abnormal_count} 项异常; 已生成维修工单 ${result.repair_order.code}, 台账已切换为维护中`
        )
      } else {
        toast.success('巡检完成, 所有巡检项已记录')
      }
      onCompleted()
    } catch (err) {
      setErrors(err.fields || {})
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  const markStarted = async () => {
    setBusy(true)
    try {
      await startTask(task.id, { executor: executor.trim() || undefined })
      toast.info('任务已标记为执行中')
      await reload()
    } catch (err) {
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      drawer
      title={editable ? '执行巡检任务' : '巡检任务详情'}
      onClose={onClose}
      footer={
        editable ? (
          <>
            <span className="small muted" style={{ marginRight: 'auto' }}>
              已记录 {filledCount} / {task?.items?.length ?? 0} 项
              {abnormalItems.length ? ` · 异常 ${abnormalItems.length} 项` : ''}
            </span>
            {task?.status === 'pending' ? (
              <button type="button" className="btn" onClick={markStarted} disabled={busy}>
                标记执行中
              </button>
            ) : null}
            <button type="button" className="btn" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
              {busy ? '提交中...' : '提交巡检结果'}
            </button>
          </>
        ) : (
          <button type="button" className="btn" onClick={onClose}>
            关闭
          </button>
        )
      }
    >
      {loading && !task ? <Loading text="正在加载巡检任务..." /> : null}
      {error && !task ? <ErrorState error={error} onRetry={() => reload().catch(() => {})} /> : null}
      {task ? (
        <div className="stack">
          <div className="inline">
            <h3 style={{ margin: 0 }}>{task.station_name}</h3>
            <Tag tone={INSPECTION_TASK_STATUS_TONE[task.status]}>{task.status_label}</Tag>
            <Tag tone="primary">{task.cycle_label}</Tag>
            {task.result ? (
              <Tag tone={task.result === 'normal' ? 'success' : 'danger'}>{task.result_label}</Tag>
            ) : null}
          </div>
          <dl className="kv">
            <dt>任务标题</dt>
            <dd>{task.title}</dd>
            <dt>监测点编码</dt>
            <dd className="mono">{task.station_code}</dd>
            <dt>应完成日期</dt>
            <dd>{formatDate(task.due_date)}</dd>
            <dt>计划来源</dt>
            <dd>{task.plan_name || '手工临时派发'}</dd>
            <dt>派发时间</dt>
            <dd>{formatDateTime(task.dispatched_at)}</dd>
            {task.completed_at ? (
              <>
                <dt>完成时间</dt>
                <dd>{formatDateTime(task.completed_at)}</dd>
              </>
            ) : null}
          </dl>

          <div className="card" style={{ boxShadow: 'none' }}>
            <div className="card-header">
              <h3>巡检项结果</h3>
              {editable ? (
                <button type="button" className="btn btn-sm" onClick={markAllNormal}>
                  全部正常
                </button>
              ) : null}
            </div>
            <div className="card-body stack">
              {errors.items ? <Alert tone="error">{errors.items}</Alert> : null}
              {(task.items || []).map((item, index) => {
                const entry = results[item.id] || { result: '', note: '' }
                return (
                  <div key={item.id} className="stack" style={{ gap: 8 }}>
                    <div className="inline" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
                      <span>
                        <span className="muted small">{index + 1}.</span> {item.item_name}
                      </span>
                      {editable ? (
                        <div className="result-picker">
                          {RESULT_CHOICES.map((choice) => (
                            <button
                              key={choice.value}
                              type="button"
                              className={entry.result === choice.value ? `on-${choice.value}` : ''}
                              onClick={() => setResult(item.id, choice.value)}
                            >
                              {choice.label}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <Tag tone={INSPECTION_ITEM_RESULT_TONE[item.result]}>{item.result_label}</Tag>
                      )}
                    </div>
                    {editable && entry.result === 'abnormal' ? (
                      <Input
                        value={entry.note}
                        onChange={(event) => setNote(item.id, event.target.value)}
                        placeholder="异常说明 (必填): 现象、位置、初步判断"
                      />
                    ) : null}
                    {editable && entry.result && entry.result !== 'abnormal' ? (
                      <Input
                        value={entry.note}
                        onChange={(event) => setNote(item.id, event.target.value)}
                        placeholder="备注 (选填)"
                      />
                    ) : null}
                    {!editable && item.note ? (
                      <div className="small muted">备注: {item.note}</div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </div>

          {editable ? (
            <>
              <div className="form-grid">
                <Field label="巡检人" required error={errors.executor}>
                  <Input
                    value={executor}
                    onChange={(event) => {
                      setExecutor(event.target.value)
                      setErrors((prev) => ({ ...prev, executor: undefined }))
                    }}
                    invalid={Boolean(errors.executor)}
                    placeholder="实际执行巡检的人员"
                  />
                </Field>
                <Field label="巡检总结" error={errors.summary}>
                  <Input
                    value={summary}
                    onChange={(event) => setSummary(event.target.value)}
                    placeholder="整体情况概述 (选填)"
                  />
                </Field>
              </div>

              {abnormalItems.length > 0 ? (
                <div className="card" style={{ boxShadow: 'none', borderColor: 'var(--warning)' }}>
                  <div className="card-header">
                    <h3>异常转维修工单</h3>
                    <Tag tone="warning">异常 {abnormalItems.length} 项</Tag>
                  </div>
                  <div className="card-body stack">
                    <Checkbox
                      label={`生成维修工单 (提交后台账将切换为“维护中”, 并进入待办列表)`}
                      checked={withRepair}
                      onChange={(event) => setWithRepair(event.target.checked)}
                    />
                    {withRepair ? (
                      <div className="form-grid">
                        <Field label="工单标题" hint="留空则按监测点自动生成">
                          <Input
                            value={repair.title}
                            onChange={(event) =>
                              setRepair((prev) => ({ ...prev, title: event.target.value }))
                            }
                            placeholder={`${task.station_name} 设备异常维修`}
                          />
                        </Field>
                        <Field label="优先级">
                          <Select
                            value={repair.priority}
                            onChange={(event) =>
                              setRepair((prev) => ({ ...prev, priority: event.target.value }))
                            }
                            options={PRIORITY_OPTIONS}
                          />
                        </Field>
                        <Field
                          label="问题描述"
                          className="span-2"
                          hint={`留空则自动汇总异常项: ${abnormalItems.map((item) => item.item_name).join('、')}`}
                        >
                          <Textarea
                            value={repair.description}
                            onChange={(event) =>
                              setRepair((prev) => ({ ...prev, description: event.target.value }))
                            }
                            placeholder="补充故障现象、影响范围等"
                          />
                        </Field>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </>
          ) : null}

          {!editable && task.summary ? (
            <dl className="kv">
              <dt>巡检总结</dt>
              <dd>{task.summary}</dd>
              <dt>巡检人</dt>
              <dd>{task.executor || '-'}</dd>
            </dl>
          ) : null}

          {!editable && (task.repair_orders || []).length ? (
            <div className="card" style={{ boxShadow: 'none' }}>
              <div className="card-header">
                <h3>关联维修工单</h3>
              </div>
              <div className="card-body stack">
                {task.repair_orders.map((order) => (
                  <div key={order.id} className="inline" style={{ justifyContent: 'space-between' }}>
                    <span>
                      <span className="mono small muted">{order.code}</span> {order.title}
                    </span>
                    <span className="inline">
                      <Tag tone={REPAIR_PRIORITY_TONE[order.priority]}>{order.priority_label}</Tag>
                      <Tag tone={REPAIR_STATUS_TONE[order.status]}>{order.status_label}</Tag>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </Modal>
  )
}
