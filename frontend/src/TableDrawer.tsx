import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  AlertTriangle, ArrowLeftRight, ChevronLeft, ChevronRight, Columns3, Database,
  Layers3, LoaderCircle, Network, RefreshCw, Rows3, Table2, X,
} from 'lucide-react'
import {
  api, type TableInfo, type TableRelationship, type TableRelationships, type TableRows,
} from './api'
import './table-drawer.css'

export type DrawerTab = 'data' | 'columns' | 'relations' | 'indexes'

const PAGE_SIZE = 25

export function TableDrawer({ table, initialTab = 'data', onClose, onOpenTable }: {
  table: TableInfo
  initialTab?: DrawerTab
  onClose: () => void
  onOpenTable: (name: string, tab?: DrawerTab) => void
}) {
  const [tab, setTab] = useState<DrawerTab>(initialTab)
  const tabs: { id: DrawerTab; label: string; icon: typeof Rows3 }[] = [
    { id: 'data', label: 'Dados', icon: Rows3 },
    { id: 'columns', label: 'Colunas', icon: Columns3 },
    { id: 'relations', label: 'Relacionamentos', icon: Network },
    { id: 'indexes', label: 'Índices', icon: Layers3 },
  ]
  return <div className="drawer-backdrop" onMouseDown={onClose}>
    <aside className="table-drawer detail-drawer" role="dialog" aria-label={`Detalhes de ${table.name}`} onMouseDown={event => event.stopPropagation()}>
      <div className="drawer-header">
        <div>
          <span className="eyebrow"><span className="eyebrow-line" /> DETALHES DA TABELA</span>
          <h2>{table.name}</h2>
          <p>Schema <strong>{table.schema}</strong></p>
        </div>
        <button type="button" className="icon-button bordered" onClick={onClose} aria-label="Fechar detalhes"><X size={17} /></button>
      </div>
      <div className="drawer-stats">
        <div><span>Colunas</span><strong>{table.columns.length}</strong></div>
        <div><span>Chaves</span><strong>{table.primary_key.length + table.foreign_keys.length}</strong></div>
        <div><span>Índices</span><strong>{table.indexes.length}</strong></div>
      </div>
      <div className="drawer-tabs" role="tablist" aria-label="Seções da tabela">
        {tabs.map(item => <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={tab === item.id}
          className={tab === item.id ? 'selected' : ''}
          onClick={() => setTab(item.id)}
        ><item.icon size={14} /> {item.label}</button>)}
      </div>
      {tab === 'data' && <TableDataPanel key={table.name} table={table} />}
      {tab === 'columns' && <ColumnsPanel table={table} />}
      {tab === 'relations' && <RelationshipsPanel key={table.name} table={table} onOpenTable={onOpenTable} />}
      {tab === 'indexes' && <IndexesPanel table={table} />}
    </aside>
  </div>
}

function TableDataPanel({ table }: { table: TableInfo }) {
  const [data, setData] = useState<TableRows | null>(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      setData(await api.rows(table.name, PAGE_SIZE, offset))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível carregar os registros.')
    } finally {
      setLoading(false)
    }
  }, [table.name, offset])

  useEffect(() => { void load() }, [load])

  if (loading && !data) return <PanelLoading label="Carregando registros..." />
  if (error) return <PanelError message={error} onRetry={() => void load()} />
  if (!data) return null

  const start = data.total === 0 ? 0 : Math.min(data.offset + 1, data.total)
  const end = Math.min(data.offset + data.limit, data.total)

  return <>
    <div className="data-table-toolbar">
      <p><Rows3 size={13} /> Registros <span className="data-schema">{data.schema}</span></p>
      <button type="button" className="icon-button bordered" title="Recarregar registros" onClick={() => void load()} disabled={loading}>
        {loading ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}
      </button>
    </div>
    <div className={`data-table-wrap ${loading ? 'is-loading' : ''}`} aria-busy={loading}>
      <table className="data-table">
        <thead>
          <tr>
            <th className="data-index">#</th>
            {data.columns.map(column => <th key={column.name}>
              <span className="data-column-name">{column.name}{column.is_primary_key && <span className="pk-badge">PK</span>}</span>
              <small>{column.type}</small>
            </th>)}
          </tr>
        </thead>
        <tbody>
          {data.rows.length ? data.rows.map((row, index) => <tr key={`${data.offset}-${index}`}>
            <td className="data-index">{data.offset + index + 1}</td>
            {data.columns.map(column => <td key={column.name} title={cellTitle(row[column.name])}>{renderCell(row[column.name])}</td>)}
          </tr>) : <tr>
            <td className="data-empty" colSpan={data.columns.length + 1}>
              <Database size={19} />
              <strong>Tabela sem registros</strong>
              <span>{data.total ? 'Nenhuma linha nesta página.' : 'Nenhuma linha foi retornada por esta tabela.'}</span>
            </td>
          </tr>}
        </tbody>
      </table>
    </div>
    <div className="data-pagination">
      <span>{data.total ? <>Mostrando <strong>{start}–{end}</strong> de <strong>{data.total}</strong> registros</> : 'Nenhum registro'}</span>
      <div>
        <button type="button" title="Página anterior" disabled={loading || offset === 0} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}><ChevronLeft size={15} /></button>
        <span className="page-current">{Math.floor(offset / PAGE_SIZE) + 1}</span>
        <button type="button" title="Próxima página" disabled={loading || end >= data.total} onClick={() => setOffset(value => value + PAGE_SIZE)}><ChevronRight size={15} /></button>
      </div>
    </div>
  </>
}

function ColumnsPanel({ table }: { table: TableInfo }) {
  return <>
    <div className="drawer-section-title"><h3>Colunas</h3><span>{table.columns.length} campos</span></div>
    <div className="column-list">{table.columns.map(column => <div className="column-row" key={column.name}>
      <div className="column-name">
        <span className="column-marker">{column.is_primary_key ? '⌑' : '·'}</span>
        <strong>{column.name}</strong>
        {column.is_primary_key && <span className="pk-badge">PK</span>}
      </div>
      <span className="column-type" title={column.type}>{column.type}</span>
      <span className={`nullable ${column.nullable ? '' : 'required'}`}>{column.nullable ? 'Opcional' : 'Obrigatório'}</span>
    </div>)}</div>
    {table.primary_key.length > 0 && <p className="drawer-hint">Chave primária: <code>{table.primary_key.join(', ')}</code></p>}
  </>
}

function RelationshipsPanel({ table, onOpenTable }: {
  table: TableInfo
  onOpenTable: (name: string, tab?: DrawerTab) => void
}) {
  const [data, setData] = useState<TableRelationships | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      setData(await api.relationships(table.name))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível carregar os relacionamentos.')
    } finally {
      setLoading(false)
    }
  }, [table.name])

  useEffect(() => { void load() }, [load])

  if (loading && !data) return <PanelLoading label="Carregando relacionamentos..." />
  if (error) return <PanelError message={error} onRetry={() => void load()} />
  if (!data) return null

  const total = data.outbound.length + data.inbound.length
  if (!total) return <div className="drawer-empty-state">
    <Network size={21} />
    <strong>Nenhum relacionamento identificado</strong>
    <p>Esta tabela não participa de chaves estrangeiras no schema <b>{data.schema}</b>.</p>
  </div>

  return <>
    {data.outbound.length > 0 && <RelationshipGroup
      title="Esta tabela aponta para"
      description="Chaves estrangeiras definidas nas colunas desta tabela."
      items={data.outbound}
      direction="outbound"
      onOpenTable={onOpenTable}
    />}
    {data.inbound.length > 0 && <RelationshipGroup
      title="Tabelas que apontam para esta"
      description="Chaves estrangeiras de outras tabelas que referenciam esta tabela."
      items={data.inbound}
      direction="inbound"
      onOpenTable={onOpenTable}
    />}
  </>
}

function RelationshipGroup({ title, description, items, direction, onOpenTable }: {
  title: string
  description: string
  items: TableRelationship[]
  direction: 'outbound' | 'inbound'
  onOpenTable: (name: string, tab?: DrawerTab) => void
}) {
  return <section className="relationship-group">
    <div className="relationship-group-head">
      <div><h3>{title}</h3><p>{description}</p></div>
      <span className="relationship-total">{items.length}</span>
    </div>
    <div className="relationship-list">{items.map((item, index) => {
      const otherTable = direction === 'outbound' ? item.target_table : item.source_table
      const otherSchema = direction === 'outbound' ? item.target_schema : item.source_schema
      return <article className="relationship-card" key={`${item.constraint_name}-${item.source_table}-${index}`}>
        <div className={`relationship-icon ${direction}`}><Network size={15} /></div>
        <div className="relationship-copy">
          <div className="relationship-meta">
            <span className={`relationship-direction ${direction}`}>{direction === 'outbound' ? 'Saída' : 'Entrada'}</span>
            {item.constraint_name && <span className="relationship-constraint" title={item.constraint_name}>{item.constraint_name}</span>}
          </div>
          <p className="relationship-line">
            {direction === 'outbound'
              ? <><span className="relationship-columns">{item.source_columns.join(', ') || '—'}</span>
                <ArrowLeftRight size={11} />
                <button type="button" className="relationship-table" onClick={() => onOpenTable(otherTable, 'relations')}><Table2 size={11} /> {otherSchema}.{otherTable}</button>
                <span className="relationship-columns">{item.target_columns.join(', ') || '—'}</span></>
              : <><button type="button" className="relationship-table" onClick={() => onOpenTable(otherTable, 'relations')}><Table2 size={11} /> {otherSchema}.{otherTable}</button>
                <span className="relationship-columns">{item.source_columns.join(', ') || '—'}</span>
                <ArrowLeftRight size={11} />
                <span className="relationship-columns">{item.target_columns.join(', ') || '—'}</span></>}
          </p>
          <p className="relationship-caption">{direction === 'outbound' ? 'Abrir tabela referenciada' : 'Abrir tabela que referencia esta'}</p>
        </div>
      </article>
    })}</div>
  </section>
}

function IndexesPanel({ table }: { table: TableInfo }) {
  return <>
    <div className="drawer-section-title"><h3>Índices</h3><span>{table.indexes.length}</span></div>
    {table.indexes.length ? table.indexes.map(index => <div className="index-row" key={index.name}>
      <Layers3 size={14} />
      <span><strong>{index.name}</strong><small>{index.column_names.join(', ')}{index.unique ? ' · Único' : ''}</small></span>
    </div>) : <p className="drawer-empty">Nenhum índice adicional identificado.</p>}
  </>
}

function PanelLoading({ label }: { label: string }) {
  return <div className="drawer-loading"><LoaderCircle className="spin" size={18} /><span>{label}</span></div>
}

function PanelError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="drawer-error"><AlertTriangle size={16} /><div><strong>Não foi possível carregar</strong><p>{message}</p></div><button type="button" onClick={onRetry}><RefreshCw size={13} /> Tentar novamente</button></div>
}

function renderCell(value: unknown): ReactNode {
  if (value === null || value === undefined) return <span className="cell-null">NULL</span>
  if (typeof value === 'boolean') return <span className={`cell-bool ${value ? 'true' : 'false'}`}>{value ? 'true' : 'false'}</span>
  if (typeof value === 'object') return <span className="cell-json">{JSON.stringify(value)}</span>
  const text = String(value)
  return text === '' ? <span className="cell-null">—</span> : text
}

function cellTitle(value: unknown): string {
  if (value === null || value === undefined) return 'NULL'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
