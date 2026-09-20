import { useState } from 'react'
import { convertItemToWorkOrder } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { WORK_ORDER_PRIORITY_LABELS } from '../../../constants/index.js'

const PRIORITY_OPTIONS = Object.entries(WORK_ORDER_PRIORITY_LABELS).map(([value, label]) => ({ value, label }))

export default function ConvertOrderModal({ task, item, onClose, onCreated }) {
  const [form, setForm] = useState({
    title: task && item ? `${task.station_name} · ${item.item_name}异常` : '',
    description: item?.remark || '',
    priority: 'high',
    reporter: task?.inspector || '',
    assignee: '',
    due_date: ''
  })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const order = await convertItemToWorkOrder(task.id, item.id, {
        title: form.title,
        description: form.description || null,
        priority: form.priority,
        reporter: form.reporter || null,
        assignee: form.assignee || null,
        due_date: form.due_date || null
      })
      onCreated?.(order)
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      title="巡检异常转维修工单"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '提交中...' : '确认转单'}
          </button>
        </>
      }
    >
      <div className="stack">
        <Alert tone="warning">
          转单后将自动生成维修工单，并把监测点「{task?.station_name}」台账状态置为“维护中”；
          工单办结后自动恢复“运行中”。
        </Alert>

        <dl className="kv">
          <dt>巡检任务</dt>
          <dd className="mono">{task?.code}</dd>
          <dt>异常巡检项</dt>
          <dd>{item?.item_name} <span className="muted small">({item?.category})</span></dd>
          <dt>异常说明</dt>
          <dd>{item?.remark}</dd>
        </dl>

        {message ? <Alert tone="error">{message}</Alert> : null}

        <Field label="工单标题" required error={errors.title}>
          <Input value={form.title} onChange={update('title')} maxLength={160} />
        </Field>
        <div className="form-grid">
          <Field label="优先级" error={errors.priority}>
            <Select value={form.priority} onChange={update('priority')} options={PRIORITY_OPTIONS} />
          </Field>
          <Field label="要求完成日期" error={errors.due_date}>
            <Input type="date" value={form.due_date} onChange={update('due_date')} />
          </Field>
          <Field label="报修人" error={errors.reporter}>
            <Input value={form.reporter} onChange={update('reporter')} placeholder="默认带出巡检人" />
          </Field>
          <Field label="维修负责人" error={errors.assignee}>
            <Input value={form.assignee} onChange={update('assignee')} placeholder="可稍后派单" />
          </Field>
        </div>
        <Field label="故障描述" hint="默认带入巡检异常说明, 可补充故障现象与初步判断" error={errors.description}>
          <Textarea value={form.description} onChange={update('description')} />
        </Field>
      </div>
    </Modal>
  )
}
