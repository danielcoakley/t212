const state = {
  health: null,
  brokerAccount: null,
  brokerPositions: [],
  portfolioSummary: null,
  settings: null,
  openbb: null,
  latestRun: null,
  top10: [],
  reports: [],
  watchlist: [],
  healthReport: null,
  rebalance: [],
  risks: [],
  screenerSettings: null,
  screenerResult: null,
  screenerFilters: [],
  screenerPresetName: "",
  customPresetName: "",
  screenerFilterTab: "Fundamental",
  screenerOrderBy: "PEG",
  screenerOrderDirection: "asc",
  screenerSignal: "none",
  screenerTickers: "",
  selectedColumns: [
    "Company",
    "Industry",
    "Market Cap",
    "P/E",
    "Forward P/E",
    "PEG",
    "P/S",
    "P/B",
    "P/C",
    "P/FCF",
    "EPS this Y",
    "EPS next Y",
    "EPS past 5Y",
    "EPS next 5Y",
    "Sales past 5Y",
    "Price",
    "Change",
    "Volume",
  ],
  screenerSortColumn: "PEG",
  screenerSortDirection: "asc",
  selectedDeepTickers: new Set(),
  valuationRun: null,
  maximumDepth: false,
  sourceHeavy: false,
  busy: new Set(),
};

const endpoints = {
  health: "/health",
  settings: "/settings",
  brokerAccount: "/broker/account",
  brokerPositions: "/broker/positions",
  portfolioSummary: "/portfolio/summary",
  openbb: "/health/openbb",
  latestRun: "/orchestrator/latest",
  top10: "/candidates/top10",
  reports: "/research/reports/latest",
  watchlist: "/thesis/watchlist",
  healthReport: "/health-check/latest",
  deepValuation: "/portfolio/deep-valuation",
  rebalance: "/rebalance/latest",
  risks: "/workspace/risk-warnings",
  screenerSettings: "/discovery/finviz/settings",
  screenerRun: "/discovery/finviz/screener",
  screenerPresetSave: "/discovery/finviz/presets",
};

function $(id) {
  return document.getElementById(id);
}

async function fetchJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 180)}`);
  }
  return response.json();
}

async function loadAll() {
  await Promise.allSettled([
    load("health", endpoints.health),
    load("settings", endpoints.settings),
    load("brokerAccount", endpoints.brokerAccount),
    load("brokerPositions", endpoints.brokerPositions, []),
    load("portfolioSummary", endpoints.portfolioSummary),
    load("openbb", endpoints.openbb),
    load("latestRun", endpoints.latestRun),
    load("top10", endpoints.top10, []),
    load("reports", endpoints.reports, []),
    load("watchlist", endpoints.watchlist, []),
    load("healthReport", endpoints.healthReport),
    load("rebalance", endpoints.rebalance, []),
    load("risks", endpoints.risks, []),
    load("screenerSettings", endpoints.screenerSettings),
  ]);
  ensureScreenerDefaults();
  render();
}

async function load(key, path, fallback = null) {
  try {
    state[key] = (await fetchJson(path)) ?? fallback;
  } catch (error) {
    console.warn(`Failed to load ${key}`, error);
    state[key] = fallback;
  }
}

function render() {
  renderStatusStrip();
  renderSidebarSummary();
  renderStages();
  renderHealthPanel();
  renderTop10();
  renderWatchlist();
  renderRisks();
  renderSystemStatus();
  renderPortfolio();
  renderPortfolioTab();
  renderRebalance();
  renderScreener();
  renderNotes();
  $("last-updated").textContent = `Last updated ${new Date().toLocaleTimeString("en-GB")}`;
}

function renderStatusStrip() {
  const account = state.brokerAccount || {};
  const health = state.health || {};
  const subsystems = health.subsystems || {};
  const brokerOk = ["ok", "demo", "live"].includes(String(account.status || "").toLowerCase());
  const brokerLabel = account.status
    ? `Broker (${String(account.mode || "demo").toUpperCase()})`
    : "Broker";
  $("broker-status").textContent = brokerLabel;
  $("broker-detail").textContent = account.status || subsystems.broker || "not checked";
  setDot("broker-dot", brokerOk || String(subsystems.broker || "").includes("configured"));

  const openbbOk = Boolean(state.openbb && state.openbb.available);
  $("openbb-detail").textContent = state.openbb
    ? openbbOk
      ? "Healthy"
      : state.openbb.status || "Unavailable"
    : "Not checked";
  setDot("openbb-dot", openbbOk);

  const aiModels = state.settings?.ai_models || {};
  const healthModel = aiModels.portfolio_health_check?.model || "gpt-5.5";
  const valuationModel = aiModels.selected_stock_valuation?.model || "gpt-5.5";
  $("openai-detail").textContent = `Health ${healthModel} · Valuation ${valuationModel}`;
  setDot("openai-dot", Boolean(state.settings));
  $("mode-chip").textContent = health.mode ? `${health.mode} only` : "Preview only";
}

function renderSidebarSummary() {
  const summary = state.portfolioSummary || {};
  const account = state.brokerAccount || {};
  const total = summary.total_value ?? account.total_value;
  const cash = summary.available_to_trade ?? account.cash;
  const positions = summary.top_positions || state.brokerPositions || [];
  $("side-total-value").textContent = money(total, summary.account_currency || account.currency);
  $("side-cash").textContent = money(cash, summary.account_currency || account.currency);
  $("side-holdings").textContent = String(positions.length || 0);
  const cashFraction = pctValue(summary.cash_fraction);
  $("allowance-label").textContent = cashFraction === "n/a" ? "Preview" : `Cash ${cashFraction}`;
  $("allowance-bar").style.width = `${Math.min(100, Math.max(5, (summary.cash_fraction || 0.25) * 100))}%`;
}

function renderStages() {
  const run = state.latestRun;
  const top10Count = state.top10.length;
  const reportCount = state.reports.length;
  const watchCount = state.watchlist.length;
  const healthReport = state.healthReport?.report;
  const proposalCount = state.rebalance.length;
  const holdings = state.portfolioSummary?.top_positions || state.brokerPositions || [];

  $("stage-discovery-status").textContent = run
    ? `${run.candidate_count || 0} candidates in latest run`
    : "Ready for curated screeners";
  $("stage-enrichment-status").textContent = run ? "OpenBB attempted in latest run" : "Awaiting candidates";
  $("stage-scores-status").textContent = top10Count ? `${top10Count} ranked candidates` : "Top 10 not scored";
  $("stage-research-status").textContent = reportCount ? `${reportCount} reports stored` : "No reports loaded";
  $("stage-thesis-status").textContent = watchCount ? `${watchCount} watchlist theses` : "Watchlist pending";
  $("stage-health-status").textContent = healthReport
    ? `${healthReport.holding_count} holdings checked`
    : "No report yet";
  $("stage-portfolio-status").textContent = holdings.length
    ? `${holdings.length} broker holdings loaded`
    : "No holdings loaded";
  $("stage-rebalance-status").textContent = proposalCount
    ? `${proposalCount} proposal rows`
    : "No proposals";
  $("stage-orders-status").textContent = "Preview-only endpoint available";
}

function renderHealthPanel() {
  const detail = state.healthReport;
  const report = detail?.report;
  const assessments = report?.assessments || [];
  const avg = assessments.length
    ? Math.round(assessments.reduce((sum, row) => sum + (row.confidence_score || 0), 0) / assessments.length)
    : null;
  $("health-score").textContent = avg == null ? "--" : String(avg);
  $("health-score-ring").style.background = `radial-gradient(circle at center, #fff 57%, transparent 58%), conic-gradient(var(--amber) 0deg, var(--green) ${(avg || 0) * 3.6}deg, #e5eaf1 ${(avg || 0) * 3.6}deg)`;
  $("health-subtitle").textContent = report
    ? `${report.status} by ${report.model} · ${dateShort(report.generated_at_utc)}`
    : "Run a report to update targets and actions.";

  const actionCounts = countBy(assessments.map((row) => row.recommended_action || "REVIEW"));
  $("health-factor-list").innerHTML = ["BUY_MORE", "HOLD", "TRIM", "SELL", "REVIEW"]
    .map(
      (label) => `<div class="factor-row"><span>${label.replace("_", " ")}</span><strong>${actionCounts[label] || 0}</strong></div>`,
    )
    .join("");

  const updates = new Map((detail?.updates || []).map((row) => [String(row.symbol).toUpperCase(), row]));
  const body = $("health-targets-body");
  if (!assessments.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty">No holdings health report yet.</div></td></tr>`;
    return;
  }
  body.innerHTML = assessments
    .map((row) => {
      const update = updates.get(String(row.symbol).toUpperCase());
      const targets = update?.accepted_price_targets || row.price_targets || {};
      const action = update?.carried_forward_action || row.recommended_action || "REVIEW";
      return `<tr data-health-symbol="${escapeHtml(row.symbol)}">
        <td><strong>${escapeHtml(row.symbol)}</strong></td>
        <td><span class="status-pill ${actionClass(action)}">${escapeHtml(action.replace("_", " "))}</span></td>
        <td><input class="mini-input" data-target="bear" value="${inputValue(targets.bear)}" /></td>
        <td><input class="mini-input" data-target="base" value="${inputValue(targets.base)}" /></td>
        <td><input class="mini-input" data-target="bull" value="${inputValue(targets.bull)}" /></td>
        <td><button class="link-button" data-action="accept-health" data-symbol="${escapeHtml(row.symbol)}">Accept</button></td>
      </tr>`;
    })
    .join("");
}

function renderTop10() {
  const body = $("top10-body");
  if (!state.top10.length) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty">No top 10 score snapshot yet.</div></td></tr>`;
    return;
  }
  body.innerHTML = state.top10
    .slice(0, 10)
    .map(
      (row, index) => `<tr>
        <td>${index + 1}</td>
        <td><strong>${escapeHtml(row.symbol)}</strong></td>
        <td class="number">${num(row.total_score, 1)}</td>
        <td class="number">${num(row.data_quality_score, 0)}</td>
        <td>${escapeHtml(shorten(row.explanation || "No explanation", 76))}</td>
      </tr>`,
    )
    .join("");
}

function renderWatchlist() {
  const body = $("watchlist-body");
  if (!state.watchlist.length && !state.reports.length) {
    body.innerHTML = `<tr><td colspan="4"><div class="empty">No watchlist theses or reports yet.</div></td></tr>`;
    return;
  }
  const rows = state.watchlist.length
    ? state.watchlist
    : state.reports.map((report) => ({
        symbol: report.symbol,
        status: "REPORT_READY",
        decision: report.decision,
        conviction_score: report.conviction_score,
      }));
  body.innerHTML = rows
    .slice(0, 10)
    .map(
      (row) => `<tr>
        <td><strong>${escapeHtml(row.symbol)}</strong></td>
        <td><span class="status-pill">${escapeHtml(row.status || "REPORT")}</span></td>
        <td>${escapeHtml(row.decision || "review")}</td>
        <td class="number">${num(row.conviction_score, 0)}</td>
      </tr>`,
    )
    .join("");
}

function renderRisks() {
  const risks = buildRiskRows();
  $("risk-count").textContent = String(risks.length);
  $("risk-list").innerHTML = risks
    .map(
      (risk) => `<article class="risk-card ${risk.severity === "info" ? "info" : ""}">
        <span class="risk-icon">${risk.severity === "info" ? "i" : "!"}</span>
        <div><strong>${escapeHtml(risk.title)}</strong><p>${escapeHtml(risk.message)}</p></div>
      </article>`,
    )
    .join("");
}

function renderSystemStatus() {
  const health = state.health || {};
  const subsystems = health.subsystems || {};
  const rows = [
    ["API", health.status || "unknown"],
    ["Broker", state.brokerAccount?.status || subsystems.broker || "not checked"],
    ["OpenBB", state.openbb?.status || (state.openbb?.available ? "ok" : "not checked")],
    ["Market data", state.portfolioSummary?.status || "not loaded"],
    ["Live trading", subsystems.live_trading || "not implemented"],
  ];
  $("system-status-list").innerHTML = rows
    .map(
      ([label, value]) => `<div class="status-line">
        <span><span class="dot ${statusOk(value) ? "ok" : "bad"}"></span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>`,
    )
    .join("");
}

function renderPortfolio() {
  const summary = state.portfolioSummary || {};
  const account = state.brokerAccount || {};
  $("portfolio-total").textContent = money(summary.total_value ?? account.total_value, summary.account_currency || account.currency);
  $("portfolio-invested").textContent = money(summary.invested_value, summary.account_currency || account.currency);
  $("portfolio-cash").textContent = money(summary.available_to_trade ?? account.cash, summary.account_currency || account.currency);

  const positions = summary.top_positions || [];
  $("holdings-bars").innerHTML = positions.length
    ? positions
        .slice(0, 8)
        .map(
          (row) => `<div class="bar-row">
            <strong>${escapeHtml(row.symbol)}</strong>
            <div class="bar"><span style="width:${Math.min(100, (row.weight || 0) * 100)}%"></span></div>
            <span class="number">${pctValue(row.weight)}</span>
          </div>`,
        )
        .join("")
    : `<div class="empty">No broker holdings loaded. Check Trading 212 read-only configuration.</div>`;

  const concentration = summary.concentration || {};
  $("portfolio-metrics").innerHTML = [
    ["Position count", concentration.position_count ?? state.brokerPositions.length ?? 0],
    ["Largest position", pctValue(concentration.max_position_weight)],
    ["Top five weight", pctValue(concentration.top_five_weight)],
    ["Cash weight", pctValue(summary.cash_fraction)],
    ["Unrealised P/L", money(summary.unrealised_profit_loss_total, summary.account_currency || account.currency)],
  ]
    .map(
      ([label, value]) => `<div class="metric-line"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`,
    )
    .join("");
}

function renderPortfolioTab() {
  const summary = state.portfolioSummary || {};
  const account = state.brokerAccount || {};
  const currency = summary.account_currency || account.currency || "GBP";
  const concentration = summary.concentration || {};
  $("portfolio-detail-total").textContent = money(summary.total_value ?? account.total_value, currency);
  $("portfolio-detail-invested").textContent = money(summary.invested_value, currency);
  $("portfolio-detail-cash").textContent = money(summary.available_to_trade ?? account.cash, currency);
  $("portfolio-detail-largest").textContent = pctValue(concentration.max_position_weight);
  $("portfolio-detail-metrics").innerHTML = [
    ["Position count", concentration.position_count ?? portfolioRows().length],
    ["Largest position", pctValue(concentration.max_position_weight)],
    ["Top five weight", pctValue(concentration.top_five_weight)],
    ["Herfindahl index", num(concentration.herfindahl_index, 3)],
    ["Cash weight", pctValue(summary.cash_fraction)],
    ["Unrealised P/L", money(summary.unrealised_profit_loss_total, currency)],
  ]
    .map(
      ([label, value]) => `<div class="metric-line"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`,
    )
    .join("");

  const exposure = summary.currency_exposure || [];
  $("currency-exposure-bars").innerHTML = exposure.length
    ? exposure
        .map(
          (row) => `<div class="bar-row">
            <strong>${escapeHtml(row.currency)}</strong>
            <div class="bar"><span style="width:${Math.min(100, (row.weight || 0) * 100)}%"></span></div>
            <span class="number">${pctValue(row.weight)}</span>
          </div>`,
        )
        .join("")
    : `<div class="empty">No currency exposure data is available.</div>`;

  renderPortfolioHealthCommentary();
  if ($("maximum-depth-toggle")) $("maximum-depth-toggle").checked = state.maximumDepth;
  if ($("source-heavy-toggle")) $("source-heavy-toggle").checked = state.sourceHeavy;
  renderPortfolioHoldingsSelection();
  renderDeepValuationResults();
}

function renderPortfolioHealthCommentary() {
  const report = state.healthReport?.report;
  const aiModels = state.settings?.ai_models || {};
  const healthConfig = aiModels.portfolio_health_check || {};
  $("portfolio-health-model").textContent = `${healthConfig.model || "gpt-5.5"} ${healthConfig.reasoning_effort || "medium"}`;
  const score = report?.portfolio_health_score ?? null;
  $("portfolio-health-score").textContent = score == null ? "--" : String(score);
  $("portfolio-health-score-ring").style.background = `radial-gradient(circle at center, #fff 57%, transparent 58%), conic-gradient(var(--amber) 0deg, var(--green) ${(score || 0) * 3.6}deg, #e5eaf1 ${(score || 0) * 3.6}deg)`;
  $("portfolio-health-summary").textContent = report?.summary || "Run a health check to generate commentary.";
  const risks = report?.risk_scores || {};
  $("portfolio-risk-scores").innerHTML = [
    ["Concentration", risks.concentration],
    ["Valuation", risks.valuation],
    ["Balance sheet", risks.balance_sheet],
    ["Earnings quality", risks.earnings_quality],
    ["Dividend", risks.dividend],
    ["Macro", risks.macro],
  ]
    .map(
      ([label, value]) => `<div class="factor-row"><span>${escapeHtml(label)}</span><strong>${value == null ? "n/a" : escapeHtml(String(value))}</strong></div>`,
    )
    .join("");
  const findings = report?.key_findings?.length
    ? report.key_findings
    : report?.portfolio_actions || [];
  $("portfolio-key-findings").innerHTML = findings.length
    ? findings.map((item) => `<p>${escapeHtml(item)}</p>`).join("")
    : `<div class="empty">No portfolio health findings have been generated yet.</div>`;
}

function renderPortfolioHoldingsSelection() {
  const rows = portfolioRows();
  $("deep-valuation-selection-count").textContent = `${state.selectedDeepTickers.size} selected`;
  const body = $("portfolio-holdings-body");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6"><div class="empty">No holdings are available for selection.</div></td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => {
      const symbol = row.symbol || row.ticker || "unknown";
      const checked = state.selectedDeepTickers.has(symbol.toUpperCase()) ? " checked" : "";
      return `<tr>
        <td><input type="checkbox" data-select-valuation="${escapeHtml(symbol)}"${checked} /></td>
        <td><strong>${escapeHtml(symbol)}</strong></td>
        <td>${escapeHtml(row.name || row.company_name || "")}</td>
        <td class="number">${pctValue(row.weight ?? row.current_weight)}</td>
        <td class="number">${money(row.current_value ?? row.market_value, row.currency || state.portfolioSummary?.account_currency || "GBP")}</td>
        <td>${escapeHtml(row.currency || "")}</td>
      </tr>`;
    })
    .join("");
}

function renderDeepValuationResults() {
  const aiModels = state.settings?.ai_models || {};
  const config = state.maximumDepth
    ? aiModels.selected_stock_valuation_max
    : aiModels.selected_stock_valuation;
  $("deep-valuation-model").textContent = `${config?.model || "gpt-5.5"} ${config?.reasoning_effort || (state.maximumDepth ? "xhigh" : "high")}`;
  const node = $("deep-valuation-results");
  const results = state.valuationRun?.results || [];
  if (!results.length) {
    node.innerHTML = `<div class="empty">Select holdings and run Deep Valuation to generate stock-level analysis.</div>`;
    return;
  }
  node.innerHTML = results
    .map(
      (row) => `<article class="valuation-result-card">
        <div class="valuation-result-head">
          <div>
            <h4>${escapeHtml(row.ticker)} ${row.company_name ? `· ${escapeHtml(row.company_name)}` : ""}</h4>
            <p>${escapeHtml(row.summary)}</p>
          </div>
          <span class="status-pill ${actionClass(row.rating)}">${escapeHtml(row.rating)}</span>
        </div>
        <div class="metric-grid four">
          <div class="metric-card"><span>Confidence</span><strong>${escapeHtml(row.confidence)}</strong></div>
          <div class="metric-card"><span>Business quality</span><strong>${num(row.business_quality?.score, 0)}</strong></div>
          <div class="metric-card"><span>Valuation score</span><strong>${num(row.valuation?.score, 0)}</strong></div>
          <div class="metric-card"><span>Fair value</span><strong>${escapeHtml(row.valuation?.fair_value_range || "n/a")}</strong></div>
        </div>
        <div class="valuation-columns">
          <div><h5>Portfolio fit</h5><p>${escapeHtml(row.portfolio_fit || "Not supplied.")}</p></div>
          <div><h5>Risks</h5>${listHtml(row.risks)}</div>
          <div><h5>Thesis-breakers</h5>${listHtml(row.thesis_breakers)}</div>
        </div>
        ${row.missing_data?.length ? `<div class="manual-review">${escapeHtml(row.missing_data.join(" "))}</div>` : ""}
      </article>`,
    )
    .join("");
}

function renderRebalance() {
  const body = $("rebalance-body");
  if (!state.rebalance.length) {
    body.innerHTML = `<tr><td colspan="5"><div class="empty">No rebalance proposals yet.</div></td></tr>`;
    return;
  }
  body.innerHTML = state.rebalance
    .slice(0, 10)
    .map(
      (row) => `<tr>
        <td><span class="status-pill ${actionClass(row.proposal_type)}">${escapeHtml(row.proposal_type)}</span></td>
        <td><strong>${escapeHtml(row.symbol)}</strong></td>
        <td class="number">${pctValue(row.target_weight)}</td>
        <td class="number">${money(row.estimated_trade_value, "GBP")}</td>
        <td class="number">${num(row.confidence_score, 0)}</td>
      </tr>`,
    )
    .join("");
}

function renderNotes() {
  const notes = [];
  if (state.top10.length) notes.push(`Top candidates ready: ${state.top10.slice(0, 3).map((row) => row.symbol).join(", ")}.`);
  if (state.healthReport?.report) notes.push(`Health report stored: ${state.healthReport.report.id}.`);
  if (state.rebalance.length) notes.push(`${state.rebalance.length} rebalance proposal rows require manual approval.`);
  if (!notes.length) notes.push("Run the workflow or refresh data to inspect current blockers and next actions.");
  $("workflow-notes").textContent = notes.join(" ");
}

function ensureScreenerDefaults() {
  if (!state.screenerSettings || state.screenerFilters.length) return;
  const firstPreset = state.screenerSettings.presets?.[0];
  if (!firstPreset) return;
  state.screenerPresetName = firstPreset.name;
  state.screenerFilters = [...firstPreset.filters];
  state.screenerOrderBy = firstPreset.order_by || state.screenerOrderBy || "PEG";
  state.screenerOrderDirection = firstPreset.order_direction || state.screenerOrderDirection;
  state.screenerSignal = firstPreset.signal || "none";
  state.screenerTickers = firstPreset.tickers || "";
  state.screenerSortColumn = state.screenerOrderBy;
  state.screenerSortDirection = state.screenerOrderDirection;
}

function renderScreener() {
  renderScreenerPresetSelect();
  renderScreenerToolbar();
  renderFilterTabs();
  renderFilterControls();
  renderColumnOptions();
  renderScreenerUrl();
  renderScreenerResults();
}

function renderScreenerPresetSelect() {
  const select = $("screener-preset-select");
  if (!select) return;
  const presets = state.screenerSettings?.presets || [];
  select.innerHTML = presets
    .map(
      (preset) =>
        `<option value="${escapeHtml(preset.name)}"${preset.name === state.screenerPresetName ? " selected" : ""}>${escapeHtml(preset.name)}</option>`,
    )
    .join("");
}

function renderScreenerToolbar() {
  if ($("active-filter-count")) {
    $("active-filter-count").textContent = `${state.screenerFilters.length} active`;
  }
  if ($("custom-preset-name-input")) {
    $("custom-preset-name-input").value = state.customPresetName;
  }
  const orderSelect = $("screener-order-select");
  if (orderSelect) {
    const options = orderColumns();
    orderSelect.innerHTML = options
      .map(
        (column) =>
          `<option value="${escapeHtml(column)}"${column === state.screenerOrderBy ? " selected" : ""}>${escapeHtml(column)}</option>`,
      )
      .join("");
  }
  if ($("screener-order-direction")) {
    $("screener-order-direction").value = state.screenerOrderDirection;
  }
  if ($("screener-signal-select")) {
    $("screener-signal-select").value = state.screenerSignal;
  }
  if ($("screener-tickers-input")) {
    $("screener-tickers-input").value = state.screenerTickers;
  }
  renderActiveFilterList();
}

function renderFilterTabs() {
  const node = $("finviz-filter-tabs");
  if (!node) return;
  const tabs = ["Descriptive", "Fundamental", "Technical"];
  node.innerHTML = tabs
    .map(
      (tab) => `<button class="finviz-tab ${tab === state.screenerFilterTab ? "active" : ""}" data-action="set-filter-tab" data-tab="${escapeHtml(tab)}">
        ${escapeHtml(tab)}
      </button>`,
    )
    .join("");
}

function renderFilterControls() {
  const node = $("finviz-filter-controls");
  if (!node) return;
  const controls = (state.screenerSettings?.filter_controls || []).filter(
    (control) => control.category === state.screenerFilterTab,
  );
  if (!controls.length) {
    node.innerHTML = `<div class="finviz-empty">Finviz filter controls could not be loaded.</div>`;
    return;
  }
  node.innerHTML = controls
    .map(
      (control) => `<label class="finviz-filter-control">
        <span>${escapeHtml(control.label)}</span>
        <select class="finviz-select" data-filter-control="${escapeHtml(control.key)}">
          ${control.choices
            .map((choice) => {
              const code = choice.code || "";
              return `<option value="${escapeHtml(code)}"${selectedFilterForControl(control) === code ? " selected" : ""}>${escapeHtml(choice.label)}</option>`;
            })
            .join("")}
        </select>
      </label>`,
    )
    .join("");
}

function renderActiveFilterList() {
  const node = $("active-filter-list");
  if (!node) return;
  const labels = filterLabels();
  if (!state.screenerFilters.length) {
    node.innerHTML = `<span class="muted">No active filters.</span>`;
    return;
  }
  node.innerHTML = state.screenerFilters
    .map(
      (code) => `<button class="filter-chip" data-action="remove-screener-filter" data-filter="${escapeHtml(code)}">
        <span>${escapeHtml(labels.get(code) || code)}</span>
      </button>`,
    )
    .join("");
}

function renderColumnOptions() {
  const node = $("column-option-list");
  if (!node) return;
  const groups = (state.screenerSettings?.column_options || []).reduce((acc, option) => {
    acc[option.category] = acc[option.category] || [];
    acc[option.category].push(option);
    return acc;
  }, {});
  const selected = new Set(state.selectedColumns);
  node.innerHTML = `<div class="custom-column-row">
      <label class="field" for="custom-column-input">
        <span>Custom column</span>
        <input id="custom-column-input" class="finviz-input" placeholder="e.g. Insider Ownership" />
      </label>
      <button class="button secondary" data-action="add-custom-column">Add</button>
    </div>${Object.entries(groups)
    .map(
      ([category, columns]) => `<section class="column-group">
        <h4>${escapeHtml(category)}</h4>
        ${columns
          .map(
            (column) => `<label class="column-check">
              <input type="checkbox" data-column-key="${escapeHtml(column.key)}"${selected.has(column.key) ? " checked" : ""} />
              <span>${escapeHtml(column.label)}</span>
            </label>`,
          )
          .join("")}
      </section>`,
    )
    .join("")}`;
}

function renderScreenerUrl() {
  const link = $("finviz-url-link");
  if (!link) return;
  const url = buildFinvizUrl(state.screenerFilters);
  link.href = url;
  link.title = url;
}

function renderScreenerResults() {
  const head = $("screener-results-head");
  const body = $("screener-results-body");
  if (!head || !body) return;
  const result = state.screenerResult;
  const warnings = result?.warnings || [];
  $("screener-warning-label").textContent = warnings.length
    ? warnings.join(" ")
    : "Cached, operator-triggered, preview-only";
  $("screener-results-summary").textContent = result
    ? `${result.rows.length} rows from ${result.name}. Latest candidates updated for downstream scoring.`
    : "No configurable screener run yet.";
  if (!result?.rows?.length) {
    head.innerHTML = "";
    body.innerHTML = `<tr><td><div class="finviz-empty">Choose a preset or filters, then run the screener.</div></td></tr>`;
    return;
  }
  const columns = screenerColumns();
  const rows = sortedScreenerRows(result.rows, columns);
  head.innerHTML = `<tr>
    <th class="number">No.</th>
    ${sortableHeader("Ticker")}
    ${columns.map((column) => sortableHeader(column)).join("")}
    <th class="profile-col">Profile</th>
  </tr>`;
  body.innerHTML = rows
    .map(
      (row, index) => `<tr>
        <td class="number">${index + 1}</td>
        <td class="screener-col-ticker"><strong>${escapeHtml(row.symbol)}</strong></td>
        ${columns.map((column) => `<td class="${screenerCellClass(row, column)}">${formatScreenerCell(row, column)}</td>`).join("")}
        <td class="profile-col">
          <a class="profile-link" href="${escapeHtml(row.profile_url)}" target="_blank" rel="noreferrer" title="Open ${escapeHtml(row.symbol)} in Finviz" aria-label="Open ${escapeHtml(row.symbol)} in Finviz">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <path d="M14 4h6v6" />
              <path d="M10 14 20 4" />
              <path d="M20 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4" />
            </svg>
          </a>
        </td>
      </tr>`,
    )
    .join("");
}

function screenerColumns() {
  return state.selectedColumns.filter((column) => column !== "Ticker" && column !== "No.");
}

function formatScreenerCell(row, column) {
  const value = row.fields?.[column] ?? row.valuation?.[column] ?? "";
  if (!value) return `<span class="muted">-</span>`;
  const parsed = parseNumericValue(value);
  const tone = metricTone(column, parsed, row);
  const className = [
    "metric-value",
    tone ? `metric-${tone}` : "",
    Number.isFinite(parsed) && parsed < 0 ? "negative" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return `<span class="${className}" title="${escapeHtml(metricTitle(column, tone))}">${escapeHtml(value)}</span>`;
}

function sortableHeader(column) {
  const active = state.screenerSortColumn === column;
  const direction = active ? (state.screenerSortDirection === "asc" ? " ^" : " v") : "";
  return `<th class="${columnClass(column)}"><button class="sort-header ${active ? "active" : ""}" data-action="sort-screener" data-column="${escapeHtml(column)}">${escapeHtml(column)}${direction}</button></th>`;
}

function sortedScreenerRows(rows) {
  const column = state.screenerSortColumn;
  const direction = state.screenerSortDirection === "desc" ? -1 : 1;
  return [...rows].sort((left, right) => compareScreenerValues(left, right, column) * direction);
}

function compareScreenerValues(left, right, column) {
  const leftValue = column === "Ticker" ? left.symbol : left.fields?.[column] ?? left.valuation?.[column] ?? "";
  const rightValue = column === "Ticker" ? right.symbol : right.fields?.[column] ?? right.valuation?.[column] ?? "";
  const leftNumber = parseNumericValue(leftValue);
  const rightNumber = parseNumericValue(rightValue);
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) return leftNumber - rightNumber;
  return String(leftValue).localeCompare(String(rightValue), "en-GB", { numeric: true });
}

function screenerCellClass(row, column) {
  const value = row.fields?.[column] ?? row.valuation?.[column] ?? "";
  const classes = [columnClass(column)];
  if (Number.isFinite(parseNumericValue(value))) classes.push("number");
  return classes.join(" ");
}

function parseNumericValue(value) {
  if (value == null || value === "" || value === "-") return Number.NaN;
  const text = String(value).trim().replaceAll(",", "");
  const multiplier = text.endsWith("T") ? 1_000_000_000_000 : text.endsWith("B") ? 1_000_000_000 : text.endsWith("M") ? 1_000_000 : text.endsWith("K") ? 1_000 : 1;
  const parsed = Number.parseFloat(text.replace(/[%TBMK$£]/g, ""));
  return Number.isFinite(parsed) ? parsed * multiplier : Number.NaN;
}

function columnClass(column) {
  const slug = String(column || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  const textColumns = new Set(["Company", "Industry", "Sector", "Country"]);
  return [textColumns.has(column) ? "screener-text-col" : "screener-metric-col", `screener-col-${slug}`]
    .filter(Boolean)
    .join(" ");
}

function metricTone(column, value, row) {
  if (!Number.isFinite(value)) return "";
  const normalized = column.toLowerCase();
  const profile = sectorProfileFor(row);
  if (["market cap", "price", "volume"].includes(normalized)) return "";
  if (normalized === "change") return value > 0 ? "good" : value < 0 ? "bad" : "neutral";
  if (normalized.includes("perf")) return thresholdTone(value, 10, 0, true);
  if (normalized.includes("margin")) return thresholdTone(value, profile.marginGood, profile.marginOk, true);
  if (["roe", "roa", "roi"].includes(normalized)) return thresholdTone(value, 15, 8, true);
  if (normalized.includes("eps") || normalized.includes("sales")) return thresholdTone(value, 15, 5, true);
  if (normalized === "peg") return thresholdTone(value, profile.pegGood, profile.pegOk, false);
  if (["p/e", "forward p/e"].includes(normalized)) return thresholdTone(value, profile.peGood, profile.peOk, false);
  if (normalized === "p/s") return thresholdTone(value, profile.psGood, profile.psOk, false);
  if (normalized === "p/b") return thresholdTone(value, profile.pbGood, profile.pbOk, false);
  if (normalized === "p/c") return thresholdTone(value, 12, 25, false);
  if (normalized === "p/fcf") return thresholdTone(value, profile.pfcfGood, profile.pfcfOk, false);
  if (normalized === "ev/ebitda") return thresholdTone(value, 12, 18, false);
  if (normalized === "debt/eq" || normalized === "lt debt/equity") return thresholdTone(value, 1, 2, false);
  return "";
}

function thresholdTone(value, goodThreshold, neutralThreshold, higherIsBetter) {
  if (higherIsBetter) {
    if (value >= goodThreshold) return "good";
    if (value >= neutralThreshold) return "neutral";
    return "bad";
  }
  if (value <= goodThreshold) return "good";
  if (value <= neutralThreshold) return "neutral";
  return "bad";
}

function sectorProfileFor(row) {
  const label = `${row.fields?.Sector || ""} ${row.fields?.Industry || ""}`.toLowerCase();
  if (/software|internet|semiconductor|technology|solar|biotech/.test(label)) {
    return {
      peGood: 30,
      peOk: 50,
      pegGood: 1.5,
      pegOk: 2.5,
      psGood: 8,
      psOk: 15,
      pbGood: 8,
      pbOk: 15,
      pfcfGood: 35,
      pfcfOk: 60,
      marginGood: 45,
      marginOk: 25,
    };
  }
  if (/bank|insurance|financial|asset management|capital markets/.test(label)) {
    return {
      peGood: 15,
      peOk: 25,
      pegGood: 1.2,
      pegOk: 2,
      psGood: 4,
      psOk: 8,
      pbGood: 1.5,
      pbOk: 2.5,
      pfcfGood: 20,
      pfcfOk: 35,
      marginGood: 25,
      marginOk: 12,
    };
  }
  if (/gold|mining|oil|gas|energy|materials|metal/.test(label)) {
    return {
      peGood: 15,
      peOk: 25,
      pegGood: 1.2,
      pegOk: 2,
      psGood: 3,
      psOk: 6,
      pbGood: 2,
      pbOk: 4,
      pfcfGood: 15,
      pfcfOk: 30,
      marginGood: 25,
      marginOk: 10,
    };
  }
  return {
    peGood: 20,
    peOk: 35,
    pegGood: 1.2,
    pegOk: 2,
    psGood: 4,
    psOk: 8,
    pbGood: 3,
    pbOk: 6,
    pfcfGood: 20,
    pfcfOk: 35,
    marginGood: 40,
    marginOk: 20,
  };
}

function metricTitle(column, tone) {
  if (!tone) return `${column}: not scored`;
  return `${column}: ${tone} by broad sector-adjusted heuristic`;
}

function filterLabels() {
  return new Map(
    (state.screenerSettings?.filter_options || []).map((option) => [option.code, option.label]),
  );
}

function currentPreset() {
  return (state.screenerSettings?.presets || []).find(
    (preset) => preset.name === state.screenerPresetName,
  );
}

function applyScreenerPreset() {
  const select = $("screener-preset-select");
  state.screenerPresetName = select?.value || state.screenerPresetName;
  const preset = currentPreset();
  if (!preset) return;
  state.screenerFilters = [...preset.filters];
  state.screenerOrderBy = preset.order_by || "PEG";
  state.screenerOrderDirection = preset.order_direction || "asc";
  state.screenerSignal = preset.signal || "none";
  state.screenerTickers = preset.tickers || "";
  state.screenerSortColumn = state.screenerOrderBy;
  state.screenerSortDirection = state.screenerOrderDirection;
  renderScreener();
}

function filtersForCurrentControls() {
  const controlledCodes = new Set(
    (state.screenerSettings?.filter_controls || []).flatMap((control) =>
      control.choices.map((choice) => choice.code).filter(Boolean),
    ),
  );
  return {
    controlled: state.screenerFilters.filter((code) => controlledCodes.has(code)),
    custom: state.screenerFilters.filter((code) => !controlledCodes.has(code)),
  };
}

function selectedFilterForControl(control) {
  const codes = new Set(control.choices.map((choice) => choice.code).filter(Boolean));
  return state.screenerFilters.find((code) => codes.has(code)) || "";
}

function setFilterControl(controlKey, code) {
  const controls = state.screenerSettings?.filter_controls || [];
  const control = controls.find((item) => item.key === controlKey);
  if (!control) return;
  const otherCodes = new Set(control.choices.map((choice) => choice.code).filter(Boolean));
  state.screenerFilters = state.screenerFilters.filter((item) => !otherCodes.has(item));
  if (code) addScreenerFilter(code);
}

function addScreenerFilter(code) {
  const normalized = String(code || "").trim().toLowerCase();
  if (!normalized || state.screenerFilters.includes(normalized)) return;
  state.screenerFilters = [...state.screenerFilters, normalized];
}

function removeScreenerFilter(code) {
  state.screenerFilters = state.screenerFilters.filter((item) => item !== code);
}

async function runCustomScreener(useFixtures) {
  const preset = currentPreset();
  const result = await post(endpoints.screenerRun, {
    name: preset?.name || "Custom Finviz Screener",
    purpose: preset?.purpose || "Operator-configured Finviz discovery run.",
    filters: state.screenerFilters,
    order_by: state.screenerOrderBy,
    order_direction: state.screenerOrderDirection,
    signal: state.screenerSignal,
    tickers: state.screenerTickers,
    use_fixtures: Boolean(useFixtures),
    force_refresh: false,
  });
  state.screenerResult = result;
  state.screenerSortColumn = state.screenerOrderBy;
  state.screenerSortDirection = state.screenerOrderDirection;
  renderScreener();
  toast(`Finviz screener returned ${result.rows.length} rows.`);
}

async function saveCustomPreset() {
  const name = state.customPresetName.trim();
  if (!name) {
    toast("Add a preset name before saving.");
    return;
  }
  if (!state.screenerFilters.length) {
    toast("Choose at least one filter before saving.");
    return;
  }
  const preset = await post(endpoints.screenerPresetSave, {
    name,
    filters: state.screenerFilters,
    order_by: state.screenerOrderBy,
    order_direction: state.screenerOrderDirection,
    signal: state.screenerSignal,
    tickers: state.screenerTickers,
  });
  state.screenerSettings = await fetchJson(endpoints.screenerSettings);
  state.screenerPresetName = preset.name;
  state.customPresetName = "";
  renderScreenerPresetSelect();
  applyScreenerPreset();
  toast(`Saved preset ${preset.name}.`);
}

function buildFinvizUrl(filters) {
  const query = new URLSearchParams({
    v: "121",
    f: filters.join(","),
    ft: "2",
  });
  const sortCode = finvizSortCode(state.screenerOrderBy);
  if (sortCode) {
    query.set("o", state.screenerOrderDirection === "desc" ? `-${sortCode}` : sortCode);
  }
  if (state.screenerSignal !== "none") query.set("s", state.screenerSignal);
  if (state.screenerTickers.trim()) query.set("t", state.screenerTickers.trim().toUpperCase());
  return `https://finviz.com/screener.ashx?${query.toString()}`;
}

function finvizSortCode(column) {
  return {
    Ticker: "ticker",
    "Market Cap": "marketcap",
    "P/E": "pe",
    "Forward P/E": "forwardpe",
    PEG: "peg",
    "P/S": "ps",
    "P/B": "pb",
    "P/C": "pc",
    "P/FCF": "pfcf",
    "EV/EBITDA": "evebitda",
    Price: "price",
    Change: "change",
    Volume: "volume",
  }[column];
}

function orderColumns() {
  return [
    ...new Set([
      "Ticker",
      ...(state.screenerSettings?.principal_valuation_fields || []),
      ...state.selectedColumns,
    ]),
  ];
}

function showPage(page) {
  const nextPage = ["overview", "portfolio", "screener"].includes(page) ? page : "overview";
  document.querySelectorAll(".view-section").forEach((section) => {
    section.hidden = section.dataset.view !== nextPage;
    section.classList.toggle("active", section.dataset.view === nextPage);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === nextPage);
  });
}

async function runAction(action, element) {
  if (state.busy.has(action)) return;
  state.busy.add(action);
  setButtonsDisabled(true);
  try {
    let shouldReload = true;
    if (action === "run-discovery") {
      await post("/discovery/run", { use_fixtures: false, force_refresh: false });
      toast("Finviz discovery complete.");
    } else if (action === "run-enrichment") {
      await post("/enrichment/run", { use_fixtures: false });
      toast("OpenBB enrichment attempted.");
    } else if (action === "run-scores") {
      await post("/scores/run", { limit: 10 });
      toast("Candidate scores refreshed.");
    } else if (action === "run-research") {
      await post("/research/run-top10");
      toast("Top 10 research reports updated.");
    } else if (action === "run-health") {
      await post("/health-check/run", { detailed: false });
      toast("Holdings health report stored.");
    } else if (action === "run-health-detailed") {
      await post("/health-check/run", { detailed: true });
      toast("Detailed holdings health report stored.");
    } else if (action === "run-deep-valuation") {
      if (!state.selectedDeepTickers.size) {
        toast("Select at least one stock before running deep valuation.");
        shouldReload = false;
      } else {
        state.valuationRun = await post(endpoints.deepValuation, {
          symbols: [...state.selectedDeepTickers],
          maximum_depth: state.maximumDepth,
          source_heavy: state.sourceHeavy,
        });
        toast(`Deep valuation completed for ${state.valuationRun.selected_count} stock(s).`);
      }
    } else if (action === "portfolio-review") {
      await post("/portfolio/holdings/load-broker");
      state.rebalance = await post("/portfolio/review", { cash_gbp: state.portfolioSummary?.available_to_trade || 0 });
      toast("Portfolio review completed.");
    } else if (action === "rebalance-preview") {
      state.rebalance = await post("/rebalance/propose", { cash_gbp: state.portfolioSummary?.available_to_trade || 0 });
      toast("Rebalance proposal refreshed.");
    } else if (action === "load-broker-holdings") {
      await post("/portfolio/holdings/load-broker");
      toast("Broker holdings loaded into review context.");
    } else if (action === "run-orchestrator") {
      await post("/orchestrator/run");
      toast("Full offline pipeline completed.");
    } else if (action === "accept-health") {
      await acceptHealth(element);
      toast(`Health targets accepted for ${element.dataset.symbol}.`);
    } else if (action === "apply-screener-preset") {
      applyScreenerPreset();
      shouldReload = false;
      toast("Preset filters applied.");
    } else if (action === "reset-screener-filters") {
      state.screenerFilters = [];
      renderScreener();
      shouldReload = false;
      toast("Finviz filters cleared.");
    } else if (action === "add-custom-filter") {
      addScreenerFilter($("custom-filter-input").value);
      $("custom-filter-input").value = "";
      renderScreener();
      shouldReload = false;
      toast("Finviz filter added.");
    } else if (action === "remove-screener-filter") {
      removeScreenerFilter(element.dataset.filter);
      renderScreener();
      shouldReload = false;
      toast("Finviz filter removed.");
    } else if (action === "set-filter-tab") {
      state.screenerFilterTab = element.dataset.tab || "Fundamental";
      renderScreener();
      shouldReload = false;
    } else if (action === "sort-screener") {
      const column = element.dataset.column;
      if (state.screenerSortColumn === column) {
        state.screenerSortDirection = state.screenerSortDirection === "asc" ? "desc" : "asc";
      } else {
        state.screenerSortColumn = column;
        state.screenerSortDirection = "asc";
      }
      renderScreenerResults();
      shouldReload = false;
    } else if (action === "add-custom-column") {
      const column = $("custom-column-input").value.trim();
      if (column) {
        state.selectedColumns = [...new Set([...state.selectedColumns, column])];
        $("custom-column-input").value = "";
        renderColumnOptions();
        renderScreenerResults();
        toast("Column added.");
      }
      shouldReload = false;
    } else if (action === "save-custom-preset") {
      await saveCustomPreset();
      shouldReload = false;
    } else if (action === "run-custom-screener" || action === "run-custom-screener-fixtures") {
      await runCustomScreener(action === "run-custom-screener-fixtures");
    } else if (action === "load-watchlist" || action === "orders-preview") {
      toast("Review-only data refreshed.");
    }
    if (shouldReload) {
      await loadAll();
    }
  } catch (error) {
    console.error(error);
    toast(error.message || "Action failed.");
  } finally {
    state.busy.delete(action);
    setButtonsDisabled(false);
  }
}

async function acceptHealth(button) {
  const detail = state.healthReport;
  const reportId = detail?.report?.id;
  if (!reportId) throw new Error("Run a holdings health report first.");
  const symbol = button.dataset.symbol;
  const row = button.closest("tr");
  const targets = {};
  for (const input of row.querySelectorAll("input[data-target]")) {
    const value = Number.parseFloat(input.value);
    targets[input.dataset.target] = Number.isFinite(value) ? value : null;
  }
  await post(`/health-check/reports/${encodeURIComponent(reportId)}/holdings/${encodeURIComponent(symbol)}/accept`, {
    price_targets: targets,
    carried_forward_action: findAssessment(symbol)?.recommended_action || "REVIEW",
  });
}

function findAssessment(symbol) {
  return (state.healthReport?.report?.assessments || []).find(
    (row) => String(row.symbol).toUpperCase() === String(symbol).toUpperCase(),
  );
}

async function post(path, body = undefined) {
  return fetchJson(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function buildRiskRows() {
  const base = (state.risks || []).map((risk) => ({
    severity: risk.severity || "info",
    title: risk.severity === "info" ? "Guardrail" : "Risk warning",
    message: risk.message || String(risk),
  }));
  if (state.portfolioSummary?.concentration?.max_position_weight > 0.1) {
    base.unshift({
      severity: "warning",
      title: "Single Stock Risk",
      message: `Largest position is ${pctValue(state.portfolioSummary.concentration.max_position_weight)}.`,
    });
  }
  if (!state.healthReport?.report) {
    base.unshift({
      severity: "warning",
      title: "Health Report Missing",
      message: "Run holdings health before accepting updated targets.",
    });
  }
  return base.slice(0, 6);
}

function portfolioRows() {
  const summaryRows = state.portfolioSummary?.top_positions || [];
  if (summaryRows.length) return summaryRows;
  return (state.brokerPositions || []).map((row) => ({
    symbol: row.ticker || row.symbol,
    name: row.name,
    currency: row.currency,
    quantity: row.quantity,
    current_value: null,
    weight: null,
  }));
}

function listHtml(items) {
  if (!items || !items.length) return `<div class="empty">No rows supplied.</div>`;
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function setButtonsDisabled(disabled) {
  document.querySelectorAll("button").forEach((button) => {
    button.disabled = disabled;
  });
}

function setDot(id, ok) {
  const dot = $(id);
  dot.classList.toggle("ok", Boolean(ok));
  dot.classList.toggle("bad", !ok);
}

function statusOk(value) {
  const text = String(value || "").toLowerCase();
  return text.includes("ok") || text.includes("healthy") || text.includes("configured") || text.includes("not_implemented");
}

function actionClass(value) {
  const text = String(value || "").toUpperCase();
  if (text.includes("BUY") || text.includes("ADD") || text.includes("HOLD")) return "good";
  if (text.includes("SELL") || text.includes("TRIM") || text.includes("REVIEW") || text.includes("AVOID")) return "warn";
  return "";
}

function countBy(items) {
  return items.reduce((acc, item) => {
    acc[item] = (acc[item] || 0) + 1;
    return acc;
  }, {});
}

function money(value, currency = "GBP") {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: currency || "GBP",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function pctValue(value) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function num(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return "n/a";
  return Number(value).toFixed(digits);
}

function inputValue(value) {
  return value == null || Number.isNaN(Number(value)) ? "" : Number(value).toFixed(2);
}

function dateShort(value) {
  if (!value) return "n/a";
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function shorten(text, length) {
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 3800);
}

function tickClock() {
  const now = new Date();
  $("clock-time").textContent = now.toLocaleTimeString("en-GB", {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  $("clock-date").textContent = now.toLocaleDateString("en-GB", {
    timeZone: "Europe/London",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

document.addEventListener("click", (event) => {
  const actionElement = event.target.closest("[data-action]");
  if (actionElement) {
    event.preventDefault();
    runAction(actionElement.dataset.action, actionElement);
    return;
  }
  const nav = event.target.closest(".nav-item");
  if (nav) {
    showPage(nav.dataset.page);
  }
});

document.addEventListener("change", (event) => {
  const selection = event.target.closest("[data-select-valuation]");
  if (selection) {
    const symbol = selection.dataset.selectValuation;
    if (selection.checked) {
      state.selectedDeepTickers.add(symbol.toUpperCase());
    } else {
      state.selectedDeepTickers.delete(symbol.toUpperCase());
    }
    $("deep-valuation-selection-count").textContent = `${state.selectedDeepTickers.size} selected`;
    return;
  }
  const maxDepth = event.target.closest("#maximum-depth-toggle");
  if (maxDepth) {
    state.maximumDepth = Boolean(maxDepth.checked);
    renderDeepValuationResults();
    return;
  }
  const sourceHeavy = event.target.closest("#source-heavy-toggle");
  if (sourceHeavy) {
    state.sourceHeavy = Boolean(sourceHeavy.checked);
    return;
  }
  const presetSelect = event.target.closest("#screener-preset-select");
  if (presetSelect) {
    applyScreenerPreset();
    runCustomScreener(false).catch((error) => {
      console.error(error);
      toast(error.message || "Finviz preset run failed.");
    });
    return;
  }
  const orderSelect = event.target.closest("#screener-order-select");
  if (orderSelect) {
    state.screenerOrderBy = orderSelect.value;
    state.screenerSortColumn = orderSelect.value;
    renderScreenerUrl();
    renderScreenerResults();
    return;
  }
  const directionSelect = event.target.closest("#screener-order-direction");
  if (directionSelect) {
    state.screenerOrderDirection = directionSelect.value;
    state.screenerSortDirection = directionSelect.value;
    renderScreenerUrl();
    renderScreenerResults();
    return;
  }
  const signalSelect = event.target.closest("#screener-signal-select");
  if (signalSelect) {
    state.screenerSignal = signalSelect.value;
    renderScreenerUrl();
    return;
  }
  const filterControl = event.target.closest("[data-filter-control]");
  if (filterControl) {
    setFilterControl(filterControl.dataset.filterControl, filterControl.value);
    renderScreener();
    return;
  }
  const columnInput = event.target.closest("[data-column-key]");
  if (columnInput) {
    const column = columnInput.dataset.columnKey;
    if (columnInput.checked) {
      state.selectedColumns = [...new Set([...state.selectedColumns, column])];
    } else {
      state.selectedColumns = state.selectedColumns.filter((item) => item !== column);
    }
    renderColumnOptions();
    renderScreenerResults();
  }
});

document.addEventListener("input", (event) => {
  const tickerInput = event.target.closest("#screener-tickers-input");
  if (tickerInput) {
    state.screenerTickers = tickerInput.value;
    renderScreenerUrl();
    return;
  }
  const presetNameInput = event.target.closest("#custom-preset-name-input");
  if (presetNameInput) {
    state.customPresetName = presetNameInput.value;
  }
});

$("refresh-all-button").addEventListener("click", loadAll);
tickClock();
window.setInterval(tickClock, 1000);
showPage(window.location.hash.replace("#", "") || "overview");
loadAll();
