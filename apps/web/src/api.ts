const CONFIGURED_API_BASE = normaliseBase(import.meta.env.VITE_API_BASE_URL);
let resolvedApiBase: string | null = null;
let resolveApiBasePromise: Promise<string> | null = null;

export type Health = {
  status: string;
  mode: string;
  live_armed: boolean;
  kill_switch_enabled: boolean;
  subsystems: Record<string, string>;
};

export type OpenBBStatus = {
  backend?: string;
  python_importable?: boolean;
  odp_api_base_url?: string;
  odp_api_status?: string;
  odp_api_error?: string | null;
  current_revision: string | null;
  locked_revision: string | null;
  remote_url: string | null;
  dirty: boolean;
  matches_lock: boolean;
};

export type Position = {
  symbol?: string;
  broker_ticker?: string;
  name?: string;
  currency?: string;
  quantity?: number;
  current_value?: number;
  unrealised_profit_loss?: number;
  [key: string]: unknown;
};

export type Recommendation = {
  action?: string;
  candidate?: {
    symbol?: string;
    research_symbol?: string;
    broker_ticker?: string | null;
    composite_score?: number;
    source?: string;
  };
  scores?: {
    composite?: number;
  };
  risk_flags?: string[];
  warnings?: string[];
  [key: string]: unknown;
};

export type Signal = {
  symbol?: string;
  research_symbol?: string;
  source?: string;
  action?: string;
  composite_score?: number;
  broker_validation_status?: string | null;
  broker_ticker?: string | null;
  warnings?: string[];
  [key: string]: unknown;
};

export type TickerContext = {
  status: string;
  symbol: string;
  provider: string;
  profile: Array<Record<string, unknown>>;
  fundamentals: Array<Record<string, unknown>>;
  prices: {
    provider: string;
    rows: number;
    columns: string[];
    latest: Record<string, unknown> | null;
  };
  errors: Record<string, string>;
};

function normaliseBase(value?: string) {
  return value?.replace(/\/$/, "") || null;
}

function candidateBases() {
  const preferred =
    globalThis.location?.port === "5174"
      ? "http://127.0.0.1:8002"
      : "http://127.0.0.1:8000";
  return Array.from(
    new Set(
      [CONFIGURED_API_BASE, preferred, "http://127.0.0.1:8000", "http://127.0.0.1:8002"].filter(
        Boolean
      ) as string[]
    )
  );
}

async function resolveApiBase() {
  if (resolvedApiBase) {
    return resolvedApiBase;
  }
  if (!resolveApiBasePromise) {
    resolveApiBasePromise = discoverApiBase();
  }
  resolvedApiBase = await resolveApiBasePromise;
  return resolvedApiBase;
}

async function discoverApiBase() {
  const failures: string[] = [];
  for (const base of candidateBases()) {
    try {
      const response = await fetch(`${base}/openbb/status`);
      if (response.ok) {
        return base;
      }
      failures.push(`${base} ${response.status}`);
    } catch (error) {
      failures.push(`${base} ${error instanceof Error ? error.message : "unreachable"}`);
    }
  }
  throw new Error(`No ISA API with OpenBB routes found (${failures.join("; ")})`);
}

export async function getJson<T>(path: string): Promise<T> {
  const apiBase = await resolveApiBase();
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) {
    resolvedApiBase = null;
    resolveApiBasePromise = null;
    throw new Error(`${response.status} ${response.statusText} from ${apiBase}`);
  }
  return (await response.json()) as T;
}

export async function postJson<T>(path: string): Promise<T> {
  const apiBase = await resolveApiBase();
  const response = await fetch(`${apiBase}${path}`, { method: "POST" });
  if (!response.ok) {
    resolvedApiBase = null;
    resolveApiBasePromise = null;
    throw new Error(`${response.status} ${response.statusText} from ${apiBase}`);
  }
  return (await response.json()) as T;
}

export const endpoints = {
  health: () => getJson<Health>("/health"),
  positions: () => getJson<Position[]>("/positions"),
  recommendations: () => getJson<{ recommendations: Recommendation[]; warnings: string[] }>(
    "/recommendations?include_defaults=true"
  ),
  signals: () => getJson<{ rows: Signal[]; warnings: string[]; source?: string }>(
    "/recommendations/screener?top_n=50"
  ),
  openbb: () => getJson<OpenBBStatus>("/openbb/status"),
  tickerContext: (symbol: string) =>
    getJson<TickerContext>(`/openbb/ticker/${encodeURIComponent(symbol)}/context`),
  pause: () => postJson<Record<string, string>>("/control/pause"),
  resume: () => postJson<Record<string, string>>("/control/resume"),
  paper: () => postJson<Record<string, string>>("/modes/paper"),
  disarm: () => postJson<Record<string, string>>("/live/disarm")
};
