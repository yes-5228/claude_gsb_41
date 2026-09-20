import { useCallback, useEffect, useState } from 'react'
import { getRepair, resolveRepair } from '../../../api/repairs.js'
import Modal from '../../../components/common/Modal.jsx'
import { Alert } from '../../../components/common/Feedback.jsx'
import { Field, Input, Select, Textarea } from '../../../components/common/FormField.jsx'
import { ErrorState, Loading } from '../../../components/common/Feedback.jsx'
import Tag from '../../../components/common/Tag.jsx'
import { useToast } from '../../../components/common/ToastProvider.jsx'
import { REPAIR_PRIORITY_TONE, STATION_STATUS_TONE } from '../../../constants/index.js'
import { useAsyncData } from '../../../hooks/useAsyncData.js'
import { formatDateTime } from '../../../utils/format.js'

export default function ResolveRepairModal({ repairId, options, onClose, onResolved, onError }) {
  const toast = useToast()
  const loader = useCallback(() => getRepair(repairId), [repairId])
  const { data: repair, loading, error } = useAsyncData(loader, { immediate: Boolean(repairId) })

  const [form, setForm] = useState({ resolution: '', handler: '', station_status_after: 'active' })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!repair) return
    setForm({
      resolution: '',
      handler: repair.handler || '',
      station_status_after: 'active'
    })
    setErrors({})
  }, [repair])

  const open = Boolean(repairId)
  const stationStatuses = options?.station_statuses ?? []

  const submit = async (event) => {
    event.preventDefault()
    const next = {}
    if (!form.resolution.trim()) next.resolution = '请填写处理结果'
    if (!form.handler.trim()) next.handler = '请填写处理人'
    setErrors(next)
    if (Object.keys(next).length) return

    setBusy(true)
    try {
      const result = await resolveRepair(repair.id, {
        resolution: form.resolution.trim(),
        handler: form.handler.trim(),
        station_status_after: form.station_status_after
      })
      const statusLabel = stationStatuses.find(
        (item) => item.value === result.station_status_after
      )?.label
      toast.success(`工单 ${result.code} 已办结, 台账运行状态已回写为「${statusLabel || '运行中'}」`)
      onResolved()
    } catch (err) {
      setErrors(err.fields || {})
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      title="处理维修工单"
      onClose={onClose}
      footer={
        repair ? (
          <>
            <button type="button" className="btn" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button
              type="submit"
              form="resolve-repair-form"
              className="btn btn-primary"
              disabled={busy}
            >
              {busy ? '提交中...' : '确认办结并回写台账'}
            </button>
          </>
        ) : null
      }
    >
      {loading && !repair ? <Loading text="正在加载工单..." /> : null}
      {error && !repair ? <ErrorState error={error} /> : null}
      {repair ? (
        <form id="resolve-repair-form" className="stack" onSubmit={submit}>
          <div className="inline">
            <strong>{repair.title}</strong>
            <Tag tone={REPAIR_PRIORITY_TONE[repair.priority]}>{repair.priority_label}</Tag>
            <Tag tone={STATION_STATUS_TONE[repair.station_status]}>
              台账: {repair.station_status_label}
            </Tag>
          </div>
          <dl className="kv">
            <dt>工单号</dt>
            <dd className="mono">{repair.code}</dd>
            <dt>监测点</dt>
            <dd>
              {repair.station_code} {repair.station_name}
            </dd>
            <dt>报修时间</dt>
            <dd>{formatDateTime(repair.created_at)}</dd>
            <dt>问题描述</dt>
            <dd>{repair.description || '-'}</dd>
          </dl>
          <Alert tone="info">
            办结后系统将按所选状态回写监测点台账, 待办列表同步移除该工单。
          </Alert>
          <Field label="处理结果" required error={errors.resolution}>
            <Textarea
              value={form.resolution}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, resolution: event.target.value }))
                setErrors((prev) => ({ ...prev, resolution: undefined }))
              }}
              invalid={Boolean(errors.resolution)}
              placeholder="维修内容、更换部件、复核结论"
            />
          </Field>
          <div className="form-grid">
            <Field label="处理人" required error={errors.handler}>
              <Input
                value={form.handler}
                onChange={(event) => {
                  setForm((prev) => ({ ...prev, handler: event.target.value }))
                  setErrors((prev) => ({ ...prev, handler: undefined }))
                }}
                invalid={Boolean(errors.handler)}
              />
            </Field>
            <Field
              label="台账运行状态回写"
              required
              error={errors.station_status_after}
              hint="通常恢复为“运行中”; 备件待检可保持“维护中”"
            >
              <Select
                value={form.station_status_after}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, station_status_after: event.target.value }))
                }
                options={stationStatuses}
              />
            </Field>
          </div>
        </form>
      ) : null}
    </Modal>
  )
}
