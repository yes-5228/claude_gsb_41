import { FilterPanel } from '../../../components/common/Card.jsx'
import { Field, Input, Select } from '../../../components/common/FormField.jsx'
import { INSPECTION_TASK_STATUS_LABELS } from '../../../constants/index.js'

const STATUS_OPTIONS = Object.entries(INSPECTION_TASK_STATUS_LABELS).map(([value, label]) => ({ value, label }))

export default function TaskFilters({ value, areas = [], stations = [], loading, onSubmit, onReset }) {
  const update = (key) => (event) => onSubmit({ ...value, [key]: event.target.value })

  return (
    <FilterPanel
      loading={loading}
      onSearch={() => onSubmit(value)}
      onReset={() => onReset()}
    >
      <Field label="关键字">
        <Input
          placeholder="任务单号 / 点位名称 / 编码"
          value={value.keyword || ''}
          onChange={update('keyword')}
          onKeyDown={(event) => event.key === 'Enter' && onSubmit(value)}
        />
      </Field>
      <Field label="监测点">
        <Select value={value.station_id || ''} onChange={update('station_id')} placeholder="全部点位"
          options={stations.map((s) => ({ value: s.id, label: `${s.name} (${s.code})` }))} />
      </Field>
      <Field label="所属区域">
        <Select value={value.area || ''} onChange={update('area')} placeholder="全部区域"
          options={areas.map((area) => ({ value: area, label: area }))} />
      </Field>
      <Field label="任务状态">
        <Select value={value.status || ''} onChange={update('status')} placeholder="全部状态" options={STATUS_OPTIONS} />
      </Field>
      <Field label="应检日期(起)">
        <Input type="date" value={value.date_from || ''} onChange={update('date_from')} />
      </Field>
      <Field label="应检日期(止)">
        <Input type="date" value={value.date_to || ''} onChange={update('date_to')} />
      </Field>
    </FilterPanel>
  )
}
