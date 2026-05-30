// Build stamp — bumped on every UI design pass. Visible at the bottom of the
// page AND in the console so we can confirm a fresh build is loaded when the
// user reports "I don't see changes" (usually a cache issue).
const MARKET_BOT_UI_BUILD = "20260530-sprint19 · nombre-en-workspace";
console.info(`%cMarket Bot UI build: ${MARKET_BOT_UI_BUILD}`, "color:#c6f25c;font-weight:600");
document.addEventListener("DOMContentLoaded", function () {
  const mark = document.getElementById("build-mark");
  if (mark) mark.textContent = `UI build · ${MARKET_BOT_UI_BUILD}`;
});

// API base resolution order:
// 1. ?apiBase=…       — debug / temporary override
// 2. localStorage      — user-set persistent override
// 3. window.MARKET_BOT_API_BASE  — injected at deploy time (Vercel writes
//    `config.js` with the production API origin). Empty string = unset.
// 4. window.location.origin     — same-origin (works for local FastAPI
//    serving the prototype at /app/)
// 5. window.MARKET_BOT_LOCAL_API_BASE — local backend target from `.env`
// 6. localhost fallback for `file://` and other edge cases.
const localApiBase =
  typeof window.MARKET_BOT_LOCAL_API_BASE === "string" && window.MARKET_BOT_LOCAL_API_BASE.trim()
    ? window.MARKET_BOT_LOCAL_API_BASE.trim().replace(/\/$/, "")
    : "http://127.0.0.1:8000";
const runtimeMode =
  typeof window.MARKET_BOT_RUNTIME_MODE === "string" && window.MARKET_BOT_RUNTIME_MODE.trim()
    ? window.MARKET_BOT_RUNTIME_MODE.trim().toLowerCase()
    : "local";

const defaultApiBase =
  window.location.origin && window.location.origin !== "null"
    ? window.location.origin
    : localApiBase;

const _injectedApiBase =
  typeof window.MARKET_BOT_API_BASE === "string" && window.MARKET_BOT_API_BASE.trim()
    ? window.MARKET_BOT_API_BASE.trim().replace(/\/$/, "")
    : "";

const _queryApiBase = new URLSearchParams(window.location.search).get("apiBase");
const _storedApiBase = window.localStorage.getItem("marketBotApiBase");
const API_BASE =
  runtimeMode === "local"
    ? _queryApiBase || defaultApiBase
    : _queryApiBase || _storedApiBase || _injectedApiBase || defaultApiBase;

const AUTH_TOKEN_KEY = "marketBotAccessToken";
const ANALYSIS_CACHE_TTL_MS = 60_000;
const AI_ANALYSIS_CACHE_TTL_MS = 3 * 60_000;
const RANKINGS_CACHE_TTL_MS = 30_000;
const analysisBundleCache = new Map();
const aiAnalysisCache = new Map();
const rankingsCache = new Map();
// GLOSSARY_TERMS moved to a separate lazy-loaded file (glossary.js).
// We keep a let binding here that the rest of the app reads. The data is
// injected by glossary.js when the user opens the Learning surface; until
// then this stays empty and we skip render until ready.
let GLOSSARY_TERMS = window.MARKET_BOT_GLOSSARY || [];
let _glossaryLoadPromise = null;
function ensureGlossaryLoaded() {
  if (GLOSSARY_TERMS.length) return Promise.resolve(GLOSSARY_TERMS);
  if (_glossaryLoadPromise) return _glossaryLoadPromise;
  _glossaryLoadPromise = new Promise((resolve) => {
    if (window.MARKET_BOT_GLOSSARY && window.MARKET_BOT_GLOSSARY.length) {
      GLOSSARY_TERMS = window.MARKET_BOT_GLOSSARY;
      resolve(GLOSSARY_TERMS);
      return;
    }
    const onReady = () => {
      GLOSSARY_TERMS = window.MARKET_BOT_GLOSSARY || [];
      resolve(GLOSSARY_TERMS);
    };
    window.addEventListener('market-bot:glossary-ready', onReady, { once: true });
    const s = document.createElement('script');
    s.src = './glossary.js?v=20260529-sprint7';
    s.async = true;
    s.onerror = () => resolve([]);
    document.head.appendChild(s);
  });
  return _glossaryLoadPromise;
}


const state = {
  ticker: "AAPL",
  horizon: "short",
  radarItems: [],
  universe: [],
  learningReady: false,
  learningFilter: "all",
  learningQuery: "",
  authMode: "login",
  accessToken: window.localStorage.getItem(AUTH_TOKEN_KEY),
  profile: null,
  instrumentType: "cedear",
  miniSummaryCurrency: "ARS",
  portfolioSummary: null,
  portfolioView: "summary",
  activeSurface: "workspace",
  lastTabbedSurface: "workspace",
  accountMenuOpen: false,
  editingPositionId: null,
  hasAnalyzed: false,
  analysisRequestId: 0,
  rankingMode: window.localStorage.getItem("marketBotRankingMode") || "default",
  currentFx: null,
  aiAnalysis: null,
  aiAnalysisLoading: false,
  aiAnalysisError: "",
  aiAnalysisRequestId: 0,
  // ----- Buffy / Chat -----
  chatInitialized: false,
  chatLoading: false,
  chatSending: false,
  chatProviders: [],
  chatCurrentProvider: null,
  chatThreads: [],
  chatCurrentThreadId: window.localStorage.getItem("marketBotChatThreadId") || null,
  chatMessages: [],
  chatUsage: null,
  chatEditingThreadId: null,
  chatEditingTitle: "",
  chatThreadBusyKey: null,
  chatRequestId: 0,
  chatError: null
};

let isApplyingRoute = false;
let analysisAbortController = null;
let aiAnalysisAbortController = null;

const elements = {
  body: document.body,
  accountShell: document.querySelector("#account-shell"),
  accountShortcut: document.querySelector("#account-shortcut"),
  accountShortcutKicker: document.querySelector("#account-shortcut-kicker"),
  accountShortcutLabel: document.querySelector("#account-shortcut-label"),
  accountMenu: document.querySelector("#account-menu"),
  accountMenuBody: document.querySelector("#account-menu-body"),
  accountCardTitle: document.querySelector("#account-card-title"),
  accountCardChip: document.querySelector("#account-card-chip"),
  accountCardCopy: document.querySelector("#account-card-copy"),
  openAccountButton: document.querySelector("#open-account-button"),
  openPortfolioButton: document.querySelector("#open-portfolio-button"),
  miniSummaryCurrencyButtons: Array.from(document.querySelectorAll("[data-mini-summary-currency]")),
  form: document.querySelector("#analysis-form"),
  tickerInput: document.querySelector("#ticker-input"),
  radarGrid: document.querySelector("#radar-grid"),
  verdictGrid: document.querySelector("#verdict-grid"),
  deterministicTitle: document.querySelector("#deterministic-title"),
  deterministicReasons: document.querySelector("#deterministic-reasons"),
  probabilisticTitle: document.querySelector("#probabilistic-title"),
  scenarioStack: document.querySelector("#scenario-stack"),
  probabilisticWarnings: document.querySelector("#probabilistic-warnings"),
  actionMatrix: document.querySelector("#action-matrix"),
  catalystList: document.querySelector("#catalyst-list"),
  guardrailList: document.querySelector("#guardrail-list"),
  validationTitle: document.querySelector("#validation-title"),
  validationGrid: document.querySelector("#validation-grid"),
  backtestTitle: document.querySelector("#backtest-title"),
  backtestGrid: document.querySelector("#backtest-grid"),
  newsTitle: document.querySelector("#news-title"),
  newsChip: document.querySelector("#news-chip"),
  newsFeed: document.querySelector("#news-feed"),
  earningsTitle: document.querySelector("#earnings-title"),
  earningsChip: document.querySelector("#earnings-chip"),
  tickerEarningsFeed: document.querySelector("#ticker-earnings-feed"),
  tickerEarningsHistory: document.querySelector("#ticker-earnings-history"),
  portfolioEarningsFeed: document.querySelector("#portfolio-earnings-feed"),
  workspaceTitle: document.querySelector("#workspace-title"),
  workspaceNameChip: document.querySelector("#workspace-name-chip"),
  marketChip: document.querySelector("#market-chip"),
  marketOverviewTitle: document.querySelector("#market-overview-title"),
  marketOverviewChip: document.querySelector("#market-overview-chip"),
  marketOverviewSummary: document.querySelector("#market-overview-summary"),
  marketOverviewGrid: document.querySelector("#market-overview-grid"),
  marketOverviewWarnings: document.querySelector("#market-overview-warnings"),
  indicatorGrid: document.querySelector("#indicator-grid"),
  indicatorAiButton: document.querySelector("#indicator-ai-button"),
  aiAnalysisShell: document.querySelector("#ai-analysis-shell"),
  status: document.querySelector("#analysis-status"),
  datalist: document.querySelector("#ticker-suggestions"),
  horizonButtons: Array.from(document.querySelectorAll(".horizon-pill")),
  surfaceButtons: Array.from(document.querySelectorAll("[data-surface]")),
  portfolioSurfaceButton: document.querySelector('[data-surface="portfolio"]'),
  workspaceSurface: document.querySelector("#surface-workspace"),
  portfolioSurface: document.querySelector("#surface-portfolio"),
  howtoSurface: document.querySelector("#surface-howto"),
  learningSurface: document.querySelector("#surface-learning"),
  chatSurface: document.querySelector("#surface-chat"),
  tradingSurface: document.querySelector("#surface-trading"),
  accessSurface: document.querySelector("#surface-access"),
  accessPanel: document.querySelector(".access-panel"),
  learningSearchInput: document.querySelector("#learning-search-input"),
  learningSearchClear: document.querySelector("#learning-search-clear"),
  learningFilters: document.querySelector("#learning-filters"),
  learningMeta: document.querySelector("#learning-meta"),
  learningGrid: document.querySelector("#learning-grid"),
  authTitle: document.querySelector("#auth-title"),
  authForm: document.querySelector("#auth-form"),
  authModeButtons: Array.from(document.querySelectorAll("[data-auth-mode]")),
  authUsername: document.querySelector("#auth-username"),
  authDisplayNameWrap: document.querySelector("#auth-display-name-wrap"),
  authDisplayName: document.querySelector("#auth-display-name"),
  authPassword: document.querySelector("#auth-password"),
  authSubmit: document.querySelector("#auth-submit"),
  authStatus: document.querySelector("#auth-status"),
  profileShell: document.querySelector("#profile-shell"),
  profileForm: document.querySelector("#profile-form"),
  profileUsername: document.querySelector("#profile-username"),
  profileDisplayName: document.querySelector("#profile-display-name"),
  profileInvestorProfile: document.querySelector("#profile-investor-profile"),
  profilePreferredHorizon: document.querySelector("#profile-preferred-horizon"),
  profilePreferredInstruments: document.querySelector("#profile-preferred-instruments"),
  profileRiskTolerance: document.querySelector("#profile-risk-tolerance"),
  profileBenchmarkPreference: document.querySelector("#profile-benchmark-preference"),
  logoutButton: document.querySelector("#logout-button"),
  miniSummaryGrid: document.querySelector("#mini-summary-grid"),
  portfolioLockedState: document.querySelector("#portfolio-locked-state"),
  portfolioShell: document.querySelector("#portfolio-shell"),
  portfolioViewButtons: Array.from(document.querySelectorAll("[data-portfolio-view-tab]")),
  portfolioViewSummary: document.querySelector("#portfolio-view-summary"),
  portfolioViewLoad: document.querySelector("#portfolio-view-load"),
  portfolioViewHoldings: document.querySelector("#portfolio-view-holdings"),
  portfolioViewDiagnostics: document.querySelector("#portfolio-view-diagnostics"),
  diagnosticsHeader: document.querySelector("#diagnostics-header"),
  diagnosticsTbody: document.querySelector("#diagnostics-tbody"),
  diagnosticsStatus: document.querySelector("#diagnostics-status"),
  diagnosticsRefresh: document.querySelector("#diagnostics-refresh"),
  diagnosticsToggleOnlyBad: document.querySelector("#diagnostics-toggle-only-bad"),
  portfolioEmptySummary: document.querySelector("#portfolio-empty-summary"),
  portfolioEmptyHoldings: document.querySelector("#portfolio-empty-holdings"),
  portfolioImportForm: document.querySelector("#portfolio-import-form"),
  portfolioImportFile: document.querySelector("#portfolio-import-file"),
  portfolioImportReplace: document.querySelector("#portfolio-import-replace"),
  portfolioImportStatus: document.querySelector("#portfolio-import-status"),
  portfolioForm: document.querySelector("#portfolio-form"),
  positionEditorShell: document.querySelector("#position-editor-shell"),
  positionEditorTitle: document.querySelector("#position-editor-title"),
  positionEditorCancel: document.querySelector("#position-editor-cancel"),
  instrumentButtons: Array.from(document.querySelectorAll("[data-instrument-type]")),
  positionSymbol: document.querySelector("#position-symbol"),
  positionQuantity: document.querySelector("#position-quantity"),
  positionPurchaseDate: document.querySelector("#position-purchase-date"),
  positionPurchasePrice: document.querySelector("#position-purchase-price"),
  positionPurchaseCurrency: document.querySelector("#position-purchase-currency"),
  positionUnderlying: document.querySelector("#position-underlying"),
  positionRatio: document.querySelector("#position-ratio"),
  positionNotes: document.querySelector("#position-notes"),
  portfolioStatus: document.querySelector("#portfolio-status"),
  portfolioSummaryGrid: document.querySelector("#portfolio-summary-grid"),
  holdingsGrid: document.querySelector("#holdings-grid"),
  earningsBanner: document.querySelector("#earnings-banner"),
  earningsBannerMessage: document.querySelector("#earnings-banner-message"),
  earningsBannerCta: document.querySelector("#earnings-banner-cta"),
  earningsBannerDismiss: document.querySelector("#earnings-banner-dismiss"),
  rankingModeButtons: Array.from(document.querySelectorAll("[data-ranking-mode]")),
  fxDiagnosticTile: document.querySelector("#fx-diagnostic-tile"),
  fxDiagnosticSource: document.querySelector("#fx-diagnostic-source"),
  fxDiagnosticCcl: document.querySelector("#fx-diagnostic-ccl"),
  fxDiagnosticMep: document.querySelector("#fx-diagnostic-mep"),
  fxDiagnosticOfficial: document.querySelector("#fx-diagnostic-official"),
  fxDiagnosticImplied: document.querySelector("#fx-diagnostic-implied"),
  benchmarkPanel: document.querySelector("#benchmark-panel"),
  benchmarkBars: document.querySelector("#benchmark-bars"),
  exposureRow: document.querySelector("#exposure-row"),
  exposureBarSector: document.querySelector("#exposure-bar-sector"),
  exposureLegendSector: document.querySelector("#exposure-legend-sector"),
  exposureHintSector: document.querySelector("#exposure-sector-hint"),
  exposureBarRegion: document.querySelector("#exposure-bar-region"),
  exposureLegendRegion: document.querySelector("#exposure-legend-region"),
  exposureHintRegion: document.querySelector("#exposure-region-hint"),
  closeAccountButton: document.querySelector("#close-account-button")
};

function titleCaseHorizon(horizon) {
  return horizon === "short" ? "Short horizon" : "Long horizon";
}

function setLoading(isLoading) {
  elements.body.dataset.loading = isLoading ? "true" : "false";
}

function setStatus(message) {
  elements.status.textContent = message;
}

function setAuthStatus(message) {
  elements.authStatus.textContent = message;
}

function setPortfolioStatus(message) {
  elements.portfolioStatus.textContent = message;
}

function setPortfolioImportStatus(message) {
  if (!elements.portfolioImportStatus) return;
  elements.portfolioImportStatus.textContent = message;
}

function cedearRatioSourceMeta(source) {
  const normalized = String(source || "").trim().toLowerCase();
  return {
    reference_file: {
      label: "Catalogo CEDEAR validado",
      shortLabel: "Catalogo",
      tone: "bull"
    },
    builtin_canonical: {
      label: "Tabla interna validada",
      shortLabel: "Validado",
      tone: "bull"
    },
    canonical: {
      label: "Tabla interna validada",
      shortLabel: "Validado",
      tone: "bull"
    },
    user_supplied: {
      label: "Cargado por vos",
      shortLabel: "Manual",
      tone: "neutral"
    },
    estimated_market_parity: {
      label: "Estimado por paridad",
      shortLabel: "Paridad",
      tone: "neutral"
    },
    fallback_default: {
      label: "No verificado",
      shortLabel: "Sin validar",
      tone: "bear"
    }
  }[normalized] || {
    label: "Origen no disponible",
    shortLabel: "—",
    tone: "neutral"
  };
}

function summarizeCedearRatioCoverage(positions) {
  const cedears = Array.isArray(positions)
    ? positions.filter((position) => position.instrument_type === "cedear")
    : [];
  const summary = {
    total: cedears.length,
    verified: 0,
    catalog: 0,
    builtin: 0,
    manual: 0,
    estimated: 0,
    fallback: 0
  };

  cedears.forEach((position) => {
    const source = String(position.cedear_ratio_source || "").trim().toLowerCase();
    if (source === "reference_file") {
      summary.catalog += 1;
      summary.verified += 1;
    } else if (source === "builtin_canonical" || source === "canonical") {
      summary.builtin += 1;
      summary.verified += 1;
    } else if (source === "user_supplied") {
      summary.manual += 1;
    } else if (source === "estimated_market_parity") {
      summary.estimated += 1;
    } else if (source === "fallback_default") {
      summary.fallback += 1;
    }
  });

  const detail = [];
  if (summary.catalog > 0) detail.push(`Catalogo ${summary.catalog}`);
  if (summary.builtin > 0) detail.push(`Tabla ${summary.builtin}`);
  if (summary.manual > 0) detail.push(`Manual ${summary.manual}`);
  if (summary.estimated > 0) detail.push(`Paridad ${summary.estimated}`);
  if (summary.fallback > 0) detail.push(`Revisar ${summary.fallback}`);

  return {
    ...summary,
    tone: summary.fallback > 0 ? "bear" : summary.estimated > 0 || summary.manual > 0 ? "neutral" : "bull",
    detail: detail.join(" · ")
  };
}

function readTimedCache(cache, key, ttlMs) {
  const cached = cache.get(key);
  if (!cached) return null;
  if (Date.now() - cached.storedAt > ttlMs) {
    cache.delete(key);
    return null;
  }
  return cached.value;
}

function writeTimedCache(cache, key, value) {
  cache.set(key, { value, storedAt: Date.now() });
  return value;
}

function rankingsCacheKey() {
  const profileKey = state.profile
    ? `${state.profile.username}|${state.profile.risk_tolerance}|${state.profile.benchmark_preference}`
    : "guest";
  return `${state.horizon}|${state.rankingMode}|${profileKey}`;
}

function analysisCacheKey(ticker = state.ticker, horizon = state.horizon) {
  return `${String(ticker || "").toUpperCase()}|${horizon}`;
}

function setAccountMenuOpen(isOpen) {
  const loggedIn = Boolean(state.profile && state.accessToken);
  state.accountMenuOpen = loggedIn ? Boolean(isOpen) : false;
  if (!elements.accountMenu || !elements.accountShortcut) return;
  elements.accountMenu.classList.toggle("is-hidden", !state.accountMenuOpen);
  elements.accountShortcut.setAttribute("aria-expanded", state.accountMenuOpen ? "true" : "false");
}

function renderAccountMenu() {
  if (!elements.accountMenuBody) return;
  const loggedIn = Boolean(state.profile && state.accessToken);
  if (!loggedIn) {
    elements.accountMenuBody.innerHTML = "";
    setAccountMenuOpen(false);
    return;
  }

  const displayName = state.profile.display_name || state.profile.username;
  elements.accountMenuBody.innerHTML = `
    <div class="account-menu-head">
      <p class="sidebar-kicker">Sesión activa</p>
      <strong>${escapeText(displayName)}</strong>
      <p class="account-menu-copy">@${escapeText(state.profile.username)} · ${escapeText(toHeadline(state.profile.investor_profile))} · Riesgo ${escapeText(state.profile.risk_tolerance.toUpperCase())}</p>
    </div>
    <div class="account-menu-actions" role="menu" aria-label="Acciones de cuenta">
      <button type="button" class="account-menu-action" data-account-action="portfolio" role="menuitem">
        <strong>Portfolio</strong>
        <span>Ir a posiciones, benchmarks e import Balanz.</span>
      </button>
      <button type="button" class="account-menu-action" data-account-action="settings" role="menuitem">
        <strong>Settings</strong>
        <span>Abrir perfil inversor, horizonte y benchmark FX.</span>
      </button>
      <button type="button" class="account-menu-action" data-account-action="howto" role="menuitem">
        <strong>How to use</strong>
        <span>Repasar el playbook sin salir de la app.</span>
      </button>
      <button type="button" class="account-menu-action is-danger" data-account-action="logout" role="menuitem">
        <strong>Salir</strong>
        <span>Cerrar sesión en este browser.</span>
      </button>
    </div>
  `;
}

function renderAccountChrome() {
  const loggedIn = Boolean(state.profile && state.accessToken);
  if (!loggedIn) {
    elements.accountShortcutKicker.textContent = "Guest";
    elements.accountShortcutLabel.textContent = "Login";
    elements.accountShortcut.setAttribute("aria-label", "Abrir login o registro");
    elements.accountCardTitle.textContent = "Entrá o registrate";
    elements.accountCardChip.textContent = "Guest";
    elements.accountCardCopy.textContent = "El acceso vive aparte del landing. Primero creás tu usuario local y recién ahí se habilita portfolio, benchmarks y positions tracking.";
    elements.openAccountButton.querySelector(".button-label").textContent = "Ir a login";
    elements.openPortfolioButton.textContent = "Crear cuenta";
    elements.openPortfolioButton.setAttribute("aria-label", "Crear cuenta");
    renderAccountMenu();
    return;
  }

  const displayName = state.profile.display_name || state.profile.username;
  elements.accountShortcutKicker.textContent = "Settings";
  elements.accountShortcutLabel.textContent = `@${state.profile.username}`;
  elements.accountShortcut.setAttribute("aria-label", "Abrir menú de usuario");
  elements.accountCardTitle.textContent = displayName;
  elements.accountCardChip.textContent = state.profile.risk_tolerance.toUpperCase();
  elements.accountCardCopy.textContent = `${toHeadline(state.profile.investor_profile)} · ${toHeadline(state.profile.preferred_horizon)} · Benchmark ${state.profile.benchmark_preference.toUpperCase()}`;
  elements.openAccountButton.querySelector(".button-label").textContent = "Abrir settings";
  elements.openPortfolioButton.textContent = "Ir al portfolio";
  elements.openPortfolioButton.setAttribute("aria-label", "Ir al portfolio");
  renderAccountMenu();
}

function renderContextPlaceholder(target, options) {
  if (!target) return;
  const tone = options.tone || "neutral";
  target.innerHTML = `
    <article class="context-placeholder ${tone}">
      <strong>${escapeText(options.title)}</strong>
      <p>${escapeText(options.body)}</p>
    </article>
  `;
}

function setButtonBusy(button, isBusy, busyLabel) {
  if (!button) return;
  const label = button.querySelector(".button-label");
  if (!button.dataset.defaultLabel && label) {
    button.dataset.defaultLabel = label.textContent;
  }
  button.disabled = isBusy;
  button.dataset.busy = isBusy ? "true" : "false";
  if (label) {
    label.textContent = isBusy ? busyLabel : button.dataset.defaultLabel;
  }
}

function aiAnalysisCacheKey(ticker = state.ticker, horizon = state.horizon) {
  const viewer = state.profile?.user_id ? `u${state.profile.user_id}` : "guest";
  return `${viewer}:${String(ticker || "").toUpperCase()}:${horizon}`;
}

function aiProviderLabel() {
  return "Gemini Pro";
}

function resetAiAnalysis({ preserveResult = false } = {}) {
  if (aiAnalysisAbortController) {
    aiAnalysisAbortController.abort();
    aiAnalysisAbortController = null;
  }
  state.aiAnalysisLoading = false;
  state.aiAnalysisError = "";
  if (!preserveResult) {
    state.aiAnalysis = null;
  }
}

function renderAiAnalysisPanel() {
  if (!elements.aiAnalysisShell || !elements.indicatorAiButton) return;

  const canAnalyze = state.hasAnalyzed && Boolean(state.ticker);
  elements.indicatorAiButton.disabled = !canAnalyze || state.aiAnalysisLoading;

  if (!state.hasAnalyzed) {
    elements.aiAnalysisShell.innerHTML = `
      <article class="ai-analysis-card is-empty">
        <div class="ai-analysis-head">
          <div>
            <p class="analysis-kicker">${escapeText(aiProviderLabel())} / síntesis externa</p>
            <h4>Esperando un setup real</h4>
          </div>
          <span class="tone-chip">Idle</span>
        </div>
        <p>Tocá <em>Analizar setup</em> primero. Cuando ya tengas el ticker procesado, este botón arma una segunda lectura con contexto externo, noticias y catalysts recientes.</p>
      </article>
    `;
    return;
  }

  if (state.aiAnalysisLoading) {
    elements.aiAnalysisShell.innerHTML = `
      <article class="ai-analysis-card is-loading">
        <div class="ai-analysis-head">
          <div>
            <p class="analysis-kicker">${escapeText(aiProviderLabel())} / síntesis externa</p>
            <h4>Analizando ${escapeText(state.ticker)} con ${escapeText(aiProviderLabel())}</h4>
          </div>
          <span class="tone-chip">Buscando</span>
        </div>
        <div class="ai-analysis-skeleton">
          <span></span>
          <span></span>
          <span></span>
        </div>
        <p class="panel-caption">Se consolida el setup técnico con noticias, earnings y contexto de mercado para esta lectura AI.</p>
      </article>
    `;
    return;
  }

  if (state.aiAnalysisError) {
    elements.aiAnalysisShell.innerHTML = `
      <article class="ai-analysis-card is-error">
        <div class="ai-analysis-head">
          <div>
            <p class="analysis-kicker">${escapeText(aiProviderLabel())} / síntesis externa</p>
            <h4>No se pudo completar el análisis AI</h4>
          </div>
          <span class="signal-chip bear">Retry</span>
        </div>
        <p>${escapeText(state.aiAnalysisError)}</p>
        <p class="panel-caption">Podés volver a intentar desde el mismo botón sin perder el resto del setup.</p>
      </article>
    `;
    return;
  }

  if (!state.aiAnalysis) {
    elements.aiAnalysisShell.innerHTML = `
      <article class="ai-analysis-card is-empty">
        <div class="ai-analysis-head">
          <div>
            <p class="analysis-kicker">${escapeText(aiProviderLabel())} / síntesis externa</p>
            <h4>Segunda lectura opcional del setup</h4>
          </div>
          <span class="tone-chip">On demand</span>
        </div>
        <p>Ya tenés el setup consolidado. Si querés una capa extra con contexto externo y búsqueda web reciente, corré <strong>Analizar con AI</strong>.</p>
      </article>
    `;
    return;
  }

  const citations = Array.isArray(state.aiAnalysis.citations) ? state.aiAnalysis.citations : [];
  const citationsMarkup = citations.length
    ? `
        <div class="ai-analysis-citations">
          <p class="analysis-kicker">Fuentes citadas</p>
          <ul class="ai-analysis-citation-list">
            ${citations
              .map((citation) => {
                const href = safeHttpUrl(citation.url);
                if (!href) return "";
                const meta = [citation.source, citation.published_at].filter(Boolean).join(" · ");
                return `
                  <li>
                    <a href="${href}" target="_blank" rel="noopener noreferrer">${escapeText(citation.title || href)}</a>
                    ${meta ? `<span>${escapeText(meta)}</span>` : ""}
                  </li>
                `;
              })
              .join("")}
          </ul>
        </div>
      `
    : "";

  elements.aiAnalysisShell.innerHTML = `
    <article class="ai-analysis-card">
      <div class="ai-analysis-head">
        <div>
          <p class="analysis-kicker">${escapeText(aiProviderLabel(state.aiAnalysis.provider))} / síntesis externa</p>
          <h4>Lectura AI para ${escapeText(state.aiAnalysis.ticker)}</h4>
        </div>
        <div class="ai-analysis-meta">
          <span class="tone-chip">${escapeText(aiProviderLabel(state.aiAnalysis.provider))}</span>
          <span class="tone-chip">${escapeText(state.aiAnalysis.model || "sonar")}</span>
          <span class="tone-chip">${state.aiAnalysis.used_profile_context ? "Con perfil" : "Sin perfil"}</span>
          <span class="tone-chip">${citations.length ? `${citations.length} fuentes` : "Sin citas"}</span>
        </div>
      </div>
      <div class="ai-analysis-body">${renderMarkdown(state.aiAnalysis.content)}</div>
      ${citationsMarkup}
    </article>
  `;
}

function surfaceLabel(surface) {
  const labels = {
    workspace: "workspace",
    portfolio: "portfolio",
    howto: "how to use",
    learning: "learning",
    chat: "Buffy",
    trading: "trading"
  };
  return labels[surface] || "workspace";
}

function accessFocusTarget() {
  if (state.profile && state.accessToken) {
    return elements.profileDisplayName;
  }
  return state.authMode === "register" ? elements.authDisplayName : elements.authUsername;
}

const SURFACE_ORDER = ["workspace", "portfolio", "howto", "learning", "chat", "trading", "access"];

function normalizedHashRoute(hash) {
  const route = String(hash || "")
    .replace(/^#\/?/, "")
    .trim()
    .toLowerCase();
  return route || "workspace";
}

function parseHashRoute(hash) {
  const route = normalizedHashRoute(hash);
  if (route === "login") {
    return { surface: "access", authMode: "login" };
  }
  if (route === "register") {
    return { surface: "access", authMode: "register" };
  }
  if (route === "settings") {
    return { surface: "access", authMode: "login" };
  }
  if (SURFACE_ORDER.includes(route)) {
    return { surface: route };
  }
  return { surface: "workspace" };
}

function currentRouteHash() {
  if (state.activeSurface === "access") {
    if (state.profile && state.accessToken) {
      return "#settings";
    }
    return state.authMode === "register" ? "#register" : "#login";
  }
  return `#${state.activeSurface || "workspace"}`;
}

function syncRouteHash(options = {}) {
  if (isApplyingRoute || typeof window === "undefined") return;
  const { replace = false } = options;
  const nextHash = currentRouteHash();
  const baseUrl = `${window.location.pathname}${window.location.search}`;
  const nextUrl = `${baseUrl}${nextHash}`;
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash || ""}`;
  if (currentUrl === nextUrl) return;
  if (replace) {
    window.history.replaceState({}, "", nextUrl);
    return;
  }
  window.history.pushState({}, "", nextUrl);
}

function openAccess(mode, options = {}) {
  if (!(state.profile && state.accessToken) && mode) {
    setAuthMode(mode, { syncRoute: false });
  }
  setSurface("access", options);
}

function applyHashRoute(options = {}) {
  const { replace = false } = options;
  const route = parseHashRoute(window.location.hash);
  isApplyingRoute = true;
  try {
    if (!(state.profile && state.accessToken) && route.authMode) {
      setAuthMode(route.authMode, { syncRoute: false });
    }
    setSurface(route.surface, { syncRoute: false });
  } finally {
    isApplyingRoute = false;
  }
  syncRouteHash({ replace: true });
}

function setSurface(surface, options = {}) {
  const { syncRoute = true, replaceRoute = false } = options;
  setAccountMenuOpen(false);
  if (surface === "portfolio" && !(state.profile && state.accessToken)) {
    surface = "access";
    setAuthMode("login", { syncRoute: false });
  }
  const previousSurface = state.activeSurface;
  state.activeSurface = surface;
  if (surface !== "access") {
    state.lastTabbedSurface = surface;
  }
  const surfaces = {
    workspace: elements.workspaceSurface,
    portfolio: elements.portfolioSurface,
    howto: elements.howtoSurface,
    learning: elements.learningSurface,
    chat: elements.chatSurface,
    trading: elements.tradingSurface,
    access: elements.accessSurface
  };

  // Direction (forward / backward) drives the slide side via CSS.
  // Forward = right-to-left enter; backward = left-to-right enter.
  const slider = document.querySelector(".surface-slider");
  const previousBaseSurface = previousSurface === "access" ? state.lastTabbedSurface : (previousSurface || "workspace");
  const activeBaseSurface = surface === "access" ? state.lastTabbedSurface : surface;
  if (slider) {
    const fromIndex = SURFACE_ORDER.indexOf(previousBaseSurface || "workspace");
    const toIndex = SURFACE_ORDER.indexOf(activeBaseSurface || "workspace");
    const direction = toIndex >= fromIndex ? "forward" : "backward";
    slider.setAttribute("data-direction", direction);
    slider.setAttribute("data-active-surface", activeBaseSurface);
  }

  Object.entries(surfaces).forEach(([key, node]) => {
    if (!node) return;
    const isActive = key === "access" ? surface === "access" : key === activeBaseSurface;
    // Active swap via opacity/transform (no display:none), so revealing
    // animations don't restart and the swap takes ~200ms instead of ~1s.
    node.classList.toggle("is-active", isActive);
  });
  const selectedTabSurface = surface === "access" ? state.lastTabbedSurface : surface;
  elements.surfaceButtons.forEach((button) => {
    const isSelected = button.dataset.surface === selectedTabSurface;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
  if (elements.accountShortcut) {
    elements.accountShortcut.classList.toggle("is-active", surface === "access");
    elements.accountShortcut.setAttribute("aria-pressed", surface === "access" ? "true" : "false");
  }
  if (elements.closeAccountButton) {
    elements.closeAccountButton.textContent = `Volver a ${surfaceLabel(state.lastTabbedSurface)}`;
  }
  elements.body.dataset.overlay = surface === "access" ? "access" : "none";
  if (activeBaseSurface === "learning") {
    ensureLearningReady();
  }
  if (activeBaseSurface === "chat") {
    initializeChat();
  }
  if (surface === "access") {
    window.requestAnimationFrame(() => {
      const focusTarget = accessFocusTarget();
      if (focusTarget) {
        focusTarget.focus();
      }
    });
  }
  if (syncRoute) {
    syncRouteHash({ replace: replaceRoute });
  }
}

function setPortfolioView(view) {
  state.portfolioView = view;
  const views = {
    summary: elements.portfolioViewSummary,
    load: elements.portfolioViewLoad,
    holdings: elements.portfolioViewHoldings,
    diagnostics: elements.portfolioViewDiagnostics
  };

  Object.entries(views).forEach(([key, node]) => {
    if (!node) return;
    node.classList.toggle("is-active", key === view);
  });
  elements.portfolioViewButtons.forEach((button) => {
    const isSelected = button.dataset.portfolioViewTab === view;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });

  if (view === "diagnostics") {
    loadDiagnostics();
  }
}

// Diagnostics view — surface raw per-position values to debug "the numbers
// don't add up" reports from the user. Sorted by |fx_drift| descending so
// the worst offenders appear first; one click and we know which yfinance
// fetch is broken.
let _diagnosticsOnlyBad = false;
let _diagnosticsCache = null;

async function loadDiagnostics() {
  if (!state.accessToken) {
    if (elements.diagnosticsStatus) {
      elements.diagnosticsStatus.textContent = "Ingresá para ver el diagnóstico de tu portfolio.";
    }
    if (elements.diagnosticsTbody) elements.diagnosticsTbody.innerHTML = "";
    if (elements.diagnosticsHeader) elements.diagnosticsHeader.innerHTML = "";
    return;
  }
  if (elements.diagnosticsStatus) {
    elements.diagnosticsStatus.textContent = "Pidiendo precios crudos al backend…";
  }
  if (elements.diagnosticsTbody) {
    elements.diagnosticsTbody.innerHTML = Array.from({ length: 4 })
      .map(() => `
        <tr class="diagnostics-skeleton-row" aria-hidden="true">
          ${Array.from({ length: 9 }).map(() => `<td><div class="diagnostics-skeleton-cell"></div></td>`).join("")}
        </tr>
      `)
      .join("");
  }
  try {
    const data = await fetchJson("/portfolio/diagnostics", { auth: true });
    _diagnosticsCache = data;
    renderDiagnostics(data);
  } catch (error) {
    if (elements.diagnosticsStatus) {
      elements.diagnosticsStatus.textContent = `No se pudo cargar el diagnóstico: ${error.message}`;
    }
  }
}

function renderDiagnostics(data) {
  if (!data || !Array.isArray(data.positions)) return;

  // Sort by absolute drift descending — worst rows surface first.
  const sorted = [...data.positions].sort(
    (a, b) => Math.abs(Number(b.fx_drift_pct) || 0) - Math.abs(Number(a.fx_drift_pct) || 0)
  );
  const filtered = _diagnosticsOnlyBad
    ? sorted.filter((p) => Math.abs(Number(p.fx_drift_pct) || 0) > 25)
    : sorted;

  const totalBad = sorted.filter((p) => Math.abs(Number(p.fx_drift_pct) || 0) > 25).length;
  const totalWarning = sorted.filter((p) => {
    const drift = Math.abs(Number(p.fx_drift_pct) || 0);
    return drift > 10 && drift <= 25;
  }).length;
  const totalOk = sorted.length - totalBad - totalWarning;

  if (elements.diagnosticsHeader) {
    elements.diagnosticsHeader.innerHTML = `
      <div class="diagnostics-stat">
        <span class="metric-label">Snapshot</span>
        <strong>${escapeText(data.as_of)}</strong>
      </div>
      <div class="diagnostics-stat">
        <span class="metric-label">CCL actual</span>
        <strong>${formatMoney(data.current_ccl, "ARS")}</strong>
      </div>
      <div class="diagnostics-stat">
        <span class="metric-label">MEP actual</span>
        <strong>${formatMoney(data.current_mep, "ARS")}</strong>
      </div>
      <div class="diagnostics-stat">
        <span class="metric-label">Oficial</span>
        <strong>${formatMoney(data.current_official, "ARS")}</strong>
      </div>
      <div class="diagnostics-stat tone-${totalBad > 0 ? "bear" : totalWarning > 0 ? "neutral" : "bull"}">
        <span class="metric-label">Salud</span>
        <strong>${totalOk} ✓ · ${totalWarning} ⚠ · ${totalBad} ✗</strong>
      </div>
    `;
  }

  if (elements.diagnosticsTbody) {
    elements.diagnosticsTbody.innerHTML = filtered
      .map((p) => {
        const drift = Number(p.fx_drift_pct) || 0;
        const absDrift = Math.abs(drift);
        const tone = absDrift > 25 ? "bear" : absDrift > 10 ? "neutral" : "bull";
        const ratioSourceLabel = cedearRatioSourceMeta(p.ratio_source);

        return `
          <tr class="diagnostics-row tone-${tone}">
            <td data-label="Ticker"><strong>${escapeText(p.symbol)}</strong></td>
            <td data-label="Tipo"><span class="diagnostics-chip">${escapeText(p.instrument_type)}</span></td>
            <td class="diagnostics-num" data-label="Cantidad">${(Number(p.quantity) || 0).toLocaleString("es-AR")}</td>
            <td data-label="Ratio">
              ${p.cedear_ratio ? `<strong>${p.cedear_ratio}:1</strong>` : "—"}
              <span class="diagnostics-ratio-source">${escapeText(ratioSourceLabel.shortLabel)}</span>
            </td>
            <td class="diagnostics-num" data-label="Precio">${formatMoney(p.current_price, p.current_price_currency || "ARS")}</td>
            <td class="diagnostics-num" data-label="Valor ARS">${formatMoney(p.current_value_ars, "ARS", { magnitude: true })}</td>
            <td class="diagnostics-num" data-label="Valor USD">${formatMoney(p.current_value_usd, "USD")}</td>
            <td class="diagnostics-num" data-label="FX implicito">${(Number(p.implied_fx) || 0).toLocaleString("es-AR", { maximumFractionDigits: 0 })}</td>
            <td class="diagnostics-num" data-label="Drift FX">
              <span class="diagnostics-drift tone-${tone}">${drift >= 0 ? "+" : ""}${drift.toFixed(1)}%</span>
            </td>
          </tr>
        `;
      })
      .join("");
  }

  if (elements.diagnosticsStatus) {
    if (totalBad > 0) {
      elements.diagnosticsStatus.innerHTML = `<strong>${totalBad} posiciones</strong> tienen FX implícito que se aleja del CCL en más de 25%. Probablemente yfinance está devolviendo un precio stale para esos <code>.BA</code>. Esas filas están manchando el total del portfolio.`;
    } else if (totalWarning > 0) {
      elements.diagnosticsStatus.innerHTML = `${totalWarning} posiciones con drift moderado (10-25%). Aceptable pero conviene revisar.`;
    } else {
      elements.diagnosticsStatus.innerHTML = `Todas las posiciones cuadran con el CCL actual. Si el total te sigue chirriando, el problema está en el cost basis o en una posición específica.`;
    }
  }
}

// ============================================================
// ----- Buffy / Chat module -------------------------------
// ============================================================
// Lightweight chat surface backed by /chat/* endpoints. Handles
// provider selection, thread list, message rendering with inline
// markdown (bold, code, code fence, bullets, links), quick-action
// pills, optimistic user-message rendering, and a shimmer state
// on the assistant bubble while waiting for the response.
//
// Streaming (typed-out effect) is out of scope for v1: we just
// paint the full assistant message when the POST resolves.

const CHAT_QUICK_ACTIONS = [
  "Resumime mi portfolio en 5 puntos",
  "Que riesgos ves hoy para mi cartera",
  "Como viene NVDA en corto plazo",
  "Explicame que es ROIC"
];

const CHAT_THREAD_KEY = "marketBotChatThreadId";
const CHAT_PROVIDER_LABELS = {
  anthropic: "Claude",
  gemini: "Buffy",
  openai: "OpenAI"
};

function chatEl(id) {
  return document.getElementById(id);
}

function currentChatProviderInfo() {
  return (state.chatProviders || []).find((provider) => provider.id === state.chatCurrentProvider) || null;
}

function focusChatInput() {
  const input = chatEl("chat-input");
  if (!input) return;
  window.requestAnimationFrame(() => input.focus());
}

async function initializeChat() {
  if (state.chatInitialized || state.chatLoading) {
    // Already running or done — but keep gating fresh if auth state changed.
    renderChatGateOrPanel();
    return;
  }
  if (!state.accessToken || !state.profile) {
    renderChatGateOrPanel();
    bindChatEventsOnce();
    return;
  }
  state.chatLoading = true;
  state.chatError = null;
  renderChatGateOrPanel();
  renderChatQuickActions();
  bindChatEventsOnce();
  try {
    const [providers, threads] = await Promise.all([
      fetchJson("/chat/providers", { auth: true }).catch(() => []),
      fetchJson("/chat/threads", { auth: true }).catch(() => [])
    ]);
    state.chatProviders = Array.isArray(providers) ? providers : [];
    state.chatThreads = Array.isArray(threads) ? threads : [];

    // Default provider: first configured, else first available.
    const configured = state.chatProviders.find((p) => p.configured);
    state.chatCurrentProvider = configured ? configured.id : (state.chatProviders[0] ? state.chatProviders[0].id : null);

    // Restore selected thread from localStorage if it still exists.
    const persistedId = state.chatCurrentThreadId;
    const persistedExists = persistedId && state.chatThreads.some((t) => String(t.id) === String(persistedId));
    if (persistedExists) {
      state.chatCurrentThreadId = persistedId;
    } else if (state.chatThreads.length > 0) {
      state.chatCurrentThreadId = state.chatThreads[0].id;
      window.localStorage.setItem(CHAT_THREAD_KEY, String(state.chatCurrentThreadId));
    } else {
      state.chatCurrentThreadId = null;
      window.localStorage.removeItem(CHAT_THREAD_KEY);
    }

    state.chatInitialized = true;
    state.chatMessages = [];
    renderChatGateOrPanel();
    if (state.chatCurrentThreadId) {
      loadChatMessages(state.chatCurrentThreadId)
        .then(() => renderChatMessages())
        .catch(() => {})
        .finally(() => focusChatInput());
    } else {
      renderChatMessages();
      focusChatInput();
    }
    refreshChatUsage();
  } catch (error) {
    state.chatError = error.message || String(error);
  } finally {
    state.chatLoading = false;
    renderChatGateOrPanel();
  }
}

async function loadChatMessages(threadId) {
  if (!threadId) {
    state.chatMessages = [];
    return;
  }
  try {
    const messages = await fetchJson(`/chat/threads/${encodeURIComponent(threadId)}/messages`, { auth: true });
    state.chatMessages = Array.isArray(messages) ? messages : [];
  } catch (error) {
    state.chatMessages = [];
    state.chatError = error.message || String(error);
  }
}

function renderChatGateOrPanel() {
  const layout = document.querySelector("#surface-chat .chat-layout");
  if (!layout) return;
  const gated = !(state.accessToken && state.profile);
  if (gated) {
    layout.innerHTML = `
      <div class="chat-gate" style="grid-column: 1 / -1;">
        <strong>Para usar Buffy necesitás una sesión activa.</strong>
        <p>Ingresá desde la cuenta y vas a poder conversar sobre tu portfolio, tickers, CEDEARs, noticias y conceptos.</p>
      </div>
    `;
    return;
  }
  // Restore panel structure if it was replaced by the gate.
  if (!chatEl("chat-messages")) {
    layout.innerHTML = `
      <aside class="chat-threads">
        <div class="chat-threads-head">
          <button type="button" class="ghost-button" id="chat-new-thread">+ Nuevo hilo</button>
        </div>
        <ul class="chat-thread-list" id="chat-thread-list"></ul>
        <div class="chat-usage" id="chat-usage"></div>
      </aside>
      <div class="chat-conversation">
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-quick-actions" id="chat-quick-actions"></div>
        <form class="chat-composer" id="chat-composer">
          <textarea
            id="chat-input"
            placeholder="Preguntale a Buffy por tu portfolio, un ticker o un concepto..."
            rows="2"
            autocomplete="off"
            spellcheck="false"
          ></textarea>
          <button type="submit" class="primary-button">
            <span class="button-label">Enviar</span>
          </button>
        </form>
        <p class="chat-disclaimer">Esto no es asesoramiento financiero. Buffy resume contexto, riesgos y marcos de decision; no ejecuta ordenes ni da calls binarias.</p>
      </div>
    `;
    bindChatPanelEvents();
  }
  renderChatProviders();
  renderChatThreads();
  renderChatMessages();
  renderChatUsage();
  renderChatQuickActions();
}

function renderChatProviders() {
  const switcher = chatEl("chat-provider-switch");
  if (!switcher) return;
  const providers = state.chatProviders || [];
  const configured = providers.filter((p) => p.configured);
  if (configured.length === 0) {
    switcher.innerHTML = `<span class="chat-provider-note">Sin proveedores configurados — agregá una API key en <code>.env</code></span>`;
    return;
  }
  if (configured.length === 1) {
    // Hide selector when there's nothing to switch.
    switcher.innerHTML = "";
    return;
  }
  switcher.innerHTML = configured
    .map((p) => {
      const selected = p.id === state.chatCurrentProvider;
      const label = CHAT_PROVIDER_LABELS[p.id] || p.label || p.id;
      return `<button type="button" class="ranking-mode-pill${selected ? " is-selected" : ""}" data-chat-provider="${escapeAttribute(p.id)}">${escapeText(label)}</button>`;
    })
    .join("");
  switcher.querySelectorAll("[data-chat-provider]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.chatCurrentProvider = btn.dataset.chatProvider;
      renderChatProviders();
    });
  });
}

function renderChatThreads() {
  const list = chatEl("chat-thread-list");
  if (!list) return;
  const threads = state.chatThreads || [];
  if (threads.length === 0) {
    list.innerHTML = `
      <li class="chat-threads-empty">
        <span>Todavía no tenés hilos.</span>
        <button type="button" class="ghost-button" id="chat-empty-create">Crear primer hilo</button>
      </li>
    `;
    const cta = chatEl("chat-empty-create");
    if (cta) cta.addEventListener("click", () => createChatThread());
    return;
  }
  list.innerHTML = threads
    .map((t) => {
      const isActive = String(t.id) === String(state.chatCurrentThreadId);
      const isEditing = String(t.id) === String(state.chatEditingThreadId);
      const isBusy = state.chatThreadBusyKey === `rename:${t.id}` || state.chatThreadBusyKey === `delete:${t.id}`;
      const dateLabel = formatChatDate(t.updated_at || t.created_at);
      const providerLabel = providerLabelFor(t.provider) || t.provider || "";
      const title = t.title || "Hilo sin título";
      if (isEditing) {
        return `
          <li class="chat-thread-item">
            <form class="chat-thread-edit-form" data-chat-thread-edit-form="${escapeAttribute(t.id)}">
              <input
                type="text"
                class="chat-thread-edit-input"
                data-chat-thread-edit-input="${escapeAttribute(t.id)}"
                value="${escapeAttribute(state.chatEditingTitle || title)}"
                maxlength="120"
                placeholder="Etiqueta del hilo"
                aria-label="Cambiar etiqueta de la conversación"
              />
              <div class="chat-thread-edit-actions">
                <button type="submit" class="chat-thread-edit-button is-primary"${isBusy ? " disabled" : ""}>
                  ${isBusy ? "Guardando..." : "Guardar"}
                </button>
                <button type="button" class="chat-thread-edit-button" data-chat-thread-cancel="${escapeAttribute(t.id)}"${isBusy ? " disabled" : ""}>
                  Cancelar
                </button>
              </div>
            </form>
          </li>
        `;
      }
      return `
        <li class="chat-thread-item">
          <div class="chat-thread-shell">
            <button type="button" class="chat-thread-card${isActive ? " is-active" : ""}" data-chat-thread="${escapeAttribute(t.id)}">
              <span class="chat-thread-card-kicker">${escapeText(t.model || providerLabel || "Buffy")}</span>
              <span class="chat-thread-card-title">${escapeText(title)}</span>
              <span class="chat-thread-card-meta">
                <span>${escapeText(dateLabel)}</span>
                ${providerLabel ? `<span class="chat-thread-card-chip">${escapeText(providerLabel)}</span>` : ""}
              </span>
            </button>
            <div class="chat-thread-actions">
              <button type="button" class="chat-thread-action" data-chat-thread-rename="${escapeAttribute(t.id)}"${isBusy ? " disabled" : ""}>
                Etiquetar
              </button>
              <button type="button" class="chat-thread-action is-danger" data-chat-thread-delete="${escapeAttribute(t.id)}"${isBusy ? " disabled" : ""}>
                ${state.chatThreadBusyKey === `delete:${t.id}` ? "Borrando..." : "Borrar"}
              </button>
            </div>
          </div>
        </li>
      `;
    })
    .join("");
  list.querySelectorAll("[data-chat-thread]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.chatThread;
      if (String(id) === String(state.chatCurrentThreadId)) return;
      state.chatCurrentThreadId = id;
      window.localStorage.setItem(CHAT_THREAD_KEY, String(id));
      state.chatMessages = [];
      renderChatThreads();
      renderChatMessages();
      await loadChatMessages(id);
      renderChatMessages();
    });
  });
  list.querySelectorAll("[data-chat-thread-rename]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const id = btn.dataset.chatThreadRename;
      const thread = threads.find((item) => String(item.id) === String(id));
      state.chatEditingThreadId = id;
      state.chatEditingTitle = thread ? (thread.title || "") : "";
      renderChatThreads();
      const input = list.querySelector(`[data-chat-thread-edit-input="${String(id)}"]`);
      if (input) {
        input.focus();
        input.select();
      }
    });
  });
  list.querySelectorAll("[data-chat-thread-delete]").forEach((btn) => {
    btn.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopPropagation();
      await deleteChatThread(btn.dataset.chatThreadDelete);
    });
  });
  list.querySelectorAll("[data-chat-thread-cancel]").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      state.chatEditingThreadId = null;
      state.chatEditingTitle = "";
      state.chatThreadBusyKey = null;
      renderChatThreads();
    });
  });
  list.querySelectorAll("[data-chat-thread-edit-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const id = form.dataset.chatThreadEditForm;
      const input = form.querySelector("[data-chat-thread-edit-input]");
      await renameChatThread(id, input ? input.value : "");
    });
  });
}

function providerLabelFor(providerId) {
  if (!providerId) return null;
  const found = (state.chatProviders || []).find((p) => p.id === providerId);
  return found ? (CHAT_PROVIDER_LABELS[found.id] || found.label || found.id) : (CHAT_PROVIDER_LABELS[providerId] || providerId);
}

function sortChatThreads(threads) {
  return [...(threads || [])].sort((left, right) => {
    const leftValue = new Date(left.updated_at || left.created_at || 0).getTime();
    const rightValue = new Date(right.updated_at || right.created_at || 0).getTime();
    return rightValue - leftValue;
  });
}

function formatChatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) {
      return d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
    }
    return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
  } catch (e) {
    return "";
  }
}

function renderChatMessages() {
  const container = chatEl("chat-messages");
  if (!container) return;
  const messages = state.chatMessages || [];
  if (state.chatLoading && messages.length === 0) {
    container.innerHTML = `
      <div class="chat-messages-empty is-loading" aria-live="polite">
        <strong>Preparando a Buffy</strong>
        <p>Cargando providers, hilos y contexto base.</p>
      </div>
    `;
    return;
  }
  if (messages.length === 0 && !state.chatSending) {
    container.innerHTML = `
      <div class="chat-messages-empty">
        <strong>Empezá la conversación con Buffy</strong>
        <p>Tocá una acción rápida abajo o escribí tu pregunta. Buffy puede ayudarte con análisis, riesgos, benchmarks, conceptos y lectura de portfolio.</p>
      </div>
    `;
    return;
  }
  const parts = messages.map((m) => renderChatMessageMarkup(m));
  if (state.chatSending) {
    parts.push(`
      <div class="chat-message chat-message-assistant">
        <div class="chat-message-bubble is-loading" aria-live="polite">Pensando…</div>
      </div>
    `);
  }
  if (state.chatError) {
    parts.push(`
      <div class="chat-message chat-message-assistant">
        <div class="chat-message-bubble is-error">${escapeText(state.chatError)}</div>
      </div>
    `);
  }
  container.innerHTML = parts.join("");
  // Auto-scroll to bottom on every render.
  window.requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

function renderChatMessageMarkup(message) {
  const role = message.role === "user" ? "user" : "assistant";
  const bubbleClass = role === "user" ? "chat-message-user" : "chat-message-assistant";
  const content = role === "assistant" ? renderMarkdown(message.content || "") : escapeText(message.content || "").replace(/\n/g, "<br>");
  const meta = role === "assistant" ? renderChatMessageMeta(message) : "";
  return `
    <div class="chat-message ${bubbleClass}">
      <div class="chat-message-bubble">${content}</div>
      ${meta ? `<div class="chat-message-meta">${meta}</div>` : ""}
    </div>
  `;
}

function renderChatMessageMeta(message) {
  const provider = providerLabelFor(message.provider) || message.provider || "";
  const model = message.model || "";
  const tokensIn = message.tokens_in;
  const tokensOut = message.tokens_out;
  const cost = message.cost_usd;
  const bits = [];
  if (provider) bits.push(escapeText(provider));
  if (model) bits.push(escapeText(model));
  if (tokensIn != null || tokensOut != null) {
    bits.push(`${tokensIn || 0}↑ / ${tokensOut || 0}↓ tok`);
  }
  if (cost != null && !Number.isNaN(Number(cost))) {
    bits.push(`$${Number(cost).toFixed(4)}`);
  }
  return bits.join(" · ");
}

// ----- Tiny inline markdown renderer -----
// Covers: triple-backtick code fences, inline code, bold (**text**),
// links [text](href), bullet lists, paragraph breaks. Newlines preserved.
function renderMarkdown(src) {
  if (!src) return "";
  const text = String(src);
  // Pull code fences out first so we don't transform their contents.
  const fences = [];
  let working = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, body) => {
    fences.push({ lang: lang || "", body: body.replace(/\n$/, "") });
    return ` FENCE${fences.length - 1} `;
  });

  // Escape everything else.
  working = escapeText(working);

  // Inline code: `code`
  working = working.replace(/`([^`\n]+)`/g, (_m, code) => `<code>${code}</code>`);

  // Bold: **text**
  working = working.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");

  // Links: [text](href) — only allow http(s) and mailto to avoid XSS via javascript: URLs.
  working = working.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, href) => {
    const safe = /^(https?:|mailto:)/i.test(href) ? href : "#";
    return `<a href="${safe}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });

  // Bullet lists: group consecutive lines starting with "- " or "* ".
  const lines = working.split(/\n/);
  const out = [];
  let buffer = [];
  let inList = false;
  const flushParagraph = () => {
    if (buffer.length) {
      out.push(`<p>${buffer.join("<br>")}</p>`);
      buffer = [];
    }
  };
  for (const raw of lines) {
    const line = raw;
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    if (bullet) {
      flushParagraph();
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${bullet[1]}</li>`);
      continue;
    }
    if (inList) { out.push("</ul>"); inList = false; }
    if (line.trim() === "") {
      flushParagraph();
      continue;
    }
    buffer.push(line);
  }
  if (inList) out.push("</ul>");
  flushParagraph();

  let html = out.join("");

  // Restore code fences.
  html = html.replace(/ FENCE(\d+) /g, (_m, idx) => {
    const fence = fences[Number(idx)];
    if (!fence) return "";
    return `<pre><code>${escapeText(fence.body)}</code></pre>`;
  });

  return html;
}

function renderChatUsage() {
  const node = chatEl("chat-usage");
  if (!node) return;
  const usage = state.chatUsage;
  if (!usage) {
    node.innerHTML = "";
    return;
  }
  const total = Number(usage.total_cost_usd || 0).toFixed(4);
  const byProvider = Array.isArray(usage.by_provider) ? usage.by_provider : [];
  const providerRows = byProvider
    .map((row) => {
      const provider = row.provider || "";
      const cost = row.cost_usd || 0;
      return `<div class="chat-usage-row"><span>${escapeText(providerLabelFor(provider) || provider)}</span><span>$${Number(cost).toFixed(4)}</span></div>`;
    })
    .join("");
  node.innerHTML = `
    <div class="chat-usage-total">$${total} / mes</div>
    ${providerRows}
  `;
}

function renderChatQuickActions() {
  const node = chatEl("chat-quick-actions");
  if (!node) return;
  node.innerHTML = CHAT_QUICK_ACTIONS
    .map((label) => `<button type="button" class="chat-quick-action" data-chat-action="${escapeAttribute(label)}">${escapeText(label)}</button>`)
    .join("");
  node.querySelectorAll("[data-chat-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = chatEl("chat-input");
      if (!input) return;
      input.value = btn.dataset.chatAction || "";
      input.focus();
      autoGrowChatInput(input);
    });
  });
}

async function createChatThread(title) {
  if (!state.accessToken) return;
  try {
    const provider = currentChatProviderInfo();
    const body = {};
    if (title) body.title = title;
    if (state.chatCurrentProvider) body.provider = state.chatCurrentProvider;
    if (provider && provider.model) body.model = provider.model;
    const thread = await fetchJson("/chat/threads", {
      method: "POST",
      auth: true,
      body: JSON.stringify(body)
    });
    if (!thread || !thread.id) return;
    state.chatThreads = sortChatThreads([thread, ...(state.chatThreads || [])]);
    state.chatCurrentThreadId = thread.id;
    window.localStorage.setItem(CHAT_THREAD_KEY, String(thread.id));
    state.chatMessages = [];
    state.chatEditingThreadId = null;
    state.chatEditingTitle = "";
    renderChatThreads();
    renderChatMessages();
    return thread;
  } catch (error) {
    state.chatError = error.message || String(error);
    renderChatMessages();
  }
}

async function renameChatThread(threadId, rawTitle) {
  if (!state.accessToken || !threadId) return;
  const title = String(rawTitle || "").trim();
  if (!title) {
    state.chatError = "La etiqueta del hilo no puede quedar vacia.";
    renderChatMessages();
    return;
  }
  state.chatThreadBusyKey = `rename:${threadId}`;
  renderChatThreads();
  try {
    const updated = await fetchJson(`/chat/threads/${encodeURIComponent(threadId)}`, {
      method: "PATCH",
      auth: true,
      body: JSON.stringify({ title })
    });
    state.chatThreads = sortChatThreads(
      (state.chatThreads || []).map((thread) =>
        String(thread.id) === String(threadId) ? updated : thread
      )
    );
    state.chatEditingThreadId = null;
    state.chatEditingTitle = "";
    state.chatError = null;
  } catch (error) {
    state.chatError = error.message || String(error);
  } finally {
    state.chatThreadBusyKey = null;
    renderChatThreads();
    renderChatMessages();
  }
}

async function deleteChatThread(threadId) {
  if (!state.accessToken || !threadId) return;
  const thread = (state.chatThreads || []).find((item) => String(item.id) === String(threadId));
  const title = thread && thread.title ? thread.title : "esta conversación";
  const confirmed = window.confirm(`Vas a borrar "${title}". Esta acción no se puede deshacer.`);
  if (!confirmed) return;

  state.chatThreadBusyKey = `delete:${threadId}`;
  renderChatThreads();
  try {
    await fetchJson(`/chat/threads/${encodeURIComponent(threadId)}`, {
      method: "DELETE",
      auth: true
    });
    state.chatThreads = (state.chatThreads || []).filter((item) => String(item.id) !== String(threadId));
    const deletedActive = String(state.chatCurrentThreadId) === String(threadId);
    if (deletedActive) {
      const nextThread = state.chatThreads[0] || null;
      if (nextThread) {
        state.chatCurrentThreadId = nextThread.id;
        window.localStorage.setItem(CHAT_THREAD_KEY, String(nextThread.id));
        state.chatMessages = [];
        renderChatMessages();
        await loadChatMessages(nextThread.id);
      } else {
        state.chatCurrentThreadId = null;
        state.chatMessages = [];
        window.localStorage.removeItem(CHAT_THREAD_KEY);
      }
    }
    if (String(state.chatEditingThreadId) === String(threadId)) {
      state.chatEditingThreadId = null;
      state.chatEditingTitle = "";
    }
    state.chatError = null;
  } catch (error) {
    state.chatError = error.message || String(error);
  } finally {
    state.chatThreadBusyKey = null;
    renderChatThreads();
    renderChatMessages();
  }
}

async function sendChatMessage(content) {
  const trimmed = String(content || "").trim();
  if (!trimmed || state.chatSending) return;
  if (!state.accessToken) return;

  // Ensure a thread exists before sending.
  if (!state.chatCurrentThreadId) {
    const created = await createChatThread(trimmed.slice(0, 60));
    if (!created) return;
  }

  state.chatError = null;
  state.chatSending = true;
  state.chatRequestId += 1;
  const requestId = state.chatRequestId;
  const optimisticId = `local-${requestId}`;

  // Optimistic user-message append.
  state.chatMessages = [
    ...state.chatMessages,
    {
      id: optimisticId,
      role: "user",
      content: trimmed,
      provider: state.chatCurrentProvider,
      created_at: new Date().toISOString()
    }
  ];
  renderChatMessages();

  try {
    const payload = {
      role: "user",
      content: trimmed
    };
    if (state.chatCurrentProvider) payload.provider = state.chatCurrentProvider;
    const response = await fetchJson(`/chat/threads/${encodeURIComponent(state.chatCurrentThreadId)}/messages`, {
      method: "POST",
      auth: true,
      body: JSON.stringify(payload)
    });
    if (requestId !== state.chatRequestId) return;
    if (response && response.user_message) {
      state.chatMessages = state.chatMessages.map((message) =>
        String(message.id) === optimisticId ? response.user_message : message
      );
    }
    if (response && response.assistant_message) {
      state.chatMessages = [...state.chatMessages, response.assistant_message];
    }
    // Refresh usage in the background — don't block the UI.
    refreshChatUsage();
  } catch (error) {
    if (requestId === state.chatRequestId) {
      state.chatError = error.message || String(error);
    }
  } finally {
    if (requestId === state.chatRequestId) {
      state.chatSending = false;
    }
    renderChatMessages();
  }
}

async function refreshChatUsage() {
  try {
    const usage = await fetchJson("/chat/usage", { auth: true });
    state.chatUsage = usage || null;
    renderChatUsage();
  } catch (error) {
    // Non-fatal — usage stays stale.
  }
}

function handleChatFormSubmit(event) {
  event.preventDefault();
  const input = chatEl("chat-input");
  if (!input) return;
  const value = input.value;
  if (!value.trim()) return;
  input.value = "";
  autoGrowChatInput(input);
  sendChatMessage(value);
}

function autoGrowChatInput(input) {
  if (!input) return;
  input.style.height = "auto";
  // Grow up to ~6 rows (matching CSS max-height: 168px).
  const next = Math.min(input.scrollHeight, 168);
  input.style.height = `${next}px`;
}

// Bind events on container elements that exist on first DOM load. Idempotent.
let _chatEventsBound = false;
function bindChatEventsOnce() {
  if (_chatEventsBound) return;
  _chatEventsBound = true;
  bindChatPanelEvents();
}

function bindChatPanelEvents() {
  const newBtn = chatEl("chat-new-thread");
  if (newBtn && !newBtn.dataset.bound) {
    newBtn.dataset.bound = "1";
    newBtn.addEventListener("click", () => createChatThread());
  }
  const form = chatEl("chat-composer");
  if (form && !form.dataset.bound) {
    form.dataset.bound = "1";
    form.addEventListener("submit", handleChatFormSubmit);
  }
  const input = chatEl("chat-input");
  if (input && !input.dataset.bound) {
    input.dataset.bound = "1";
    input.addEventListener("input", () => autoGrowChatInput(input));
    input.addEventListener("keydown", (event) => {
      // Submit on Enter (without Shift) — standard chat UX.
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleChatFormSubmit(event);
      }
    });
  }
}

function glossaryCategories() {
  return Array.from(new Set(GLOSSARY_TERMS.map((term) => term.category))).sort((left, right) =>
    left.localeCompare(right, "es")
  );
}

function normalizeSearchValue(value) {
  return String(value || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function collapseSearchValue(value) {
  return normalizeSearchValue(value).replace(/[^a-z0-9]+/g, "");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function wrapLearningMatches(text, pattern) {
  pattern.lastIndex = 0;
  let cursor = 0;
  let match;
  const fragments = [];
  let found = false;

  while ((match = pattern.exec(text)) !== null) {
    const hit = match[0];
    const start = match.index;
    const end = start + hit.length;
    if (start === end) {
      pattern.lastIndex += 1;
      continue;
    }
    fragments.push(escapeText(text.slice(cursor, start)));
    fragments.push(`<mark class="learning-highlight">${escapeText(hit)}</mark>`);
    cursor = end;
    found = true;
  }

  if (!found) return null;
  fragments.push(escapeText(text.slice(cursor)));
  return fragments.join("");
}

function highlightLearningText(value, query) {
  const text = String(value ?? "");
  const rawQuery = String(query || "").trim();
  if (!rawQuery) return escapeText(text);

  const exactPattern = new RegExp(escapeRegExp(rawQuery), "ig");
  const exactHit = wrapLearningMatches(text, exactPattern);
  if (exactHit) return exactHit;

  const collapsedQuery = collapseSearchValue(rawQuery);
  if (collapsedQuery) {
    const fuzzyPattern = new RegExp(
      collapsedQuery.split("").map((char) => escapeRegExp(char)).join("[^a-zA-Z0-9]*"),
      "ig"
    );
    const fuzzyHit = wrapLearningMatches(text, fuzzyPattern);
    if (fuzzyHit) return fuzzyHit;
  }

  return escapeText(text);
}

function matchesLearningQuery(term, query) {
  if (!query) return true;
  const normalizedQuery = normalizeSearchValue(query);
  const collapsedQuery = collapseSearchValue(query);
  const haystacks = [
    term.label,
    term.category,
    term.short,
    term.detail,
    ...(Array.isArray(term.keywords) ? term.keywords : [])
  ];
  return haystacks.some((value) => {
    const normalizedValue = normalizeSearchValue(value);
    const collapsedValue = collapseSearchValue(value);
    return normalizedValue.includes(normalizedQuery) || (collapsedQuery && collapsedValue.includes(collapsedQuery));
  });
}

function renderGlossary() {
  // Glossary data is lazy-loaded. If it isn't ready yet (first time the
  // user opens Learning), kick off the fetch + show a quick skeleton and
  // re-render once it lands.
  if (!GLOSSARY_TERMS.length) {
    if (elements.learningGrid) {
      elements.learningGrid.innerHTML = `
        <article class="learning-empty-state">
          <strong>Cargando diccionario…</strong>
          <p>Estamos trayendo todos los conceptos. Demora menos de un segundo.</p>
        </article>
      `;
    }
    ensureGlossaryLoaded().then(() => renderGlossary());
    return;
  }
  const categories = glossaryCategories();
  const categoryTerms = state.learningFilter === "all"
    ? GLOSSARY_TERMS
    : GLOSSARY_TERMS.filter((term) => term.category === state.learningFilter);
  const visibleTerms = categoryTerms.filter((term) => matchesLearningQuery(term, state.learningQuery));
  const categoryCounts = new Map();
  GLOSSARY_TERMS.forEach((term) => {
    categoryCounts.set(term.category, (categoryCounts.get(term.category) || 0) + 1);
  });

  elements.learningFilters.innerHTML = [
    { key: "all", label: "Todos", count: GLOSSARY_TERMS.length },
    ...categories.map((category) => ({ key: category, label: category, count: categoryCounts.get(category) || 0 }))
  ]
    .map(
      (item) => `
        <button
          type="button"
          class="learning-filter-pill ${state.learningFilter === item.key ? "is-selected" : ""}"
          data-learning-filter="${escapeAttribute(item.key)}"
          aria-pressed="${state.learningFilter === item.key ? "true" : "false"}"
        >
          <span>${escapeText(item.label)}</span>
          <strong>${item.count}</strong>
        </button>
      `
    )
    .join("");

  if (elements.learningSearchInput && elements.learningSearchInput.value !== state.learningQuery) {
    elements.learningSearchInput.value = state.learningQuery;
  }
  elements.learningSearchClear.classList.toggle("is-hidden", !state.learningQuery.trim());

  const scopeLabel = state.learningFilter === "all"
    ? "todo el diccionario"
    : `la categoría ${state.learningFilter}`;
  const queryLabel = state.learningQuery.trim()
    ? ` para "${state.learningQuery.trim()}"`
    : "";
  elements.learningMeta.textContent = `Mostrando ${visibleTerms.length} conceptos de ${scopeLabel}${queryLabel}.`;

  if (!visibleTerms.length) {
    elements.learningGrid.innerHTML = `
      <article class="learning-empty-state">
        <strong>Sin conceptos para esta búsqueda.</strong>
        <p>Probá cambiar el filtro o buscar con otra palabra, por ejemplo "P/E", "short", "ATR" o "earnings".</p>
      </article>
    `;
    return;
  }

  elements.learningGrid.innerHTML = visibleTerms.map(
    (term) => `
      <article class="learning-card ${state.learningQuery.trim() ? "is-query-active" : ""}">
        <div class="learning-head">
          <div>
            <p class="analysis-kicker">${highlightLearningText(term.category, state.learningQuery)}</p>
            <h3>${highlightLearningText(term.label, state.learningQuery)}</h3>
          </div>
        </div>
        <p class="learning-short">${highlightLearningText(term.short, state.learningQuery)}</p>
        <p class="learning-detail">${highlightLearningText(term.detail, state.learningQuery)}</p>
      </article>
    `
  ).join("");
}

function setLearningFilter(filter) {
  state.learningFilter = filter;
  ensureLearningReady();
  renderGlossary();
}

function setLearningQuery(query) {
  state.learningQuery = String(query || "");
  ensureLearningReady();
  renderGlossary();
}

function authHeaders(required = false) {
  if (!state.accessToken) {
    if (required) {
      throw new Error("Necesitás iniciar sesión.");
    }
    return {};
  }
  return { Authorization: `Bearer ${state.accessToken}` };
}

function formatErrorDetail(detail) {
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const path = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
          const message = item.msg || item.message || JSON.stringify(item);
          return path ? `${path}: ${message}` : String(message);
        }
        return String(item);
      })
      .filter(Boolean);
    return messages.join(" · ");
  }
  if (detail && typeof detail === "object") {
    return detail.detail || detail.message || JSON.stringify(detail);
  }
  return String(detail);
}

const FETCH_TIMEOUT_MS = 90_000;

async function fetchJson(path, options = {}) {
  const { auth = false, headers = {}, signal: externalSignal, ...rest } = options;

  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), FETCH_TIMEOUT_MS);

  // Combine external abort signal (e.g. from analyzeTicker) with the timeout.
  const signals = [timeoutController.signal];
  if (externalSignal) signals.push(externalSignal);
  const signal = signals.length > 1 && AbortSignal.any ? AbortSignal.any(signals) : timeoutController.signal;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...headers,
        ...(auth ? authHeaders(true) : {})
      },
      signal,
      ...rest
    });
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === "AbortError") {
      if (timeoutController.signal.aborted && !(externalSignal && externalSignal.aborted)) {
        throw new Error("El servidor está tardando más de lo normal. Intentá de nuevo en un momento.");
      }
    }
    throw error;
  }
  clearTimeout(timeoutId);

  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      detail = body && "detail" in body ? formatErrorDetail(body.detail) : detail;
    } catch (error) {
      // Ignore invalid JSON on error paths.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

let _toastTimeout = null;
function showToast(message, { tone = "bull" } = {}) {
  let toast = document.getElementById("analysis-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "analysis-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.className = `analysis-toast tone-${tone} is-visible`;
  toast.textContent = message;
  clearTimeout(_toastTimeout);
  _toastTimeout = setTimeout(() => {
    toast.classList.remove("is-visible");
  }, 4000);
}

async function requestAiAnalysis() {
  if (!state.hasAnalyzed || !state.ticker) {
    showToast("Primero corré el setup antes de pedir la lectura AI.", { tone: "neutral" });
    return;
  }

  const cacheKey = aiAnalysisCacheKey(state.ticker, state.horizon);
  const cached = readTimedCache(aiAnalysisCache, cacheKey, AI_ANALYSIS_CACHE_TTL_MS);
  if (cached) {
    state.aiAnalysis = cached;
    state.aiAnalysisError = "";
    state.aiAnalysisLoading = false;
    renderAiAnalysisPanel();
    showToast(`Lectura AI de ${state.ticker} servida desde cache local.`, { tone: "neutral" });
    return;
  }

  const requestId = ++state.aiAnalysisRequestId;
  resetAiAnalysis();
  state.aiAnalysisLoading = true;
  renderAiAnalysisPanel();
  setButtonBusy(elements.indicatorAiButton, true, `Consultando...`);

  if (aiAnalysisAbortController) {
    aiAnalysisAbortController.abort();
  }
  aiAnalysisAbortController = new AbortController();

  try {
    const result = await fetchJson("/analyze/ai", {
      method: "POST",
      auth: Boolean(state.accessToken),
      signal: aiAnalysisAbortController.signal,
      body: JSON.stringify({
        ticker: state.ticker,
        horizon: state.horizon
      })
    });
    if (requestId !== state.aiAnalysisRequestId) return;
    state.aiAnalysis = result;
    state.aiAnalysisError = "";
    writeTimedCache(aiAnalysisCache, cacheKey, result);
    renderAiAnalysisPanel();
    showToast(`Lectura ${aiProviderLabel()} de ${state.ticker} lista.`, { tone: "bull" });
  } catch (error) {
    if (requestId !== state.aiAnalysisRequestId) return;
    if (error?.name === "AbortError") return;
    state.aiAnalysis = null;
    state.aiAnalysisError = error.message || "No se pudo completar el análisis AI.";
    renderAiAnalysisPanel();
    showToast(`No se pudo completar la lectura ${aiProviderLabel()}.`, { tone: "bear" });
  } finally {
    state.aiAnalysisLoading = false;
    if (requestId === state.aiAnalysisRequestId) {
      setButtonBusy(elements.indicatorAiButton, false);
      renderAiAnalysisPanel();
    }
    aiAnalysisAbortController = null;
  }
}

function persistSession(session) {
  state.accessToken = session.access_token;
  state.profile = session.profile;
  window.localStorage.setItem(AUTH_TOKEN_KEY, session.access_token);
}

function clearSession() {
  state.accessToken = null;
  state.profile = null;
  state.portfolioSummary = null;
  resetAiAnalysis();
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

function setAuthMode(mode, options = {}) {
  const { syncRoute = true, replaceRoute = false } = options;
  state.authMode = mode;
  const isRegister = mode === "register";
  elements.authTitle.textContent = isRegister
    ? "Creá tu usuario local para guardar portfolio"
    : "Ingresá para guardar perfil y portfolio";
  elements.authDisplayNameWrap.classList.toggle("is-hidden", !isRegister);
  elements.authPassword.setAttribute("autocomplete", isRegister ? "new-password" : "current-password");
  elements.authModeButtons.forEach((button) => {
    const isSelected = button.dataset.authMode === mode;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
  elements.authSubmit.dataset.defaultLabel = isRegister ? "Crear usuario" : "Ingresar";
  const label = elements.authSubmit.querySelector(".button-label");
  if (label) {
    label.textContent = elements.authSubmit.dataset.defaultLabel;
  }
  if (syncRoute && state.activeSurface === "access" && !(state.profile && state.accessToken)) {
    syncRouteHash({ replace: replaceRoute });
  }
}

function updatePortfolioAccessState() {
  const loggedIn = Boolean(state.profile && state.accessToken);
  if (elements.portfolioSurfaceButton) {
    elements.portfolioSurfaceButton.classList.toggle("is-hidden", !loggedIn);
  }
  if (!loggedIn && state.activeSurface === "portfolio") {
    setSurface("workspace");
  }
  if (!loggedIn && state.lastTabbedSurface === "portfolio") {
    state.lastTabbedSurface = "workspace";
  }
}

function setMiniSummaryCurrency(currency) {
  state.miniSummaryCurrency = currency === "USD" ? "USD" : "ARS";
  elements.miniSummaryCurrencyButtons.forEach((button) => {
    const isSelected = button.dataset.miniSummaryCurrency === state.miniSummaryCurrency;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
  renderMiniSummary(state.portfolioSummary);
}

function ensureLearningReady() {
  if (state.learningReady) return;
  renderGlossary();
  state.learningReady = true;
}

function renderUnauthenticated() {
  updatePortfolioAccessState();
  elements.body.dataset.loggedIn = "false";
  clearPositionEditor();
  resetPortfolioForm();
  elements.authForm.classList.remove("is-hidden");
  elements.profileShell.classList.add("is-hidden");
  elements.portfolioLockedState.classList.remove("is-hidden");
  elements.portfolioShell.classList.add("is-hidden");
  elements.portfolioEmptySummary.classList.add("is-hidden");
  elements.portfolioEmptyHoldings.classList.add("is-hidden");
  setPortfolioView("summary");
  if (elements.benchmarkPanel) {
    elements.benchmarkPanel.classList.add("is-hidden");
  }
  if (elements.benchmarkBars) {
    elements.benchmarkBars.innerHTML = "";
  }
  elements.miniSummaryGrid.innerHTML = `
    <div class="metric-tile">
      <span class="metric-label">Estado</span>
      <span class="metric-value">Bloqueado</span>
    </div>
    <div class="metric-tile">
      <span class="metric-label">Moneda</span>
      <span class="metric-value">ARS</span>
    </div>
  `;
  elements.portfolioSummaryGrid.innerHTML = "";
  elements.holdingsGrid.innerHTML = "";
  renderPortfolioEarningsLocked();
  renderAccountChrome();
  setAuthStatus("Podés entrar o registrarte sin mail.");
  setPortfolioImportStatus("Iniciá sesión para importar tu extracto de Balanz.");
}

function hydrateProfile(profile) {
  elements.profileUsername.textContent = `@${profile.username}`;
  elements.profileDisplayName.value = profile.display_name;
  elements.profileInvestorProfile.value = profile.investor_profile;
  elements.profilePreferredHorizon.value = profile.preferred_horizon;
  elements.profilePreferredInstruments.value = profile.preferred_instrument_types;
  elements.profileRiskTolerance.value = profile.risk_tolerance;
  elements.profileBenchmarkPreference.value = profile.benchmark_preference;
}

function renderAuthenticated() {
  updatePortfolioAccessState();
  elements.body.dataset.loggedIn = "true";
  clearPositionEditor();
  elements.authForm.classList.add("is-hidden");
  elements.profileShell.classList.remove("is-hidden");
  elements.portfolioLockedState.classList.add("is-hidden");
  elements.portfolioShell.classList.remove("is-hidden");
  hydrateProfile(state.profile);
  renderAccountChrome();
  setAuthStatus(`Sesión activa para ${state.profile.username}.`);
  setPortfolioImportStatus("Podés importar un extracto de Balanz o seguir cargando posiciones manualmente.");
}

function renderMiniSummary(summary) {
  if (!summary || !summary.positions_count) {
    elements.miniSummaryGrid.innerHTML = `
      <div class="metric-tile">
        <span class="metric-label">Posiciones</span>
        <span class="metric-value">0</span>
      </div>
      <div class="metric-tile">
        <span class="metric-label">Benchmark</span>
        <span class="metric-value">${state.profile?.benchmark_preference?.toUpperCase() || "MEP"}</span>
      </div>
    `;
    return;
  }

  const pnlLabel = state.miniSummaryCurrency === "USD" ? "P&amp;L USD" : "P&amp;L ARS";
  const pnlValue = state.miniSummaryCurrency === "USD"
    ? formatCurrency(summary.total_pnl_usd, "USD")
    : formatCurrency(summary.total_pnl_ars, "ARS");

  elements.miniSummaryGrid.innerHTML = [
    ["Posiciones", summary.positions_count],
    [pnlLabel, pnlValue]
  ]
    .map(
      ([label, value]) => `
        <div class="metric-tile">
          <span class="metric-label">${label}</span>
          <span class="metric-value">${value}</span>
        </div>
      `
    )
    .join("");
}

function renderWorkspaceIdle() {
  state.hasAnalyzed = false;
  resetAiAnalysis();
  elements.workspaceTitle.textContent = `Ticker seleccionado: ${state.ticker}`;
  setWorkspaceName(state.ticker);
  elements.marketChip.textContent = `${titleCaseHorizon(state.horizon)} · Radar listo`;
  elements.verdictGrid.innerHTML = `
    <article class="verdict-card">
      <p class="analysis-kicker">Estado</p>
      <div class="verdict-value neutral">Listo</div>
    </article>
    <article class="verdict-card">
      <p class="analysis-kicker">Siguiente paso</p>
      <div class="verdict-value neutral">Elegí un ticker</div>
    </article>
  `;
  elements.deterministicTitle.textContent = "Todavía no corriste el análisis.";
  elements.deterministicReasons.innerHTML = "<li>Elegí una card del radar o escribí un ticker para disparar el motor completo.</li>";
  elements.probabilisticTitle.textContent = "El análisis probabilístico aparece cuando corrés un ticker.";
  elements.scenarioStack.innerHTML = "";
  elements.probabilisticWarnings.innerHTML = "";
  elements.validationTitle.textContent = "Sin validación para mostrar";
  elements.validationGrid.innerHTML = "";
  elements.backtestTitle.textContent = "Sin backtest para mostrar";
  elements.backtestGrid.innerHTML = "";
  elements.actionMatrix.innerHTML = `
    <button type="button" class="action-tile is-primary">
      <div class="verdict-stat">
        <strong class="neutral">Seleccionar</strong>
        <span class="tone-chip">Radar</span>
      </div>
      <p>Usá el ranking de arriba o el buscador para correr el análisis consolidado.</p>
    </button>
  `;
  elements.catalystList.innerHTML = "<li>Los catalysts aparecen una vez que elijas un ticker.</li>";
  elements.guardrailList.innerHTML = "<li>Los guardrails se calculan junto con el análisis.</li>";
  renderContextPlaceholder(elements.marketOverviewGrid, {
    title: "Market regime en espera",
    body: "Se carga cuando analizás un ticker.",
    tone: "neutral"
  });
  elements.marketOverviewTitle.textContent = "Tape general en espera";
  elements.marketOverviewChip.textContent = "Idle";
  elements.marketOverviewSummary.textContent = "No corremos contexto externo hasta que elijas un activo para mantener el primer render ágil.";
  elements.marketOverviewWarnings.innerHTML = "";
  renderContextPlaceholder(elements.newsFeed, {
    title: "News tape en espera",
    body: "Los titulares llegan cuando dispares el análisis.",
    tone: "neutral"
  });
  elements.newsTitle.textContent = "Sin titulares cargados";
  elements.newsChip.textContent = "Idle";
  renderContextPlaceholder(elements.tickerEarningsFeed, {
    title: "Earnings en espera",
    body: "El calendario del ticker se consulta recién cuando elegís un activo.",
    tone: "neutral"
  });
  elements.earningsTitle.textContent = "Sin calendario cargado";
  renderAiAnalysisPanel();
  syncSelection();
}

async function bootstrapSession(options = {}) {
  const { refreshRankings = true } = options;
  if (!state.accessToken) {
    renderUnauthenticated();
    return;
  }

  try {
    const profile = await fetchJson("/profile", { auth: true });
    state.profile = profile;
    renderAuthenticated();
    if (refreshRankings) {
      await loadRankings();
    }
    await loadPortfolioSummary();
  } catch (error) {
    clearSession();
    renderUnauthenticated();
    setAuthStatus(`La sesión previa no fue válida: ${error.message}`);
  }
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const payload = {
    username: elements.authUsername.value.trim(),
    password: elements.authPassword.value
  };
  if (state.authMode === "register") {
    payload.display_name = elements.authDisplayName.value.trim() || payload.username;
  }

  if (payload.username.length < 3) {
    setAuthStatus("El username necesita al menos 3 caracteres.");
    elements.authUsername.focus();
    return;
  }
  if (payload.password.length < 6) {
    setAuthStatus("La password necesita al menos 6 caracteres.");
    elements.authPassword.focus();
    return;
  }

  setButtonBusy(elements.authSubmit, true, state.authMode === "register" ? "Creando..." : "Ingresando...");
  try {
    const path = state.authMode === "register" ? "/auth/register" : "/auth/login";
    const session = await fetchJson(path, {
      method: "POST",
      body: JSON.stringify(payload)
    });
    persistSession(session);
    renderAuthenticated();
    setPortfolioView("summary");
    setSurface("portfolio");
    setAuthStatus(state.authMode === "register" ? "Usuario creado y sesión iniciada." : "Sesión iniciada.");
    elements.authPassword.value = "";
    Promise.allSettled([loadRankings(), loadPortfolioSummary()]).catch(() => {
      // Individual loaders already publish their own UI errors.
    });
    // Show onboarding only on fresh registration or first-ever login on this device.
    if (state.authMode === "register") maybeShowOnboarding();
  } catch (error) {
    setAuthStatus(`No se pudo completar el acceso: ${error.message}`);
  } finally {
    setButtonBusy(elements.authSubmit, false);
  }
}

async function handleProfileSubmit(event) {
  event.preventDefault();
  const submitButton = elements.profileForm.querySelector(".primary-button");
  setButtonBusy(submitButton, true, "Guardando...");
  try {
    const profile = await fetchJson("/profile", {
      auth: true,
      method: "PUT",
      body: JSON.stringify({
        display_name: elements.profileDisplayName.value.trim(),
        investor_profile: elements.profileInvestorProfile.value,
        preferred_horizon: elements.profilePreferredHorizon.value,
        preferred_instrument_types: elements.profilePreferredInstruments.value,
        risk_tolerance: elements.profileRiskTolerance.value,
        benchmark_preference: elements.profileBenchmarkPreference.value
      })
    });
    state.profile = profile;
    renderAuthenticated();
    await loadRankings();
    await loadPortfolioSummary();
    setAuthStatus("Perfil actualizado.");
  } catch (error) {
    setAuthStatus(`No se pudo guardar el perfil: ${error.message}`);
  } finally {
    setButtonBusy(submitButton, false);
  }
}

async function handleLogout() {
  try {
    await fetchJson("/auth/logout", {
      auth: true,
      method: "POST"
    });
  } catch (error) {
    // Best effort logout.
  }
  clearSession();
  renderUnauthenticated();
  await loadRankings();
  setSurface("workspace");
}

function setInstrumentType(type) {
  state.instrumentType = type;
  elements.instrumentButtons.forEach((button) => {
    const isSelected = button.dataset.instrumentType === type;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
  const currency = type === "cedear" ? "ARS" : "USD";
  elements.positionPurchaseCurrency.value = currency;
}

function resetPortfolioForm() {
  elements.portfolioForm.reset();
  setInstrumentType("cedear");
}

function clearPositionEditor() {
  state.editingPositionId = null;
  if (elements.positionEditorShell) {
    elements.positionEditorShell.classList.add("is-hidden");
  }
  if (elements.positionEditorTitle) {
    elements.positionEditorTitle.textContent = "Editando una posición";
  }
  const submitLabel = elements.portfolioForm.querySelector(".button-label");
  if (submitLabel) {
    submitLabel.textContent = "Agregar posición";
  }
}

function beginPositionEdit(positionId) {
  if (!state.portfolioSummary || !Array.isArray(state.portfolioSummary.positions)) return;
  const position = state.portfolioSummary.positions.find((item) => String(item.position_id) === String(positionId));
  if (!position) return;

  state.editingPositionId = Number(position.position_id);
  setPortfolioView("load");
  setSurface("portfolio");
  if (elements.positionEditorShell) {
    elements.positionEditorShell.classList.remove("is-hidden");
  }
  if (elements.positionEditorTitle) {
    elements.positionEditorTitle.textContent = `${position.symbol} · ${toHeadline(position.instrument_type)}`;
  }
  const submitLabel = elements.portfolioForm.querySelector(".button-label");
  if (submitLabel) {
    submitLabel.textContent = "Guardar cambios";
  }

  setInstrumentType(position.instrument_type);
  elements.positionSymbol.value = position.symbol || "";
  elements.positionQuantity.value = position.quantity ?? "";
  elements.positionPurchaseDate.value = position.purchase_date || "";
  elements.positionPurchasePrice.value = position.purchase_price ?? "";
  elements.positionPurchaseCurrency.value = position.purchase_currency || (position.instrument_type === "cedear" ? "ARS" : "USD");
  elements.positionUnderlying.value = position.underlying_ticker || "";
  elements.positionRatio.value = position.cedear_ratio ?? "";
  elements.positionNotes.value = position.user_notes || "";
  setPortfolioStatus(`Editando ${position.symbol}. Guardá cambios o cancelá.`);
  window.requestAnimationFrame(() => {
    elements.positionSymbol.focus();
    elements.portfolioForm.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
}

async function loadPortfolioSummary() {
  if (!state.accessToken) {
    return;
  }

  setPortfolioStatus("Actualizando portfolio...");
  if (!state.portfolioSummary && elements.portfolioSummaryGrid) {
    elements.portfolioSummaryGrid.innerHTML = `
      <article class="portfolio-hero-summary is-skeleton" aria-hidden="true">
        <div class="portfolio-skeleton-hero"></div>
        <div class="portfolio-skeleton-satellites">
          <div class="portfolio-skeleton-sat"></div>
          <div class="portfolio-skeleton-sat"></div>
          <div class="portfolio-skeleton-sat"></div>
        </div>
      </article>
    `;
  }
  try {
    const summary = await fetchJson("/portfolio/summary", { auth: true });
    state.portfolioSummary = summary;
    // Quick visibility into the math so the user (and us) can sanity-check
    // numbers without opening devtools network panel. The implied FX should
    // closely match the CCL/MEP — if it doesn't, something is off in the
    // valuation path.
    const valArs = Number(summary.total_value_ars) || 0;
    const valUsd = Number(summary.total_value_usd) || 0;
    const impliedFx = valUsd ? valArs / valUsd : 0;
    console.info(
      `[portfolio] positions=${summary.positions_count} · ARS=${valArs.toLocaleString("es-AR")} · USD=${valUsd.toLocaleString("es-AR")} · implied FX=${impliedFx.toFixed(1)}`
    );
    renderPortfolioSummary(summary);
    renderMiniSummary(summary);
    await loadPortfolioEarningsWatch();
    // Banner uses the user's own holdings to prioritize "tickers tuyos primero".
    const heldSymbols = (summary.positions || []).map((p) => p.underlying_ticker || p.symbol);
    refreshEarningsBanner(heldSymbols);
    setPortfolioStatus(
      summary.positions_count
        ? `Portfolio actualizado con benchmark ${state.profile.benchmark_preference.toUpperCase()}.`
        : "Aún no cargaste posiciones."
    );
  } catch (error) {
    renderPortfolioEarningsError(error.message);
    setPortfolioStatus(`No se pudo cargar el portfolio: ${error.message}`);
  }
}

function renderPortfolioSummary(summary) {
  refreshFxDiagnostic(summary);

  if (!summary.positions_count) {
    elements.portfolioEmptySummary.classList.remove("is-hidden");
    elements.portfolioEmptyHoldings.classList.remove("is-hidden");
    elements.portfolioSummaryGrid.innerHTML = "";
    elements.holdingsGrid.innerHTML = "";
    renderBenchmarkBars(summary);
    renderExposureCards(summary);
    return;
  }

  elements.portfolioEmptySummary.classList.add("is-hidden");
  elements.portfolioEmptyHoldings.classList.add("is-hidden");

  // Hero summary — one protagonist number + satellites with semantic color.
  // Editorial typography pass: replaced 6 equal-weight tiles with a clear
  // hierarchy. The hero is the ARS value (the user thinks in pesos primarily);
  // the satellites carry USD and the P&L direction with bull/bear coloring.
  const totalReturnPct = summary.total_return_pct_ars || 0;
  const realReturnPct = summary.total_real_return_pct || 0;
  const pnlArsTone = toneOf(summary.total_pnl_ars);
  const pnlUsdTone = toneOf(summary.total_pnl_usd);
  const realTone = toneOf(realReturnPct);
  const ratioCoverage = summarizeCedearRatioCoverage(summary.positions);
  const ratioCoverageBlock = ratioCoverage.total
    ? `
        <div class="satellite satellite-ratio-audit">
          <span class="satellite-label">Ratios CEDEAR</span>
          <strong class="satellite-value tone-${ratioCoverage.tone}">${ratioCoverage.verified}/${ratioCoverage.total} validados</strong>
          <span class="satellite-subcopy">${escapeText(ratioCoverage.detail || "Todos los ratios tienen origen trazable.")}</span>
        </div>
      `
    : "";

  elements.portfolioSummaryGrid.innerHTML = `
    <article class="portfolio-hero-summary">
      <div class="portfolio-hero-main">
        <p class="analysis-kicker">Valor consolidado</p>
        <h2 class="portfolio-hero-value" title="${formatMoney(summary.total_value_ars, "ARS")}">
          ${formatMoney(summary.total_value_ars, "ARS", { magnitude: true })}
        </h2>
        <p class="portfolio-hero-meta">
          <span class="hero-meta-chip tone-${toneOf(totalReturnPct)}">${formatPercent(totalReturnPct, { signed: true })} vs cost basis</span>
          <span class="hero-meta-divider" aria-hidden="true">·</span>
          <span>${summary.positions_count} posiciones</span>
        </p>
      </div>
      <div class="portfolio-hero-satellites">
        <div class="satellite">
          <span class="satellite-label">Valor USD</span>
          <strong class="satellite-value">${formatMoney(summary.total_value_usd, "USD")}</strong>
        </div>
        <div class="satellite">
          <span class="satellite-label">P&amp;L ARS</span>
          <strong class="satellite-value tone-${pnlArsTone}">${formatMoney(summary.total_pnl_ars, "ARS", { magnitude: true, signed: true })}</strong>
        </div>
        <div class="satellite">
          <span class="satellite-label">P&amp;L USD</span>
          <strong class="satellite-value tone-${pnlUsdTone}">${formatMoney(summary.total_pnl_usd, "USD", { signed: true })}</strong>
        </div>
        <div class="satellite satellite-real">
          <span class="satellite-label">Real vs inflación</span>
          <strong class="satellite-value tone-${realTone}">${formatPercent(realReturnPct, { signed: true })}</strong>
          <div class="real-return-bar" role="presentation">
            <div class="real-return-bar-fill tone-${realTone}" style="width:${Math.min(Math.abs(realReturnPct) * 100 * 4, 100).toFixed(2)}%"></div>
          </div>
        </div>
        ${ratioCoverageBlock}
      </div>
    </article>
  `;

  renderBenchmarkBars(summary);
  renderExposureCards(summary);

  elements.holdingsGrid.innerHTML = summary.positions
    .map((position) => {
      const inflation = position.benchmark_comparisons.find((item) => item.label === "inflation");
      const plazoFijo = position.benchmark_comparisons.find((item) => item.label === "plazo_fijo");
      const ccl = position.benchmark_comparisons.find((item) => item.label === "ccl_usd");
      // Effective US shares — how many real underlying shares this CEDEAR
      // position represents. Surfacing this defuses confusion when the user
      // sees "159 NVDA CEDEARs" but knows NVDA trades at $130 (which would
      // imply ~$20k if you treated CEDEARs as 1:1 instead of 20:1).
      const ratio = Number(position.cedear_ratio) || 1;
      const effectiveShares = position.instrument_type === "cedear" && ratio > 0
        ? position.quantity / ratio
        : null;
      const ratioSourceLabel = cedearRatioSourceMeta(position.cedear_ratio_source);

      const ratioLine = position.cedear_ratio
        ? `
          <div class="ratio-chip-stack">
            <span class="tone-chip">Ratio ${position.cedear_ratio}:1</span>
            <span class="ratio-source-chip tone-${ratioSourceLabel.tone}" title="${escapeText(ratioSourceLabel.label)}">${escapeText(ratioSourceLabel.shortLabel)}</span>
          </div>
        `
        : "";

      const effectiveSharesLine = effectiveShares !== null
        ? `<p class="effective-shares-line">
             <span>Equivale a</span>
             <strong>${effectiveShares.toLocaleString("es-AR", { maximumFractionDigits: 3 })}</strong>
             <span>acciones de ${escapeText(position.underlying_ticker)}</span>
           </p>`
        : "";

      const noteList = position.notes.length
        ? `<ul class="warning-list compact-list">${position.notes.map((note) => `<li>${escapeText(note)}</li>`).join("")}</ul>`
        : "";
      const userNotesBlock = position.user_notes
        ? `<p class="panel-caption">${escapeText(position.user_notes)}</p>`
        : "";
      const dailyChangePct = position.change_pct_1d || 0;
      const dailyChangeTone = dailyChangePct > 0 ? "bull" : dailyChangePct < 0 ? "bear" : "neutral";
      const dailyChangeBadge = dailyChangePct !== 0
        ? `<span class="holding-daily-badge ${dailyChangeTone}">${dailyChangePct > 0 ? "+" : ""}${(dailyChangePct * 100).toFixed(2)}% hoy</span>`
        : "";

      return `
        <article class="holding-card ${state.editingPositionId === position.position_id ? "is-editing" : ""}">
          <div class="holding-head">
            <div>
              <p class="analysis-kicker">${toHeadline(position.instrument_type)}</p>
              <h3>${escapeText(position.symbol)} ${dailyChangeBadge}</h3>
              <p class="panel-caption">${escapeText(position.underlying_ticker)} · Compra ${escapeText(position.purchase_date)}</p>
              ${effectiveSharesLine}
              ${userNotesBlock}
            </div>
            <div class="holding-actions">
              ${ratioLine}
              <div class="holding-actions-row">
                <button type="button" class="ghost-button" data-edit-position="${position.position_id}">Editar</button>
                <button type="button" class="ghost-button" data-delete-position="${position.position_id}">Eliminar</button>
              </div>
            </div>
          </div>

          <div class="holding-metrics">
            <div class="metric-tile">
              <span class="metric-label">Valor ARS</span>
              <span class="metric-value">${formatCurrency(position.current_value_ars, "ARS")}</span>
            </div>
            <div class="metric-tile">
              <span class="metric-label">Valor USD</span>
              <span class="metric-value">${formatCurrency(position.current_value_usd, "USD")}</span>
            </div>
            <div class="metric-tile">
              <span class="metric-label">P&amp;L ARS</span>
              <span class="metric-value ${position.pnl_ars >= 0 ? "bull" : "bear"}">${formatCurrency(position.pnl_ars, "ARS")}</span>
            </div>
            <div class="metric-tile">
              <span class="metric-label">P&amp;L USD</span>
              <span class="metric-value ${position.pnl_usd >= 0 ? "bull" : "bear"}">${formatCurrency(position.pnl_usd, "USD")}</span>
            </div>
            <div class="metric-tile">
              <span class="metric-label">Return nominal</span>
              <span class="metric-value">${formatPercent(position.return_pct_ars)}</span>
            </div>
            <div class="metric-tile">
              <span class="metric-label">Return real</span>
              <span class="metric-value ${position.real_return_pct >= 0 ? "bull" : "bear"}">${formatPercent(position.real_return_pct)}</span>
            </div>
          </div>

          <div class="comparison-chips">
            ${renderComparisonChip("Inflación", inflation)}
            ${renderComparisonChip("Plazo fijo", plazoFijo)}
            ${renderComparisonChip("CCL", ccl)}
          </div>
          ${noteList}
        </article>
      `;
    })
    .join("");
}

const BENCHMARK_LABELS = {
  official_usd: "Oficial",
  mep_usd: "MEP",
  ccl_usd: "CCL",
  inflation: "Inflación",
  plazo_fijo: "Plazo Fijo"
};

const BENCHMARK_GLYPHS = {
  __portfolio: "📈",
  official_usd: "💵",
  mep_usd: "💵",
  ccl_usd: "💵",
  plazo_fijo: "💸",
  inflation: "📊",
  __custom: "🎯"
};

const BENCHMARK_NARRATIVES = {
  __portfolio: (cost, current, deltaPct) =>
    `Vendiste tus pesos, los pusiste en estas acciones y hoy te quedan ${formatMoney(current, "ARS", { magnitude: true })}. Eso es ${formatPercent(deltaPct, { signed: true })} respecto a la plata que pusiste.`,
  mep_usd: (cost, tracked) =>
    `Si hubieras comprado dólar MEP en cada compra, hoy tendrías ${formatMoney(tracked, "ARS", { magnitude: true })} (convertido al MEP de hoy).`,
  ccl_usd: (cost, tracked) =>
    `Si hubieras dolarizado por CCL en cada compra y lo mantuvieras hasta hoy, tendrías ${formatMoney(tracked, "ARS", { magnitude: true })}.`,
  official_usd: (cost, tracked) =>
    `Comprar dólar oficial habría dejado ${formatMoney(tracked, "ARS", { magnitude: true })} en ARS hoy (asumiendo acceso al oficial — irreal en muchos casos).`,
  plazo_fijo: (cost, tracked) =>
    `Plazo fijo tradicional: capitalización diaria con la tasa promedio del BCRA. Hoy serían ${formatMoney(tracked, "ARS", { magnitude: true })}.`,
  inflation: (cost, tracked) =>
    `Si tus pesos hubieran solo seguido la inflación (poder de compra), hoy serían ${formatMoney(tracked, "ARS", { magnitude: true })}. Esto es el piso real, no una inversión.`
};

// Internal store of ad-hoc indicators the user added during the session.
// Persisted to localStorage so a refresh doesn't wipe their work.
const CUSTOM_BENCHMARKS_KEY = "marketBotCustomBenchmarks";
function loadCustomBenchmarks() {
  try {
    const raw = window.localStorage.getItem(CUSTOM_BENCHMARKS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (err) {
    return [];
  }
}
function saveCustomBenchmarks(list) {
  try {
    window.localStorage.setItem(CUSTOM_BENCHMARKS_KEY, JSON.stringify(list));
  } catch (err) {}
}

// ============================================================
//  Sector + region exposure cards
//  Horizontal stacked bar + colored legend chips. One palette per
//  card, derived via HSL rotation around the existing tokens so the
//  buckets stay distinguishable but still feel native to the
//  editorial theme. Up to 8 hues — anything beyond that wraps.
// ============================================================

// 8 hand-tuned HSL anchors. The first four ride the existing palette
// (citrus = bull-ish primary, bull-green, bear-orange, neutral-amber);
// the remaining four are derivations rotated around the colour wheel
// at editorial saturation so they don't fight the bull/bear cues.
const EXPOSURE_HUES = [
  "hsl(78 70% 56%)",   // citrus (anchor)
  "hsl(96 55% 55%)",   // bull green (anchor)
  "hsl(22 75% 58%)",   // bear orange (anchor)
  "hsl(42 70% 55%)",   // neutral amber (anchor)
  "hsl(192 55% 55%)",  // teal — cool, distinct from green
  "hsl(258 50% 65%)",  // soft violet — non-aggressive accent
  "hsl(340 55% 62%)",  // rose — separates from bear orange
  "hsl(168 45% 50%)"   // muted seafoam — terminates the rotation
];

function pickExposureHue(index) {
  return EXPOSURE_HUES[index % EXPOSURE_HUES.length];
}

function renderExposureChart(containerId, buckets) {
  // containerId is the BAR container id; we derive the legend id by
  // swapping the prefix. Keeps the call site terse.
  const bar = document.getElementById(containerId);
  const legendId = containerId.replace("exposure-bar-", "exposure-legend-");
  const legend = document.getElementById(legendId);
  if (!bar || !legend) return;

  const list = Array.isArray(buckets) ? buckets.filter((b) => b && b.pct > 0) : [];

  if (!list.length) {
    // Skeleton: a single dim segment + a placeholder chip. Stops the
    // card from collapsing when the portfolio is empty or all-unknown.
    bar.innerHTML = `<div class="exposure-bar-segment is-skeleton" style="flex-grow:1"></div>`;
    legend.innerHTML = `<span class="exposure-legend-item is-skeleton"><span class="exposure-legend-chip"></span><span class="exposure-legend-label">Sin datos</span></span>`;
    return;
  }

  // Build segments + legend in lockstep so colors stay in sync.
  const segments = list.map((bucket, idx) => {
    const hue = pickExposureHue(idx);
    const pctScaled = Math.max(bucket.pct * 100, 0.5); // floor so very small slices stay visible
    const titleText = `${bucket.label}: ${(bucket.pct * 100).toFixed(1)}%`;
    return `<div
      class="exposure-bar-segment"
      data-bucket-index="${idx}"
      style="flex-grow:${pctScaled};background:${hue};"
      title="${escapeHtml(titleText)}"
    ></div>`;
  }).join("");

  const legendItems = list.map((bucket, idx) => {
    const hue = pickExposureHue(idx);
    return `<span class="exposure-legend-item" data-bucket-index="${idx}">
      <span class="exposure-legend-chip" style="background:${hue};"></span>
      <span class="exposure-legend-label">${escapeHtml(bucket.label)}</span>
      <span class="exposure-legend-pct">${(bucket.pct * 100).toFixed(1)}%</span>
    </span>`;
  }).join("");

  bar.innerHTML = segments;
  legend.innerHTML = legendItems;
}

function renderExposureCards(summary) {
  if (!elements.exposureBarSector || !elements.exposureBarRegion) return;

  const sectors = Array.isArray(summary?.sector_exposure) ? summary.sector_exposure : [];
  const regions = Array.isArray(summary?.region_exposure) ? summary.region_exposure : [];

  renderExposureChart("exposure-bar-sector", sectors);
  renderExposureChart("exposure-bar-region", regions);

  // Hint line above each bar: "N sectores · top = Tech 60%".
  if (elements.exposureHintSector) {
    if (sectors.length) {
      const top = sectors[0];
      elements.exposureHintSector.textContent = `${sectors.length} sector${sectors.length === 1 ? "" : "es"} · top ${top.label} ${(top.pct * 100).toFixed(0)}%`;
    } else {
      elements.exposureHintSector.textContent = "—";
    }
  }
  if (elements.exposureHintRegion) {
    if (regions.length) {
      const top = regions[0];
      elements.exposureHintRegion.textContent = `${regions.length} región${regions.length === 1 ? "" : "es"} · top ${top.label} ${(top.pct * 100).toFixed(0)}%`;
    } else {
      elements.exposureHintRegion.textContent = "—";
    }
  }
}

// Lightweight escape — the labels come from the backend so we expect
// safe values, but defensive HTML escaping never hurts in innerHTML
// paths.
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderBenchmarkBars(summary) {
  if (!elements.benchmarkPanel || !elements.benchmarkBars) return;

  if (!summary || !summary.positions_count || !Array.isArray(summary.positions) || !summary.positions.length) {
    elements.benchmarkPanel.classList.add("is-hidden");
    elements.benchmarkBars.innerHTML = "";
    return;
  }

  // ---- Opportunity-cost framing ----
  // "Pusiste X plata hace Y días en promedio. Hoy tendrías Z en cada alternativa."
  // Aggregate per-benchmark tracked value so we can rank by what would have
  // been the best parking spot for the user's pesos.
  const aggregates = new Map();
  summary.positions.forEach((position) => {
    const comparisons = Array.isArray(position.benchmark_comparisons) ? position.benchmark_comparisons : [];
    comparisons.forEach((cmp) => {
      if (!cmp || typeof cmp.tracked_value_ars !== "number") return;
      const entry = aggregates.get(cmp.label) || { trackedArs: 0 };
      entry.trackedArs += cmp.tracked_value_ars;
      aggregates.set(cmp.label, entry);
    });
  });

  const portfolioArs = Number(summary.total_value_ars) || 0;
  const portfolioUsd = Number(summary.total_value_usd) || 0;
  const costArs = Number(summary.total_cost_ars) || 0;
  const costUsd = Number(summary.total_cost_usd) || 0;
  const pnlArs = Number(summary.total_pnl_ars) || 0;
  const portfolioReturnPct = costArs > 0 ? pnlArs / costArs : 0;

  // Compute average holding days + first/last purchase from position metadata.
  const today = new Date();
  let totalDays = 0;
  let firstDate = null;
  let lastDate = null;
  summary.positions.forEach((position) => {
    const purchased = new Date(`${position.purchase_date}T00:00:00`);
    if (Number.isNaN(purchased.getTime())) return;
    const days = Math.max(0, (today - purchased) / (1000 * 60 * 60 * 24));
    totalDays += days;
    if (!firstDate || purchased < firstDate) firstDate = purchased;
    if (!lastDate || purchased > lastDate) lastDate = purchased;
  });
  const avgDays = summary.positions.length ? totalDays / summary.positions.length : 0;

  const formatLocalDate = (d) => {
    if (!d || Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
  };

  // Build comparison rows. Portfolio sits at top as the user's actual result.
  // Below it, every benchmark = the "what if" value the user could have had.
  const benchmarkRows = Array.from(aggregates.entries())
    .filter(([label]) => BENCHMARK_LABELS[label])
    .map(([label, value]) => {
      const trackedArs = value.trackedArs;
      const deltaVsCost = costArs > 0 ? trackedArs / costArs - 1 : 0;
      return {
        key: label,
        label: BENCHMARK_LABELS[label],
        valueArs: trackedArs,
        deltaPct: deltaVsCost,
        deltaArs: trackedArs - costArs,
        tone: deltaVsCost >= 0 ? "bull" : "bear",
        narrative: BENCHMARK_NARRATIVES[label] ? BENCHMARK_NARRATIVES[label](costArs, trackedArs) : null
      };
    })
    .sort((a, b) => b.valueArs - a.valueArs);

  // Inject custom user-added benchmarks (loaded from localStorage). Each one
  // will be enriched async via a backend call — render the placeholder first.
  const customs = loadCustomBenchmarks();
  const customRows = customs.map((c) => ({
    key: `__custom__${c.ticker}`,
    label: c.label || c.ticker,
    valueArs: c.trackedArs ?? null,
    deltaPct: c.deltaPct ?? null,
    deltaArs: c.deltaArs ?? null,
    tone: c.deltaPct == null ? "anchor" : (c.deltaPct >= 0 ? "bull" : "bear"),
    custom: true,
    ticker: c.ticker,
    pending: c.trackedArs == null
  }));

  const portfolioRow = {
    key: "__portfolio",
    label: "Tu portfolio (acciones)",
    valueArs: portfolioArs,
    deltaPct: portfolioReturnPct,
    deltaArs: pnlArs,
    tone: portfolioReturnPct >= 0 ? "bull" : "bear",
    isPortfolio: true,
    narrative: BENCHMARK_NARRATIVES.__portfolio(costArs, portfolioArs, portfolioReturnPct)
  };

  // Render order: PORTFOLIO first (it's the actual result), then alternatives
  // ranked by hypothetical value descending so the user sees "best parking spot
  // first" → "what you actually did" at a glance.
  const allRows = [portfolioRow, ...benchmarkRows, ...customRows];
  const maxAbs = allRows.reduce((m, r) => Math.max(m, Math.abs(Number(r.valueArs) || 0)), 1);

  elements.benchmarkPanel.classList.remove("is-hidden");

  const rowsHtml = allRows.map((row) => renderOpportunityRow(row, maxAbs, costArs)).join("");

  elements.benchmarkBars.innerHTML = `
    <article class="opportunity-origin">
      <div class="opportunity-origin-main">
        <p class="analysis-kicker">Punto de partida</p>
        <h3 class="opportunity-origin-value">${formatMoney(costArs, "ARS", { magnitude: true })}</h3>
        <p class="opportunity-origin-meta">
          <span class="opportunity-origin-chip">${summary.positions_count} posiciones</span>
          <span class="opportunity-origin-divider" aria-hidden="true">·</span>
          <span>Promedio <strong>${Math.round(avgDays)} días</strong> en cartera</span>
          <span class="opportunity-origin-divider" aria-hidden="true">·</span>
          <span>${formatLocalDate(firstDate)} → ${formatLocalDate(lastDate)}</span>
        </p>
      </div>
      <div class="opportunity-origin-aside">
        <span class="opportunity-origin-aside-label">Equivalente en USD invertido (a la fecha de cada compra)</span>
        <strong class="opportunity-origin-aside-value">${formatMoney(costUsd, "USD")}</strong>
      </div>
    </article>

    <p class="opportunity-section-kicker">Cuánto tendrías hoy según qué hiciste con esos pesos</p>
    <ul class="opportunity-rows" role="list">
      ${rowsHtml}
    </ul>

    <article class="opportunity-custom-add" data-custom-state="idle">
      <div class="opportunity-custom-prompt">
        <span class="opportunity-custom-glyph" aria-hidden="true">🎯</span>
        <div>
          <p class="analysis-kicker">Sumá un benchmark custom</p>
          <p class="opportunity-custom-copy">¿Te preguntás qué hubiera pasado si en vez de tus acciones comprabas SPY, un FCI o cualquier otro ticker? Cargá el símbolo y lo agregamos a la comparación con la misma lógica (fecha de cada compra → valor actual).</p>
        </div>
      </div>
      <form class="opportunity-custom-form" id="opportunity-custom-form">
        <label class="opportunity-custom-field">
          <span class="metric-label">Ticker (US)</span>
          <input
            type="text"
            id="opportunity-custom-input"
            class="opportunity-custom-input"
            placeholder="SPY · VOO · BTC-USD · XAUUSD=X"
            maxlength="14"
            autocomplete="off"
            spellcheck="false"
          />
        </label>
        <button type="submit" class="primary-button opportunity-custom-submit">
          <span class="button-label">Agregar</span>
        </button>
      </form>
      <p class="opportunity-custom-hint" id="opportunity-custom-hint"></p>
    </article>
  `;

  attachOpportunityRowHandlers();
}

function renderOpportunityRow(row, maxAbs, costArs) {
  const widthPct = row.pending
    ? 6
    : Math.max(3, (Math.abs(Number(row.valueArs) || 0) / Math.max(1, maxAbs)) * 100);
  const glyph = row.custom
    ? BENCHMARK_GLYPHS.__custom
    : (BENCHMARK_GLYPHS[row.key] || "💠");
  const deltaLabel = row.pending
    ? "Calculando…"
    : formatPercent(row.deltaPct || 0, { signed: true });
  const deltaArsLabel = row.pending
    ? ""
    : `${row.deltaArs >= 0 ? "+" : "−"}${formatMoney(Math.abs(row.deltaArs), "ARS", { magnitude: true }).replace(/^-/, "").trim()}`;
  const valueLabel = row.pending
    ? "—"
    : formatMoney(row.valueArs, "ARS", { magnitude: true });

  // Detail panel shown when the row is expanded — uses grid-template-rows
  // 0fr → 1fr tween for a buttery card-resize feel (transitions.dev).
  const detailHtml = row.pending
    ? `<p class="opportunity-detail-pending">Estamos pidiéndole los precios históricos a yfinance. Si el ticker existe, en unos segundos vas a ver la comparativa.</p>`
    : `
      <div class="opportunity-detail-grid">
        <div class="opportunity-detail-tile">
          <span class="metric-label">Plata original</span>
          <strong>${formatMoney(costArs, "ARS")}</strong>
        </div>
        <div class="opportunity-detail-tile">
          <span class="metric-label">Valor hipotético hoy</span>
          <strong>${formatMoney(row.valueArs, "ARS")}</strong>
        </div>
        <div class="opportunity-detail-tile">
          <span class="metric-label">Diferencia</span>
          <strong class="tone-${row.tone}">${deltaArsLabel}</strong>
        </div>
        <div class="opportunity-detail-tile">
          <span class="metric-label">Rendimiento</span>
          <strong class="tone-${row.tone}">${deltaLabel}</strong>
        </div>
      </div>
      ${row.narrative ? `<p class="opportunity-detail-narrative">${escapeText(row.narrative)}</p>` : ""}
    `;

  return `
    <li class="opportunity-row tone-${row.tone} ${row.isPortfolio ? "is-portfolio" : ""} ${row.custom ? "is-custom" : ""}"
        data-key="${escapeText(row.key)}"
        data-expanded="false">
      <button type="button" class="opportunity-row-trigger" aria-expanded="false">
        <span class="opportunity-row-glyph" aria-hidden="true">${glyph}</span>
        <span class="opportunity-row-label">${escapeText(row.label)}</span>
        <span class="opportunity-row-value">${valueLabel}</span>
        <span class="opportunity-row-delta tone-${row.tone}">${escapeText(deltaLabel)}</span>
        <span class="opportunity-row-chevron" aria-hidden="true">▾</span>
      </button>
      <div class="opportunity-row-track" role="presentation">
        <div class="opportunity-row-fill tone-${row.tone}" style="width:${widthPct.toFixed(2)}%"></div>
      </div>
      <div class="opportunity-row-detail">
        <div class="opportunity-row-detail-inner">
          ${detailHtml}
          ${row.custom && !row.pending ? `<button type="button" class="ghost-button opportunity-remove" data-remove-custom="${escapeText(row.ticker)}">Quitar</button>` : ""}
        </div>
      </div>
    </li>
  `;
}

function attachOpportunityRowHandlers() {
  document.querySelectorAll(".opportunity-row-trigger").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const row = trigger.closest(".opportunity-row");
      const expanded = row.dataset.expanded === "true";
      row.dataset.expanded = expanded ? "false" : "true";
      trigger.setAttribute("aria-expanded", expanded ? "false" : "true");
    });
  });
  document.querySelectorAll(".opportunity-remove").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.stopPropagation();
      const ticker = btn.dataset.removeCustom;
      const current = loadCustomBenchmarks().filter((c) => c.ticker !== ticker);
      saveCustomBenchmarks(current);
      if (state.portfolioSummary) renderBenchmarkBars(state.portfolioSummary);
    });
  });
  const form = document.getElementById("opportunity-custom-form");
  if (form) {
    form.addEventListener("submit", handleOpportunityCustomSubmit);
  }
}

async function handleOpportunityCustomSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("opportunity-custom-input");
  const hint = document.getElementById("opportunity-custom-hint");
  const ticker = (input.value || "").trim().toUpperCase();
  if (!ticker) {
    if (hint) hint.textContent = "Cargá un ticker primero (ej: SPY, VOO, BTC-USD).";
    return;
  }

  const existing = loadCustomBenchmarks();
  if (existing.some((c) => c.ticker === ticker)) {
    if (hint) hint.textContent = `${ticker} ya está en la comparación.`;
    return;
  }

  // Insert pending placeholder first so the user sees feedback immediately.
  const next = [...existing, { ticker, label: ticker, trackedArs: null, deltaPct: null, deltaArs: null }];
  saveCustomBenchmarks(next);
  if (hint) hint.textContent = `Buscando ${ticker}…`;
  input.value = "";
  if (state.portfolioSummary) renderBenchmarkBars(state.portfolioSummary);

  try {
    const data = await fetchJson(`/portfolio/benchmarks/custom?ticker=${encodeURIComponent(ticker)}`, { auth: true });
    const updated = loadCustomBenchmarks().map((c) =>
      c.ticker === ticker
        ? {
            ticker,
            label: data.label || ticker,
            trackedArs: data.tracked_value_ars,
            deltaPct: data.outperformance_pct,
            deltaArs: data.outperformance_ars
          }
        : c
    );
    saveCustomBenchmarks(updated);
    if (hint) hint.textContent = `${ticker} agregado. Clickeá para ver el detalle.`;
  } catch (error) {
    // Strip the failed pending row so the user can try again.
    const cleaned = loadCustomBenchmarks().filter((c) => c.ticker !== ticker);
    saveCustomBenchmarks(cleaned);
    if (hint) hint.textContent = `No se pudo agregar ${ticker}: ${error.message}`;
  } finally {
    if (state.portfolioSummary) renderBenchmarkBars(state.portfolioSummary);
  }
}

function renderPortfolioEarningsLocked() {
  if (!elements.portfolioEarningsFeed) return;
  elements.earningsChip.textContent = "Ticker";
  renderContextPlaceholder(elements.portfolioEarningsFeed, {
    title: "Requiere sesión",
    body: "Ingresá y cargá posiciones para seguir próximos earnings de tu portfolio.",
    tone: "neutral"
  });
}

function renderPortfolioEarningsEmpty() {
  if (!elements.portfolioEarningsFeed) return;
  renderContextPlaceholder(elements.portfolioEarningsFeed, {
    title: "Sin eventos cercanos",
    body: "No aparecen earnings próximos en tu portfolio o watchlist actual.",
    tone: "neutral"
  });
}

function renderPortfolioEarningsError(message) {
  if (!elements.portfolioEarningsFeed) return;
  renderContextPlaceholder(elements.portfolioEarningsFeed, {
    title: "No se pudo cargar",
    body: message,
    tone: "error"
  });
}

// Earnings banner — sticky alert when the user has reports within the next 48h
// in tickers they hold or watch. Persists dismissal per-event in localStorage
// so closing it once doesn't make it reappear on every refresh, but a *new*
// upcoming event still surfaces.
const EARNINGS_BANNER_DISMISS_KEY = "marketBotEarningsBannerDismissed";

function dismissedEarningsKeys() {
  try {
    const raw = window.localStorage.getItem(EARNINGS_BANNER_DISMISS_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw));
  } catch (err) {
    return new Set();
  }
}

function rememberDismissedEarning(key) {
  try {
    const current = dismissedEarningsKeys();
    current.add(key);
    window.localStorage.setItem(
      EARNINGS_BANNER_DISMISS_KEY,
      JSON.stringify(Array.from(current))
    );
  } catch (err) {
    // localStorage blocked — fine, user will see the banner again next time.
  }
}

function eventDismissKey(event) {
  return `${event.ticker}::${event.report_date}::${event.report_time || ""}`;
}

function describeEarningsCountdown(event) {
  // Best-effort: most events come with a date but ambiguous TZ. We anchor to
  // local midnight of the report_date and use the report_time string only
  // as a label, not for math.
  if (!event.report_date) return null;
  const target = new Date(`${event.report_date}T16:30:00-04:00`); // approx after-hours NY
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  const diffMs = target.getTime() - now.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);
  return { target, diffHours };
}

async function refreshEarningsBanner(positionsSymbols) {
  if (!elements.earningsBanner) return;
  if (!state.accessToken) {
    elements.earningsBanner.classList.add("is-hidden");
    return;
  }

  try {
    const events = await fetchJson("/earnings/upcoming?days_ahead=7", { auth: true });
    if (!Array.isArray(events) || !events.length) {
      elements.earningsBanner.classList.add("is-hidden");
      return;
    }

    const heldSet = new Set((positionsSymbols || []).map((s) => String(s).toUpperCase()));
    const dismissed = dismissedEarningsKeys();

    // Prioritize: held tickers first, then any upcoming. Drop anything > 48h.
    const annotated = events
      .map((event) => {
        const countdown = describeEarningsCountdown(event);
        return countdown ? { event, ...countdown } : null;
      })
      .filter(
        (item) =>
          item &&
          item.diffHours > -8 &&
          item.diffHours < 48 &&
          !dismissed.has(eventDismissKey(item.event))
      )
      .sort((a, b) => {
        const aHeld = heldSet.has(a.event.ticker.toUpperCase()) ? 1 : 0;
        const bHeld = heldSet.has(b.event.ticker.toUpperCase()) ? 1 : 0;
        if (aHeld !== bHeld) return bHeld - aHeld;
        return a.diffHours - b.diffHours;
      });

    if (!annotated.length) {
      elements.earningsBanner.classList.add("is-hidden");
      return;
    }

    const next = annotated[0];
    const { event, diffHours } = next;
    const isHeld = heldSet.has(event.ticker.toUpperCase());
    const countdownLabel = formatEarningsCountdown(diffHours);
    const reportTime = event.report_time ? ` · ${event.report_time}` : "";
    const positionTag = isHeld
      ? `<span class="earnings-banner-position is-held">Tenés esta posición</span>`
      : `<span class="earnings-banner-position">No tenés posición</span>`;

    elements.earningsBannerMessage.innerHTML = `
      <strong>${escapeText(event.ticker)}</strong>
      reporta <span class="earnings-banner-when">${escapeText(countdownLabel)}</span>${escapeText(reportTime)}
      ${positionTag}
      ${
        annotated.length > 1
          ? `<span class="earnings-banner-more">+${annotated.length - 1} evento${annotated.length > 2 ? "s" : ""} más en las próximas 48h</span>`
          : ""
      }
    `;

    elements.earningsBanner.dataset.bannerKey = eventDismissKey(event);
    elements.earningsBanner.dataset.bannerTicker = event.ticker;
    elements.earningsBanner.classList.toggle("is-held", isHeld);
    elements.earningsBanner.classList.remove("is-hidden");
  } catch (error) {
    // Soft fail: the banner is enhancement, never block the rest of the UI.
    elements.earningsBanner.classList.add("is-hidden");
  }
}

function formatEarningsCountdown(diffHours) {
  if (diffHours < 0) {
    return `hoy (cerrado hace ${Math.abs(Math.round(diffHours))}h)`;
  }
  if (diffHours < 1) {
    const minutes = Math.max(1, Math.round(diffHours * 60));
    return `en ${minutes}min`;
  }
  if (diffHours < 24) {
    const hours = Math.floor(diffHours);
    const mins = Math.round((diffHours - hours) * 60);
    return mins > 0 ? `en ${hours}h ${mins}min` : `en ${hours}h`;
  }
  const days = Math.floor(diffHours / 24);
  const hours = Math.round(diffHours - days * 24);
  return hours > 0 ? `en ${days}d ${hours}h` : `en ${days}d`;
}

async function loadPortfolioEarningsWatch() {
  if (!state.accessToken) {
    renderPortfolioEarningsLocked();
    return;
  }

  elements.earningsChip.textContent = "Watchlist";
  renderContextPlaceholder(elements.portfolioEarningsFeed, {
    title: "Actualizando watchlist",
    body: "Buscando próximos earnings de tus posiciones y del universo sugerido.",
    tone: "loading"
  });

  try {
    const events = await fetchJson("/earnings/upcoming?days_ahead=60", { auth: true });
    if (!events.length) {
      renderPortfolioEarningsEmpty();
      return;
    }
    elements.portfolioEarningsFeed.innerHTML = events
      .slice(0, 6)
      .map((event) => renderEarningsEventCard(event, { compact: true }))
      .join("");
  } catch (error) {
    renderPortfolioEarningsError(error.message);
  }
}

function renderComparisonChip(label, comparison) {
  if (!comparison) return "";
  return `
    <div class="comparison-chip ${comparison.outperformance_ars >= 0 ? "is-positive" : "is-negative"}">
      <span>${label}</span>
      <strong>${formatPercent(comparison.outperformance_pct)}</strong>
    </div>
  `;
}

async function handlePortfolioSubmit(event) {
  event.preventDefault();
  const submitButton = elements.portfolioForm.querySelector(".primary-button");
  const isEditing = Number.isInteger(state.editingPositionId);
  setButtonBusy(submitButton, true, isEditing ? "Guardando..." : "Guardando...");
  try {
    const payload = {
      instrument_type: state.instrumentType,
      symbol: elements.positionSymbol.value.trim().toUpperCase(),
      quantity: Number(elements.positionQuantity.value),
      purchase_date: elements.positionPurchaseDate.value,
      purchase_price: Number(elements.positionPurchasePrice.value),
      purchase_currency: elements.positionPurchaseCurrency.value,
      underlying_ticker: elements.positionUnderlying.value.trim().toUpperCase() || null,
      cedear_ratio: elements.positionRatio.value ? Number(elements.positionRatio.value) : null,
      notes: elements.positionNotes.value.trim()
    };

    await fetchJson(isEditing ? `/portfolio/positions/${state.editingPositionId}` : "/portfolio/positions", {
      auth: true,
      method: isEditing ? "PUT" : "POST",
      body: JSON.stringify(payload)
    });
    resetPortfolioForm();
    clearPositionEditor();
    await loadPortfolioSummary();
    setPortfolioView(isEditing ? "holdings" : "summary");
    setSurface("portfolio");
    setPortfolioStatus(isEditing ? "Posición actualizada." : "Posición guardada.");
  } catch (error) {
    setPortfolioStatus(`No se pudo guardar la posición: ${error.message}`);
  } finally {
    setButtonBusy(submitButton, false);
  }
}

async function handlePortfolioImportSubmit(event) {
  event.preventDefault();
  const submitButton = elements.portfolioImportForm.querySelector(".primary-button");
  const file = elements.portfolioImportFile.files?.[0];
  if (!file) {
    setPortfolioImportStatus("Elegí un archivo `.xlsx` de Balanz antes de importar.");
    elements.portfolioImportFile.focus();
    return;
  }

  setButtonBusy(submitButton, true, "Importando...");
  setPortfolioImportStatus("Leyendo extracto de Balanz y generando posiciones...");
  try {
    const fileBuffer = await file.arrayBuffer();
    const replaceExisting = Boolean(elements.portfolioImportReplace.checked);
    const response = await fetch(
      `${API_BASE}/portfolio/import/balanz?replace_existing=${replaceExisting ? "true" : "false"}`,
      {
        method: "POST",
        headers: {
          Authorization: authHeaders(true).Authorization,
          "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        },
        body: fileBuffer
      }
    );

    if (!response.ok) {
      let detail = `Error ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch (error) {
        // Ignore invalid JSON on error paths.
      }
      throw new Error(detail);
    }

    const result = await response.json();
    const skippedPreview = Array.isArray(result.skipped_rows) && result.skipped_rows.length
      ? ` Saltadas: ${result.skipped_rows
          .slice(0, 3)
          .map((item) => `fila ${item.row_number}${item.ticker ? ` (${item.ticker})` : ""}`)
          .join(", ")}.`
      : "";
    elements.portfolioImportForm.reset();
    await loadPortfolioSummary();
    setPortfolioView("summary");
    setSurface("portfolio");
    setPortfolioImportStatus(
      `Importación lista desde ${result.source_sheet}: ${result.imported_count} posiciones agregadas, ${result.skipped_count} salteadas.${skippedPreview}`
    );
  } catch (error) {
    setPortfolioImportStatus(`No se pudo importar el extracto: ${error.message}`);
  } finally {
    setButtonBusy(submitButton, false);
  }
}

async function handleDeletePosition(positionId) {
  try {
    await fetchJson(`/portfolio/positions/${positionId}`, {
      auth: true,
      method: "DELETE"
    });
    if (Number(state.editingPositionId) === Number(positionId)) {
      resetPortfolioForm();
      clearPositionEditor();
    }
    await loadPortfolioSummary();
    setPortfolioStatus("Posición eliminada.");
  } catch (error) {
    setPortfolioStatus(`No se pudo eliminar la posición: ${error.message}`);
  }
}

async function loadUniverse() {
  const universe = await fetchJson("/universe?cedear_only=true");
  state.universe = universe.map((item) => item.ticker);
  elements.datalist.innerHTML = state.universe
    .map((ticker) => `<option value="${ticker}"></option>`)
    .join("");
}

function renderRadarSkeleton() {
  if (!elements.radarGrid) return;
  elements.radarGrid.innerHTML = Array.from({ length: 6 })
    .map(() => `
      <div class="radar-card is-skeleton" aria-hidden="true">
        <div class="radar-skeleton-chip"></div>
        <div class="radar-skeleton-title"></div>
        <div class="radar-skeleton-body"></div>
      </div>
    `)
    .join("");
}

async function loadRankings() {
  const mode = state.rankingMode === "opportunities" ? "opportunities" : "default";
  const url = `/rankings?horizon=${state.horizon}&limit=12&cedear_only=true&mode=${mode}`;
  const cacheKey = rankingsCacheKey();
  const cachedRankings = readTimedCache(rankingsCache, cacheKey, RANKINGS_CACHE_TTL_MS);
  if (!cachedRankings) {
    renderRadarSkeleton();
  }
  const rankings = cachedRankings || await fetchJson(url, {
    auth: Boolean(state.accessToken)
  });
  if (!cachedRankings) {
    writeTimedCache(rankingsCache, cacheKey, rankings);
  }
  state.radarItems = rankings;
  renderRadar();

  if (!rankings.length) {
    setStatus(
      mode === "opportunities"
        ? "No hay oportunidades activas ahora (catalysts/volúmen/volatilidad bajos). Probá el ranking completo."
        : "No hay rankings disponibles para el horizonte seleccionado."
    );
    return;
  }

  if (!rankings.some((item) => item.ticker === state.ticker)) {
    state.ticker = rankings[0].ticker;
  }
}

function setRankingMode(mode) {
  const normalized = mode === "opportunities" ? "opportunities" : "default";
  if (state.rankingMode === normalized) return;
  state.rankingMode = normalized;
  try {
    window.localStorage.setItem("marketBotRankingMode", normalized);
  } catch (err) {
    // localStorage can be blocked in private mode — ignore, mode just won't persist.
  }
  syncRankingModeButtons();
  loadRankings().catch((error) => {
    setStatus(`No se pudo recargar el ranking: ${error.message}`);
  });
}

function syncRankingModeButtons() {
  if (!elements.rankingModeButtons || !elements.rankingModeButtons.length) return;
  elements.rankingModeButtons.forEach((button) => {
    const isSelected = button.dataset.rankingMode === state.rankingMode;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-pressed", isSelected ? "true" : "false");
  });
}

async function refreshFxDiagnostic(summary) {
  if (!elements.fxDiagnosticTile) return;

  // Only show the tile if the user actually has positions — otherwise the
  // numbers are meaningless and it just adds noise to the empty state.
  if (!summary || !summary.positions_count) {
    elements.fxDiagnosticTile.classList.add("is-hidden");
    return;
  }

  try {
    const rates = await fetchJson("/benchmarks/current");
    state.currentFx = rates;
    const preference = (state.profile && state.profile.benchmark_preference) || "mep";
    const formatter = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 1 });

    elements.fxDiagnosticTile.classList.remove("is-hidden");
    elements.fxDiagnosticSource.textContent = preference.toUpperCase();
    elements.fxDiagnosticCcl.textContent = rates.ccl ? `$${formatter.format(rates.ccl)}` : "—";
    elements.fxDiagnosticMep.textContent = rates.mep ? `$${formatter.format(rates.mep)}` : "—";
    elements.fxDiagnosticOfficial.textContent = rates.official
      ? `$${formatter.format(rates.official)}`
      : "—";

    const valorArs = Number(summary.total_value_ars) || 0;
    const valorUsd = Number(summary.total_value_usd) || 0;
    if (valorUsd > 0 && valorArs > 0) {
      const implied = valorArs / valorUsd;
      const drift = rates.ccl ? Math.abs(implied - rates.ccl) / rates.ccl : 0;
      elements.fxDiagnosticImplied.textContent = `$${formatter.format(implied)}`;
      elements.fxDiagnosticImplied.classList.toggle("is-warning", drift > 0.25);
    } else {
      elements.fxDiagnosticImplied.textContent = "—";
      elements.fxDiagnosticImplied.classList.remove("is-warning");
    }
  } catch (error) {
    // Soft-fail: hide the tile if we can't fetch FX. We don't want to break
    // the portfolio view just because the benchmark service is offline.
    elements.fxDiagnosticTile.classList.add("is-hidden");
  }
}

function renderRadar() {
  if (!state.radarItems.length) {
    elements.radarGrid.innerHTML = `
      <article class="radar-card" aria-disabled="true">
        <div class="radar-card-top">
          <span class="radar-chip">Sin datos</span>
          <strong>CEDEAR only</strong>
        </div>
        <h3>No hay activos sugeridos ahora</h3>
        <p>Probá cambiar el horizonte o verificar que el API esté respondiendo.</p>
      </article>
    `;
    return;
  }

  // Hint del modo activo (qué estoy viendo).
  const hint = document.getElementById("radar-mode-hint");
  if (hint) {
    hint.textContent = state.rankingMode === "opportunities"
      ? "Solo nombres con algo pasando hoy (earnings, noticia, volumen o volatilidad). Sin índices."
      : "Todo el universo, ordenado por fuerza del setup.";
  }

  elements.radarGrid.innerHTML = state.radarItems
    .map((item, index) => {
      const action = _rankActionEs(item.action);
      const score = Math.max(0, Math.min(100, Number(item.rank_score) || 0));
      const strength = score >= 72 ? "Fuerte" : score >= 55 ? "Moderado" : "Flojo";
      const conv = Math.round((Number(item.conviction) || 0) * 100);
      const reasons = Array.isArray(item.why_for_you) ? item.why_for_you : [];
      const reasonsHtml = reasons.length
        ? `<div class="why-for-you">${reasons
            .map((reason) => `<span class="why-chip">${escapeText(reason)}</span>`)
            .join("")}</div>`
        : `<div class="why-for-you"><span class="why-chip is-muted">Setup técnico sin catalyst destacado</span></div>`;
      return `
        <button
          class="radar-card ${item.ticker === state.ticker ? "is-selected" : ""}"
          data-ticker="${escapeText(item.ticker)}"
          type="button"
          title="Tocá para ver el análisis completo de ${escapeText(item.ticker)}"
        >
          <div class="radar-card-top">
            <span class="radar-rank">#${index + 1}</span>
            <strong>${escapeText(item.ticker)}</strong>
            <span class="radar-action tone-${action.tone}">${action.label}</span>
          </div>
          ${stockName(item.ticker) ? `<p class="radar-name">${escapeText(stockName(item.ticker))}</p>` : ""}
          <div class="radar-score">
            <div class="radar-score-track"><div class="radar-score-fill tone-${action.tone}" style="width:${score.toFixed(0)}%"></div></div>
            <span class="radar-score-label">Setup ${strength} · convicción ${conv}%</span>
          </div>
          ${reasonsHtml}
        </button>
      `;
    })
    .join("");
}

// Nombre completo del activo (sin fetch; cubre el universo CEDEAR).
const STOCK_NAMES = {
  AAPL: "Apple", AMZN: "Amazon", GOOGL: "Alphabet (Google)", GOOG: "Alphabet (Google)",
  META: "Meta Platforms", MSFT: "Microsoft", NVDA: "NVIDIA", TSLA: "Tesla",
  QQQ: "Nasdaq 100 ETF", SPY: "S&P 500 ETF", DIA: "Dow Jones ETF", VOO: "Vanguard S&P 500",
  VTI: "Vanguard Total Market", GGAL: "Grupo Galicia", MELI: "Mercado Libre",
  PAM: "Pampa Energía", PBR: "Petrobras", VIST: "Vista Energy", YPF: "YPF",
  AMD: "AMD", AVGO: "Broadcom", INTC: "Intel", TSM: "Taiwan Semiconductor", ARM: "Arm Holdings",
  MU: "Micron", QCOM: "Qualcomm", SNOW: "Snowflake", PLTR: "Palantir", CRWD: "CrowdStrike",
  DDOG: "Datadog", NET: "Cloudflare", MDB: "MongoDB", ZS: "Zscaler", OKTA: "Okta",
  CRM: "Salesforce", ORCL: "Oracle", ADBE: "Adobe", COIN: "Coinbase", PYPL: "PayPal",
  SHOP: "Shopify", SQ: "Block (Square)", ABNB: "Airbnb", UBER: "Uber", SPOT: "Spotify",
  ABBV: "AbbVie", LLY: "Eli Lilly", UNH: "UnitedHealth", JPM: "JPMorgan", BAC: "Bank of America",
  "BRK.B": "Berkshire Hathaway", KO: "Coca-Cola", MCD: "McDonald's", WMT: "Walmart",
  DIS: "Disney", XOM: "ExxonMobil", VALE: "Vale", BABA: "Alibaba", BIDU: "Baidu",
  JD: "JD.com", PDD: "PDD (Temu)", NU: "Nubank", IBB: "Biotech ETF", ABEV: "Ambev",
  ALAB: "Astera Labs"
};
function stockName(ticker) {
  return STOCK_NAMES[String(ticker || "").toUpperCase()] || "";
}

// Chip verde con el nombre completo, al lado del "Ticker seleccionado: AAPL".
function setWorkspaceName(ticker) {
  const chip = elements.workspaceNameChip;
  if (!chip) return;
  const name = stockName(ticker);
  if (name) {
    chip.textContent = name;
    chip.hidden = false;
  } else {
    chip.textContent = "";
    chip.hidden = true;
  }
}

// Traduce la acción del motor a verbo claro en castellano + tono de color.
function _rankActionEs(action) {
  const a = String(action || "").toLowerCase();
  if (a === "buy" || a === "go_long") return { label: "Comprar", tone: "bull" };
  if (a === "hold") return { label: "Mantener", tone: "neutral" };
  if (a === "avoid") return { label: "Evitar", tone: "bear" };
  if (a === "go_short" || a === "long_put") return { label: "Bajista", tone: "bear" };
  if (a === "covered_call" || a === "cash_secured_put") return { label: "Estrategia opción", tone: "neutral" };
  return { label: toHeadline(action), tone: "neutral" };
}

function escapeText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Only linkify when the URL is a valid http(s) URL; otherwise callers fall back to plain text.
function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(String(value), window.location.href);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch (_error) {
    return null;
  }
}

async function analyzeTicker(nextTicker = state.ticker) {
  const ticker = nextTicker.toUpperCase().trim();
  if (!ticker) {
    setStatus("Ingresá un ticker para correr el análisis.");
    elements.tickerInput.focus();
    return;
  }

  const requestId = ++state.analysisRequestId;
  state.ticker = ticker;
  resetAiAnalysis();
  renderAiAnalysisPanel();
  syncSelection();
  setLoading(true);
  const submitBtn = elements.form ? elements.form.querySelector("button[type=submit]") : null;
  setButtonBusy(submitBtn, true, "Analizando…");
  primeContextLoading(ticker);
  const firstAnalysis = !state.hasAnalyzed;
  setStatus(
    firstAnalysis
      ? `Analizando ${ticker}... El primer análisis tarda unos segundos; los próximos serán instantáneos por cache.`
      : `Corriendo análisis real para ${ticker} en ${state.horizon}...`
  );

  const cachedBundle = readTimedCache(
    analysisBundleCache,
    analysisCacheKey(ticker, state.horizon),
    ANALYSIS_CACHE_TTL_MS
  );
  if (cachedBundle) {
    renderAnalysis(cachedBundle.analysis);
    if (cachedBundle.market) {
      renderMarketOverview(cachedBundle.market);
    } else {
      renderMarketOverviewError("No se pudo leer el tape general.");
    }
    if (cachedBundle.news) {
      renderNewsFeed(cachedBundle.news);
    } else {
      renderNewsError("No se pudo consultar el feed.");
    }
    if (cachedBundle.earnings) {
      renderTickerEarningsFeed(ticker, cachedBundle.earnings);
    } else {
      renderTickerEarningsError("No se pudo consultar el calendario.");
    }
    // History uses its own endpoint + cache; fire-and-forget so a slow yfinance
    // hop never blocks the cached analysis paint.
    renderSurpriseHistory(ticker);
    setLoading(false);
    setButtonBusy(submitBtn, false);
    setStatus(`Análisis listo para ${ticker}. Resultado servido desde cache local.`);
    return;
  }

  if (analysisAbortController) {
    analysisAbortController.abort();
  }
  analysisAbortController = new AbortController();

  try {
    const [analysisResult, marketResult, newsResult, earningsResult] = await Promise.allSettled([
      fetchJson("/analyze", {
        method: "POST",
        signal: analysisAbortController.signal,
        body: JSON.stringify({
          ticker,
          horizon: state.horizon
        })
      }),
      fetchJson(`/market/overview?ticker=${encodeURIComponent(ticker)}&horizon=${encodeURIComponent(state.horizon)}`, {
        signal: analysisAbortController.signal
      }),
      fetchJson(`/news/${ticker}?limit=6`, {
        signal: analysisAbortController.signal
      }),
      fetchJson(`/earnings/${ticker}?days_ahead=180`, {
        signal: analysisAbortController.signal
      })
    ]);
    if (requestId !== state.analysisRequestId) return;
    if (analysisResult.status !== "fulfilled") {
      throw analysisResult.reason;
    }

    const analysis = analysisResult.value;
    renderAnalysis(analysis);
    if (marketResult.status === "fulfilled") {
      renderMarketOverview(marketResult.value);
    } else {
      renderMarketOverviewError(marketResult.reason?.message || "No se pudo leer el tape general.");
    }
    if (newsResult.status === "fulfilled") {
      renderNewsFeed(newsResult.value);
    } else {
      renderNewsError(newsResult.reason?.message || "No se pudo consultar el feed.");
    }
    if (earningsResult.status === "fulfilled") {
      renderTickerEarningsFeed(ticker, earningsResult.value);
    } else {
      renderTickerEarningsError(earningsResult.reason?.message || "No se pudo consultar el calendario.");
    }
    // Surprise history runs independently (separate endpoint + 24h cache) so we
    // don't gate the rest of the analysis paint on yfinance's historical hop.
    renderSurpriseHistory(ticker);
    const cedearMessage = state.universe.includes(ticker)
      ? "Ticker con CEDEAR disponible."
      : "Ticker fuera del universo CEDEAR sugerido. Se analiza igual, pero no se usará en rankings.";
    writeTimedCache(analysisBundleCache, analysisCacheKey(ticker, state.horizon), {
      analysis,
      market: marketResult.status === "fulfilled" ? marketResult.value : null,
      news: newsResult.status === "fulfilled" ? newsResult.value : null,
      earnings: earningsResult.status === "fulfilled" ? earningsResult.value : null
    });
    setStatus(`Análisis listo para ${ticker}. ${cedearMessage}`);

    // Toast + scroll to verdict
    showToast(`Analisis de ${ticker} listo`, { tone: "bull" });
    const verdictPanel = document.querySelector(".verdict-panel");
    if (verdictPanel) {
      verdictPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    // Notification API when the tab is in the background
    if (document.hidden && "Notification" in window) {
      if (Notification.permission === "granted") {
        new Notification(`Market Bot: analisis de ${ticker} listo`);
      } else if (Notification.permission === "default") {
        Notification.requestPermission().then((permission) => {
          if (permission === "granted") {
            new Notification(`Market Bot: analisis de ${ticker} listo`);
          }
        });
      }
    }
  } catch (error) {
    if (requestId !== state.analysisRequestId) return;
    if (error?.name === "AbortError") {
      return;
    }
    renderErrorState(ticker, error);
    renderMarketOverviewError(error.message);
    renderNewsError(error.message);
    renderTickerEarningsError(error.message);
    setStatus(`No se pudo analizar ${ticker}: ${error.message}`);
  } finally {
    if (analysisAbortController?.signal?.aborted) {
      analysisAbortController = null;
    } else {
      analysisAbortController = null;
    }
    if (requestId === state.analysisRequestId) {
      setLoading(false);
      setButtonBusy(submitBtn, false);
    }
  }
}

function renderAnalysis(analysis) {
  state.hasAnalyzed = true;
  elements.workspaceTitle.textContent = `Ticker seleccionado: ${analysis.ticker}`;
  setWorkspaceName(analysis.ticker);
  elements.marketChip.textContent = `${titleCaseHorizon(analysis.horizon)} · ${state.universe.includes(analysis.ticker) ? "CEDEAR" : "No CEDEAR"}`;
  elements.tickerInput.value = analysis.ticker;
  renderAiAnalysisPanel();

  const primaryAction = analysis.actions[0]?.action || "hold";
  const convictionPct = `${Math.round(analysis.probabilistic.confidence * 100)}%`;
  const probabilityUpPct = `${Math.round(analysis.probabilistic.probability_up * 100)}%`;
  const riskTone = deriveRiskTone(analysis.guardrails);

  elements.verdictGrid.innerHTML = [
    { label: "Acción", value: toHeadline(primaryAction), tone: toneForAction(primaryAction) },
    { label: "Precio", value: formatCurrency(analysis.indicators.price, "USD"), tone: "neutral" },
    { label: "Régimen", value: toHeadline(analysis.deterministic.regime), tone: "neutral" },
    { label: "Convicción", value: convictionPct, tone: riskTone === "bull" ? "bull" : "neutral" }
  ]
    .map(
      (item) => `
        <article class="verdict-card">
          <p class="analysis-kicker">${item.label}</p>
          <div class="verdict-value ${item.tone}">${item.value}</div>
        </article>
      `
    )
    .join("");

  renderIndicators(analysis.indicators || {});

  elements.deterministicTitle.textContent = toSentence(analysis.deterministic.setup_name);
  elements.deterministicReasons.innerHTML = analysis.deterministic.reasons
    .map((reason) => `<li>${escapeText(reason)}</li>`)
    .join("");

  elements.probabilisticTitle.textContent = `P(up) ${probabilityUpPct} · ${toHeadline(primaryAction)} con ${convictionPct} de convicción`;
  elements.scenarioStack.innerHTML = analysis.probabilistic.scenarios
    .map((scenario) => {
      const probabilityPct = Math.round(scenario.probability * 100);
      return `
        <div class="scenario-row">
          <strong>${toHeadline(scenario.label)}</strong>
          <div class="scenario-bar">
            <div
              class="scenario-bar-fill ${toneForScenario(scenario.label)}"
              style="width:${probabilityPct}%; background:${colorForScenario(scenario.label)}"
            ></div>
          </div>
          <span>${probabilityPct}%</span>
        </div>
        <p class="panel-caption">${escapeText(scenario.thesis)}</p>
      `;
    })
    .join("");
  elements.probabilisticWarnings.innerHTML = analysis.probabilistic.warnings.length
    ? analysis.probabilistic.warnings.map((warning) => `<li>${escapeText(warning)}</li>`).join("")
    : "";

  elements.actionMatrix.innerHTML = analysis.actions
    .map(
      (action, index) => `
        <button
          type="button"
          class="action-tile ${index === 0 ? "is-primary" : ""}"
        >
          <div class="verdict-stat">
            <strong class="${toneForAction(action.action)}">${toHeadline(action.action)}</strong>
            <span class="tone-chip">${index === 0 ? "Prioridad" : "Alternativa"}</span>
          </div>
          <p>${escapeText(action.rationale)}</p>
        </button>
      `
    )
    .join("");

  renderValidation(analysis.validation);
  renderBacktest(analysis.backtest);

  renderCatalysts(analysis.catalysts);

  elements.guardrailList.innerHTML = analysis.guardrails.length
    ? analysis.guardrails.map((item) => `<li>${escapeText(item)}</li>`).join("")
    : "<li>Sin guardrails adicionales.</li>";

  syncSelection();
}

// Indicator cards (sprint 13.2): surface the most useful technical readings with
// a hover/tap tooltip that combines the glossary definition + the live value.
function indicatorReading(key, value, indicators) {
  const num = Number(value);
  const has = Number.isFinite(num);
  switch (key) {
    case "rsi":
      if (!has) return { tone: "neutral", reading: "sin dato" };
      if (num >= 70) return { tone: "bear", reading: "sobrecompra" };
      if (num >= 60) return { tone: "neutral", reading: "acercándose a sobrecompra" };
      if (num <= 30) return { tone: "bull", reading: "sobreventa" };
      if (num <= 40) return { tone: "neutral", reading: "acercándose a sobreventa" };
      return { tone: "neutral", reading: "momentum neutral" };
    case "macd": {
      const signal = Number(indicators.macd_signal);
      if (!has) return { tone: "neutral", reading: "sin dato" };
      if (Number.isFinite(signal)) {
        return num >= signal
          ? { tone: "bull", reading: "por encima de la señal (impulso alcista)" }
          : { tone: "bear", reading: "por debajo de la señal (impulso bajista)" };
      }
      return num >= 0
        ? { tone: "bull", reading: "momentum positivo" }
        : { tone: "bear", reading: "momentum negativo" };
    }
    case "adx":
      if (!has) return { tone: "neutral", reading: "sin dato" };
      if (num >= 25) return { tone: "bull", reading: "tendencia fuerte" };
      if (num >= 20) return { tone: "neutral", reading: "tendencia incipiente" };
      return { tone: "neutral", reading: "tendencia débil / lateral" };
    case "atr": {
      const price = Number(indicators.price);
      if (!has) return { tone: "neutral", reading: "sin dato" };
      if (Number.isFinite(price) && price > 0) {
        const pct = (num / price) * 100;
        const tone = pct >= 4 ? "bear" : "neutral";
        return { tone, reading: `~${pct.toFixed(1).replace(".", ",")}% del precio` };
      }
      return { tone: "neutral", reading: "rango medio diario" };
    }
    case "volume_ratio":
      if (!has) return { tone: "neutral", reading: "sin dato" };
      if (num >= 1.5) return { tone: "bull", reading: "volumen muy por encima del promedio" };
      if (num >= 1.1) return { tone: "bull", reading: "volumen por encima del promedio" };
      if (num <= 0.7) return { tone: "bear", reading: "volumen flojo" };
      return { tone: "neutral", reading: "volumen en línea con el promedio" };
    case "price_vs_sma50": {
      const price = Number(indicators.price);
      const sma = Number(indicators.sma_50);
      if (!Number.isFinite(price) || !Number.isFinite(sma) || sma === 0) {
        return { tone: "neutral", reading: "sin dato" };
      }
      const pct = ((price - sma) / sma) * 100;
      const tone = pct >= 0 ? "bull" : "bear";
      const verb = pct >= 0 ? "por encima" : "por debajo";
      return { tone, reading: `${verb} de la SMA50 (${formatPercent((price - sma) / sma, { signed: true })})` };
    }
    case "price_vs_sma200": {
      const price = Number(indicators.price);
      const sma = Number(indicators.sma_200);
      if (!Number.isFinite(price) || !Number.isFinite(sma) || sma === 0) {
        return { tone: "neutral", reading: "sin dato" };
      }
      const pct = ((price - sma) / sma) * 100;
      const tone = pct >= 0 ? "bull" : "bear";
      const verb = pct >= 0 ? "por encima" : "por debajo";
      return { tone, reading: `${verb} de la SMA200 (${formatPercent((price - sma) / sma, { signed: true })})` };
    }
    default:
      return { tone: "neutral", reading: "" };
  }
}

function renderIndicators(indicators) {
  if (!elements.indicatorGrid) return;

  // Definition: which indicators we surface, their display value + matching glossary id.
  const specs = [
    {
      key: "rsi",
      glossaryId: "rsi",
      label: "RSI",
      sub: "Momentum",
      present: indicators.rsi !== null && indicators.rsi !== undefined,
      value: Number.isFinite(Number(indicators.rsi)) ? Number(indicators.rsi).toFixed(0) : "—"
    },
    {
      key: "macd",
      glossaryId: "macd",
      label: "MACD",
      sub: "Cruce de medias",
      present: indicators.macd !== null && indicators.macd !== undefined,
      value: Number.isFinite(Number(indicators.macd)) ? Number(indicators.macd).toFixed(2).replace(".", ",") : "—"
    },
    {
      key: "adx",
      glossaryId: "adx",
      label: "ADX",
      sub: "Fuerza de tendencia",
      present: indicators.adx !== null && indicators.adx !== undefined,
      value: Number.isFinite(Number(indicators.adx)) ? Number(indicators.adx).toFixed(0) : "—"
    },
    {
      key: "atr",
      glossaryId: "atr",
      label: "ATR",
      sub: "Volatilidad",
      present: indicators.atr !== null && indicators.atr !== undefined,
      value: Number.isFinite(Number(indicators.atr)) ? formatCurrency(indicators.atr, "USD") : "—"
    },
    {
      key: "volume_ratio",
      glossaryId: "liquidity",
      label: "Volumen",
      sub: "Ratio vs promedio",
      present: indicators.volume_ratio !== null && indicators.volume_ratio !== undefined,
      value: Number.isFinite(Number(indicators.volume_ratio)) ? `${Number(indicators.volume_ratio).toFixed(2).replace(".", ",")}×` : "—"
    },
    {
      key: "price_vs_sma50",
      glossaryId: "trend-following",
      label: "Precio vs SMA50",
      sub: "Estructura de mediano plazo",
      present:
        Number.isFinite(Number(indicators.price)) && Number.isFinite(Number(indicators.sma_50)),
      value: Number.isFinite(Number(indicators.sma_50)) ? formatCurrency(indicators.sma_50, "USD") : "—"
    },
    {
      key: "price_vs_sma200",
      glossaryId: "trend-following",
      label: "Precio vs SMA200",
      sub: "Estructura de largo plazo",
      present:
        Number.isFinite(Number(indicators.price)) && Number.isFinite(Number(indicators.sma_200)),
      value: Number.isFinite(Number(indicators.sma_200)) ? formatCurrency(indicators.sma_200, "USD") : "—"
    }
  ];

  const shown = specs.filter((spec) => spec.present);
  if (!shown.length) {
    renderContextPlaceholder(elements.indicatorGrid, {
      title: "Sin indicadores disponibles",
      body: "El snapshot no trajo lecturas técnicas para este ticker.",
      tone: "neutral"
    });
    return;
  }

  // Glossary may not be loaded yet; render now, then enrich tooltips when it arrives.
  const paint = () => {
    const terms = window.MARKET_BOT_GLOSSARY || GLOSSARY_TERMS || [];
    const byId = new Map(terms.map((t) => [t.id, t]));
    elements.indicatorGrid.innerHTML = shown.map((spec) => indicatorCardMarkup(spec, indicators, byId)).join("");
  };
  paint();
  ensureGlossaryLoaded().then(() => {
    // Re-paint only if the grid still holds this analysis (cheap and idempotent).
    if (elements.indicatorGrid) paint();
  });
}

function indicatorCardMarkup(spec, indicators, byId) {
  const sourceValue =
    spec.key === "price_vs_sma50" || spec.key === "price_vs_sma200" ? indicators.price : indicators[spec.key];
  const { tone, reading } = indicatorReading(spec.key, sourceValue, indicators);
  const term = byId.get(spec.glossaryId);
  const definition = term ? `${term.label}: ${term.detail || term.short || ""}`.trim() : "";
  const valueLine = reading ? `Actual: ${spec.value} — ${reading}` : `Actual: ${spec.value}`;
  const tooltipText = definition ? `${definition} | ${valueLine}` : valueLine;
  return `
    <div class="indicator-card" tabindex="0" data-tone="${tone}" aria-label="${escapeAttribute(`${spec.label}. ${tooltipText}`)}">
      <div class="indicator-card-head">
        <span class="indicator-name">${escapeText(spec.label)}</span>
        <span class="indicator-value ${tone}">${escapeText(spec.value)}</span>
      </div>
      <span class="indicator-sub">${escapeText(spec.sub)}</span>
      ${reading ? `<span class="indicator-reading ${tone}">${escapeText(reading)}</span>` : ""}
      <div class="indicator-tooltip" role="tooltip">
        ${definition ? `<p class="indicator-tooltip-def">${escapeText(definition)}</p>` : ""}
        <p class="indicator-tooltip-value">${escapeText(valueLine)}</p>
      </div>
    </div>
  `;
}

function renderMarketOverview(overview) {
  const regimeLabel = overview.regime === "risk_on"
    ? "Contexto favorable"
    : overview.regime === "risk_off"
      ? "Contexto defensivo"
      : "Contexto mixto";
  const breadthLabel = overview.breadth ? `Breadth ${toHeadline(overview.breadth)}` : "Breadth n/d";

  elements.marketOverviewTitle.textContent = regimeLabel;
  elements.marketOverviewChip.textContent = breadthLabel;
  elements.marketOverviewSummary.textContent = `${overview.summary} Leé estas cards como semáforos del contexto: si predominan señales constructivas, el mercado acompaña más; si predominan las de presión, conviene pedir más confirmación.`;

  if (!Array.isArray(overview.instruments) || !overview.instruments.length) {
    renderContextPlaceholder(elements.marketOverviewGrid, {
      title: "Sin métricas macro",
      body: "No llegaron snapshots del mercado general para esta corrida.",
      tone: "neutral"
    });
  } else {
    elements.marketOverviewGrid.innerHTML = overview.instruments
      .map((item) => renderMarketPulseCard(item))
      .join("");
  }

  elements.marketOverviewWarnings.innerHTML = Array.isArray(overview.warnings) && overview.warnings.length
    ? overview.warnings.map((warning) => `<li>${escapeText(warning)}</li>`).join("")
    : "<li>Sin alertas macro dominantes en este snapshot.</li>";
}

function renderMarketOverviewError(message) {
  elements.marketOverviewTitle.textContent = "No se pudo leer el tape general";
  elements.marketOverviewChip.textContent = "Error";
  elements.marketOverviewSummary.textContent = "El análisis principal puede salir, pero te quedás sin la capa de régimen de mercado.";
  renderContextPlaceholder(elements.marketOverviewGrid, {
    title: "Market overview no disponible",
    body: message,
    tone: "error"
  });
  elements.marketOverviewWarnings.innerHTML = "<li>Sin lectura macro por error de datos.</li>";
}

function marketCategoryLabel(category) {
  const labels = {
    indices: "Indices",
    breadth: "Amplitud",
    volatility: "Volatilidad",
    crypto: "Cripto",
    macro: "Macro",
    rates: "Tasas"
  };
  return labels[category] || toHeadline(category || "general");
}

function marketToneLabel(tone) {
  if (tone === "bull") return "Acompaña";
  if (tone === "bear") return "Presiona";
  return "Mixto";
}

function primeContextLoading(ticker) {
  elements.marketOverviewTitle.textContent = "Régimen general en sincronización";
  elements.marketOverviewChip.textContent = "Sync";
  elements.marketOverviewSummary.textContent = `Midiendo índices, volatilidad, cripto, petróleo y tasas para entender si el mercado acompaña a ${ticker}.`;
  renderContextPlaceholder(elements.marketOverviewGrid, {
    title: "Cargando market regime",
    body: "Armando lectura macro y de tape general antes de consolidar el contexto.",
    tone: "loading"
  });
  elements.marketOverviewWarnings.innerHTML = "";

  elements.newsTitle.textContent = `Tape reciente de ${ticker}`;
  elements.newsChip.textContent = "Sync";
  renderContextPlaceholder(elements.newsFeed, {
    title: "Cargando titulares",
    body: `Buscando headlines recientes y señales externas para ${ticker}.`,
    tone: "loading"
  });

  elements.earningsTitle.textContent = `Ventana de eventos para ${ticker}`;
  elements.earningsChip.textContent = state.accessToken ? "Ticker + watchlist" : "Ticker";
  renderContextPlaceholder(elements.tickerEarningsFeed, {
    title: "Cargando earnings",
    body: `Chequeando próximos reportes y gap risk para ${ticker}.`,
    tone: "loading"
  });

  if (!state.accessToken) {
    renderPortfolioEarningsLocked();
  }
}

function renderNewsFeed(items) {
  elements.newsTitle.textContent = items.length ? `${items.length} titulares en radar` : "Sin titulares relevantes";
  elements.newsChip.textContent = items.length ? "Reported" : "Quiet";

  if (!items.length) {
    renderContextPlaceholder(elements.newsFeed, {
      title: "Sin cobertura reciente",
      body: "No aparecieron titulares frescos para este ticker en la ventana consultada.",
      tone: "neutral"
    });
    return;
  }

  elements.newsFeed.innerHTML = items.map((item) => renderNewsCard(item)).join("");
}

function renderNewsError(message) {
  elements.newsTitle.textContent = "No se pudo cargar el tape";
  elements.newsChip.textContent = "Error";
  renderContextPlaceholder(elements.newsFeed, {
    title: "Feed no disponible",
    body: message,
    tone: "error"
  });
}

function renderTickerEarningsFeed(ticker, events) {
  elements.earningsTitle.textContent = events.length
    ? `Próximos earnings para ${ticker}`
    : `Sin earnings próximos para ${ticker}`;

  if (!events.length) {
    renderContextPlaceholder(elements.tickerEarningsFeed, {
      title: "Ventana limpia",
      body: "No aparecen earnings próximos en la ventana consultada.",
      tone: "neutral"
    });
    return;
  }

  elements.tickerEarningsFeed.innerHTML = events
    .slice(0, 3)
    .map((event) => renderEarningsEventCard(event))
    .join("");
}

function renderTickerEarningsError(message) {
  elements.earningsTitle.textContent = "No se pudo cargar earnings";
  renderContextPlaceholder(elements.tickerEarningsFeed, {
    title: "Calendario no disponible",
    body: message,
    tone: "error"
  });
}

function renderErrorState(ticker, error) {
  resetAiAnalysis();
  elements.workspaceTitle.textContent = `Ticker seleccionado: ${ticker}`;
  setWorkspaceName(ticker);
  elements.marketChip.textContent = `${titleCaseHorizon(state.horizon)} · Error`;
  elements.verdictGrid.innerHTML = `
    <article class="verdict-card">
      <p class="analysis-kicker">Estado</p>
      <div class="verdict-value bear">Sin análisis</div>
    </article>
    <article class="verdict-card">
      <p class="analysis-kicker">Detalle</p>
      <div class="verdict-value neutral">API</div>
    </article>
  `;
  elements.deterministicTitle.textContent = "No se pudo completar el análisis.";
  elements.deterministicReasons.innerHTML = `<li>${escapeText(error.message)}</li>`;
  elements.probabilisticTitle.textContent = "Revisar ticker, dependencias o conexión con el API.";
  elements.scenarioStack.innerHTML = "";
  elements.probabilisticWarnings.innerHTML = "";
  elements.validationTitle.textContent = "Sin validación disponible";
  elements.validationGrid.innerHTML = "";
  elements.backtestTitle.textContent = "Sin backtest disponible";
  elements.backtestGrid.innerHTML = "";
  elements.actionMatrix.innerHTML = `
    <button type="button" class="action-tile is-primary">
      <div class="verdict-stat">
        <strong class="bear">Retry</strong>
        <span class="tone-chip">Error</span>
      </div>
      <p>Verificar que el backend FastAPI esté corriendo en ${escapeText(API_BASE)}.</p>
    </button>
  `;
  elements.catalystList.innerHTML = "<li>No hay catalysts porque el análisis falló.</li>";
  elements.guardrailList.innerHTML = "<li>Verificar que `uvicorn services.api.app:app --reload` esté levantado.</li>";
  renderAiAnalysisPanel();
}

function syncSelection() {
  elements.tickerInput.value = state.ticker;
  elements.horizonButtons.forEach((button) => {
    const isSelected = button.dataset.horizon === state.horizon;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-checked", isSelected ? "true" : "false");
  });
  document.querySelectorAll(".radar-card").forEach((card) => {
    const isSelected = card.dataset.ticker === state.ticker;
    card.classList.toggle("is-selected", isSelected);
    card.setAttribute("aria-pressed", isSelected ? "true" : "false");
  });
}

function deriveRiskTone(guardrails) {
  const text = guardrails.join(" ").toLowerCase();
  if (text.includes("alta") || text.includes("volatilidad")) return "bear";
  if (text.includes("no se detectaron")) return "bull";
  return "neutral";
}

function toneForAction(action) {
  if (["buy", "go_long", "cash_secured_put"].includes(action)) return "bull";
  if (["go_short", "sell", "long_put", "avoid"].includes(action)) return "bear";
  return "neutral";
}

function toneForScenario(label) {
  if (label === "bull") return "bull";
  if (label === "bear") return "bear";
  return "neutral";
}

function colorForScenario(label) {
  if (label === "bull") return "#1d7a52";
  if (label === "bear") return "#b24f2b";
  return "#8a6f3c";
}

// Money formatter with explicit prefix so ARS and USD read uniformly across
// the UI. Intl's "es-AR" returns "$" for ARS and "US$" for USD, which mixes
// implicit and explicit currency cues. We force "AR$" / "US$" everywhere and
// optionally compact magnitudes (12.34M, 9,8k) for hero numbers that would
// otherwise overflow the layout.
function formatMoney(value, currency, options = {}) {
  const { magnitude = false, signed = false, fractionDigits } = options;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";

  const prefix = currency === "ARS" ? "AR$" : currency === "USD" ? "US$" : "";
  const sign = numeric < 0 ? "−" : signed ? "+" : "";
  const abs = Math.abs(numeric);

  if (magnitude) {
    let formatted;
    if (abs >= 1_000_000) {
      formatted = `${(abs / 1_000_000).toLocaleString("es-AR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })} M`;
    } else if (abs >= 1_000) {
      formatted = `${(abs / 1_000).toLocaleString("es-AR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1
      })} k`;
    } else {
      formatted = abs.toLocaleString("es-AR", {
        minimumFractionDigits: currency === "ARS" ? 0 : 2,
        maximumFractionDigits: currency === "ARS" ? 0 : 2
      });
    }
    return `${sign}${prefix} ${formatted}`.trim();
  }

  const digits = fractionDigits ?? (currency === "ARS" ? 0 : 2);
  const formatted = abs.toLocaleString("es-AR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
  return `${sign}${prefix} ${formatted}`.trim();
}

// Back-compat shim — keeps existing call sites working until they migrate
// to formatMoney directly. Old code expected no sign on negatives, but the
// new shim shows a typographic minus on negatives (matches the rest of the UI).
function formatCurrency(value, currency) {
  return formatMoney(value, currency);
}

function formatPercent(value, { signed = false } = {}) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const pct = numeric * 100;
  const sign = pct < 0 ? "−" : signed ? "+" : "";
  return `${sign}${Math.abs(pct).toFixed(2).replace(".", ",")}%`;
}

function toneOf(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "neutral";
  return numeric > 0 ? "bull" : "bear";
}

function formatMacroValue(symbol, value) {
  if (symbol === "^VIX" || symbol === "^TNX") {
    return Number(value).toFixed(2);
  }
  return formatCurrency(value, "USD");
}

function formatDateLabel(value) {
  if (!value) return "Fecha no informada";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(parsed);
}

function toHeadline(value) {
  return String(value).replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function toSentence(value) {
  const text = toHeadline(value);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function renderValidation(validation) {
  if (!validation) {
    elements.validationTitle.textContent = "Sin validación disponible";
    elements.validationGrid.innerHTML = "";
    return;
  }

  elements.validationTitle.textContent = `F1 ${validation.f1.toFixed(2)} · Brier ${validation.brier_score.toFixed(2)}`;
  elements.validationGrid.innerHTML = [
    ["Samples", validation.sample_size],
    ["Train/Test", `${validation.train_size}/${validation.test_size}`],
    ["Accuracy", validation.accuracy.toFixed(2)],
    ["Precision", validation.precision.toFixed(2)],
    ["Recall", validation.recall.toFixed(2)],
    ["Calibración", validation.calibration_method]
  ]
    .map(
      ([label, value]) => `
        <div class="metric-tile">
          <span class="metric-label">${label}</span>
          <span class="metric-value">${value}</span>
        </div>
      `
    )
    .join("");
}

function renderCatalysts(catalysts) {
  if (!catalysts || !catalysts.length) {
    elements.catalystList.innerHTML = "<li>Sin catalysts destacados para este snapshot.</li>";
    return;
  }

  elements.catalystList.innerHTML = catalysts
    .map((item) => {
      const status = (item.status || "inferred").toLowerCase();
      const validStatus = ["confirmed", "reported", "rumored", "inferred"].includes(status)
        ? status
        : "inferred";
      const chip = `<span class="catalyst-chip" data-status="${validStatus}">${toHeadline(validStatus)}</span>`;
      const url = safeHttpUrl(item.source_url);
      const source = url
        ? `<a class="context-link" href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">Fuente</a>`
        : "";
      return `<li>${escapeText(item.name)} ${chip} ${source}</li>`;
    })
    .join("");
}

function renderNewsCard(item) {
  const sentimentTone = item.sentiment >= 0.15 ? "bull" : item.sentiment <= -0.15 ? "bear" : "neutral";
  const confidencePct = Math.round((item.confidence || 0) * 100);
  const url = safeHttpUrl(item.url);
  const linkOpen = url
    ? `<a class="context-link" href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">Abrir</a>`
    : `<span class="context-link is-muted">Sin link</span>`;
  const headline = escapeText(item.title);
  const headlineMarkup = url
    ? `<a class="context-headline-link" href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${headline}</a>`
    : headline;
  const summary = item.summary ? `<p>${escapeText(item.summary)}</p>` : "";
  return `
    <article class="context-card">
      <div class="context-card-top">
        <span class="tone-chip">${escapeText(item.impact_category || "general")}</span>
        <span class="signal-chip ${sentimentTone}">${sentimentTone === "bull" ? "Bullish" : sentimentTone === "bear" ? "Bearish" : "Neutral"}</span>
      </div>
      <h4>${headlineMarkup}</h4>
      ${summary}
      <div class="context-meta">
        <span>${escapeText(item.source || "Fuente no informada")}</span>
        <span>${confidencePct}% confianza</span>
        <span>${escapeText(formatDateLabel(item.published_at || item.fetched_at))}</span>
      </div>
      <div class="context-actions">
        ${linkOpen}
      </div>
    </article>
  `;
}

function renderMarketPulseCard(item) {
  const sma20 = item.relative_to_sma20_pct !== null && item.relative_to_sma20_pct !== undefined
    ? formatPercent(item.relative_to_sma20_pct, { signed: true })
    : "n/d";
  const sma50 = item.relative_to_sma50_pct !== null && item.relative_to_sma50_pct !== undefined
    ? formatPercent(item.relative_to_sma50_pct, { signed: true })
    : "n/d";
  const toneLabel = marketToneLabel(item.tone);
  const categoryLabel = marketCategoryLabel(item.category);
  return `
    <article class="market-pulse-card ${escapeText(item.tone || "neutral")}">
      <div class="context-card-top market-card-top">
        <span class="tone-chip">${escapeText(categoryLabel)}</span>
        <span class="signal-chip ${escapeText(item.tone || "neutral")}">${toneLabel}</span>
      </div>
      <h4>${escapeText(item.label)}</h4>
      <p class="market-pulse-copy">${escapeText(item.note)}</p>
      <div class="market-pulse-metrics">
        <div class="market-pulse-metric">
          <span class="metric-label">Precio</span>
          <strong>${formatMacroValue(item.symbol, item.price)}</strong>
        </div>
        <div class="market-pulse-metric">
          <span class="metric-label">Día</span>
          <strong class="tone-${toneOf(item.day_change_pct)}">${formatPercent(item.day_change_pct, { signed: true })}</strong>
        </div>
        <div class="market-pulse-metric">
          <span class="metric-label">Vs media 20d</span>
          <strong>${sma20}</strong>
        </div>
        <div class="market-pulse-metric">
          <span class="metric-label">Vs media 50d</span>
          <strong>${sma50}</strong>
        </div>
      </div>
      <p class="market-pulse-footnote">Símbolo ${escapeText(item.symbol)} · Lectura ${toneLabel.toLowerCase()}.</p>
    </article>
  `;
}

const OFFICIAL_IR_LINKS = {
  AAPL: "https://investor.apple.com/financials.cfm",
  AMD: "https://ir.amd.com/",
  AMZN: "https://ir.aboutamazon.com/",
  COIN: "https://investor.coinbase.com/home/default.aspx",
  GGAL: "https://www.gfgsa.com/en",
  GOOG: "https://abc.xyz/investor/earnings",
  GOOGL: "https://abc.xyz/investor/earnings",
  MELI: "https://investor.mercadolibre.com/",
  META: "https://investor.atmeta.com/home/",
  MSFT: "https://www.microsoft.com/en-us/investor",
  NU: "https://investors.nu/",
  NVDA: "https://investor.nvidia.com/home/default.aspx",
  PLTR: "https://investors.palantir.com/",
  SNOW: "https://investors.snowflake.com/overview/default.aspx?lang=none",
  TSLA: "https://ir.tesla.com/investor-relations",
  YPF: "https://investors.ypf.com/"
};

function earningsResourceLink(ticker) {
  const normalizedTicker = String(ticker || "")
    .trim()
    .toUpperCase()
    .replace(/\.BA$/, "")
    .replace("/", ".");
  if (!normalizedTicker) {
    return { url: "", label: "Sin link" };
  }
  const official = OFFICIAL_IR_LINKS[normalizedTicker];
  if (official) {
    return {
      url: official,
      label: "IR oficial"
    };
  }
  const nasdaqTicker = normalizedTicker.toLowerCase().replace(/[./\s]+/g, "-");
  return {
    url: `https://www.nasdaq.com/market-activity/stocks/${encodeURIComponent(nasdaqTicker)}/earnings`,
    label: "Nasdaq"
  };
}

function renderEarningsEventCard(event, options = {}) {
  const compact = Boolean(options.compact);
  const estimateLine = event.eps_estimate !== null && event.eps_estimate !== undefined
    ? `EPS est. ${event.eps_estimate}`
    : "EPS est. n/d";
  const earningsLink = earningsResourceLink(event.ticker);
  return `
    <article class="earnings-card ${compact ? "is-compact" : ""}">
      <div class="context-card-top">
        <span class="tone-chip">${escapeText(event.ticker)}</span>
        <span class="signal-chip neutral">${escapeText(event.report_time || "Time TBD")}</span>
      </div>
      <h4>${escapeText(formatDateLabel(event.report_date))}</h4>
      <p>${escapeText(estimateLine)}</p>
      <div class="context-actions">
        <a class="context-link" href="${escapeAttribute(earningsLink.url)}" target="_blank" rel="noopener noreferrer">${escapeText(earningsLink.label)}</a>
      </div>
    </article>
  `;
}

// Tracks the latest in-flight surprise-history request so a fast ticker swap
// doesn't paint stale data over the new selection.
let surpriseHistoryRequestId = 0;

function formatSurprisePct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "n/d";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function formatFiscalQuarterParts(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return { quarter: "Q?", year: "" };
  }
  const parts = raw.split(/\s+/);
  return {
    quarter: parts[0] || raw,
    year: parts.slice(1).join(" ")
  };
}

function formatEpsValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/d";
  return numeric.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function renderSurpriseHistoryCell(event) {
  // beat flag drives the bull/bear tint. surprise_pct is the magnitude chip.
  // next_day_return_pct is shown below — useful because sometimes the print
  // is a beat but the stock still sells off on guidance.
  const tone = event.beat === true ? "bull" : event.beat === false ? "bear" : "neutral";
  const surpriseLabel = formatSurprisePct(event.surprise_pct);
  const moveLabel = formatSurprisePct(event.next_day_return_pct);
  const moveTone =
    event.next_day_return_pct === null || event.next_day_return_pct === undefined
      ? "neutral"
      : event.next_day_return_pct >= 0
        ? "bull"
        : "bear";
  const beatLabel =
    event.beat === true
      ? "Superó"
      : event.beat === false
        ? "Falló"
        : "En línea";
  const { quarter, year } = formatFiscalQuarterParts(event.fiscal_quarter);
  const earningsLink = earningsResourceLink(event.ticker || state.ticker);
  const details = [
    { label: "EPS est.", value: formatEpsValue(event.eps_estimate) },
    { label: "EPS real", value: formatEpsValue(event.eps_actual) },
    { label: "Cierre D+1", value: event.next_day_close_date ? formatDateLabel(event.next_day_close_date) : "n/d" }
  ];
  return `
    <article class="earnings-history-cell ${tone}" tabindex="0" title="${escapeAttribute(`${event.fiscal_quarter} · ${event.report_date}`)}">
      <div class="earnings-history-top">
        <div class="earnings-history-period">
          <span class="earnings-history-quarter">${escapeText(quarter)}</span>
          ${year ? `<span class="earnings-history-year">${escapeText(year)}</span>` : ""}
        </div>
        <div class="earnings-history-pill-row">
          <div class="earnings-history-pill ${tone}">
            <span class="earnings-history-pill-label">${escapeText(beatLabel)}</span>
            <strong>${escapeText(surpriseLabel)}</strong>
          </div>
          <div class="earnings-history-pill ${moveTone}">
            <span class="earnings-history-pill-label">D+1</span>
            <strong>${escapeText(moveLabel)}</strong>
          </div>
        </div>
      </div>
      <div class="earnings-history-meta">
        <span class="earnings-history-date">${escapeText(event.report_date)}</span>
        <span class="earnings-history-hover-hint">Hover para más</span>
      </div>
      <div class="earnings-history-detail" aria-hidden="true">
        ${details
          .map(
            (item) => `
              <div class="earnings-history-detail-row">
                <span>${escapeText(item.label)}</span>
                <strong>${escapeText(item.value)}</strong>
              </div>
            `
          )
          .join("")}
        <a class="context-link earnings-history-link" href="${escapeAttribute(earningsLink.url)}" target="_blank" rel="noopener noreferrer">Abrir ${escapeText(earningsLink.label)}</a>
      </div>
    </article>
  `;
}

function renderSurpriseHistorySkeleton() {
  if (!elements.tickerEarningsHistory) return;
  const cells = Array.from({ length: 12 })
    .map(() => `<article class="earnings-history-cell is-skeleton" aria-hidden="true"></article>`)
    .join("");
  elements.tickerEarningsHistory.innerHTML = cells;
}

function renderSurpriseHistoryEmpty() {
  if (!elements.tickerEarningsHistory) return;
  elements.tickerEarningsHistory.innerHTML = `
    <p class="earnings-history-empty">No tenemos surprise history para este ticker.</p>
  `;
}

async function renderSurpriseHistory(ticker) {
  if (!elements.tickerEarningsHistory) return;
  const symbol = (ticker || "").toUpperCase().trim();
  if (!symbol) {
    elements.tickerEarningsHistory.innerHTML = "";
    return;
  }
  const requestId = ++surpriseHistoryRequestId;
  renderSurpriseHistorySkeleton();
  try {
    const payload = await fetchJson(`/earnings/${encodeURIComponent(symbol)}/history?limit=12`);
    if (requestId !== surpriseHistoryRequestId) return; // a newer ticker won
    const events = Array.isArray(payload?.events) ? payload.events : [];
    if (!events.length) {
      renderSurpriseHistoryEmpty();
      return;
    }
    elements.tickerEarningsHistory.innerHTML = events
      .slice(0, 12)
      .map((event) => renderSurpriseHistoryCell(event))
      .join("");
  } catch (error) {
    if (requestId !== surpriseHistoryRequestId) return;
    renderSurpriseHistoryEmpty();
  }
}

function renderBacktest(backtest) {
  if (!backtest) {
    elements.backtestTitle.textContent = "Sin backtest disponible";
    elements.backtestGrid.innerHTML = "";
    return;
  }

  elements.backtestTitle.textContent = `${backtest.strategy_name} · ${backtest.execution_model}`;
  elements.backtestGrid.innerHTML = [
    ["Return", `${backtest.total_return_pct.toFixed(2)}%`],
    ["Max DD", `${backtest.max_drawdown_pct.toFixed(2)}%`],
    ["Trades", backtest.total_trades],
    ["Win rate", `${backtest.win_rate_pct.toFixed(2)}%`],
    ["Expectancy", backtest.expectancy.toFixed(2)],
    ["Costs", `${backtest.fee_bps + backtest.slippage_bps} bps`]
  ]
    .map(
      ([label, value]) => `
        <div class="metric-tile">
          <span class="metric-label">${label}</span>
          <span class="metric-value">${value}</span>
        </div>
      `
    )
    .join("");
}

function escapeAttribute(value) {
  return escapeText(value).replace(/`/g, "&#96;");
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  analyzeTicker(elements.tickerInput.value);
});

elements.surfaceButtons.forEach((button) => {
  button.addEventListener("click", () => setSurface(button.dataset.surface));
  // Prefetch heavier surface bundles when the user hovers/focuses the tab,
  // so by the time they click, data is in cache. Currently only Learning
  // benefits (glossary.js is lazy-loaded). Future: chat module on
  // pointerenter of the Buffy tab.
  if (button.dataset.surface === "learning") {
    const warm = () => ensureGlossaryLoaded();
    button.addEventListener("pointerenter", warm, { once: true });
    button.addEventListener("focus", warm, { once: true });
  }
});

elements.accountShortcut.addEventListener("click", () => {
  if (state.profile && state.accessToken) {
    setAccountMenuOpen(!state.accountMenuOpen);
    return;
  }
  openAccess("login");
});
elements.openAccountButton.addEventListener("click", () => openAccess("login"));
elements.openPortfolioButton.addEventListener("click", () => {
  if (state.profile && state.accessToken) {
    setSurface("portfolio");
    return;
  }
  openAccess("register");
});
elements.closeAccountButton.addEventListener("click", () => setSurface(state.lastTabbedSurface || "workspace"));
elements.accessSurface.addEventListener("click", (event) => {
  if (event.target !== elements.accessSurface) return;
  setSurface(state.lastTabbedSurface || "workspace");
});
if (elements.accountMenuBody) {
  elements.accountMenuBody.addEventListener("click", (event) => {
    const action = event.target.closest("[data-account-action]")?.dataset.accountAction;
    if (!action) return;
    if (action === "portfolio") {
      setSurface("portfolio");
      return;
    }
    if (action === "settings") {
      openAccess("login");
      return;
    }
    if (action === "howto") {
      setSurface("howto");
      return;
    }
    if (action === "logout") {
      handleLogout();
    }
  });
}

elements.authForm.addEventListener("submit", handleAuthSubmit);
elements.profileForm.addEventListener("submit", handleProfileSubmit);
elements.logoutButton.addEventListener("click", handleLogout);
elements.portfolioImportForm.addEventListener("submit", handlePortfolioImportSubmit);
elements.portfolioForm.addEventListener("submit", handlePortfolioSubmit);
if (elements.positionEditorCancel) {
  elements.positionEditorCancel.addEventListener("click", () => {
    resetPortfolioForm();
    clearPositionEditor();
    setPortfolioStatus("Edición cancelada.");
  });
}

elements.portfolioViewButtons.forEach((button) => {
  button.addEventListener("click", () => setPortfolioView(button.dataset.portfolioViewTab));
});

elements.authModeButtons.forEach((button) => {
  button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
});

elements.instrumentButtons.forEach((button) => {
  button.addEventListener("click", () => setInstrumentType(button.dataset.instrumentType));
});

elements.miniSummaryCurrencyButtons.forEach((button) => {
  button.addEventListener("click", () => setMiniSummaryCurrency(button.dataset.miniSummaryCurrency));
});

if (elements.rankingModeButtons && elements.rankingModeButtons.length) {
  elements.rankingModeButtons.forEach((button) => {
    button.addEventListener("click", () => setRankingMode(button.dataset.rankingMode));
  });
  syncRankingModeButtons();
}

if (elements.diagnosticsRefresh) {
  elements.diagnosticsRefresh.addEventListener("click", () => loadDiagnostics());
}

if (elements.diagnosticsToggleOnlyBad) {
  elements.diagnosticsToggleOnlyBad.addEventListener("click", () => {
    _diagnosticsOnlyBad = !_diagnosticsOnlyBad;
    elements.diagnosticsToggleOnlyBad.classList.toggle("is-active", _diagnosticsOnlyBad);
    elements.diagnosticsToggleOnlyBad.textContent = _diagnosticsOnlyBad
      ? "Mostrar todas"
      : "Sólo problemáticas";
    if (_diagnosticsCache) renderDiagnostics(_diagnosticsCache);
  });
}

if (elements.earningsBannerDismiss) {
  elements.earningsBannerDismiss.addEventListener("click", () => {
    const key = elements.earningsBanner.dataset.bannerKey;
    if (key) rememberDismissedEarning(key);
    elements.earningsBanner.classList.add("is-hidden");
  });
}

if (elements.earningsBannerCta) {
  elements.earningsBannerCta.addEventListener("click", () => {
    // Drop the user into the analyzer for the ticker with the imminent event.
    const ticker = elements.earningsBanner.dataset.bannerTicker;
    if (!ticker) return;
    setSurface("workspace");
    analyzeTicker(ticker);
  });
}

if (elements.indicatorAiButton) {
  elements.indicatorAiButton.addEventListener("click", () => {
    requestAiAnalysis();
  });
}

elements.horizonButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    state.horizon = button.dataset.horizon;
    setLoading(true);
    try {
      await loadRankings();
      if (state.hasAnalyzed) {
        await analyzeTicker(state.ticker);
      } else {
        renderWorkspaceIdle();
        setStatus("Horizonte actualizado. Elegí un ticker o una card para correr el análisis.");
      }
    } finally {
      setLoading(false);
    }
  });
});

elements.radarGrid.addEventListener("click", (event) => {
  const card = event.target.closest(".radar-card");
  if (!card) return;
  analyzeTicker(card.dataset.ticker);
});

// Touch devices have no hover: tap an indicator card to toggle its tooltip.
if (elements.indicatorGrid) {
  elements.indicatorGrid.addEventListener("click", (event) => {
    const card = event.target.closest(".indicator-card");
    if (!card) return;
    const wasOpen = card.classList.contains("is-open");
    elements.indicatorGrid.querySelectorAll(".indicator-card.is-open").forEach((c) => c.classList.remove("is-open"));
    if (!wasOpen) card.classList.add("is-open");
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".indicator-card")) {
      elements.indicatorGrid.querySelectorAll(".indicator-card.is-open").forEach((c) => c.classList.remove("is-open"));
    }
  });
}

elements.learningFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-learning-filter]");
  if (!button) return;
  setLearningFilter(button.dataset.learningFilter);
});

elements.learningSearchInput.addEventListener("input", (event) => {
  setLearningQuery(event.target.value);
});

elements.learningSearchClear.addEventListener("click", () => {
  setLearningQuery("");
  elements.learningSearchInput.focus();
});

elements.holdingsGrid.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit-position]");
  if (editButton) {
    beginPositionEdit(editButton.dataset.editPosition);
    return;
  }
  const button = event.target.closest("[data-delete-position]");
  if (!button) return;
  handleDeletePosition(button.dataset.deletePosition);
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (state.accountMenuOpen) {
    setAccountMenuOpen(false);
    return;
  }
  if (state.activeSurface !== "access") return;
  setSurface(state.lastTabbedSurface || "workspace");
});

document.addEventListener("click", (event) => {
  if (!state.accountMenuOpen) return;
  if (elements.accountShell && elements.accountShell.contains(event.target)) return;
  setAccountMenuOpen(false);
});

window.addEventListener("popstate", () => {
  applyHashRoute();
});

// ─── Track Record (Sprint 10) ────────────────────────────────────────────────

let _trackRecordLoaded = false;

async function loadTrackRecord() {
  const grid = document.getElementById("track-record-grid");
  if (!grid) return;
  grid.innerHTML = `<p class="panel-caption">Cargando backtest y track record…</p>`;

  const [backtestResult, trackRecordResult] = await Promise.allSettled([
    fetchJson("/backtest/ranking?horizon=short&lookback_days=90"),
    state.accessToken ? fetchJson("/decisions/track-record", { auth: true }) : Promise.resolve(null),
  ]);
  _trackRecordLoaded = true;
  renderTrackRecord(
    backtestResult.status === "fulfilled" ? backtestResult.value : null,
    trackRecordResult.status === "fulfilled" ? trackRecordResult.value : null,
  );
}

function renderTrackRecord(backtest, trackRecord) {
  const grid = document.getElementById("track-record-grid");
  if (!grid) return;

  // Solo mostrar el panel cuando hay un backtest válido. Si no, queda oculto
  // (evita una caja vacía/confusa en el landing). Reaparece al tener data.
  const panel = document.getElementById("track-record-panel");
  const hasData = backtest && !backtest.error;
  if (panel) panel.classList.toggle("is-hidden", !hasData);
  if (!hasData) return;

  const fmtPct = (v) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`);
  const fmtRate = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
  const tone = (v) => (v == null ? "neutral" : v > 0 ? "bull" : "bear");

  // ── Backtest ──
  let backtestHtml = "";
  if (!backtest || backtest.error) {
    backtestHtml = `<p class="panel-caption bear">Backtest no disponible${backtest?.error ? ": " + escapeText(backtest.error) : ""}.</p>`;
  } else {
    const hitSpy = backtest.hit_rate_vs_spy;
    const edgeVerdict =
      hitSpy != null && hitSpy > 0.55
        ? `<span class="bull">✓ Algo de edge vs SPY (${(hitSpy * 100).toFixed(0)}% de los períodos)</span>`
        : hitSpy != null
        ? `<span class="bear">Sin edge claro vs SPY (${(hitSpy * 100).toFixed(0)}% — cerca del azar)</span>`
        : "—";

    backtestHtml = `
      <article class="analysis-card">
        <p class="analysis-kicker">Backtest ranking · últimos ${backtest.lookback_days}d · top-${backtest.top_n}</p>
        <h3>Señal determinística vs benchmarks</h3>
        <div class="track-record-metrics">
          <div class="metric-tile"><span class="metric-label">Estrategia (acum.)</span><span class="metric-value ${tone(backtest.strategy_cum_return)}">${fmtPct(backtest.strategy_cum_return)}</span></div>
          <div class="metric-tile"><span class="metric-label">SPY (acum.)</span><span class="metric-value ${tone(backtest.spy_cum_return)}">${fmtPct(backtest.spy_cum_return)}</span></div>
          <div class="metric-tile"><span class="metric-label">Plazo fijo (acum.)</span><span class="metric-value neutral">${fmtPct(backtest.pf_cum_return)}</span></div>
          <div class="metric-tile"><span class="metric-label">Hit rate vs SPY</span><span class="metric-value">${fmtRate(hitSpy)}</span></div>
          <div class="metric-tile"><span class="metric-label">Períodos positivos</span><span class="metric-value">${fmtRate(backtest.hit_rate_positive)}</span></div>
          <div class="metric-tile"><span class="metric-label">Sharpe (anualiz.)</span><span class="metric-value">${backtest.sharpe ?? "—"}</span></div>
        </div>
        <p class="panel-caption" style="margin-top:12px">Veredicto: ${edgeVerdict}</p>
        <p class="panel-caption" style="margin-top:6px;opacity:.65">
          Señal: RSI(14) + momentum 20d · Rebalanceo cada ${backtest.step_days ?? 5} días ·
          ${backtest.n_periods} períodos · ${backtest.computed_at ? "Computado " + backtest.computed_at.slice(0, 10) : ""}
        </p>
      </article>`;

    if (backtest.periods && backtest.periods.length) {
      const recent = backtest.periods.slice(-8).reverse();
      const rows = recent
        .map(
          (p) => `<tr>
          <td>${escapeText(p.anchor_date)}</td>
          <td class="diagnostics-num">${escapeText(p.top_tickers.join(", "))}</td>
          <td class="diagnostics-num ${tone(p.strategy_return)}">${fmtPct(p.strategy_return)}</td>
          <td class="diagnostics-num ${tone(p.spy_return)}">${fmtPct(p.spy_return)}</td>
          <td class="diagnostics-num">${p.beat_spy ? "✓" : "✗"}</td>
        </tr>`,
        )
        .join("");
      backtestHtml += `
        <article class="analysis-card wide-card" style="margin-top:16px">
          <p class="analysis-kicker">Últimos períodos</p>
          <div class="diagnostics-table-wrap">
            <table class="diagnostics-table">
              <thead><tr><th>Fecha</th><th>Top tickers</th><th>Estrategia</th><th>SPY</th><th>Ganó</th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </article>`;
    }
  }

  // ── Personal track record ──
  let personalHtml = "";
  if (!state.accessToken) {
    personalHtml = `<p class="panel-caption" style="opacity:.7">Iniciá sesión para ver tu track record personal.</p>`;
  } else if (!trackRecord || trackRecord.n_realized === 0) {
    personalHtml = `<p class="panel-caption">Sin decisiones realizadas todavía. Guardá decisiones al analizar un ticker; el retorno se computa automáticamente en ${trackRecord?.n_pending ?? 0} período(s).</p>`;
  } else {
    const tr = trackRecord;
    personalHtml = `
      <article class="analysis-card">
        <p class="analysis-kicker">Tus decisiones · track record personal</p>
        <h3>${tr.n_realized} decisión(es) realizada(s)</h3>
        <div class="track-record-metrics">
          <div class="metric-tile"><span class="metric-label">Hit rate</span><span class="metric-value ${tr.hit_rate > 0.5 ? "bull" : "bear"}">${fmtRate(tr.hit_rate)}</span></div>
          <div class="metric-tile"><span class="metric-label">Retorno promedio</span><span class="metric-value ${tone(tr.avg_return)}">${fmtPct(tr.avg_return)}</span></div>
          <div class="metric-tile"><span class="metric-label">Sharpe</span><span class="metric-value">${tr.sharpe ?? "—"}</span></div>
          <div class="metric-tile"><span class="metric-label">Mejor ticker</span><span class="metric-value bull">${escapeText(tr.best_ticker ?? "—")}</span></div>
          <div class="metric-tile"><span class="metric-label">Peor ticker</span><span class="metric-value bear">${escapeText(tr.worst_ticker ?? "—")}</span></div>
          <div class="metric-tile"><span class="metric-label">Pendientes</span><span class="metric-value">${tr.n_pending}</span></div>
        </div>
      </article>`;
  }

  grid.innerHTML = `
    <div class="track-record-section">${backtestHtml}</div>
    <div class="track-record-section">${personalHtml}</div>
  `;
}

// ─── Onboarding (Sprint 11.2) ─────────────────────────────────────────────────

const ONBOARDING_STEPS = [
  {
    title: "1. Completá tu perfil",
    body: "Decinos tu tolerancia al riesgo y benchmark preferido. El motor personaliza el ranking y el chat para vos.",
    cta: "Ir al perfil",
    action: () => { setSurface("portfolio"); setPortfolioView("summary"); },
  },
  {
    title: "2. Importá tu portfolio",
    body: "Subí el extracto Balanz (.xlsx) o cargá posiciones manualmente. Una vez cargado, todo el análisis usa tus datos reales.",
    cta: "Ir al portfolio",
    action: () => { setSurface("portfolio"); setPortfolioView("load"); },
  },
  {
    title: "3. Preguntale al asistente",
    body: "El chat conoce tu portfolio y tu perfil. Preguntale \"¿cómo viene NVDA?\" o \"¿cuál es mi exposición a tech?\".",
    cta: "Abrir chat",
    action: () => setSurface("chat"),
  },
];

let _onboardingStep = 0;

function showOnboarding() {
  let overlay = document.getElementById("onboarding-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "onboarding-overlay";
    overlay.className = "onboarding-overlay";
    overlay.innerHTML = `
      <div class="onboarding-card">
        <div class="onboarding-steps" id="ob-dots"></div>
        <div class="onboarding-body">
          <h2 id="ob-title"></h2>
          <p id="ob-body"></p>
        </div>
        <div class="onboarding-actions">
          <button type="button" class="ghost-button" id="ob-skip">Saltar tour</button>
          <button type="button" class="cta-button" id="ob-cta"></button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    document.getElementById("ob-skip").addEventListener("click", dismissOnboarding);
    document.getElementById("ob-cta").addEventListener("click", () => {
      const step = ONBOARDING_STEPS[_onboardingStep];
      step.action();
      if (_onboardingStep < ONBOARDING_STEPS.length - 1) {
        _onboardingStep++;
        renderOnboardingStep();
      } else {
        dismissOnboarding();
      }
    });
  }
  _onboardingStep = 0;
  overlay.classList.remove("is-hidden");
  renderOnboardingStep();
}

function renderOnboardingStep() {
  const step = ONBOARDING_STEPS[_onboardingStep];
  const titleEl = document.getElementById("ob-title");
  const bodyEl = document.getElementById("ob-body");
  const ctaEl = document.getElementById("ob-cta");
  const dotsEl = document.getElementById("ob-dots");
  if (!titleEl || !bodyEl || !ctaEl || !dotsEl) return;
  titleEl.textContent = step.title;
  bodyEl.textContent = step.body;
  ctaEl.textContent = _onboardingStep < ONBOARDING_STEPS.length - 1 ? step.cta + " →" : step.cta + " ✓";
  dotsEl.innerHTML = ONBOARDING_STEPS.map((_, i) =>
    `<span class="onboarding-step-dot ${i < _onboardingStep ? "is-done" : i === _onboardingStep ? "is-active" : ""}"></span>`
  ).join("");
}

function dismissOnboarding() {
  const overlay = document.getElementById("onboarding-overlay");
  if (overlay) overlay.classList.add("is-hidden");
  try { localStorage.setItem("marketBotOnboardingDone", "1"); } catch (_) {}
}

function maybeShowOnboarding() {
  try { if (localStorage.getItem("marketBotOnboardingDone")) return; } catch (_) {}
  // Only show after successful login with empty portfolio (or first ever login)
  setTimeout(showOnboarding, 800);
}

// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const refreshBtn = document.getElementById("track-record-refresh");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      _trackRecordLoaded = false;
      loadTrackRecord();
    });
  }

  // ── Feedback (Sprint 11.1) ──────────────────────────────────────────────
  const fab = document.getElementById("feedback-fab");
  const dialog = document.getElementById("feedback-dialog");
  const closeBtn = document.getElementById("feedback-close");
  const form = document.getElementById("feedback-form");
  const msgInput = document.getElementById("feedback-message");
  const submitBtn = document.getElementById("feedback-submit");
  const statusEl = document.getElementById("feedback-status");

  if (fab && dialog) {
    fab.addEventListener("click", () => {
      if (statusEl) statusEl.textContent = "";
      if (msgInput) msgInput.value = "";
      dialog.showModal();
      setTimeout(() => msgInput?.focus(), 50);
    });
    if (closeBtn) closeBtn.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  }

  if (form && submitBtn && msgInput) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = msgInput.value.trim();
      if (!msg) return;
      submitBtn.disabled = true;
      if (statusEl) statusEl.textContent = "Enviando…";
      try {
        const surface = document.querySelector(".surface-slider")?.dataset?.activeSurface || "";
        await fetchJson("/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: msg, page: surface }),
          auth: Boolean(state.accessToken),
        });
        if (statusEl) statusEl.textContent = "✓ Gracias por el feedback.";
        msgInput.value = "";
        setTimeout(() => dialog?.close(), 1200);
      } catch (err) {
        if (statusEl) statusEl.textContent = `Error: ${err.message}`;
        submitBtn.disabled = false;
      }
    });
  }
  // ───────────────────────────────────────────────────────────────────────
});

// ─────────────────────────────────────────────────────────────────────────────

async function bootstrap() {
  const initialRoute = parseHashRoute(window.location.hash);
  setAuthMode(initialRoute.authMode || "login", { syncRoute: false });
  setInstrumentType("cedear");
  setMiniSummaryCurrency("ARS");
  setPortfolioView("summary");
  setSurface(initialRoute.surface || "workspace", { syncRoute: false });
  updatePortfolioAccessState();
  renderUnauthenticated();
  setLoading(true);
  setStatus(`Conectando con el API en ${API_BASE}...`);

  try {
    await fetchJson("/health");
    await Promise.all([
      loadUniverse(),
      loadRankings(),
      bootstrapSession({ refreshRankings: false })
    ]);
    applyHashRoute({ replace: true });
    renderWorkspaceIdle();
    setStatus("Elegí un ticker o tocá una card del radar para correr el análisis.");
    // Load track record lazily after main bootstrap — slow (~5-15s) and non-critical.
    if (!_trackRecordLoaded) loadTrackRecord().catch(() => {});
  } catch (error) {
    renderRadar();
    renderErrorState(state.ticker, error);
    setStatus(`No se pudo inicializar la UI contra el API: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

bootstrap();
