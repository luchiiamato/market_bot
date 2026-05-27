const defaultApiBase =
  window.location.origin && window.location.origin !== "null"
    ? window.location.origin
    : "http://127.0.0.1:8000";

const API_BASE =
  new URLSearchParams(window.location.search).get("apiBase") ||
  window.localStorage.getItem("marketBotApiBase") ||
  defaultApiBase;

const AUTH_TOKEN_KEY = "marketBotAccessToken";
const GLOSSARY_TERMS = [
  {
    id: "rsi",
    label: "RSI",
    category: "Indicador",
    short: "Mide si el precio viene demasiado extendido al alza o a la baja.",
    detail: "Relative Strength Index. Suele leerse como termómetro de momentum. Arriba de 70 puede sugerir sobrecompra y debajo de 30 sobreventa, pero nunca se usa aislado."
  },
  {
    id: "macd",
    label: "MACD",
    category: "Indicador",
    short: "Compara medias para detectar aceleración o pérdida de momentum.",
    detail: "Moving Average Convergence Divergence. Sirve para ver cruces de momentum y cambios de tendencia relativa. En este producto se combina con RSI, ADX y estructura."
  },
  {
    id: "adx",
    label: "ADX",
    category: "Indicador",
    short: "Mide fuerza de tendencia, no dirección.",
    detail: "Average Directional Index. Si sube, la tendencia gana fuerza; si cae, el mercado puede estar lateral. Es útil para saber si una señal direccional merece confianza."
  },
  {
    id: "atr",
    label: "ATR",
    category: "Riesgo",
    short: "Mide volatilidad promedio para stops y tamaño.",
    detail: "Average True Range. Se usa para estimar cuánto se mueve normalmente un activo y ajustar stop loss, take profit y tamaño de posición."
  },
  {
    id: "cedear",
    label: "CEDEAR",
    category: "Instrumento",
    short: "Permite exponerte localmente a una acción extranjera.",
    detail: "Es un certificado que cotiza en Argentina y replica una acción o ETF del exterior. Para valuarlo bien importa su precio local, el underlying y la relación CEDEAR/acción."
  },
  {
    id: "mep",
    label: "MEP",
    category: "Benchmark ARG",
    short: "Dólar financiero usado para medir retorno real local.",
    detail: "El dólar MEP sirve como benchmark argentino porque refleja mejor la cobertura en moneda dura que el oficial. En portfolio se compara contra oficial, MEP, CCL, inflación y plazo fijo."
  },
  {
    id: "ccl",
    label: "CCL",
    category: "Benchmark ARG",
    short: "Dólar financiero de salida al exterior y referencia de paridad.",
    detail: "El contado con liquidación ayuda a estimar valor relativo de activos dolarizados y también a inferir paridades CEDEAR cuando no hay ratio validado explícitamente."
  },
  {
    id: "stop-loss",
    label: "Stop Loss",
    category: "Riesgo",
    short: "Precio donde la tesis deja de ser válida.",
    detail: "No es sólo un piso técnico. Debería marcar el punto en el que la premisa operativa cambió y seguir en la posición deja de tener sentido."
  },
  {
    id: "earnings",
    label: "Earnings",
    category: "Evento",
    short: "Reporte de resultados que puede invalidar setups técnicos limpios.",
    detail: "Los resultados trimestrales suelen introducir gap risk. Incluso un setup técnico fuerte puede degradarse si el evento está demasiado cerca."
  },
  {
    id: "probability-up",
    label: "P(up)",
    category: "Probabilístico",
    short: "Probabilidad estimada de que el próximo tramo sea alcista.",
    detail: "No es una orden. Es la estimación del motor probabilístico para el siguiente tramo del activo y siempre se acompaña con warnings de calibración."
  }
];

const state = {
  ticker: "AAPL",
  horizon: "short",
  radarItems: [],
  universe: [],
  authMode: "login",
  accessToken: window.localStorage.getItem(AUTH_TOKEN_KEY),
  profile: null,
  instrumentType: "cedear",
  portfolioSummary: null,
  activeSurface: "workspace"
};

const elements = {
  body: document.body,
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
  workspaceTitle: document.querySelector("#workspace-title"),
  marketChip: document.querySelector("#market-chip"),
  status: document.querySelector("#analysis-status"),
  datalist: document.querySelector("#ticker-suggestions"),
  horizonButtons: Array.from(document.querySelectorAll(".horizon-pill")),
  surfaceButtons: Array.from(document.querySelectorAll("[data-surface]")),
  workspaceSurface: document.querySelector("#surface-workspace"),
  learningSurface: document.querySelector("#surface-learning"),
  tradingSurface: document.querySelector("#surface-trading"),
  conceptRibbon: document.querySelector("#concept-ribbon"),
  tooltipPreview: document.querySelector("#tooltip-preview"),
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
  portfolioForm: document.querySelector("#portfolio-form"),
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
  holdingsGrid: document.querySelector("#holdings-grid")
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

function setSurface(surface) {
  state.activeSurface = surface;
  const surfaces = {
    workspace: elements.workspaceSurface,
    learning: elements.learningSurface,
    trading: elements.tradingSurface
  };
  Object.entries(surfaces).forEach(([key, node]) => {
    if (!node) return;
    node.classList.toggle("is-hidden", key !== surface);
  });
  elements.surfaceButtons.forEach((button) => {
    const isSelected = button.dataset.surface === surface;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
}

function renderGlossary() {
  elements.conceptRibbon.innerHTML = GLOSSARY_TERMS.map(
    (term) => `
      <button
        type="button"
        class="concept-chip"
        data-term-id="${term.id}"
        aria-describedby="tooltip-preview"
      >
        <span>${term.label}</span>
      </button>
    `
  ).join("");

  elements.learningGrid.innerHTML = GLOSSARY_TERMS.map(
    (term) => `
      <article class="learning-card">
        <div class="learning-head">
          <div>
            <p class="analysis-kicker">${term.category}</p>
            <h3>${term.label}</h3>
          </div>
          <button
            type="button"
            class="info-badge"
            data-term-id="${term.id}"
            aria-label="Explicación rápida de ${term.label}"
          >?</button>
        </div>
        <p class="learning-short">${term.short}</p>
        <p class="learning-detail">${term.detail}</p>
      </article>
    `
  ).join("");
}

function showTerm(termId) {
  const term = GLOSSARY_TERMS.find((item) => item.id === termId);
  if (!term) return;
  elements.tooltipPreview.textContent = `${term.label}: ${term.short}`;
  document.querySelectorAll("[data-term-id]").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.termId === termId);
  });
}

function clearTermPreview() {
  elements.tooltipPreview.textContent = "Pasá por un concepto para ver una explicación rápida.";
  document.querySelectorAll("[data-term-id].is-active").forEach((node) => {
    node.classList.remove("is-active");
  });
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

async function fetchJson(path, options = {}) {
  const { auth = false, headers = {}, ...rest } = options;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...headers,
      ...(auth ? authHeaders(true) : {})
    },
    ...rest
  });

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

  if (response.status === 204) {
    return null;
  }
  return response.json();
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
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

function setAuthMode(mode) {
  state.authMode = mode;
  const isRegister = mode === "register";
  elements.authTitle.textContent = isRegister
    ? "Creá tu usuario local para guardar portfolio"
    : "Ingresá para guardar perfil y portfolio";
  elements.authDisplayNameWrap.classList.toggle("is-hidden", !isRegister);
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
}

function renderUnauthenticated() {
  elements.authForm.classList.remove("is-hidden");
  elements.profileShell.classList.add("is-hidden");
  elements.portfolioLockedState.classList.remove("is-hidden");
  elements.portfolioShell.classList.add("is-hidden");
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
  setAuthStatus("Podés entrar o registrarte sin mail.");
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
  elements.authForm.classList.add("is-hidden");
  elements.profileShell.classList.remove("is-hidden");
  elements.portfolioLockedState.classList.add("is-hidden");
  elements.portfolioShell.classList.remove("is-hidden");
  hydrateProfile(state.profile);
  setAuthStatus(`Sesión activa para ${state.profile.username}.`);
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

  elements.miniSummaryGrid.innerHTML = [
    ["Posiciones", summary.positions_count],
    ["P&amp;L ARS", formatCurrency(summary.total_pnl_ars, "ARS")]
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

async function bootstrapSession() {
  if (!state.accessToken) {
    renderUnauthenticated();
    return;
  }

  try {
    const profile = await fetchJson("/profile", { auth: true });
    state.profile = profile;
    renderAuthenticated();
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

  setButtonBusy(elements.authSubmit, true, state.authMode === "register" ? "Creando..." : "Ingresando...");
  try {
    const path = state.authMode === "register" ? "/auth/register" : "/auth/login";
    const session = await fetchJson(path, {
      method: "POST",
      body: JSON.stringify(payload)
    });
    persistSession(session);
    renderAuthenticated();
    await loadPortfolioSummary();
    setAuthStatus(state.authMode === "register" ? "Usuario creado y sesión iniciada." : "Sesión iniciada.");
    elements.authPassword.value = "";
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

async function loadPortfolioSummary() {
  if (!state.accessToken) {
    return;
  }

  setPortfolioStatus("Actualizando portfolio...");
  try {
    const summary = await fetchJson("/portfolio/summary", { auth: true });
    state.portfolioSummary = summary;
    renderPortfolioSummary(summary);
    renderMiniSummary(summary);
    setPortfolioStatus(
      summary.positions_count
        ? `Portfolio actualizado con benchmark ${state.profile.benchmark_preference.toUpperCase()}.`
        : "Aún no cargaste posiciones."
    );
  } catch (error) {
    setPortfolioStatus(`No se pudo cargar el portfolio: ${error.message}`);
  }
}

function renderPortfolioSummary(summary) {
  elements.portfolioSummaryGrid.innerHTML = [
    ["Posiciones", summary.positions_count],
    ["Valor ARS", formatCurrency(summary.total_value_ars, "ARS")],
    ["Valor USD", formatCurrency(summary.total_value_usd, "USD")],
    ["P&amp;L ARS", formatCurrency(summary.total_pnl_ars, "ARS")],
    ["P&amp;L USD", formatCurrency(summary.total_pnl_usd, "USD")],
    ["Real return", formatPercent(summary.total_real_return_pct)]
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

  if (!summary.positions_count) {
    elements.holdingsGrid.innerHTML = `
      <div class="empty-state">
        <strong>No tenés posiciones cargadas.</strong>
        <p>Probá agregar un CEDEAR o un stock desde el formulario de arriba.</p>
      </div>
    `;
    return;
  }

  elements.holdingsGrid.innerHTML = summary.positions
    .map((position) => {
      const inflation = position.benchmark_comparisons.find((item) => item.label === "inflation");
      const plazoFijo = position.benchmark_comparisons.find((item) => item.label === "plazo_fijo");
      const ccl = position.benchmark_comparisons.find((item) => item.label === "ccl_usd");
      const ratioLine = position.cedear_ratio
        ? `<span class="tone-chip">Ratio ${position.cedear_ratio} · ${toHeadline(position.cedear_ratio_source || "manual")}</span>`
        : "";
      const noteList = position.notes.length
        ? `<ul class="warning-list compact-list">${position.notes.map((note) => `<li>${note}</li>`).join("")}</ul>`
        : "";
      return `
        <article class="holding-card">
          <div class="holding-head">
            <div>
              <p class="analysis-kicker">${toHeadline(position.instrument_type)}</p>
              <h3>${position.symbol}</h3>
              <p class="panel-caption">${position.underlying_ticker} · Compra ${position.purchase_date}</p>
            </div>
            <div class="holding-actions">
              ${ratioLine}
              <button type="button" class="ghost-button" data-delete-position="${position.position_id}">Eliminar</button>
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
  setButtonBusy(submitButton, true, "Guardando...");
  try {
    await fetchJson("/portfolio/positions", {
      auth: true,
      method: "POST",
      body: JSON.stringify({
        instrument_type: state.instrumentType,
        symbol: elements.positionSymbol.value.trim().toUpperCase(),
        quantity: Number(elements.positionQuantity.value),
        purchase_date: elements.positionPurchaseDate.value,
        purchase_price: Number(elements.positionPurchasePrice.value),
        purchase_currency: elements.positionPurchaseCurrency.value,
        underlying_ticker: elements.positionUnderlying.value.trim().toUpperCase() || null,
        cedear_ratio: elements.positionRatio.value ? Number(elements.positionRatio.value) : null,
        notes: elements.positionNotes.value.trim()
      })
    });
    elements.portfolioForm.reset();
    setInstrumentType("cedear");
    await loadPortfolioSummary();
    setPortfolioStatus("Posición guardada.");
  } catch (error) {
    setPortfolioStatus(`No se pudo guardar la posición: ${error.message}`);
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

async function loadRankings() {
  const rankings = await fetchJson(`/rankings?horizon=${state.horizon}&limit=6&cedear_only=true`);
  state.radarItems = rankings;
  renderRadar();

  if (!rankings.length) {
    setStatus("No hay rankings disponibles para el horizonte seleccionado.");
    return;
  }

  if (!rankings.some((item) => item.ticker === state.ticker)) {
    state.ticker = rankings[0].ticker;
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

  elements.radarGrid.innerHTML = state.radarItems
    .map((item, index) => {
      const label =
        index === 0
          ? "Top setup"
          : item.direction === "long"
            ? "Long bias"
            : item.direction === "short"
              ? "Short bias"
              : "Watch";
      return `
        <button
          class="radar-card ${item.ticker === state.ticker ? "is-selected" : ""}"
          data-ticker="${item.ticker}"
          type="button"
        >
          <div class="radar-card-top">
            <span class="radar-chip">${label}</span>
            <strong>${item.ticker}</strong>
          </div>
          <h3>${toHeadline(item.action)} / ${item.regime}</h3>
          <p>Score ${item.rank_score.toFixed(2)} · Convicción ${(item.conviction * 100).toFixed(0)}% · CEDEAR ${item.is_cedear ? "sí" : "no"}</p>
        </button>
      `;
    })
    .join("");
}

async function analyzeTicker(nextTicker = state.ticker) {
  const ticker = nextTicker.toUpperCase().trim();
  if (!ticker) {
    setStatus("Ingresá un ticker para correr el análisis.");
    elements.tickerInput.focus();
    return;
  }

  state.ticker = ticker;
  syncSelection();
  setLoading(true);
  setStatus(`Corriendo análisis real para ${ticker} en ${state.horizon}...`);

  try {
    const analysis = await fetchJson("/analyze", {
      method: "POST",
      body: JSON.stringify({
        ticker,
        horizon: state.horizon
      })
    });
    renderAnalysis(analysis);
    const cedearMessage = state.universe.includes(ticker)
      ? "Ticker con CEDEAR disponible."
      : "Ticker fuera del universo CEDEAR sugerido. Se analiza igual, pero no se usará en rankings.";
    setStatus(`Análisis listo para ${ticker}. ${cedearMessage}`);
  } catch (error) {
    renderErrorState(ticker, error);
    setStatus(`No se pudo analizar ${ticker}: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

function renderAnalysis(analysis) {
  elements.workspaceTitle.textContent = `Ticker seleccionado: ${analysis.ticker}`;
  elements.marketChip.textContent = `${titleCaseHorizon(analysis.horizon)} · ${state.universe.includes(analysis.ticker) ? "CEDEAR" : "No CEDEAR"}`;
  elements.tickerInput.value = analysis.ticker;

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

  elements.deterministicTitle.textContent = toSentence(analysis.deterministic.setup_name);
  elements.deterministicReasons.innerHTML = analysis.deterministic.reasons
    .map((reason) => `<li>${reason}</li>`)
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
        <p class="panel-caption">${scenario.thesis}</p>
      `;
    })
    .join("");
  elements.probabilisticWarnings.innerHTML = analysis.probabilistic.warnings.length
    ? analysis.probabilistic.warnings.map((warning) => `<li>${warning}</li>`).join("")
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
          <p>${action.rationale}</p>
        </button>
      `
    )
    .join("");

  renderValidation(analysis.validation);
  renderBacktest(analysis.backtest);

  elements.catalystList.innerHTML = analysis.catalysts.length
    ? analysis.catalysts.map((item) => `<li>${item.name}</li>`).join("")
    : "<li>Sin catalysts destacados para este snapshot.</li>";

  elements.guardrailList.innerHTML = analysis.guardrails.length
    ? analysis.guardrails.map((item) => `<li>${item}</li>`).join("")
    : "<li>Sin guardrails adicionales.</li>";

  syncSelection();
}

function renderErrorState(ticker, error) {
  elements.workspaceTitle.textContent = `Ticker seleccionado: ${ticker}`;
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
  elements.deterministicReasons.innerHTML = `<li>${error.message}</li>`;
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
      <p>Verificar que el backend FastAPI esté corriendo en ${API_BASE}.</p>
    </button>
  `;
  elements.catalystList.innerHTML = "<li>No hay catalysts porque el análisis falló.</li>";
  elements.guardrailList.innerHTML = "<li>Verificar que `uvicorn services.api.app:app --reload` esté levantado.</li>";
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

function formatCurrency(value, currency) {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "ARS" ? 0 : 2
  }).format(value);
}

function formatPercent(value) {
  return `${(value * 100).toFixed(2)}%`;
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

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  analyzeTicker(elements.tickerInput.value);
});

elements.surfaceButtons.forEach((button) => {
  button.addEventListener("click", () => setSurface(button.dataset.surface));
});

elements.authForm.addEventListener("submit", handleAuthSubmit);
elements.profileForm.addEventListener("submit", handleProfileSubmit);
elements.logoutButton.addEventListener("click", handleLogout);
elements.portfolioForm.addEventListener("submit", handlePortfolioSubmit);

elements.authModeButtons.forEach((button) => {
  button.addEventListener("click", () => setAuthMode(button.dataset.authMode));
});

elements.instrumentButtons.forEach((button) => {
  button.addEventListener("click", () => setInstrumentType(button.dataset.instrumentType));
});

elements.horizonButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    state.horizon = button.dataset.horizon;
    setLoading(true);
    try {
      await loadRankings();
      await analyzeTicker(state.ticker);
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

elements.holdingsGrid.addEventListener("click", (event) => {
  const button = event.target.closest("[data-delete-position]");
  if (!button) return;
  handleDeletePosition(button.dataset.deletePosition);
});

document.addEventListener("mouseover", (event) => {
  const trigger = event.target.closest("[data-term-id]");
  if (!trigger) return;
  showTerm(trigger.dataset.termId);
});

document.addEventListener("focusin", (event) => {
  const trigger = event.target.closest("[data-term-id]");
  if (!trigger) return;
  showTerm(trigger.dataset.termId);
});

document.addEventListener("mouseout", (event) => {
  const trigger = event.target.closest("[data-term-id]");
  if (!trigger) return;
  if (trigger.contains(event.relatedTarget)) return;
  clearTermPreview();
});

document.addEventListener("focusout", (event) => {
  const trigger = event.target.closest("[data-term-id]");
  if (!trigger) return;
  if (trigger.contains(event.relatedTarget)) return;
  clearTermPreview();
});

async function bootstrap() {
  setAuthMode("login");
  setInstrumentType("cedear");
  setSurface("workspace");
  renderGlossary();
  renderUnauthenticated();
  setLoading(true);
  setStatus(`Conectando con el API en ${API_BASE}...`);

  try {
    await fetchJson("/health");
    await loadUniverse();
    await loadRankings();
    await analyzeTicker(state.ticker);
    await bootstrapSession();
  } catch (error) {
    renderRadar();
    renderErrorState(state.ticker, error);
    setStatus(`No se pudo inicializar la UI contra el API: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

bootstrap();
