/**
 * Aplicação React do GenomAI.
 *
 * Componentes principais:
 * - `Overview` / `Catalog` / `Analysis`: leitura do catálogo e da análise.
 * - `Suggestions`: revisão humana, edição versionada e aplicação controlada.
 * - `SuggestionEditModal`, `ApplyPreviewModal`, `PrivacyModal`: fluxos que
 *   exigem confirmação explícita do usuário.
 *
 * A persona é enviada em `api.ts` no cabeçalho `X-GenomAI-Persona`. O backend
 * é a fonte de verdade das permissões; este arquivo apenas ajusta a UX.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Database,
  Eye,
  FileSearch,
  Gauge,
  History,
  Layers3,
  LoaderCircle,
  Lock,
  Network,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Table2,
  UserCog,
  X,
  XCircle,
} from "lucide-react";
import {
  api,
  getStoredPersona,
  setStoredPersona,
  type AiAnalysisResult,
  type AiPayloadPreview,
  type ApplyPreview,
  type Metrics,
  type PersonaId,
  type PersonaInfo,
  type PrivacyPolicy,
  type Recommendation,
  type StorageInfo,
  type Suggestion,
  type SuggestionEdit,
  type SuggestionRevision,
  type SuggestionStatus,
  type TableInfo,
  type TableSummary,
} from "./api";
import { TableDrawer, type DrawerTab } from "./TableDrawer";

type Section = "overview" | "catalog" | "analysis" | "suggestions";
const navItems: { id: Section; label: string; icon: typeof Gauge }[] = [
  { id: "overview", label: "Visão geral", icon: Gauge },
  { id: "catalog", label: "Explorador de tabelas", icon: Table2 },
  { id: "analysis", label: "Análise estrutural", icon: FileSearch },
  { id: "suggestions", label: "Revisão de sugestões", icon: ShieldCheck },
];

/** Fallback exibido antes de a API responder com a matriz de personas. */
const fallbackPersonas: PersonaInfo[] = [
  {
    id: "leitor",
    label: "Leitor",
    description: "Consulta catálogo, análise e sugestões, sem alterar nada.",
    capabilities: ["read"],
  },
  {
    id: "analista",
    label: "Analista de dados",
    description: "Cria, edita e revisa sugestões; não executa mudanças no banco.",
    capabilities: ["read", "suggest", "review"],
  },
  {
    id: "desenvolvedor",
    label: "Desenvolvedor",
    description: "Revisa e aplica mudanças aprovadas, com SQL validado.",
    capabilities: ["read", "suggest", "review", "apply", "audit"],
  },
  {
    id: "administrador",
    label: "Administrador",
    description: "Acesso completo, incluindo auditoria de aplicações.",
    capabilities: ["read", "suggest", "review", "apply", "audit"],
  },
];

function App() {
  const [section, setSection] = useState<Section>("overview");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("pending");
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("data");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiNotice, setAiNotice] = useState("");
  const [aiResult, setAiResult] = useState<AiAnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [persona, setPersona] = useState<PersonaId>(getStoredPersona());
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [storage, setStorage] = useState<StorageInfo | null>(null);
  const [editing, setEditing] = useState<Suggestion | null>(null);
  const [applyTarget, setApplyTarget] = useState<ApplyPreview | null>(null);
  const [privacy, setPrivacy] = useState<{
    preview: AiPayloadPreview;
    policy: PrivacyPolicy;
  } | null>(null);
  const [privacyBusy, setPrivacyBusy] = useState(false);

  const loadCore = useCallback(async () => {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([
      api.health(),
      api.metrics(),
      api.tables(),
      api.personas(),
      api.storage(),
    ]);
    const health = results[0],
      metricsResult = results[1],
      tablesResult = results[2],
      personasResult = results[3],
      storageResult = results[4];
    if (health.status === "fulfilled") setConnected(true);
    else {
      setConnected(false);
      setError(
        health.reason instanceof Error
          ? health.reason.message
          : "Não foi possível conectar à API.",
      );
    }
    if (metricsResult.status === "fulfilled") setMetrics(metricsResult.value);
    if (tablesResult.status === "fulfilled")
      setTables(tablesResult.value.items);
    if (personasResult.status === "fulfilled") setPersonas(personasResult.value);
    if (storageResult.status === "fulfilled") setStorage(storageResult.value);
    setLoading(false);
  }, []);

  const reloadSuggestions = useCallback(async () => {
    if (!connected) return;
    try {
      setSuggestions(await api.suggestions(status));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível carregar as sugestões.");
    }
  }, [connected, status]);

  useEffect(() => {
    void loadCore();
  }, [loadCore]);
  useEffect(() => {
    if (section === "analysis" && connected)
      void api
        .analyze()
        .then((result) => setRecommendations(result.recommendations))
        .catch((e) => setError(e.message));
    if (section === "suggestions" && connected) void reloadSuggestions();
  }, [section, status, connected, reloadSuggestions]);
  useEffect(() => {
    if (!query.trim() || section !== "catalog" || !connected) {
      if (section === "catalog" && connected && !query.trim())
        void api
          .tables()
          .then((r) => setTables(r.items))
          .catch((e) => setError(e.message));
      return;
    }
    const timer = window.setTimeout(
      () =>
        void api
          .tables(query)
          .then((r) => setTables(r.items))
          .catch((e) => setError(e.message)),
      250,
    );
    return () => window.clearTimeout(timer);
  }, [query, section, connected]);

  const currentPersona =
    personas.find((item) => item.id === persona) ??
    fallbackPersonas.find((item) => item.id === persona);
  const can = (capability: string) =>
    currentPersona?.capabilities.includes(capability) ?? false;
  const isDeveloper = can("apply");

  const changePersona = (value: PersonaId) => {
    setPersona(value);
    setStoredPersona(value);
    const label = personas.find((item) => item.id === value)?.label ?? value;
    setNotice(`Persona alterada para ${label}.`);
    window.setTimeout(() => setNotice(""), 2600);
  };

  const openTable = async (name: string, tab: DrawerTab = "data") => {
    try {
      setBusy(true);
      setDrawerTab(tab);
      setSelectedTable(await api.table(name));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível abrir a tabela.",
      );
    } finally {
      setBusy(false);
    }
  };

  const reviewSuggestion = async (
    id: number,
    decision: SuggestionStatus,
  ) => {
    let comment = "";
    if (decision === "partially_approved") {
      comment =
        window.prompt(
          "Descreva o que foi aprovado parcialmente e o que ainda precisa de ajuste:",
          "",
        ) ?? "";
      if (!comment.trim()) return;
    }
    try {
      setBusy(true);
      await api.review(id, decision, comment);
      setNotice(
        decision === "approved"
          ? "Sugestão aprovada. Nenhuma mudança foi aplicada automaticamente."
          : decision === "rejected"
            ? "Sugestão rejeitada."
            : "Sugestão aprovada parcialmente. Edite os pontos pendentes.",
      );
      await reloadSuggestions();
      setMetrics(await api.metrics());
      window.setTimeout(() => setNotice(""), 3200);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível revisar a sugestão.",
      );
    } finally {
      setBusy(false);
    }
  };

  const saveSuggestion = async (id: number, body: SuggestionEdit) => {
    try {
      setBusy(true);
      const updated = await api.editSuggestion(id, body);
      setEditing(null);
      setNotice(
        `Sugestão salva na versão ${updated.version} e reaberta para revisão.`,
      );
      await reloadSuggestions();
      setMetrics(await api.metrics());
      window.setTimeout(() => setNotice(""), 3200);
    } catch (e) {
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const openApplyPreview = async (id: number) => {
    try {
      setBusy(true);
      setApplyTarget(await api.applyPreview(id));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível preparar a aplicação.",
      );
    } finally {
      setBusy(false);
    }
  };

  const confirmApply = async (id: number) => {
    try {
      setBusy(true);
      const result = await api.apply(id);
      setApplyTarget(null);
      if (result.success) {
        setNotice("Mudança aplicada e registrada na auditoria.");
      } else {
        setError(result.error || "A aplicação falhou e foi registrada na auditoria.");
      }
      await reloadSuggestions();
      setMetrics(await api.metrics());
      window.setTimeout(() => setNotice(""), 3200);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Não foi possível aplicar a mudança.",
      );
    } finally {
      setBusy(false);
    }
  };

  const openPrivacy = async () => {
    try {
      setPrivacyBusy(true);
      const [preview, policy] = await Promise.all([
        api.aiPayload(),
        api.privacyPolicy(),
      ]);
      setPrivacy({ preview, policy });
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Não foi possível carregar a política de privacidade.",
      );
    } finally {
      setPrivacyBusy(false);
    }
  };

  const runAiAnalysis = async () => {
    try {
      setAiBusy(true);
      setError("");
      setAiNotice("");
      setAiResult(null);
      const result = await api.aiAnalyze();
      setAiResult(result);
      setAiNotice("complete");
      const updated = await api.metrics();
      setMetrics(updated);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Não foi possível concluir a análise com IA.",
      );
    } finally {
      setAiBusy(false);
    }
  };

  const pageTitle =
    navItems.find((item) => item.id === section)?.label ?? "Visão geral";
  const pendingLabel = metrics?.pending_suggestions ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Layers3 size={19} strokeWidth={2.3} />
          </div>
          <span>
            genom<span className="brand-ai">AI</span>
          </span>
          <span className="brand-beta">BETA</span>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-select">
          <span className="workspace-dot" />
          <span className="workspace-copy">
            <strong>Banco de dados</strong>
            <small>
              PostgreSQL ·{" "}
              {metrics ? `${metrics.tables_total} tabelas` : "conectando..."}
            </small>
          </span>
          <ChevronDown size={15} />
        </button>
        <div className="persona-box">
          <div className="persona-box-label">
            <UserCog size={12} /> PERSONA ATIVA
          </div>
          <select
            className="persona-select"
            value={persona}
            onChange={(event) => changePersona(event.target.value as PersonaId)}
            aria-label="Selecionar persona"
          >
            {(personas.length ? personas : fallbackPersonas).map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <p className="persona-hint">
            {currentPersona?.description ??
              "Carregando permissões da persona..."}
          </p>
        </div>
        <div className="nav-label">PLATAFORMA</div>
        <nav className="main-nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${section === item.id ? "active" : ""}`}
              onClick={() => setSection(item.id)}
            >
              <item.icon size={17} strokeWidth={1.8} />
              <span>{item.label}</span>
              {item.id === "suggestions" && pendingLabel > 0 && (
                <b className="nav-count">{pendingLabel}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon">
              <CircleHelp size={17} />
            </div>
            <div>
              <strong>Precisa de ajuda?</strong>
              <p>Consulte o guia do GenomAI.</p>
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noreferrer"
              >
                Abrir documentação <ArrowUpRight size={12} />
              </a>
            </div>
          </div>
          <div className="profile">
            <div className="avatar">G</div>
            <div>
              <strong>Equipe GenomAI</strong>
              <small>Workspace de demonstração</small>
            </div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>GenomAI</span>
            <ChevronRight size={14} />
            <strong>{pageTitle}</strong>
          </div>
          <div className="top-actions">
            <span
              className={`connection-pill ${connected ? "online" : "offline"}`}
            >
              <i />
              {connected ? "API conectada" : "API desconectada"}
            </span>
            <button
              className="icon-button"
              title="Atualizar dados"
              onClick={() => void loadCore()}
            >
              <RefreshCw size={16} />
            </button>
            <div className="top-avatar">G</div>
          </div>
        </header>
        <div className="page-content">
          {error && (
            <div className="alert error">
              <AlertTriangle size={16} />
              <span>{error}</span>
              <button onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success">
              <Check size={16} />
              <span>{notice}</span>
            </div>
          )}
          {section === "overview" && (
            <Overview
              metrics={metrics}
              tables={tables}
              loading={loading}
              onNavigate={setSection}
              onOpenTable={openTable}
              onAnalyze={() => setSection("analysis")}
            />
          )}
          {section === "catalog" && (
            <Catalog
              tables={tables}
              query={query}
              setQuery={setQuery}
              loading={loading}
              onOpenTable={openTable}
            />
          )}
          {section === "analysis" && (
            <Analysis
              recommendations={recommendations}
              loading={loading}
              connected={connected}
              onReload={() => {
                setBusy(true);
                void api
                  .analyze()
                  .then((r) => setRecommendations(r.recommendations))
                  .catch((e) => setError(e.message))
                  .finally(() => setBusy(false));
              }}
              busy={busy}
              onAiAnalyze={runAiAnalysis}
              aiBusy={aiBusy}
              aiNotice={aiNotice}
              aiResult={aiResult}
              onPrivacy={openPrivacy}
              privacyBusy={privacyBusy}
              canSuggest={can("suggest")}
            />
          )}
          {section === "suggestions" && (
            <Suggestions
              items={suggestions}
              status={status}
              setStatus={setStatus}
              loading={loading}
              busy={busy}
              persona={persona}
              canEdit={can("suggest")}
              canReview={can("review")}
              canApply={isDeveloper}
              onReview={reviewSuggestion}
              onEdit={setEditing}
              onApply={openApplyPreview}
            />
          )}
          <footer className="page-footer">
            <span>
              GenomAI <b>·</b> Catálogo e governança de dados
            </span>
            <span>
              {storage
                ? storage.app_store.remote
                  ? `Sugestões no ${storage.app_store.backend} · schema ${storage.app_store.schema}`
                  : "Sugestões em SQLite local · configure APP_DATABASE_URL para PostgreSQL"
                : "Conectado ao PostgreSQL em modo somente leitura"}{" "}
              <span className="footer-lock">◆</span>
            </span>
          </footer>
        </div>
      </main>
      {selectedTable && (
        <TableDrawer
          table={selectedTable}
          initialTab={drawerTab}
          onClose={() => setSelectedTable(null)}
          onOpenTable={openTable}
        />
      )}
      {editing && (
        <SuggestionEditModal
          item={editing}
          busy={busy}
          onClose={() => setEditing(null)}
          onSave={saveSuggestion}
        />
      )}
      {applyTarget && (
        <ApplyPreviewModal
          preview={applyTarget}
          busy={busy}
          onClose={() => setApplyTarget(null)}
          onConfirm={() => void confirmApply(applyTarget.suggestion_id)}
        />
      )}
      {privacy && (
        <PrivacyModal
          data={privacy}
          storage={storage}
          onClose={() => setPrivacy(null)}
        />
      )}
    </div>
  );
}

function Overview({
  metrics,
  tables,
  loading,
  onNavigate,
  onOpenTable,
  onAnalyze,
}: {
  metrics: Metrics | null;
  tables: TableSummary[];
  loading: boolean;
  onNavigate: (s: Section) => void;
  onOpenTable: (name: string) => void;
  onAnalyze: () => void;
}) {
  const recent = tables.slice(0, 5);
  const risks = metrics?.tables_without_primary_key ?? 0;
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> VISÃO DO AMBIENTE
          </div>
          <h1>
            Bom dia, equipe <span>👋</span>
          </h1>
          <p>Acompanhe a estrutura e a governança do seu banco de dados.</p>
        </div>
        <button className="button-primary" onClick={onAnalyze}>
          <Sparkles size={16} /> Executar análise <ArrowUpRight size={15} />
        </button>
      </div>
      <div className="hero-banner">
        <div className="hero-copy">
          <div className="hero-label">
            <span className="hero-orb">
              <Sparkles size={13} />
            </span>{" "}
            SEU BANCO, DECODIFICADO
          </div>
          <h2>
            Entenda o que existe
            <br />
            por trás dos seus dados.
          </h2>
          <p>
            Explore tabelas, descubra relações e encontre pontos de atenção na
            estrutura do seu banco.
          </p>
          <button
            className="button-light"
            onClick={() => onNavigate("catalog")}
          >
            Explorar catálogo <ChevronRight size={15} />
          </button>
        </div>
        <div className="hero-art">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="art-core">
            <Database size={25} />
          </div>
          <div className="art-node node-a">
            <Table2 size={15} />
          </div>
          <div className="art-node node-b">
            <Network size={15} />
          </div>
          <div className="art-node node-c">
            <Layers3 size={15} />
          </div>
          <div className="art-connector c1" />
          <div className="art-connector c2" />
          <div className="art-connector c3" />
        </div>
        <div className="hero-side-note">
          <span className="live-dot" /> ESTRUTURA EM TEMPO REAL
        </div>
      </div>
      <div className="section-head">
        <div>
          <h2>Saúde do ambiente</h2>
          <p>Indicadores atualizados a partir dos metadados do banco.</p>
        </div>
        <span className="updated-label">
          <Activity size={13} />{" "}
          {loading ? "Atualizando..." : "Atualizado agora"}
        </span>
      </div>
      <div className="metrics-grid">
        <MetricCard
          icon={Database}
          label="Tabelas catalogadas"
          value={metrics?.tables_total ?? "—"}
          detail={`${metrics?.tables_with_basic_metadata ?? "—"} com metadados básicos`}
          tone="blue"
          trend="Estrutura"
        />
        <MetricCard
          icon={Gauge}
          label="Cobertura de metadados"
          value={metrics ? `${metrics.metadata_coverage_percent}%` : "—"}
          detail="Tabelas com colunas identificadas"
          tone="green"
          progress={metrics?.metadata_coverage_percent ?? 0}
        />
        <MetricCard
          icon={AlertTriangle}
          label="Sem chave primária"
          value={metrics?.tables_without_primary_key ?? "—"}
          detail={
            risks ? "Requer atenção na estrutura" : "Nenhum ponto identificado"
          }
          tone={risks ? "amber" : "green"}
          trend={risks ? "Atenção" : "Saudável"}
        />
        <MetricCard
          icon={ShieldCheck}
          label="Sugestões revisadas"
          value={metrics ? `${metrics.review_rate_percent}%` : "—"}
          detail={`${metrics?.reviewed_suggestions ?? "—"} de ${metrics?.total_suggestions ?? "—"} sugestões`}
          tone="purple"
          progress={metrics?.review_rate_percent ?? 0}
        />
      </div>
      <div className="content-grid">
        <section className="panel table-panel">
          <div className="panel-heading">
            <div>
              <h3>Tabelas do catálogo</h3>
              <p>Uma visão rápida das tabelas do seu banco.</p>
            </div>
            <button className="text-link" onClick={() => onNavigate("catalog")}>
              Ver catálogo <ChevronRight size={14} />
            </button>
          </div>
          {recent.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>NOME DA TABELA</th>
                    <th>COLUNAS</th>
                    <th>CHAVE PRIMÁRIA</th>
                    <th>RELAÇÕES</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((table) => (
                    <tr
                      key={table.name}
                      onClick={() => onOpenTable(table.name)}
                    >
                      <td>
                        <span className="table-name-icon">
                          <Table2 size={15} />
                        </span>
                        <strong>{table.name}</strong>
                      </td>
                      <td>{table.columns_count}</td>
                      <td>
                        {table.primary_key.length ? (
                          <span className="tag tag-green">Configurada</span>
                        ) : (
                          <span className="tag tag-amber">Ausente</span>
                        )}
                      </td>
                      <td>
                        <span className="relation-count">
                          <Network size={13} /> {table.foreign_keys_count}
                        </span>
                      </td>
                      <td>
                        <ChevronRight size={15} className="row-arrow" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              loading={loading}
              title="Nenhuma tabela encontrada"
              detail="Conecte a API para carregar o catálogo do banco."
            />
          )}
        </section>
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <h3>Visão de governança</h3>
              <p>Status da revisão de sugestões.</p>
            </div>
            <button
              className="more-button"
              onClick={() => onNavigate("suggestions")}
            >
              •••
            </button>
          </div>
          <div className="governance-ring-wrap">
            <div
              className="governance-ring"
              style={
                {
                  "--progress": `${metrics?.review_rate_percent ?? 0}%`,
                } as React.CSSProperties
              }
            >
              <div>
                <strong>{metrics?.review_rate_percent ?? 0}%</strong>
                <span>revisadas</span>
              </div>
            </div>
            <div className="ring-legend">
              <span>
                <i className="legend-dot dot-reviewed" /> Revisadas{" "}
                <b>{metrics?.reviewed_suggestions ?? 0}</b>
              </span>
              <span>
                <i className="legend-dot dot-pending" /> Pendentes{" "}
                <b>{metrics?.pending_suggestions ?? 0}</b>
              </span>
            </div>
          </div>
          <div className="activity-note">
            <div className="note-icon">
              <ShieldCheck size={15} />
            </div>
            <p>
              {metrics?.note ||
                "As sugestões passam por revisão humana antes de qualquer decisão."}
            </p>
          </div>
          <button
            className="button-outline full-button"
            onClick={() => onNavigate("suggestions")}
          >
            Acessar revisão <ArrowUpRight size={14} />
          </button>
        </section>
      </div>
      <div className="bottom-insight">
        <div className="insight-icon">
          <Sparkles size={18} />
        </div>
        <div>
          <strong>Pronto para conhecer melhor seu banco?</strong>
          <p>
            Execute uma análise estrutural para encontrar recomendações de
            melhoria.
          </p>
        </div>
        <button onClick={() => onNavigate("analysis")}>
          Ver análise <ChevronRight size={15} />
        </button>
      </div>
    </>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone,
  progress,
  trend,
}: {
  icon: typeof Gauge;
  label: string;
  value: string | number;
  detail: string;
  tone: string;
  progress?: number;
  trend?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span className={`metric-icon ${tone}`}>
          <Icon size={17} />
        </span>
        {trend && <span className={`metric-trend ${tone}`}>{trend}</span>}
        {progress !== undefined && (
          <span className="metric-mini">
            {progress >= 80 ? (
              <ArrowUpRight size={14} />
            ) : (
              <ArrowDown size={13} />
            )}
          </span>
        )}
      </div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
      {progress !== undefined && (
        <div className="progress-track">
          <i
            className={tone}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}
    </div>
  );
}

function Catalog({
  tables,
  query,
  setQuery,
  loading,
  onOpenTable,
}: {
  tables: TableSummary[];
  query: string;
  setQuery: (q: string) => void;
  loading: boolean;
  onOpenTable: (name: string, tab?: DrawerTab) => void;
}) {
  const [sort, setSort] = useState<"name" | "columns">("name");
  const sorted = useMemo(
    () =>
      [...tables].sort((a, b) =>
        sort === "name"
          ? a.name.localeCompare(b.name)
          : b.columns_count - a.columns_count,
      ),
    [tables, sort],
  );
  return (
    <>
      <div className="page-heading compact-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> EXPLORADOR
          </div>
          <h1>Catálogo de tabelas</h1>
          <p>
            Navegue pela estrutura do banco e consulte colunas, chaves e
            relacionamentos.
          </p>
        </div>
        <div className="catalog-total">
          <Database size={17} />
          <strong>{tables.length}</strong>
          <span>tabelas</span>
        </div>
      </div>
      <section className="panel catalog-panel">
        <div className="catalog-toolbar">
          <div className="search-box">
            <Search size={16} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por tabela ou coluna..."
            />
            <kbd>⌘ K</kbd>
          </div>
          <div className="toolbar-right">
            <span className="filter-label">Ordenar por</span>
            <button
              className="select-button"
              onClick={() => setSort(sort === "name" ? "columns" : "name")}
            >
              {sort === "name" ? "Nome da tabela" : "Quantidade de colunas"}{" "}
              <ChevronDown size={14} />
            </button>
            <button className="icon-button bordered" title="Atualizar catálogo">
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
        {sorted.length ? (
          <div className="table-wrap catalog-table">
            <table>
              <thead>
                <tr>
                  <th>
                    TABELA <span className="sort-mark">↕</span>
                  </th>
                  <th>SCHEMA</th>
                  <th>COLUNAS</th>
                  <th>CHAVE PRIMÁRIA</th>
                  <th>RELACIONAMENTOS</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((t) => (
                  <tr key={t.name} onClick={() => onOpenTable(t.name)}>
                    <td>
                      <span className="table-name-icon">
                        <Table2 size={15} />
                      </span>
                      <strong>{t.name}</strong>
                    </td>
                    <td>
                      <span className="schema-tag">{t.schema}</span>
                    </td>
                    <td>
                      {t.columns_count} <span className="muted">colunas</span>
                    </td>
                    <td>
                      {t.primary_key.length ? (
                        <span className="tag tag-green">
                          <Check size={11} /> Sim
                        </span>
                      ) : (
                        <span className="tag tag-amber">
                          <AlertTriangle size={11} /> Não
                        </span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="relation-count relation-link"
                        title="Ver relacionamentos"
                        aria-label={`Ver relacionamentos de ${t.name}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onOpenTable(t.name, "relations");
                        }}
                      >
                        <Network size={13} /> {t.foreign_keys_count}
                      </button>
                    </td>
                    <td>
                      <button
                        className="open-row"
                        aria-label={`Abrir ${t.name}`}
                      >
                        <ArrowUpRight size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            loading={loading}
            title="Nenhuma tabela encontrada"
            detail={
              query
                ? "Tente buscar por outro nome."
                : "O catálogo aparecerá aqui quando a API estiver conectada."
            }
          />
        )}
        <div className="table-pagination">
          <span>
            Exibindo <strong>{sorted.length}</strong> de{" "}
            <strong>{tables.length}</strong> tabelas
          </span>
          <div>
            <button disabled>
              <ChevronLeft size={15} />
            </button>
            <button className="page-current">1</button>
            <button disabled>
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

function Analysis({
  recommendations,
  loading,
  connected,
  onReload,
  busy,
  onAiAnalyze,
  aiBusy,
  aiNotice,
  aiResult,
  onPrivacy,
  privacyBusy,
  canSuggest,
}: {
  recommendations: Recommendation[];
  loading: boolean;
  connected: boolean;
  onReload: () => void;
  busy: boolean;
  onAiAnalyze: () => void;
  aiBusy: boolean;
  aiNotice: string;
  aiResult: AiAnalysisResult | null;
  onPrivacy: () => void;
  privacyBusy: boolean;
  canSuggest: boolean;
}) {
  const countHigh = recommendations.filter((r) => r.severity === "high").length;
  const countMedium = recommendations.filter(
    (r) => r.severity === "medium",
  ).length;
  const countLow = recommendations.filter((r) => r.severity === "low").length;
  return (
    <>
      <div className="page-heading compact-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> DIAGNÓSTICO
          </div>
          <h1>Análise estrutural</h1>
          <p>Recomendações geradas a partir dos metadados do banco de dados.</p>
        </div>
        <div className="toolbar-right">
          <button
            className="button-primary"
            onClick={onReload}
            disabled={busy || !connected}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <RefreshCw size={15} />
            )}{" "}
            Regras
          </button>
          <button
            className="button-primary"
            onClick={onAiAnalyze}
            disabled={aiBusy || !connected || !canSuggest}
            title={
              canSuggest
                ? "Analisa metadados seguros e salva propostas"
                : "Requer persona analista ou superior"
            }
          >
            {aiBusy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Sparkles size={15} />
            )}{" "}
            {aiBusy ? "Analisando..." : "Analisar com Groq"}
          </button>
          <button
            className="button-outline"
            onClick={onPrivacy}
            disabled={privacyBusy || !connected}
            title="Ver exatamente quais metadados seriam enviados à IA"
          >
            {privacyBusy ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <Eye size={15} />
            )}{" "}
            Metadados da IA
          </button>
        </div>
      </div>
      {aiNotice && aiResult && (
        <div className="alert success ai-completion-alert">
          <Sparkles size={16} />
          <span>
            {aiResult.suggestions_created > 0
              ? `Análise do Groq concluída: ${aiResult.suggestions_created} nova(s) proposta(s) salva(s). `
              : aiResult.duplicates_skipped > 0
                ? "Análise do Groq concluída: as propostas já estavam salvas, então nenhuma foi repetida. "
                : "Análise do Groq concluída: não houve novas propostas. "}
            {aiResult.duplicates_skipped > 0 &&
              `${aiResult.duplicates_skipped} semelhante(s) ignorada(s). `}
            Resumo: {aiResult.summary} Propostas ficam salvas para revisão,
            mesmo depois de fechar o app.
          </span>
        </div>
      )}
      {aiResult?.privacy && (
        <div className="privacy-strip">
          <Lock size={15} />
          <span>
            <strong>Privacidade verificada.</strong>{" "}
            {aiResult.privacy.tables_sent} tabela(s) e{" "}
            {aiResult.privacy.columns_sent} coluna(s) enviadas;{" "}
            {aiResult.privacy.sensitive_columns_flagged} coluna(s) sensível(is)
            marcada(s); {aiResult.privacy.records_sent} registro(s) e{" "}
            {aiResult.privacy.defaults_sent} default(s) enviados. Hash do
            payload: <code>{aiResult.privacy.payload_sha256.slice(0, 16)}…</code>
          </span>
          <button className="text-link" onClick={onPrivacy}>
            Ver payload <ArrowUpRight size={13} />
          </button>
        </div>
      )}
      {aiResult && aiResult.suggestions.length > 0 && (
        <section
          className="panel"
          style={{ padding: "14px 16px", marginBottom: 13 }}
        >
          <div className="section-head">
            <div>
              <h2>Propostas do Groq</h2>
              <p>
                Geradas com base nos metadados do esquema e salvas para revisão
                humana.
              </p>
            </div>
          </div>
          <div className="suggestion-list">
            {aiResult.suggestions.map((item) => (
              <article className="suggestion-card" key={item.id}>
                <div className="suggestion-type-icon">
                  <Sparkles size={16} />
                </div>
                <div className="suggestion-content">
                  <div className="suggestion-meta">
                    <span className="suggestion-kind">{item.kind}</span>
                    <span className="table-reference">
                      <Table2 size={13} /> {item.table}
                    </span>
                    <span className="status-tag pending">Pendente</span>
                  </div>
                  <ExpandableText
                    text={item.description}
                    className="suggestion-description"
                    limit={220}
                  />
                  <ExpandableText
                    text={item.rationale}
                    className="suggestion-rationale"
                    limit={360}
                  />
                  <div className="confidence">
                    <span>Confiança</span>
                    <div className="confidence-track">
                      <i
                        style={{
                          width: `${Math.round(item.confidence * 100)}%`,
                        }}
                      />
                    </div>
                    <strong>{Math.round(item.confidence * 100)}%</strong>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
      <div className="analysis-summary">
        <div className="summary-main">
          <div className="summary-icon">
            <FileSearch size={19} />
          </div>
          <div>
            <strong>
              {recommendations.length
                ? `${recommendations.length} ponto${recommendations.length === 1 ? "" : "s"} para revisar`
                : "Estrutura analisada"}
            </strong>
            <p>
              {loading
                ? "Carregando análise..."
                : connected
                  ? "A análise usa regras determinísticas e não altera o banco."
                  : "Conecte a API para executar a análise."}
            </p>
          </div>
        </div>
        <div className="severity-counts">
          <span>
            <i className="sev-dot high" /> Alta <b>{countHigh}</b>
          </span>
          <span>
            <i className="sev-dot medium" /> Média <b>{countMedium}</b>
          </span>
          <span>
            <i className="sev-dot low" /> Baixa <b>{countLow}</b>
          </span>
        </div>
      </div>
      {recommendations.length ? (
        <div className="recommendation-list">
          {recommendations.map((item, index) => (
            <RecommendationCard
              key={`${item.table}-${item.category}-${index}`}
              item={item}
            />
          ))}
        </div>
      ) : (
        <div className="panel empty-analysis">
          <div className="empty-symbol">
            <Check size={22} />
          </div>
          <h3>
            {connected
              ? "Nenhuma recomendação encontrada"
              : "API não conectada"}
          </h3>
          <p>
            {connected
              ? "A estrutura analisada não apresentou pontos de atenção nas regras atuais."
              : "Inicie o backend e atualize a página para consultar o banco."}
          </p>
        </div>
      )}
      <div className="analysis-footnote">
        <ShieldCheck size={15} />
        <span>
          As recomendações são informativas. O GenomAI nunca executa alterações
          automaticamente no banco.
        </span>
      </div>
    </>
  );
}

function RecommendationCard({ item }: { item: Recommendation }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className="recommendation-card">
      <div className={`severity-bar ${item.severity}`} />
      <div className="recommendation-body">
        <div className="recommendation-top">
          <span className={`severity-tag ${item.severity}`}>
            {item.severity === "high"
              ? "Alta prioridade"
              : item.severity === "medium"
                ? "Média prioridade"
                : "Baixa prioridade"}
          </span>
          <span className="category-tag">
            {item.category.replace("_", " ")}
          </span>
          <span className="table-reference">
            <Table2 size={13} /> {item.table}
          </span>
          <button
            className="expand-button"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? "Menos detalhes" : "Ver detalhes"}{" "}
            <ChevronDown size={14} className={expanded ? "rotate" : ""} />
          </button>
        </div>
        <h3>{item.message}</h3>
        {expanded && (
          <div className="recommendation-details">
            <p>
              {item.evidence ||
                "A recomendação foi identificada durante a inspeção da estrutura."}
            </p>
            {item.suggested_sql && (
              <div className="sql-box">
                <div>
                  <span>SQL SUGERIDO</span>
                  <button
                    onClick={() =>
                      void navigator.clipboard?.writeText(
                        item.suggested_sql || "",
                      )
                    }
                  >
                    Copiar
                  </button>
                </div>
                <code>{item.suggested_sql}</code>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

function ExpandableText({
  text,
  className,
  limit,
}: {
  text: string;
  className: string;
  limit: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [maxHeight, setMaxHeight] = useState("7.2em");
  const copyRef = useRef<HTMLDivElement>(null);
  const canExpand = text.length > limit;
  const toggleExpanded = () => {
    if (expanded) setMaxHeight("7.2em");
    else if (copyRef.current) setMaxHeight(`${copyRef.current.scrollHeight}px`);
    setExpanded((value) => !value);
  };
  return (
    <div className={`expandable-text ${className}`}>
      <div
        ref={copyRef}
        className={`expandable-copy ${canExpand && !expanded ? "collapsed" : ""}`}
        style={{ maxHeight: canExpand ? maxHeight : "none" }}
      >
        {text}
      </div>
      {canExpand && (
        <button
          className="expandable-toggle"
          aria-expanded={expanded}
          onClick={toggleExpanded}
        >
          {expanded ? "Mostrar menos" : "Mostrar mais"}
        </button>
      )}
    </div>
  );
}

function Suggestions({
  items,
  status,
  setStatus,
  loading,
  busy,
  persona,
  canEdit,
  canReview,
  canApply,
  onReview,
  onEdit,
  onApply,
}: {
  items: Suggestion[];
  status: string;
  setStatus: (s: string) => void;
  loading: boolean;
  busy: boolean;
  persona: PersonaId;
  canEdit: boolean;
  canReview: boolean;
  canApply: boolean;
  onReview: (id: number, decision: SuggestionStatus) => void;
  onEdit: (item: Suggestion) => void;
  onApply: (id: number) => void;
}) {
  const statuses = [
    ["pending", "Pendentes"],
    ["partially_approved", "Parciais"],
    ["approved", "Aprovadas"],
    ["rejected", "Rejeitadas"],
    ["all", "Todas"],
  ];
  const labelFor = (value: string) =>
    value === "pending"
      ? "Pendente"
      : value === "approved"
        ? "Aprovada"
        : value === "partially_approved"
          ? "Parcial"
          : "Rejeitada";
  return (
    <>
      <div className="page-heading compact-heading">
        <div>
          <div className="eyebrow">
            <span className="eyebrow-line" /> GOVERNANÇA
          </div>
          <h1>Revisão de sugestões</h1>
          <p>
            Revise, edite e aplique propostas com trilha de auditoria e
            permissões por persona.
          </p>
        </div>
        <div className="review-count">
          <ShieldCheck size={17} />
          <strong>{items.length}</strong>
          <span>{status === "pending" ? "pendentes" : "itens"}</span>
          <span className="persona-chip">{persona}</span>
        </div>
      </div>
      <section className="panel suggestions-panel">
        <div className="suggestion-tabs">
          {statuses.map(([key, label]) => (
            <button
              key={key}
              className={status === key ? "selected" : ""}
              onClick={() => setStatus(key)}
            >
              {label}
              {key === "pending" && items.length > 0 && status === key && (
                <b>{items.length}</b>
              )}
            </button>
          ))}
        </div>
        {items.length ? (
          <div className="suggestion-list">
            {items.map((item) => {
              const applied = Boolean(item.applied_at);
              return (
                <article className="suggestion-card" key={item.id}>
                  <div
                    className={`suggestion-type-icon ${applied ? "applied" : ""}`}
                  >
                    {applied ? <Check size={16} /> : <Sparkles size={16} />}
                  </div>
                  <div className="suggestion-content">
                    <div className="suggestion-meta">
                      <span className="suggestion-kind">{item.kind}</span>
                      <span className="table-reference">
                        <Table2 size={13} /> {item.table}
                        {item.column_name ? (
                          <code className="column-reference">
                            {item.column_name}
                          </code>
                        ) : null}
                      </span>
                      <span
                        className={`status-tag ${applied ? "applied" : item.status}`}
                      >
                        {applied ? "Aplicada" : labelFor(item.status)}
                      </span>
                      <span className="revision-hint">
                        v{item.version} · {item.revision_count} revisão(ões)
                      </span>
                    </div>
                    <ExpandableText
                      text={item.description}
                      className="suggestion-description"
                      limit={220}
                    />
                    <ExpandableText
                      text={item.rationale}
                      className="suggestion-rationale"
                      limit={360}
                    />
                    {item.suggested_sql && (
                      <details className="sql-details">
                        <summary>SQL candidato (não executado)</summary>
                        <code>{item.suggested_sql}</code>
                      </details>
                    )}
                    <div className="confidence">
                      <span>Confiança</span>
                      <div className="confidence-track">
                        <i
                          style={{
                            width: `${Math.round(item.confidence * 100)}%`,
                          }}
                        />
                      </div>
                      <strong>{Math.round(item.confidence * 100)}%</strong>
                    </div>
                    {applied && (
                      <div className="applied-note">
                        <Check size={13} /> Aplicada em{" "}
                        {item.applied_at
                          ? new Date(item.applied_at).toLocaleString("pt-BR")
                          : "—"}{" "}
                        por {item.applied_by ?? "—"}.
                      </div>
                    )}
                    {item.apply_error && (
                      <div className="apply-error">
                        <AlertTriangle size={13} /> Última tentativa falhou:{" "}
                        {item.apply_error}
                      </div>
                    )}
                  </div>
                  <div className="suggestion-actions">
                    {!applied && canEdit && (
                      <button
                        type="button"
                        disabled={busy}
                        className="edit-button"
                        onClick={() => onEdit(item)}
                      >
                        <Pencil size={13} /> Editar
                      </button>
                    )}
                    {!applied &&
                      canReview &&
                      (item.status === "pending" ||
                        item.status === "partially_approved") && (
                        <>
                          <button
                            type="button"
                            disabled={busy}
                            className="reject-button"
                            onClick={() => onReview(item.id, "rejected")}
                          >
                            <XCircle size={13} /> Rejeitar
                          </button>
                          {item.status === "pending" && (
                            <button
                              type="button"
                              disabled={busy}
                              className="partial-button"
                              onClick={() =>
                                onReview(item.id, "partially_approved")
                              }
                            >
                              <ShieldCheck size={13} /> Parcial
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={busy}
                            className="approve-button"
                            onClick={() => onReview(item.id, "approved")}
                          >
                            <Check size={13} /> Aprovar
                          </button>
                        </>
                      )}
                    {!applied && item.status === "approved" && canApply && (
                      <button
                        type="button"
                        disabled={busy}
                        className="apply-button"
                        onClick={() => onApply(item.id)}
                      >
                        <Send size={13} /> Aplicar no BD
                      </button>
                    )}
                    {!applied && item.status === "approved" && !canApply && (
                      <span className="permission-hint">
                        <Lock size={12} /> Requer desenvolvedor
                      </span>
                    )}
                    {!applied && item.status === "rejected" && canReview && (
                      <button
                        type="button"
                        disabled={busy}
                        className="edit-button"
                        onClick={() => onEdit(item)}
                      >
                        <Pencil size={13} /> Reabrir
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            loading={loading}
            title={
              status === "pending"
                ? "Tudo em dia por aqui"
                : "Nenhuma sugestão encontrada"
            }
            detail={
              status === "pending"
                ? "Não há sugestões aguardando revisão."
                : "As sugestões registradas aparecerão nesta lista."
            }
            icon={<ShieldCheck size={20} />}
          />
        )}
        <div className="suggestions-note">
          <ShieldCheck size={14} />
          <span>
            Aprovar registra a decisão. Editar reabre a sugestão e gera uma
            versão imutável. Aplicar no banco exige persona
            desenvolvedor/administrador e DB_WRITE_ENABLED=true.
          </span>
        </div>
      </section>
    </>
  );
}

function SuggestionEditModal({
  item,
  busy,
  onClose,
  onSave,
}: {
  item: Suggestion;
  busy: boolean;
  onClose: () => void;
  onSave: (id: number, body: SuggestionEdit) => Promise<void>;
}) {
  const [form, setForm] = useState({
    table: item.table,
    kind: item.kind,
    column_name: item.column_name ?? "",
    description: item.description,
    confidence: item.confidence,
    rationale: item.rationale,
    suggested_sql: item.suggested_sql ?? "",
    comment: "",
  });
  const [revisions, setRevisions] = useState<SuggestionRevision[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void api
      .revisions(item.id)
      .then(setRevisions)
      .catch((e) =>
        setHistoryError(
          e instanceof Error ? e.message : "Não foi possível carregar o histórico.",
        ),
      );
  }, [item.id]);

  const update = <K extends keyof typeof form>(
    key: K,
    value: (typeof form)[K],
  ) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await onSave(item.id, {
        table: form.table,
        kind: form.kind,
        column_name: form.column_name.trim() || null,
        description: form.description,
        confidence: Number(form.confidence),
        rationale: form.rationale,
        suggested_sql: form.suggested_sql.trim() || null,
        comment: form.comment,
        reopen: true,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível salvar.");
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal-card edit-modal"
        role="dialog"
        aria-modal="true"
        aria-label={`Editar sugestão ${item.id}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <span className="eyebrow">
              <span className="eyebrow-line" /> EDIÇÃO HUMANA
            </span>
            <h2>Editar sugestão #{item.id}</h2>
            <p>
              A edição gera a versão {item.version + 1} e reabre a sugestão para
              nova decisão.
            </p>
          </div>
          <button
            type="button"
            className="icon-button bordered"
            onClick={onClose}
            aria-label="Fechar edição"
          >
            <X size={16} />
          </button>
        </div>
        <form onSubmit={submit} className="modal-body">
          <div className="form-grid">
            <label>
              Tabela
              <input
                value={form.table}
                onChange={(e) => update("table", e.target.value)}
                required
              />
            </label>
            <label>
              Tipo
              <select
                value={form.kind}
                onChange={(e) => update("kind", e.target.value)}
              >
                {[
                  "documentation",
                  "index",
                  "integrity",
                  "relationship",
                  "naming",
                  "review",
                ].map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Coluna alvo (opcional)
              <input
                value={form.column_name}
                onChange={(e) => update("column_name", e.target.value)}
                placeholder="ex.: cd_status"
              />
            </label>
            <label>
              Confiança (0 a 1)
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={form.confidence}
                onChange={(e) => update("confidence", Number(e.target.value))}
                required
              />
            </label>
          </div>
          <label>
            Descrição
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
              required
            />
          </label>
          <label>
            Justificativa / evidência
            <textarea
              rows={5}
              value={form.rationale}
              onChange={(e) => update("rationale", e.target.value)}
              required
            />
          </label>
          <label>
            SQL candidato (informativo; nunca executado automaticamente)
            <textarea
              rows={3}
              value={form.suggested_sql}
              onChange={(e) => update("suggested_sql", e.target.value)}
            />
          </label>
          <label>
            Comentário da edição (vai para o histórico)
            <input
              value={form.comment}
              onChange={(e) => update("comment", e.target.value)}
              maxLength={1000}
              placeholder="Por que esta sugestão precisou de ajuste?"
            />
          </label>
          {error && (
            <div className="modal-error">
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          <div className="revision-list">
            <h4>
              <History size={14} /> Histórico de versões
            </h4>
            {historyError && <p className="muted">{historyError}</p>}
            {revisions.map((revision) => (
              <div className="revision-row" key={revision.id}>
                <strong>v{revision.version}</strong>
                <span>{revision.status}</span>
                <span>{revision.edited_by}</span>
                <span>
                  {revision.created_at
                    ? new Date(revision.created_at).toLocaleString("pt-BR")
                    : "—"}
                </span>
                {revision.comment && <em>{revision.comment}</em>}
              </div>
            ))}
          </div>
          <div className="modal-actions">
            <button type="button" className="button-outline" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="button-primary" disabled={busy}>
              {busy ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Save size={15} />
              )}{" "}
              Salvar e reabrir
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ApplyPreviewModal({
  preview,
  busy,
  onClose,
  onConfirm,
}: {
  preview: ApplyPreview;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal-card apply-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Confirmar aplicação no banco"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <span className="eyebrow">
              <span className="eyebrow-line" /> MUDANÇA NO BANCO
            </span>
            <h2>Aplicar sugestão #{preview.suggestion_id}</h2>
            <p>
              Ação reservada a desenvolvedor/administrador e registrada em
              auditoria.
            </p>
          </div>
          <button
            type="button"
            className="icon-button bordered"
            onClick={onClose}
            aria-label="Fechar aplicação"
          >
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          <div className="modal-warning">
            <AlertTriangle size={15} />
            <span>
              Esta é a única operação que altera o banco analisado. O SQL foi
              gerado pelo servidor, não pelo modelo de IA.
            </span>
          </div>
          {preview.sql && (
            <div className="sql-preview">
              <span>SQL que será executado</span>
              <pre>{preview.sql}</pre>
            </div>
          )}
          {preview.blockers.length > 0 && (
            <div className="blocker-list">
              <strong>Bloqueios</strong>
              {preview.blockers.map((blocker) => (
                <p key={blocker}>
                  <XCircle size={13} /> {blocker}
                </p>
              ))}
            </div>
          )}
          {preview.warnings.length > 0 && (
            <div className="warning-list">
              {preview.warnings.map((warning) => (
                <p key={warning}>
                  <ShieldCheck size={13} /> {warning}
                </p>
              ))}
            </div>
          )}
          <div className="modal-actions">
            <button type="button" className="button-outline" onClick={onClose}>
              Cancelar
            </button>
            <button
              type="button"
              className="apply-button"
              disabled={!preview.can_apply || busy}
              onClick={onConfirm}
            >
              {busy ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Send size={15} />
              )}{" "}
              Confirmar e aplicar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PrivacyModal({
  data,
  storage,
  onClose,
}: {
  data: { preview: AiPayloadPreview; policy: PrivacyPolicy };
  storage: StorageInfo | null;
  onClose: () => void;
}) {
  const report = data.preview.report;
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal-card privacy-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Metadados enviados à IA"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <div>
            <span className="eyebrow">
              <span className="eyebrow-line" /> PRIVACIDADE
            </span>
            <h2>Metadados enviados à IA</h2>
            <p>{report.notice}</p>
          </div>
          <button
            type="button"
            className="icon-button bordered"
            onClick={onClose}
            aria-label="Fechar privacidade"
          >
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          <div className="privacy-grid">
            <div>
              <strong>{report.tables_included}</strong>
              <span>tabelas enviadas</span>
            </div>
            <div>
              <strong>{report.columns_included}</strong>
              <span>colunas enviadas</span>
            </div>
            <div>
              <strong>{report.sensitive_columns}</strong>
              <span>colunas sensíveis marcadas</span>
            </div>
            <div>
              <strong>{report.redacted_identifiers}</strong>
              <span>identificadores redigidos</span>
            </div>
            <div>
              <strong>0</strong>
              <span>registros enviados</span>
            </div>
            <div>
              <strong>0</strong>
              <span>defaults enviados</span>
            </div>
          </div>
          {storage && (
            <div
              className={`modal-note ${storage.app_store.remote ? "success" : "warning"}`}
            >
              <Lock size={14} />
              <span>
                Armazenamento interno:{" "}
                {storage.app_store.remote
                  ? `${storage.app_store.backend} · schema ${storage.app_store.schema}`
                  : "SQLite local (configure APP_DATABASE_URL para PostgreSQL em produção)"}
                . As sugestões nunca entram no payload da IA.
              </span>
            </div>
          )}
          <div className="policy-columns">
            <div>
              <h4>Nunca enviado</h4>
              <ul>
                {data.policy.never_sent.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4>Tabelas excluídas por isolamento</h4>
              <ul>
                {report.excluded_table_names.map((item) => (
                  <li key={item}>
                    <code>{item}</code>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="sql-preview">
            <span>
              Payload exato (SHA-256: <code>{data.preview.sha256}</code>)
            </span>
            <pre>{JSON.stringify(data.preview.payload, null, 2)}</pre>
          </div>
          <div className="modal-actions">
            <button type="button" className="button-primary" onClick={onClose}>
              Entendi
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  loading,
  title,
  detail,
  icon,
}: {
  loading: boolean;
  title: string;
  detail: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">
        {loading ? (
          <LoaderCircle className="spin" size={20} />
        ) : (
          icon || <Database size={20} />
        )}
      </div>
      <strong>{loading ? "Carregando dados..." : title}</strong>
      <p>{loading ? "Consultando o backend do GenomAI." : detail}</p>
    </div>
  );
}

export default App;
