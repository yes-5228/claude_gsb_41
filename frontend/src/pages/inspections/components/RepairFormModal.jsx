import { useEffect, useState } from 'react'
import { createRepair } from '../../../api/repairs.js'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'

const EMPTY = {
  station_id: '',
  title: '',
  description: '',
  priority: 'medium',
  reporter: '',
  handler: ''
}

export default function RepairFormModal({ open, options, stations, onClose, onCreated, onError }) {
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setForm(EMPTY)
    setErrors({})
  }, [open])

  const set = (key) => (event) => {
    setForm((prev) => ({ ...prev, [key]: event.target.value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  const submit = async (event) => {
    event.preventDefault()
    const next = {}
    if (!form.station_id) next.station_id = '请选择监测点'
    if (!form.title.trim()) next.title = '请填写工单标题'
    setErrors(next)
    if (Object.keys(next).length) return

    setBusy(true)
    try {
      const repair = await createRepair({
        station_id: Number(form.station_id),
        title: form.title.trim(),
        description: form.description.trim() || null,
        priority: form.priority,
        reporter: form.reporter.trim() || null,
        handler: form.handler.trim() || null
      })
      toast.success(`维修工单 ${repair.code} 已创建, 台账状态已同步为维护中`)
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
      title="手工报修"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" form="repair-form" className="btn btn-primary" disabled={busy}>
            {busy ? '提交中...' : '创建工单'}
          </button>
        </>
      }
    >
      <form id="repair-form" className="stack" onSubmit={submit}>
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
          <Field label="优先级" required>
            <Select
              value={form.priority}
              onChange={set('priority')}
              options={options?.priorities ?? []}
            />
          </Field>
          <Field label="工单标题" required error={errors.title} className="span-2">
            <Input
              value={form.title}
              onChange={set('title')}
              invalid={Boolean(errors.title)}
              placeholder="如: SO2 分析仪无响应"
            />
          </Field>
          <Field label="问题描述" error={errors.description} className="span-2">
            <Textarea
              value={form.description}
              onChange={set('description')}
              placeholder="故障现象、发现途径、影响范围"
            />
          </Field>
          <Field label="报修人">
            <Input value={form.reporter} onChange={set('reporter')} placeholder="如: 李静" />
          </Field>
          <Field label="处理人" hint="填写后工单直接进入处理中">
            <Input value={form.handler} onChange={set('handler')} placeholder="可稍后接单再填" />
          </Field>
        </div>
      </form>
    </Modal>
  )
}
