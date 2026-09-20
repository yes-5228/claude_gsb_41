import { useState } from 'react'
import { createWorkOrder } from '../../../api/workOrders.js'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { WORK_ORDER_PRIORITY_LABELS } from '../../../constants/index.js'

const PRIORITY_OPTIONS = Object.entries(WORK_ORDER_PRIORITY_LABELS).map(([value, label]) => ({ value, label }))

const EMPTY = {
  station_id: '',
  title: '',
  description: '',
  priority: 'normal',
  reporter: '',
  assignee: '',
  due_date: ''
}

export default function WorkOrderFormModal({ open, stations, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const order = await createWorkOrder({
        ...form,
        station_id: Number(form.station_id),
        due_date: form.due_date || null
      })
      onCreated?.(order)
      setForm(EMPTY)
    } catch (err) {
      setErrors(err.fields || {})
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      title="新建维修工单"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '提交中...' : '创建工单'}
          </button>
        </>
      }
    >
      <div className="stack">
        <Alert tone="info">人工建单后点位台账将同步置为“维护中”, 维修办结后自动恢复“运行中”。</Alert>
        {message ? <Alert tone="error">{message}</Alert> : null}

        <Field label="监测点" required error={errors.station_id}>
          <Select
            value={form.station_id}
            onChange={update('station_id')}
            placeholder="请选择出现故障的监测点"
            options={stations.map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))}
            invalid={Boolean(errors.station_id)}
          />
        </Field>
        <Field label="工单标题" required error={errors.title}>
          <Input value={form.title} onChange={update('title')} placeholder="如: 分析仪光源故障" maxLength={160}
            invalid={Boolean(errors.title)} />
        </Field>
        <div className="form-grid">
          <Field label="优先级" error={errors.priority}>
            <Select value={form.priority} onChange={update('priority')} options={PRIORITY_OPTIONS} />
          </Field>
          <Field label="要求完成日期" error={errors.due_date}>
            <Input type="date" value={form.due_date} onChange={update('due_date')} />
          </Field>
          <Field label="报修人" error={errors.reporter}>
            <Input value={form.reporter} onChange={update('reporter')} />
          </Field>
          <Field label="维修负责人" error={errors.assignee}>
            <Input value={form.assignee} onChange={update('assignee')} placeholder="可暂不指派" />
          </Field>
        </div>
        <Field label="故障描述" error={errors.description}>
          <Textarea value={form.description} onChange={update('description')}
            placeholder="故障现象、发生时间、初步判断等" />
        </Field>
      </div>
    </Modal>
  )
}
