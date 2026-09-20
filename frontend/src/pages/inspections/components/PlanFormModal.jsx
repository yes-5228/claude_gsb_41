import { useEffect, useState } from 'react'
import { createPlan, updatePlan } from '../../../api/inspections.js'
import Modal from '../../../components/common/Modal.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { INSPECTION_CYCLE_LABELS } from '../../../constants/index.js'

const CYCLE_OPTIONS = Object.entries(INSPECTION_CYCLE_LABELS).map(([value, label]) => ({ value, label }))

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function PlanFormModal({ open, plan, catalog = [], stations = [], onClose, onSaved }) {
  const toast = useToast()
  const [form, setForm] = useState(() =>
    plan
      ? {
          name: plan.name || '',
          cycle: plan.cycle || 'weekly',
          start_date: plan.start_date || todayStr(),
          end_date: plan.end_date || '',
          inspector: plan.inspector || '',
          remark: plan.remark || '',
          enabled: plan.enabled,
          station_ids: plan.station_ids || [],
          item_codes: plan.items || []
        }
      : {
          name: '',
          cycle: 'weekly',
          start_date: todayStr(),
          end_date: '',
          inspector: '',
          remark: '',
          enabled: true,
          station_ids: [],
          item_codes: []
        }
  )
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm({ ...form, [key]: value })
  }

  const toggleId = (id) => {
    const value = Number(id)
    setForm((prev) => ({
      ...prev,
      station_ids: prev.station_ids.includes(value)
        ? prev.station_ids.filter((item) => item !== value)
        : [...prev.station_ids, value]
    }))
  }

  const toggleItem = (code) => {
    setForm((prev) => ({
      ...prev,
      item_codes: prev.item_codes.includes(code)
        ? prev.item_codes.filter((item) => item !== code)
        : [...prev.item_codes, code]
    }))
  }

  const grouped = catalog.reduce((acc, item) => {
    ;(acc[item.category] ||= []).push(item)
    return acc
  }, {})

  const submit = async () => {
    setBusy(true)
    setMessage(null)
    const payload = {
      ...form,
      end_date: form.end_date || null,
      station_ids: form.station_ids,
      items: form.item_codes
    }
    try {
      if (plan) {
        await updatePlan(plan.id, payload)
        toast.success('巡检计划已更新')
      } else {
        await createPlan(payload)
        toast.success('巡检计划已创建, 将在到达开始日期后自动派发')
      }
      onSaved?.()
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
      wide
      title={plan ? '编辑巡检计划' : '新建巡检计划'}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={busy}>
            {busy ? '保存中...' : '保存计划'}
          </button>
        </>
      }
    >
      <div className="stack">
        {message ? <Alert tone="error">{message}</Alert> : null}
        <Field label="计划名称" required error={errors.name}>
          <Input value={form.name} onChange={update('name')} placeholder="如: 运行点位每周设备巡检" maxLength={120}
            invalid={Boolean(errors.name)} />
        </Field>
        <div className="form-grid">
          <Field label="巡检周期" required error={errors.cycle} hint="每日 / 每周 / 每月自动派单, 单次计划派发后停用">
            <Select value={form.cycle} onChange={update('cycle')} options={CYCLE_OPTIONS} />
          </Field>
          <Field label="开始日期" required error={errors.start_date}>
            <Input type="date" value={form.start_date} onChange={update('start_date')} min={todayStr()}
              invalid={Boolean(errors.start_date)} />
          </Field>
          <Field label="结束日期" error={errors.end_date} hint="为空表示长期执行">
            <Input type="date" value={form.end_date} onChange={update('end_date')} min={form.start_date} />
          </Field>
          <Field label="默认巡检人" error={errors.inspector}>
            <Input value={form.inspector} onChange={update('inspector')} placeholder="可在任务执行时修改" />
          </Field>
        </div>

        <Field label="覆盖监测点" required error={errors.station_ids}
          hint={`已选 ${form.station_ids.length} 个点位 (停用点位派单时自动跳过)`}>
          <div className="check-grid">
            {stations.map((station) => (
              <label key={station.id} className={`check-card ${form.station_ids.includes(station.id) ? 'selected' : ''}`}>
                <input
                  type="checkbox"
                  checked={form.station_ids.includes(station.id)}
                  onChange={() => toggleId(station.id)}
                />
                <span>
                  <span className="strong">{station.name}</span>
                  <span className="small muted" style={{ display: 'block' }}>
                    {station.code} · {station.area}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </Field>

        <Field label="巡检项" required error={errors.items} hint={`已选 ${form.item_codes.length} 项, 派发时会固化到任务明细`}>
          <div className="stack" style={{ gap: 8 }}>
            {Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <div className="field-label" style={{ marginBottom: 6 }}>{category}</div>
                <div className="check-grid">
                  {items.map((item) => (
                    <label key={item.code}
                      className={`check-card ${form.item_codes.includes(item.code) ? 'selected' : ''}`}
                      title={item.description}>
                      <input
                        type="checkbox"
                        checked={form.item_codes.includes(item.code)}
                        onChange={() => toggleItem(item.code)}
                      />
                      <span>
                        <span className="strong">{item.name}</span>
                        <span className="small muted" style={{ display: 'block' }}>{item.description}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Field>

        <Field label="备注">
          <Textarea value={form.remark} onChange={update('remark')} />
        </Field>
        {plan ? (
          <label className="checkbox">
            <input type="checkbox" checked={form.enabled} onChange={update('enabled')} />
            <span>计划启用中 (停用后不再参与自动派发)</span>
          </label>
        ) : null}
      </div>
    </Modal>
  )
}
