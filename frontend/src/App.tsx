import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, ArrowDown, ArrowUpRight, Check, ChevronDown, ChevronLeft, ChevronRight,
  CircleHelp, Database, FileSearch, Gauge, Layers3, LoaderCircle, Network, RefreshCw,
  Search, ShieldCheck, Sparkles, Table2, X, XCircle,
} from 'lucide-react'
import { api, type Metrics, type Recommendation, type Suggestion, type TableInfo, type TableSummary } from './api'

type Section = 'overview' | 'catalog' | 'analysis' | 'suggestions'
const navItems: { id: Section; label: string; icon: typeof Gauge }[] = [
  { id: 'overview', label: 'Visão geral', icon: Gauge },
  { id: 'catalog', label: 'Explorador de tabelas', icon: Table2 },
  { id: 'analysis', label: 'Análise estrutural', icon: FileSearch },
  { id: 'suggestions', label: 'Revisão de sugestões', icon: ShieldCheck },
]

function App() {
  const [section, setSection] = useState<Section>('overview')
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [tables, setTables] = useState<TableSummary[]>([])
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('pending')
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null)
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [aiBusy, setAiBusy] = useState(false)
  const [aiNotice, setAiNotice] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const loadCore = useCallback(async () => {
    setLoading(true); setError('')
    const results = await Promise.allSettled([api.health(), api.metrics(), api.tables()])
    const health = results[0], metricsResult = results[1], tablesResult = results[2]
    if (health.status === 'fulfilled') setConnected(true)
    else { setConnected(false); setError(health.reason instanceof Error ? health.reason.message : 'Não foi possível conectar à API.') }
    if (metricsResult.status === 'fulfilled') setMetrics(metricsResult.value)
    if (tablesResult.status === 'fulfilled') setTables(tablesResult.value.items)
    setLoading(false)
  }, [])

  useEffect(() => { void loadCore() }, [loadCore])
  useEffect(() => {
    if (section === 'analysis' && connected) void api.analyze().then(result => setRecommendations(result.recommendations)).catch(e => setError(e.message))
    if (section === 'suggestions' && connected) void api.suggestions(status).then(setSuggestions).catch(e => setError(e.message))
  }, [section, status, connected])
  useEffect(() => {
    if (!query.trim() || section !== 'catalog' || !connected) {
      if (section === 'catalog' && connected && !query.trim()) void api.tables().then(r => setTables(r.items)).catch(e => setError(e.message))
      return
    }
    const timer = window.setTimeout(() => void api.tables(query).then(r => setTables(r.items)).catch(e => setError(e.message)), 250)
    return () => window.clearTimeout(timer)
  }, [query, section, connected])

  const openTable = async (name: string) => {
    try { setBusy(true); setSelectedTable(await api.table(name)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível abrir a tabela.') }
    finally { setBusy(false) }
  }
  const reviewSuggestion = async (id: number, decision: 'approved' | 'rejected') => {
    try {
      setBusy(true); await api.review(id, decision)
      setSuggestions(items => items.filter(item => item.id !== id))
      setNotice(decision === 'approved' ? 'Sugestão aprovada.' : 'Sugestão rejeitada.')
      const updated = await api.metrics(); setMetrics(updated)
      window.setTimeout(() => setNotice(''), 2600)
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível revisar a sugestão.') }
    finally { setBusy(false) }
  }

  const runAiAnalysis = async () => {
    try {
      setAiBusy(true); setError(''); setAiNotice('')
      const result = await api.aiAnalyze()
      setAiNotice(`${result.suggestions_created} proposta(s) criada(s) para revisão. ${result.summary}`)
      const updated = await api.metrics(); setMetrics(updated)
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível concluir a análise com IA.') }
    finally { setAiBusy(false) }
  }

  const pageTitle = navItems.find(item => item.id === section)?.label ?? 'Visão geral'
  const pendingLabel = metrics?.pending_suggestions ?? 0

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Layers3 size={19} strokeWidth={2.3} /></div><span>genom<span className="brand-ai">AI</span></span><span className="brand-beta">BETA</span></div>
      <div className="workspace-label">WORKSPACE</div>
      <button className="workspace-select"><span className="workspace-dot" /><span className="workspace-copy"><strong>Banco de dados</strong><small>PostgreSQL · {metrics ? `${metrics.tables_total} tabelas` : 'conectando...'}</small></span><ChevronDown size={15} /></button>
      <div className="nav-label">PLATAFORMA</div>
      <nav className="main-nav">{navItems.map(item => <button key={item.id} className={`nav-item ${section === item.id ? 'active' : ''}`} onClick={() => setSection(item.id)}><item.icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.id === 'suggestions' && pendingLabel > 0 && <b className="nav-count">{pendingLabel}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={17} /></div><div><strong>Precisa de ajuda?</strong><p>Consulte o guia do GenomAI.</p><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">Abrir documentação <ArrowUpRight size={12} /></a></div></div><div className="profile"><div className="avatar">G</div><div><strong>Equipe GenomAI</strong><small>Workspace de demonstração</small></div><ChevronDown size={15} /></div></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>GenomAI</span><ChevronRight size={14} /><strong>{pageTitle}</strong></div><div className="top-actions"><span className={`connection-pill ${connected ? 'online' : 'offline'}`}><i />{connected ? 'API conectada' : 'API desconectada'}</span><button className="icon-button" title="Atualizar dados" onClick={() => void loadCore()}><RefreshCw size={16} /></button><div className="top-avatar">G</div></div></header>
      <div className="page-content">
        {error && <div className="alert error"><AlertTriangle size={16} /><span>{error}</span><button onClick={() => setError('')}><X size={15} /></button></div>}
        {notice && <div className="alert success"><Check size={16} /><span>{notice}</span></div>}
        {section === 'overview' && <Overview metrics={metrics} tables={tables} loading={loading} onNavigate={setSection} onOpenTable={openTable} onAnalyze={() => setSection('analysis')} />}
        {section === 'catalog' && <Catalog tables={tables} query={query} setQuery={setQuery} loading={loading} onOpenTable={openTable} />}
        {section === 'analysis' && <Analysis recommendations={recommendations} loading={loading} connected={connected} onReload={() => { setBusy(true); void api.analyze().then(r => setRecommendations(r.recommendations)).catch(e => setError(e.message)).finally(() => setBusy(false)) }} busy={busy} onAiAnalyze={runAiAnalysis} aiBusy={aiBusy} aiNotice={aiNotice} />}
        {section === 'suggestions' && <Suggestions items={suggestions} status={status} setStatus={setStatus} loading={loading} busy={busy} onReview={reviewSuggestion} />}
        <footer className="page-footer"><span>GenomAI <b>·</b> Catálogo e governança de dados</span><span>Conectado ao PostgreSQL em modo somente leitura <span className="footer-lock">◆</span></span></footer>
      </div>
    </main>
    {selectedTable && <TableDrawer table={selectedTable} onClose={() => setSelectedTable(null)} />}
  </div>
}

function Overview({ metrics, tables, loading, onNavigate, onOpenTable, onAnalyze }: { metrics: Metrics | null; tables: TableSummary[]; loading: boolean; onNavigate: (s: Section) => void; onOpenTable: (name: string) => void; onAnalyze: () => void }) {
  const recent = tables.slice(0, 5)
  const risks = metrics?.tables_without_primary_key ?? 0
  return <>
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> VISÃO DO AMBIENTE</div><h1>Bom dia, equipe <span>👋</span></h1><p>Acompanhe a estrutura e a governança do seu banco de dados.</p></div><button className="button-primary" onClick={onAnalyze}><Sparkles size={16} /> Executar análise <ArrowUpRight size={15} /></button></div>
    <div className="hero-banner"><div className="hero-copy"><div className="hero-label"><span className="hero-orb"><Sparkles size={13} /></span> SEU BANCO, DECODIFICADO</div><h2>Entenda o que existe<br />por trás dos seus dados.</h2><p>Explore tabelas, descubra relações e encontre pontos de atenção na estrutura do seu banco.</p><button className="button-light" onClick={() => onNavigate('catalog')}>Explorar catálogo <ChevronRight size={15} /></button></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><div className="art-core"><Database size={25} /></div><div className="art-node node-a"><Table2 size={15} /></div><div className="art-node node-b"><Network size={15} /></div><div className="art-node node-c"><Layers3 size={15} /></div><div className="art-connector c1"/><div className="art-connector c2"/><div className="art-connector c3"/></div><div className="hero-side-note"><span className="live-dot"/> ESTRUTURA EM TEMPO REAL</div></div>
    <div className="section-head"><div><h2>Saúde do ambiente</h2><p>Indicadores atualizados a partir dos metadados do banco.</p></div><span className="updated-label"><Activity size={13} /> {loading ? 'Atualizando...' : 'Atualizado agora'}</span></div>
    <div className="metrics-grid">
      <MetricCard icon={Database} label="Tabelas catalogadas" value={metrics?.tables_total ?? '—'} detail={`${metrics?.tables_with_basic_metadata ?? '—'} com metadados básicos`} tone="blue" trend="Estrutura" />
      <MetricCard icon={Gauge} label="Cobertura de metadados" value={metrics ? `${metrics.metadata_coverage_percent}%` : '—'} detail="Tabelas com colunas identificadas" tone="green" progress={metrics?.metadata_coverage_percent ?? 0} />
      <MetricCard icon={AlertTriangle} label="Sem chave primária" value={metrics?.tables_without_primary_key ?? '—'} detail={risks ? 'Requer atenção na estrutura' : 'Nenhum ponto identificado'} tone={risks ? 'amber' : 'green'} trend={risks ? 'Atenção' : 'Saudável'} />
      <MetricCard icon={ShieldCheck} label="Sugestões revisadas" value={metrics ? `${metrics.review_rate_percent}%` : '—'} detail={`${metrics?.reviewed_suggestions ?? '—'} de ${metrics?.total_suggestions ?? '—'} sugestões`} tone="purple" progress={metrics?.review_rate_percent ?? 0} />
    </div>
    <div className="content-grid"><section className="panel table-panel"><div className="panel-heading"><div><h3>Tabelas do catálogo</h3><p>Uma visão rápida das tabelas do seu banco.</p></div><button className="text-link" onClick={() => onNavigate('catalog')}>Ver catálogo <ChevronRight size={14} /></button></div>{recent.length ? <div className="table-wrap"><table><thead><tr><th>NOME DA TABELA</th><th>COLUNAS</th><th>CHAVE PRIMÁRIA</th><th>RELAÇÕES</th><th></th></tr></thead><tbody>{recent.map(table => <tr key={table.name} onClick={() => onOpenTable(table.name)}><td><span className="table-name-icon"><Table2 size={15} /></span><strong>{table.name}</strong></td><td>{table.columns_count}</td><td>{table.primary_key.length ? <span className="tag tag-green">Configurada</span> : <span className="tag tag-amber">Ausente</span>}</td><td><span className="relation-count"><Network size={13} /> {table.foreign_keys_count}</span></td><td><ChevronRight size={15} className="row-arrow" /></td></tr>)}</tbody></table></div> : <EmptyState loading={loading} title="Nenhuma tabela encontrada" detail="Conecte a API para carregar o catálogo do banco." />}</section>
      <section className="panel activity-panel"><div className="panel-heading"><div><h3>Visão de governança</h3><p>Status da revisão de sugestões.</p></div><button className="more-button" onClick={() => onNavigate('suggestions')}>•••</button></div><div className="governance-ring-wrap"><div className="governance-ring" style={{ '--progress': `${metrics?.review_rate_percent ?? 0}%` } as React.CSSProperties}><div><strong>{metrics?.review_rate_percent ?? 0}%</strong><span>revisadas</span></div></div><div className="ring-legend"><span><i className="legend-dot dot-reviewed"/> Revisadas <b>{metrics?.reviewed_suggestions ?? 0}</b></span><span><i className="legend-dot dot-pending"/> Pendentes <b>{metrics?.pending_suggestions ?? 0}</b></span></div></div><div className="activity-note"><div className="note-icon"><ShieldCheck size={15} /></div><p>{metrics?.note || 'As sugestões passam por revisão humana antes de qualquer decisão.'}</p></div><button className="button-outline full-button" onClick={() => onNavigate('suggestions')}>Acessar revisão <ArrowUpRight size={14} /></button></section></div>
    <div className="bottom-insight"><div className="insight-icon"><Sparkles size={18} /></div><div><strong>Pronto para conhecer melhor seu banco?</strong><p>Execute uma análise estrutural para encontrar recomendações de melhoria.</p></div><button onClick={() => onNavigate('analysis')}>Ver análise <ChevronRight size={15} /></button></div>
  </>
}

function MetricCard({ icon: Icon, label, value, detail, tone, progress, trend }: { icon: typeof Gauge; label: string; value: string | number; detail: string; tone: string; progress?: number; trend?: string }) {
  return <div className="metric-card"><div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={17} /></span>{trend && <span className={`metric-trend ${tone}`}>{trend}</span>}{progress !== undefined && <span className="metric-mini">{progress >= 80 ? <ArrowUpRight size={14} /> : <ArrowDown size={13} />}</span>}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-detail">{detail}</div>{progress !== undefined && <div className="progress-track"><i className={tone} style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} /></div>}</div>
}

function Catalog({ tables, query, setQuery, loading, onOpenTable }: { tables: TableSummary[]; query: string; setQuery: (q: string) => void; loading: boolean; onOpenTable: (name: string) => void }) {
  const [sort, setSort] = useState<'name' | 'columns'>('name')
  const sorted = useMemo(() => [...tables].sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : b.columns_count - a.columns_count), [tables, sort])
  return <><div className="page-heading compact-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> EXPLORADOR</div><h1>Catálogo de tabelas</h1><p>Navegue pela estrutura do banco e consulte colunas, chaves e relacionamentos.</p></div><div className="catalog-total"><Database size={17} /><strong>{tables.length}</strong><span>tabelas</span></div></div><section className="panel catalog-panel"><div className="catalog-toolbar"><div className="search-box"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar por tabela ou coluna..." /><kbd>⌘ K</kbd></div><div className="toolbar-right"><span className="filter-label">Ordenar por</span><button className="select-button" onClick={() => setSort(sort === 'name' ? 'columns' : 'name')}>{sort === 'name' ? 'Nome da tabela' : 'Quantidade de colunas'} <ChevronDown size={14} /></button><button className="icon-button bordered" title="Atualizar catálogo"><RefreshCw size={15} /></button></div></div>{sorted.length ? <div className="table-wrap catalog-table"><table><thead><tr><th>TABELA <span className="sort-mark">↕</span></th><th>SCHEMA</th><th>COLUNAS</th><th>CHAVE PRIMÁRIA</th><th>RELACIONAMENTOS</th><th></th></tr></thead><tbody>{sorted.map(t => <tr key={t.name} onClick={() => onOpenTable(t.name)}><td><span className="table-name-icon"><Table2 size={15} /></span><strong>{t.name}</strong></td><td><span className="schema-tag">{t.schema}</span></td><td>{t.columns_count} <span className="muted">colunas</span></td><td>{t.primary_key.length ? <span className="tag tag-green"><Check size={11} /> Sim</span> : <span className="tag tag-amber"><AlertTriangle size={11} /> Não</span>}</td><td><span className="relation-count"><Network size={13} /> {t.foreign_keys_count}</span></td><td><button className="open-row" aria-label={`Abrir ${t.name}`}><ArrowUpRight size={15} /></button></td></tr>)}</tbody></table></div> : <EmptyState loading={loading} title="Nenhuma tabela encontrada" detail={query ? 'Tente buscar por outro nome.' : 'O catálogo aparecerá aqui quando a API estiver conectada.'} />}<div className="table-pagination"><span>Exibindo <strong>{sorted.length}</strong> de <strong>{tables.length}</strong> tabelas</span><div><button disabled><ChevronLeft size={15} /></button><button className="page-current">1</button><button disabled><ChevronRight size={15} /></button></div></div></section></>
}

function Analysis({ recommendations, loading, connected, onReload, busy, onAiAnalyze, aiBusy, aiNotice }: { recommendations: Recommendation[]; loading: boolean; connected: boolean; onReload: () => void; busy: boolean; onAiAnalyze: () => void; aiBusy: boolean; aiNotice: string }) {
  const countHigh = recommendations.filter(r => r.severity === 'high').length
  const countMedium = recommendations.filter(r => r.severity === 'medium').length
  const countLow = recommendations.filter(r => r.severity === 'low').length
  return <><div className="page-heading compact-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> DIAGNÓSTICO</div><h1>Análise estrutural</h1><p>Recomendações geradas a partir dos metadados do banco de dados.</p></div><div className="toolbar-right"><button className="button-primary" onClick={onReload} disabled={busy || !connected}>{busy ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={15} />} Regras</button><button className="button-primary" onClick={onAiAnalyze} disabled={aiBusy || !connected}>{aiBusy ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={15} />} Analisar com Gemini</button></div></div>{aiNotice && <div className="alert success"><Sparkles size={16} /><span>{aiNotice} As propostas estão na Revisão de sugestões; nenhuma alteração foi executada.</span></div>}<div className="analysis-summary"><div className="summary-main"><div className="summary-icon"><FileSearch size={19} /></div><div><strong>{recommendations.length ? `${recommendations.length} ponto${recommendations.length === 1 ? '' : 's'} para revisar` : 'Estrutura analisada'}</strong><p>{loading ? 'Carregando análise...' : connected ? 'A análise usa regras determinísticas e não altera o banco.' : 'Conecte a API para executar a análise.'}</p></div></div><div className="severity-counts"><span><i className="sev-dot high" /> Alta <b>{countHigh}</b></span><span><i className="sev-dot medium" /> Média <b>{countMedium}</b></span><span><i className="sev-dot low" /> Baixa <b>{countLow}</b></span></div></div>{recommendations.length ? <div className="recommendation-list">{recommendations.map((item, index) => <RecommendationCard key={`${item.table}-${item.category}-${index}`} item={item} />)}</div> : <div className="panel empty-analysis"><div className="empty-symbol"><Check size={22} /></div><h3>{connected ? 'Nenhuma recomendação encontrada' : 'API não conectada'}</h3><p>{connected ? 'A estrutura analisada não apresentou pontos de atenção nas regras atuais.' : 'Inicie o backend e atualize a página para consultar o banco.'}</p></div>}<div className="analysis-footnote"><ShieldCheck size={15} /><span>As recomendações são informativas. O GenomAI nunca executa alterações automaticamente no banco.</span></div></>
}

function RecommendationCard({ item }: { item: Recommendation }) {
  const [expanded, setExpanded] = useState(false)
  return <article className="recommendation-card"><div className={`severity-bar ${item.severity}`} /><div className="recommendation-body"><div className="recommendation-top"><span className={`severity-tag ${item.severity}`}>{item.severity === 'high' ? 'Alta prioridade' : item.severity === 'medium' ? 'Média prioridade' : 'Baixa prioridade'}</span><span className="category-tag">{item.category.replace('_', ' ')}</span><span className="table-reference"><Table2 size={13} /> {item.table}</span><button className="expand-button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Menos detalhes' : 'Ver detalhes'} <ChevronDown size={14} className={expanded ? 'rotate' : ''} /></button></div><h3>{item.message}</h3>{expanded && <div className="recommendation-details"><p>{item.evidence || 'A recomendação foi identificada durante a inspeção da estrutura.'}</p>{item.suggested_sql && <div className="sql-box"><div><span>SQL SUGERIDO</span><button onClick={() => void navigator.clipboard?.writeText(item.suggested_sql || '')}>Copiar</button></div><code>{item.suggested_sql}</code></div>}</div>}</div></article>
}

function Suggestions({ items, status, setStatus, loading, busy, onReview }: { items: Suggestion[]; status: string; setStatus: (s: string) => void; loading: boolean; busy: boolean; onReview: (id: number, decision: 'approved' | 'rejected') => void }) {
  const statuses = [['pending', 'Pendentes'], ['approved', 'Aprovadas'], ['rejected', 'Rejeitadas'], ['all', 'Todas']]
  return <><div className="page-heading compact-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> GOVERNANÇA</div><h1>Revisão de sugestões</h1><p>Revise as propostas registradas e mantenha as decisões sob controle humano.</p></div><div className="review-count"><ShieldCheck size={17} /><strong>{items.length}</strong><span>{status === 'pending' ? 'pendentes' : 'itens'}</span></div></div><section className="panel suggestions-panel"><div className="suggestion-tabs">{statuses.map(([key, label]) => <button key={key} className={status === key ? 'selected' : ''} onClick={() => setStatus(key)}>{label}{key === 'pending' && items.length > 0 && status === key && <b>{items.length}</b>}</button>)}</div>{items.length ? <div className="suggestion-list">{items.map(item => <article className="suggestion-card" key={item.id}><div className="suggestion-type-icon"><Sparkles size={16} /></div><div className="suggestion-content"><div className="suggestion-meta"><span className="suggestion-kind">{item.kind}</span><span className="table-reference"><Table2 size={13} /> {item.table}</span><span className={`status-tag ${item.status}`}>{item.status === 'pending' ? 'Pendente' : item.status === 'approved' ? 'Aprovada' : 'Rejeitada'}</span></div><h3>{item.description}</h3><p>{item.rationale}</p><div className="confidence"><span>Confiança</span><div className="confidence-track"><i style={{ width: `${Math.round(item.confidence * 100)}%` }} /></div><strong>{Math.round(item.confidence * 100)}%</strong></div></div>{item.status === 'pending' && <div className="suggestion-actions"><button disabled={busy} className="reject-button" onClick={() => onReview(item.id, 'rejected')}><XCircle size={14} /> Rejeitar</button><button disabled={busy} className="approve-button" onClick={() => onReview(item.id, 'approved')}><Check size={14} /> Aprovar</button></div>}</article>)}</div> : <EmptyState loading={loading} title={status === 'pending' ? 'Tudo em dia por aqui' : 'Nenhuma sugestão encontrada'} detail={status === 'pending' ? 'Não há sugestões aguardando revisão.' : 'As sugestões registradas aparecerão nesta lista.'} icon={<ShieldCheck size={20} />} />}<div className="suggestions-note"><ShieldCheck size={14} /><span>Aprovar uma sugestão registra a decisão. Nenhuma alteração é aplicada ao banco analisado.</span></div></section></>
}

function TableDrawer({ table, onClose }: { table: TableInfo; onClose: () => void }) {
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="table-drawer" onMouseDown={e => e.stopPropagation()}><div className="drawer-header"><div><span className="eyebrow"><span className="eyebrow-line" /> DETALHES DA TABELA</span><h2>{table.name}</h2><p>Schema <strong>{table.schema}</strong></p></div><button className="icon-button bordered" onClick={onClose}><X size={17} /></button></div><div className="drawer-stats"><div><span>Colunas</span><strong>{table.columns.length}</strong></div><div><span>Chaves</span><strong>{table.primary_key.length + table.foreign_keys.length}</strong></div><div><span>Índices</span><strong>{table.indexes.length}</strong></div></div><div className="drawer-section-title"><h3>Colunas</h3><span>{table.columns.length} campos</span></div><div className="column-list">{table.columns.map(column => <div className="column-row" key={column.name}><div className="column-name"><span className="column-marker">{column.is_primary_key ? '⌑' : '·'}</span><strong>{column.name}</strong>{column.is_primary_key && <span className="pk-badge">PK</span>}</div><span className="column-type">{column.type}</span><span className={`nullable ${column.nullable ? '' : 'required'}`}>{column.nullable ? 'Opcional' : 'Obrigatório'}</span></div>)}</div>{table.foreign_keys.length > 0 && <><div className="drawer-section-title"><h3>Relacionamentos</h3><span>{table.foreign_keys.length}</span></div><div className="relation-list">{table.foreign_keys.map((fk, i) => <div className="relation-card" key={`${fk.referred_table}-${i}`}><Network size={15} /><span><strong>{fk.constrained_columns.join(', ')}</strong> → {fk.referred_schema}.{fk.referred_table} ({fk.referred_columns.join(', ')})</span></div>)}</div></>}<div className="drawer-section-title"><h3>Índices</h3><span>{table.indexes.length}</span></div>{table.indexes.length ? table.indexes.map(index => <div className="index-row" key={index.name}><Layers3 size={14} /><span><strong>{index.name}</strong><small>{index.column_names.join(', ')}{index.unique ? ' · Único' : ''}</small></span></div>) : <p className="drawer-empty">Nenhum índice adicional identificado.</p>}</aside></div>
}

function EmptyState({ loading, title, detail, icon }: { loading: boolean; title: string; detail: string; icon?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol">{loading ? <LoaderCircle className="spin" size={20} /> : icon || <Database size={20} />}</div><strong>{loading ? 'Carregando dados...' : title}</strong><p>{loading ? 'Consultando o backend do GenomAI.' : detail}</p></div>
}

export default App
