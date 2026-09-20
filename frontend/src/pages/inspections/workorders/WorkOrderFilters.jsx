import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import {
  WORK_ORDER_PRIORITY_LABELS,
  WORK_ORDER_STATUS_LABELS
} from '../../../constants/index.js'

const STATUS_OPTIONS = Object.entries(WORK_ORDER_STATUS_LABELS).map(([value, label]) => ({ value, label }))
const PRIORITY_OPTIONS = Object.entries(WORK_ORDER_PRIORITY_LABELS).map(([value, label]) => ({ value, label }))

export default function WorkOrderFilters({ value, areas = [], loading, onSubmit, onReset }) {
  const update = (key) => (event) => onSubmit({ ...value, [key]: event.target.value })

  return (
    <FilterPanel loading={loading} onSearch={() => onSubmit(value)} onReset={() => onReset()}>
      <Field label="关键字">
        <Input
          placeholder="工单号 / 标题 / 点位 / 负责人"
          value={value.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={(event) => event.key === 'Enter' && onSubmit(value)}
        />
      </Field>
      <Field label="所属区域">
        <Select value={value.area || ''} onChange={update('area')} placeholder="全部区域"
          options={areas.map((area) => ({ value: area, label: area }))} />
      </Field>
      <Field label="工单状态">
        <Select value={value.status || ''} onChange={update('status')} placeholder="全部状态" options={STATUS_OPTIONS} />
      </Field>
      <Field label="优先级">
        <Select value={value.priority || ''} onChange={update('priority')} placeholder="全部优先级" options={PRIORITY_OPTIONS} />
      </Field>
    </FilterPanel>
  )
}
