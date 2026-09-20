import { useState } from 'react'
import { createTask } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function ManualTaskModal({ open, catalog = [], stations = [], onClose, onCreated }) {
  const [form, setForm] = useState({
    station_id: '',
    due_date: todayStr(),
    inspector: '',
    item_codes: []
  })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => setForm({ ...form, [key]: event.target.value })
  const toggle = (code) =>
    setForm((prev) => ({
      ...prev,
      item_codes: prev.item_codes.includes(code)
        ? prev.item_codes.filter((item) => item !== code)
        : [...prev.item_codes, code]
    }))

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const task = await createTask({
        station_id: Number(form.station_id),
        due_date: form.due_date || null,
        inspector: form.inspector || null,
        items: form.item_codes
      })
      onCreated?.(task)
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
      title="手动派发巡检任务"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '提交中...' : '创建任务'}
          </button>
        </>
      }
    >
      <div className="stack">
        {message ? <Alert tone="error">{message}</Alert> : null}
        <div className="form-grid">
          <Field label="监测点" required error={errors.station_id}>
            <select
              className={`select ${errors.station_id ? 'invalid' : ''}`}
              value={form.station_id}
              onChange={update('station_id')}
            >
              <option value="">请选择监测点</option>
              {stations.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </Field>
          <Field label="应检日期" required error={errors.due_date}>
            <Input type="date" value={form.due_date} onChange={update('due_date')} />
          </Field>
        </div>
        <Field label="巡检人" error={errors.inspector}>
          <Input value={form.inspector} onChange={update('inspector')} />
        </Field>
        <Field label="巡检项" required error={errors.items} hint={`已选 ${form.item_codes.length} 项`}>
          <div className="check-grid">
            {catalog.map((item) => (
              <label key={item.code}
                className={`check-card ${form.item_codes.includes(item.code) ? 'selected' : ''}`}
                title={item.description}>
                <input type="checkbox" checked={form.item_codes.includes(item.code)} onChange={() => toggle(item.code)} />
                <span>
                  <span className="strong">{item.name}</span>
                  <span className="small muted" style={{ display: 'block' }}>{item.description}</span>
                </span>
              </label>
            ))}
          </div>
        </Field>
      </div>
    </Modal>
  )
}
