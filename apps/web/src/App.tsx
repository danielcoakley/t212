import {
  AlertTriangle,
  BarChart3,
  Building2,
  CheckCircle2,
  ClipboardList,
  Database,
  FileClock,
  LineChart,
  Pause,
  Play,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  WalletCards,
  type LucideIcon
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { endpoints, Health, OpenBBStatus, Position, Signal, TickerContext } from "./api";

type Tab = "overview" | "signals" | "positions" | "orders" | "backtests" | "settings" | "logs";

const tabs: Array<{ id: Tab; label: string; icon: LucideIcon }> = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "signals", label: "Signals", icon: LineChart },
  { id: "positions", label: "Positions", icon: WalletCards },
  { id: "orders", label: "Orders", icon: ClipboardList },
  { id: "backtests", label: "Backtests", icon: FileClock },
  { id: "settings", label: "Settings", icon: Settings },
  { id: "logs", label: "Logs", icon: Database }
];

type DashboardState = {
  health: Health | null;
  openbb: OpenBBStatus | null;
  positions: Position[];
  signals: Signal[];
  warnings: string[];
};

const emptyState: DashboardState = {
  health: null,
  openbb: null,
  positions: [],
  signals: [],
  warnings: []
};

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [state, setState] = useState<DashboardState>(emptyState);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    const [health, openbb, positions] = await Promise.allSettled([
      endpoints.health(),
      endpoints.openbb(),
      endpoints.positions()
    ]);
    const failures = [health, openbb, positions].flatMap((result) =>
      result.status === "rejected" ? [failureReason(result.reason)] : []
    );
    setState((current) => ({
      health: health.status === "fulfilled" ? health.value : current.health,
      openbb: openbb.status === "fulfilled" ? openbb.value : current.openbb,
      positions: positions.status === "fulfilled" ? positions.value : current.positions,
      signals: current.signals,
      warnings: current.warnings
    }));
    setError(failures.length ? failures.join(" | ") : null);
    setLoading(false);
    void endpoints
      .signals()
      .then((signals) => {
        setState((current) => ({
          ...current,
          signals: signals.rows ?? [],
          warnings: signals.warnings ?? []
        }));
      })
      .catch((err) => {
        setError(failureReason(err));
      });
  };

  useEffect(() => {
    void refresh();
  }, []);

  const totalValue = useMemo(() => {
    return state.positions.reduce((sum, position) => sum + Number(position.current_value ?? 0), 0);
  }, [state.positions]);

  const pause = async () => {
    await endpoints.pause();
    await refresh();
  };

  const resumePaper = async () => {
    await endpoints.resume();
    await endpoints.paper();
    await refresh();
  };

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <ShieldCheck size={24} />
          <span>ISA System</span>
        </div>
        <nav className="tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={activeTab === tab.id ? "tab active" : "tab"}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
              >
                <Icon size={18} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{tabs.find((tab) => tab.id === activeTab)?.label}</h1>
            <p>{state.health?.mode ?? "preview"} | {state.health?.status ?? "offline"}</p>
          </div>
          <div className="actions">
            <button className="iconButton" onClick={refresh} title="Refresh">
              <RefreshCw size={18} className={loading ? "spin" : ""} />
            </button>
            <button className="iconButton danger" onClick={pause} title="Pause trading">
              <Pause size={18} />
            </button>
            <button className="iconButton success" onClick={resumePaper} title="Resume in paper mode">
              <Play size={18} />
            </button>
          </div>
        </header>

        {error ? <div className="alert"><AlertTriangle size={18} />{error}</div> : null}

        {activeTab === "overview" && (
          <Overview state={state} totalValue={totalValue} />
        )}
        {activeTab === "signals" && <Signals rows={state.signals} />}
        {activeTab === "positions" && <Positions rows={state.positions} />}
        {activeTab === "orders" && <Orders />}
        {activeTab === "backtests" && <Backtests />}
        {activeTab === "settings" && <SettingsView state={state} />}
        {activeTab === "logs" && <Logs warnings={state.warnings} />}
      </section>
    </main>
  );
}

function Overview({ state, totalValue }: { state: DashboardState; totalValue: number }) {
  return (
    <div className="contentGrid">
      <Metric label="Position Value" value={money(totalValue)} tone="blue" />
      <Metric label="Open Positions" value={String(state.positions.length)} tone="green" />
      <Metric label="Live Armed" value={state.health?.live_armed ? "Yes" : "No"} tone="red" />
      <Metric label="OpenBB Lock" value={state.openbb?.matches_lock ? "Matched" : "Check"} tone="amber" />
      <section className="panel wide">
        <h2>Health</h2>
        <div className="healthGrid">
          {Object.entries(state.health?.subsystems ?? {}).map(([name, value]) => (
            <div className="health" key={name}>
              <CheckCircle2 size={18} />
              <span>{name}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>
      <CompanyContextPanel />
      <section className="panel">
        <h2>OpenBB</h2>
        <p className="mono">{state.openbb?.backend ?? "unknown"} | {state.openbb?.odp_api_status ?? "unknown"}</p>
        <p>{state.openbb?.odp_api_base_url ?? state.openbb?.remote_url ?? "OpenBB backend not configured"}</p>
      </section>
    </div>
  );
}

function CompanyContextPanel() {
  const [symbol, setSymbol] = useState("AAPL");
  const [context, setContext] = useState<TickerContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async (nextSymbol = symbol) => {
    const cleanSymbol = nextSymbol.trim().toUpperCase();
    if (!cleanSymbol) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await endpoints.tickerContext(cleanSymbol);
      setContext(result);
      if (result.status === "error") {
        setError(Object.values(result.errors)[0] ?? "OpenBB did not return context data.");
      }
    } catch (err) {
      setError(failureReason(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load("AAPL");
  }, []);

  const profile = context?.profile[0] ?? {};
  const latest = context?.prices.latest ?? {};
  const companyName = pickField(profile, ["name", "company_name", "short_name", "long_name"]);
  const sector = pickField(profile, ["sector"]);
  const industry = pickField(profile, ["industry", "industry_category"]);
  const exchange = pickField(profile, ["exchange", "exchange_name", "stock_exchange"]);
  const close = pickField(latest, ["close", "adj_close"]);

  return (
    <section className="panel wide">
      <div className="panelHeader">
        <div>
          <h2><Building2 size={18} /> OpenBB Company Context</h2>
          <p>{context ? `${context.provider} | ${context.symbol}` : "OpenBB profile, fundamentals, and prices"}</p>
        </div>
        <form
          className="symbolSearch"
          onSubmit={(event) => {
            event.preventDefault();
            void load();
          }}
        >
          <input
            aria-label="Ticker symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            spellCheck={false}
          />
          <button className="iconButton" title="Load ticker context" type="submit">
            <Search size={18} />
          </button>
        </form>
      </div>
      {error ? <div className="inlineAlert"><AlertTriangle size={16} />{error}</div> : null}
      <dl className="contextGrid">
        <div>
          <dt>Company</dt>
          <dd>{companyName || context?.symbol || "Waiting for OpenBB"}</dd>
        </div>
        <div>
          <dt>Sector</dt>
          <dd>{sector || "unknown"}</dd>
        </div>
        <div>
          <dt>Industry</dt>
          <dd>{industry || "unknown"}</dd>
        </div>
        <div>
          <dt>Exchange</dt>
          <dd>{exchange || "unknown"}</dd>
        </div>
        <div>
          <dt>Latest Close</dt>
          <dd>{close || (loading ? "loading" : "unknown")}</dd>
        </div>
        <div>
          <dt>Fundamentals Rows</dt>
          <dd>{String(context?.fundamentals.length ?? 0)}</dd>
        </div>
      </dl>
    </section>
  );
}

function Signals({ rows }: { rows: Signal[] }) {
  return <Table rows={rows.slice(0, 20).map((row) => ({
    symbol: row.research_symbol ?? row.symbol ?? "unknown",
    action: row.action ?? "WATCH",
    score: formatScore(row.composite_score),
    broker: row.broker_ticker ?? row.broker_validation_status ?? "",
    source: row.source ?? ""
  }))} />;
}

function Positions({ rows }: { rows: Position[] }) {
  return <Table rows={rows.map((row) => ({
    symbol: row.symbol ?? row.broker_ticker ?? "unknown",
    quantity: row.quantity ?? "",
    value: typeof row.current_value === "number" ? money(row.current_value) : "",
    pnl: typeof row.unrealised_profit_loss === "number" ? money(row.unrealised_profit_loss) : "",
    currency: row.currency ?? ""
  }))} />;
}

function Orders() {
  return <EmptyPanel title="Approval Queue" value="No queued live orders" />;
}

function Backtests() {
  return <EmptyPanel title="Latest Run" value="No backtest selected" />;
}

function SettingsView({ state }: { state: DashboardState }) {
  return <Table rows={[
    { name: "mode", value: state.health?.mode ?? "preview" },
    { name: "kill_switch", value: state.health?.kill_switch_enabled ? "enabled" : "disabled" },
    { name: "openbb_revision", value: shortSha(state.openbb?.locked_revision) }
  ]} />;
}

function Logs({ warnings }: { warnings: string[] }) {
  return <Table rows={(warnings.length ? warnings : ["No warnings"]).map((message) => ({ message }))} />;
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <section className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  );
}

function EmptyPanel({ title, value }: { title: string; value: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p>{value}</p>
    </section>
  );
}

function Table({ rows }: { rows: Array<Record<string, unknown>> }) {
  const headers = Object.keys(rows[0] ?? {});
  if (!headers.length) {
    return (
      <section className="panel wide">
        <p>No rows</p>
      </section>
    );
  }
  return (
    <section className="panel wide">
      <table>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {headers.map((header) => <td key={header}>{String(row[header] ?? "")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function money(value: number) {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);
}

function shortSha(value?: string | null) {
  return value ? value.slice(0, 12) : "unknown";
}

function formatScore(value?: number) {
  return typeof value === "number" ? value.toFixed(2) : "";
}

function failureReason(error: unknown) {
  return error instanceof Error ? error.message : "Unknown API error";
}

function pickField(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (value !== null && value !== undefined && value !== "") {
      return String(value);
    }
  }
  return "";
}
