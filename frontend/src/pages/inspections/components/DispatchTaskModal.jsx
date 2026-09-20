import { useEffect, useState } from 'react'
import { createTask } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Checkbox, Field, Input } from '../../../components/common/FormField.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'

const EMPTY = { station_id: '', title: '', due_date: '', assignee: '', remark: '' }

export default function DispatchTaskModal({ open, options, stations, onClose, onCreated, onError }) {
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [items, setItems] = useState([])
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const catalog = options?.item_catalog ?? []

  useEffect(() => {
    if (!open) return
    setForm(EMPTY)
    setItems(catalog.slice(0, 4))
    setErrors({})
  }, [open, catalog])

  const set = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const toggleItem = (name) => {
    setItems((prev) =>
      prev.includes(name) ? prev.filter((item) => item !== name) : [...prev, name]
    )
    setErrors((prev) => ({ ...prev, items: undefined }))
  }

  const submit = async (event) => {
    event.preventDefault()
    const next = {}
    if (!form.station_id) next.station_id = '请选择监测点'
    if (items.length === 0) next.items = '请至少勾选一个巡检项'
    setErrors(next)
    if (Object.keys(next).length) return

    setBusy(true)
    try {
      const task = await createTask({
        station_id: Number(form.station_id),
        title: form.title.trim() || null,
        due_date: form.due_date || null,
        assignee: form.assignee.trim() || null,
        remark: form.remark.trim() || null,
        items
      })
      toast.success(`已派发巡检任务「${task.title}」`)
      onCreated()
    } catch (error) {
      setErrors(error.fields || {})
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      wide
      title="临时派发巡检任务"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" form="dispatch-task-form" className="btn btn-primary" disabled={busy}>
            {busy ? '派发中...' : '派发任务'}
          </button>
        </>
      }
    >
      <form id="dispatch-task-form" className="stack" onSubmit={submit}>
        <div className="form-grid">
          <Field label="监测点" required error={errors.station_id}>
            <select
              className={`select ${errors.station_id ? 'invalid' : ''}`}
              value={form.station_id}
              onChange={set('station_id')}
            >
              <option value="">请选择监测点</option>
              {stations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} {item.name} ({item.area})
                </option>
              ))}
            </select>
          </Field>
          <Field label="任务标题" hint="留空则按监测点自动生成">
            <Input value={form.title} onChange={set('title')} placeholder="如: 国庆前专项巡检" />
          </Field>
          <Field label="应完成日期" error={errors.due_date}>
            <Input type="date" value={form.due_date} onChange={set('due_date')} />
          </Field>
          <Field label="巡检人">
            <Input value={form.assignee} onChange={set('assignee')} placeholder="如: 李静" />
          </Field>
        </div>
        <Field label="巡检项" required error={errors.items} hint="从标准巡检项目录中勾选">
          <div className="check-grid">
            {catalog.map((name) => (
              <Checkbox
                key={name}
                label={name}
                checked={items.includes(name)}
                onChange={() => toggleItem(name)}
              />
            ))}
          </div>
        </Field>
        {errors.items ? <Alert tone="error">{errors.items}</Alert> : null}
        <Field label="备注">
          <Input value={form.remark} onChange={set('remark')} placeholder="选填" />
        </Field>
      </form>
    </Modal>
  )
}
