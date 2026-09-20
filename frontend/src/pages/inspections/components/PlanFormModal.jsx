import { useEffect, useState } from 'react'
import { createPlan, updatePlan } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Checkbox, Field, Input, Select } from '../../../components/common/FormField.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { useStationOptions } from '../../../hooks/useOptions.js'

const EMPTY = { station_id: '', name: '', cycle: 'monthly', assignee: '', remark: '', active: true }

export default function PlanFormModal({ open, plan, options, onClose, onSaved, onError }) {
  const toast = useToast()
  const stations = useStationOptions()
  const [form, setForm] = useState(EMPTY)
  const [items, setItems] = useState([])
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  const catalog = options?.item_catalog ?? []

  useEffect(() => {
    if (!open) return
    if (plan) {
      setForm({
        station_id: String(plan.station_id),
        name: plan.name || '',
        cycle: plan.cycle || 'monthly',
        assignee: plan.assignee || '',
        remark: plan.remark || '',
        active: Boolean(plan.active)
      })
      setItems(plan.items || [])
    } else {
      setForm(EMPTY)
      setItems(catalog.slice(0, 4))
    }
    setErrors({})
  }, [open, plan, catalog])

  const set = (key) => (event) => {
    const value = key === 'active' ? event.target.checked : event.target.value
    setForm((prev) => ({ ...prev, [key]: value }))
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
    if (!form.name.trim()) next.name = '请填写计划名称'
    if (items.length === 0) next.items = '请至少勾选一个巡检项'
    setErrors(next)
    if (Object.keys(next).length) return

    const payload = {
      station_id: Number(form.station_id),
      name: form.name.trim(),
      cycle: form.cycle,
      assignee: form.assignee.trim() || null,
      remark: form.remark.trim() || null,
      active: form.active,
      items
    }
    setBusy(true)
    try {
      if (plan) {
        await updatePlan(plan.id, payload)
        toast.success(`计划「${payload.name}」已更新`)
      } else {
        await createPlan(payload)
        toast.success(`计划「${payload.name}」已创建`)
      }
      onSaved()
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
      title={plan ? `编辑巡检计划 · ${plan.name}` : '新建巡检计划'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" form="plan-form" className="btn btn-primary" disabled={busy}>
            {busy ? '保存中...' : '保存'}
          </button>
        </>
      }
    >
      <form id="plan-form" className="stack" onSubmit={submit}>
        <div className="form-grid">
          <Field label="监测点" required error={errors.station_id}>
            <select
              className={`select ${errors.station_id ? 'invalid' : ''}`}
              value={form.station_id}
              onChange={set('station_id')}
              disabled={Boolean(plan)}
            >
              <option value="">请选择监测点</option>
              {(stations.data?.items ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.code} {item.name} ({item.area})
                </option>
              ))}
            </select>
          </Field>
          <Field label="计划名称" required error={errors.name}>
            <Input
              value={form.name}
              onChange={set('name')}
              invalid={Boolean(errors.name)}
              placeholder="如: 市民中心站月度巡检"
            />
          </Field>
          <Field label="巡检周期" required error={errors.cycle}>
            <Select value={form.cycle} onChange={set('cycle')} options={options?.cycles ?? []} />
          </Field>
          <Field label="默认巡检人">
            <Input value={form.assignee} onChange={set('assignee')} placeholder="如: 李静" />
          </Field>
        </div>
        <Field label="巡检项模板" required error={errors.items} hint="派发任务时按模板生成巡检项">
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
        <Checkbox label="启用该计划 (停用后不再参与一键派发)" checked={form.active} onChange={set('active')} />
      </form>
    </Modal>
  )
}
