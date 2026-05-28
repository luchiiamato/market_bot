// API base resolution order:
// 1. ?apiBase=…       — debug / temporary override
// 2. localStorage      — user-set persistent override
// 3. window.MARKET_BOT_API_BASE  — injected at deploy time (Vercel writes
//    `config.js` with the production API origin). Empty string = unset.
// 4. window.location.origin     — same-origin (works for local FastAPI
//    serving the prototype at /app/)
// 5. localhost fallback for `file://` and other edge cases.
const defaultApiBase =
  window.location.origin && window.location.origin !== "null"
    ? window.location.origin
    : "http://127.0.0.1:8000";

const _injectedApiBase =
  typeof window.MARKET_BOT_API_BASE === "string" && window.MARKET_BOT_API_BASE.trim()
    ? window.MARKET_BOT_API_BASE.trim().replace(/\/$/, "")
    : "";

const API_BASE =
  new URLSearchParams(window.location.search).get("apiBase") ||
  window.localStorage.getItem("marketBotApiBase") ||
  _injectedApiBase ||
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
  },
  {
    id: "long",
    label: "Long",
    category: "Posición",
    short: "Apostar a que el activo sube.",
    detail: "Ir long significa comprar esperando una suba. Tu riesgo clásico queda en una caída del precio y tu invalidación debería estar definida antes de entrar."
  },
  {
    id: "short",
    label: "Short",
    category: "Posición",
    short: "Apostar a que el activo baja.",
    detail: "Ir short busca ganar con una caída del precio. Requiere más control de riesgo porque las pérdidas potenciales pueden escalar rápido si el activo sube fuerte."
  },
  {
    id: "call",
    label: "Call",
    category: "Opciones",
    short: "Opción que gana valor si el subyacente sube.",
    detail: "Una call da derecho a comprar el activo a un strike. Se usa para especular al alza, cubrir un short o armar estrategias como covered call."
  },
  {
    id: "put",
    label: "Put",
    category: "Opciones",
    short: "Opción que gana valor si el subyacente baja.",
    detail: "Una put da derecho a vender el activo a un strike. Sirve para protección, sesgo bajista o estructuras como cash-secured put."
  },
  {
    id: "covered-call",
    label: "Covered Call",
    category: "Opciones",
    short: "Cobrás prima vendiendo una call sobre acciones que ya tenés.",
    detail: "Es una estrategia conservadora de income. Limitás parte del upside a cambio de cobrar prima, y funciona mejor en activos laterales o con suba moderada."
  },
  {
    id: "cash-secured-put",
    label: "Cash-Secured Put",
    category: "Opciones",
    short: "Vendés una put con efectivo reservado por si te asignan.",
    detail: "Se usa para intentar entrar más abajo cobrando prima. Sólo tiene sentido si realmente querés comprar el activo al strike pactado."
  },
  {
    id: "implied-volatility",
    label: "Implied Volatility",
    category: "Opciones",
    short: "Volatilidad que el mercado descuenta en el precio de las opciones.",
    detail: "La volatilidad implícita afecta muchísimo la prima. Si está muy alta, comprar opciones puede ser caro aunque tengas la dirección correcta."
  },
  {
    id: "open-interest",
    label: "Open Interest",
    category: "Opciones",
    short: "Cantidad de contratos abiertos en un strike o vencimiento.",
    detail: "El open interest ayuda a medir liquidez y zonas de atención del mercado. No es señal por sí solo, pero suma contexto sobre dónde está mirando el flujo."
  },
  {
    id: "delta",
    label: "Delta",
    category: "Opciones",
    short: "Sensibilidad de una opción ante un cambio del subyacente.",
    detail: "Delta aproxima cuánto se mueve la prima si el activo sube o baja un punto. También se usa como probabilidad aproximada de terminar in the money, con matices."
  },
  {
    id: "theta",
    label: "Theta",
    category: "Opciones",
    short: "Pérdida de valor temporal de una opción.",
    detail: "Theta mide cuánto valor pierde una opción por el mero paso del tiempo. Por eso comprar opciones tarde y con poco movimiento puede destruir la operación."
  },
  {
    id: "breakout",
    label: "Breakout",
    category: "Técnico",
    short: "Ruptura al alza de una zona importante.",
    detail: "Un breakout busca capturar expansión de precio cuando una resistencia cede. Idealmente va acompañado por volumen y contexto de mercado que no lo contradiga."
  },
  {
    id: "breakdown",
    label: "Breakdown",
    category: "Técnico",
    short: "Ruptura a la baja de un soporte o rango.",
    detail: "Un breakdown señala deterioro de estructura. Cuando aparece con volumen y mercado débil, suele habilitar setups short o de salida defensiva."
  },
  {
    id: "support",
    label: "Support",
    category: "Técnico",
    short: "Zona donde históricamente apareció demanda.",
    detail: "El soporte no es una línea mágica. Es una zona donde el precio reaccionó antes, y si se pierde con convicción puede transformarse en resistencia."
  },
  {
    id: "resistance",
    label: "Resistance",
    category: "Técnico",
    short: "Zona donde históricamente apareció oferta.",
    detail: "Una resistencia frena avances o exige más volumen para romperse. Si el precio no logra superarla varias veces, el mercado está diciendo que aún no valida niveles más altos."
  },
  {
    id: "mean-reversion",
    label: "Mean Reversion",
    category: "Setup",
    short: "Buscar retorno hacia una media o equilibrio.",
    detail: "La reversión a la media intenta explotar excesos de corto plazo. Funciona mejor en mercados laterales o cuando un movimiento se estiró demasiado sin nueva información."
  },
  {
    id: "trend-following",
    label: "Trend Following",
    category: "Setup",
    short: "Seguir una tendencia ya confirmada.",
    detail: "No intenta adivinar pisos ni techos. Busca sumarse a una dirección ya vigente mientras la estructura, el volumen y el contexto general la sostienen."
  },
  {
    id: "risk-reward",
    label: "Risk / Reward",
    category: "Riesgo",
    short: "Relación entre lo que podés perder y lo que aspirás a ganar.",
    detail: "Una buena tesis con mal risk/reward puede ser una mala operación. La entrada, el stop y el target tienen que justificar el riesgo que estás tomando."
  },
  {
    id: "drawdown",
    label: "Drawdown",
    category: "Riesgo",
    short: "Caída desde un máximo hasta un mínimo posterior.",
    detail: "El drawdown mide dolor real de estrategia o portfolio. Dos setups con el mismo retorno final pueden ser muy distintos si uno te obligó a soportar una caída mucho mayor."
  },
  {
    id: "slippage",
    label: "Slippage",
    category: "Ejecución",
    short: "Diferencia entre el precio esperado y el ejecutado.",
    detail: "En activos ilíquidos o eventos rápidos, el slippage puede destruir una ventaja estadística. Por eso el backtest serio siempre debería modelarlo."
  },
  {
    id: "liquidity",
    label: "Liquidity",
    category: "Ejecución",
    short: "Facilidad para entrar y salir sin mover mucho el precio.",
    detail: "La liquidez importa tanto como la tesis. Un activo poco líquido te puede dar una buena señal y aun así convertirse en una mala operación por spread y ejecución."
  },
  {
    id: "gap-risk",
    label: "Gap Risk",
    category: "Riesgo",
    short: "Riesgo de que el precio abra muy lejos del cierre previo.",
    detail: "El gap risk aparece mucho alrededor de earnings, noticias o macro. Es clave porque puede saltarse tu stop y empeorar mucho el resultado esperado."
  },
  {
    id: "market-cap",
    label: "Market Cap",
    category: "Fundamental",
    short: "Valor bursátil total de la compañía.",
    detail: "La capitalización de mercado te da una escala del tamaño de la empresa. No dice si está barata o cara, pero cambia expectativas de crecimiento, riesgo y liquidez."
  },
  {
    id: "pe-ratio",
    label: "P/E",
    category: "Fundamental",
    short: "Relación entre precio de la acción y ganancias por acción.",
    detail: "Price-to-Earnings ratio. Se usa para comparar valuación relativa: cuánto paga el mercado por cada unidad de ganancia. En Twitter suele verse como P/E o PE, pero sin crecimiento, márgenes y contexto sectorial puede engañar.",
    keywords: ["pe", "p/e", "price earnings", "price to earnings", "valuacion"]
  },
  {
    id: "guidance",
    label: "Guidance",
    category: "Evento",
    short: "Proyección futura que hace la propia empresa.",
    detail: "Muchas veces el mercado reacciona más al guidance que al número del trimestre. Un beat con guía floja puede caer igual."
  },
  {
    id: "beat-miss",
    label: "Beat / Miss",
    category: "Evento",
    short: "Superar o decepcionar expectativas del mercado.",
    detail: "No alcanza con mirar si ganó más o menos. También importa contra qué expectativa se compara y cómo queda la historia de crecimiento hacia adelante."
  },
  {
    id: "vix",
    label: "VIX",
    category: "Macro",
    short: "Índice de volatilidad implícita del S&P 500.",
    detail: "Se usa como termómetro de miedo del mercado. Cuando sube demasiado, los setups técnicos suelen requerir más confirmación y menor tamaño."
  },
  {
    id: "beta",
    label: "Beta",
    category: "Macro",
    short: "Sensibilidad de una acción frente al mercado general.",
    detail: "Una beta alta amplifica movimientos del índice. En un régimen risk-off, un activo con beta alta puede sufrir más aunque su historia individual siga intacta."
  },
  {
    id: "take-profit",
    label: "Take Profit",
    category: "Riesgo",
    short: "Zona donde decidís realizar ganancia parcial o total.",
    detail: "Definir salida antes de entrar evita convertir una operación buena en una decisión emocional. Puede ser fijo, técnico o dinámico según el setup."
  },
  {
    id: "hedge",
    label: "Hedge",
    category: "Riesgo",
    short: "Cobertura para reducir exposición no deseada.",
    detail: "Un hedge no busca maximizar retorno sino amortiguar un riesgo puntual. Puede hacerse con puts, con posiciones inversas o con instrumentos macro."
  },
  {
    id: "bull-trap",
    label: "Bull Trap",
    category: "Técnico",
    short: "Falsa ruptura alcista que revierte rápido.",
    detail: "La bull trap suele dejar compradores atrapados arriba. Aparece cuando un breakout no logra sostenerse y el contexto no convalida el movimiento."
  },
  {
    id: "bear-trap",
    label: "Bear Trap",
    category: "Técnico",
    short: "Falsa ruptura bajista que rebota enseguida.",
    detail: "La bear trap castiga a quien entra tarde al downside. Puede ser señal de absorción de oferta y gatillo para un rebote fuerte."
  }
];

const FEATURED_TERM_IDS = new Set([
  "rsi",
  "macd",
  "adx",
  "atr",
  "long",
  "short",
  "call",
  "put",
  "cedear",
  "mep",
  "ccl",
  "vix",
  "stop-loss",
  "earnings",
  "probability-up"
]);

const state = {
  ticker: "AAPL",
  horizon: "short",
  radarItems: [],
  universe: [],
  learningFilter: "all",
  learningQuery: "",
  authMode: "login",
  accessToken: window.localStorage.getItem(AUTH_TOKEN_KEY),
  profile: null,
  instrumentType: "cedear",
  portfolioSummary: null,
  activeSurface: "workspace",
  analysisRequestId: 0
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
  newsTitle: document.querySelector("#news-title"),
  newsChip: document.querySelector("#news-chip"),
  newsFeed: document.querySelector("#news-feed"),
  earningsTitle: document.querySelector("#earnings-title"),
  earningsChip: document.querySelector("#earnings-chip"),
  tickerEarningsFeed: document.querySelector("#ticker-earnings-feed"),
  portfolioEarningsFeed: document.querySelector("#portfolio-earnings-feed"),
  workspaceTitle: document.querySelector("#workspace-title"),
  marketChip: document.querySelector("#market-chip"),
  marketOverviewTitle: document.querySelector("#market-overview-title"),
  marketOverviewChip: document.querySelector("#market-overview-chip"),
  marketOverviewSummary: document.querySelector("#market-overview-summary"),
  marketOverviewGrid: document.querySelector("#market-overview-grid"),
  marketOverviewWarnings: document.querySelector("#market-overview-warnings"),
  status: document.querySelector("#analysis-status"),
  datalist: document.querySelector("#ticker-suggestions"),
  horizonButtons: Array.from(document.querySelectorAll(".horizon-pill")),
  surfaceButtons: Array.from(document.querySelectorAll("[data-surface]")),
  workspaceSurface: document.querySelector("#surface-workspace"),
  howtoSurface: document.querySelector("#surface-howto"),
  learningSurface: document.querySelector("#surface-learning"),
  tradingSurface: document.querySelector("#surface-trading"),
  conceptRibbon: document.querySelector("#concept-ribbon"),
  tooltipPreview: document.querySelector("#tooltip-preview"),
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
  portfolioImportForm: document.querySelector("#portfolio-import-form"),
  portfolioImportFile: document.querySelector("#portfolio-import-file"),
  portfolioImportReplace: document.querySelector("#portfolio-import-replace"),
  portfolioImportStatus: document.querySelector("#portfolio-import-status"),
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
  holdingsGrid: document.querySelector("#holdings-grid"),
  benchmarkPanel: document.querySelector("#benchmark-panel"),
  benchmarkBars: document.querySelector("#benchmark-bars")
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

const SURFACE_ORDER = ["workspace", "howto", "learning", "trading"];

function setSurface(surface) {
  const previousSurface = state.activeSurface;
  state.activeSurface = surface;
  const surfaces = {
    workspace: elements.workspaceSurface,
    howto: elements.howtoSurface,
    learning: elements.learningSurface,
    trading: elements.tradingSurface
  };

  // Direction (forward / backward) drives the slide side via CSS.
  // Forward = right-to-left enter; backward = left-to-right enter.
  const slider = document.querySelector(".surface-slider");
  if (slider) {
    const fromIndex = SURFACE_ORDER.indexOf(previousSurface || "workspace");
    const toIndex = SURFACE_ORDER.indexOf(surface);
    const direction = toIndex >= fromIndex ? "forward" : "backward";
    slider.setAttribute("data-direction", direction);
    slider.setAttribute("data-active-surface", surface);
  }

  Object.entries(surfaces).forEach(([key, node]) => {
    if (!node) return;
    // Active swap via opacity/transform (no display:none), so revealing
    // animations don't restart and the swap takes ~200ms instead of ~1s.
    node.classList.toggle("is-active", key === surface);
  });
  elements.surfaceButtons.forEach((button) => {
    const isSelected = button.dataset.surface === surface;
    button.classList.toggle("is-selected", isSelected);
    button.setAttribute("aria-selected", isSelected ? "true" : "false");
  });
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
  const featuredTerms = GLOSSARY_TERMS.filter((term) => FEATURED_TERM_IDS.has(term.id));
  const categories = glossaryCategories();
  const categoryTerms = state.learningFilter === "all"
    ? GLOSSARY_TERMS
    : GLOSSARY_TERMS.filter((term) => term.category === state.learningFilter);
  const visibleTerms = categoryTerms.filter((term) => matchesLearningQuery(term, state.learningQuery));
  const categoryCounts = new Map();
  GLOSSARY_TERMS.forEach((term) => {
    categoryCounts.set(term.category, (categoryCounts.get(term.category) || 0) + 1);
  });

  elements.conceptRibbon.innerHTML = featuredTerms.map(
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
          <button
            type="button"
            class="info-badge"
            data-term-id="${term.id}"
            aria-label="Explicación rápida de ${term.label}"
          >?</button>
        </div>
        <p class="learning-short">${highlightLearningText(term.short, state.learningQuery)}</p>
        <p class="learning-detail">${highlightLearningText(term.detail, state.learningQuery)}</p>
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

function setLearningFilter(filter) {
  state.learningFilter = filter;
  renderGlossary();
  clearTermPreview();
}

function setLearningQuery(query) {
  state.learningQuery = String(query || "");
  renderGlossary();
  clearTermPreview();
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
  elements.body.dataset.loggedIn = "false";
  elements.authForm.classList.remove("is-hidden");
  elements.profileShell.classList.add("is-hidden");
  elements.portfolioLockedState.classList.remove("is-hidden");
  elements.portfolioShell.classList.add("is-hidden");
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
  elements.body.dataset.loggedIn = "true";
  elements.authForm.classList.add("is-hidden");
  elements.profileShell.classList.remove("is-hidden");
  elements.portfolioLockedState.classList.add("is-hidden");
  elements.portfolioShell.classList.remove("is-hidden");
  hydrateProfile(state.profile);
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
    await loadRankings();
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
    await loadRankings();
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
    await loadPortfolioEarningsWatch();
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
    renderBenchmarkBars(summary);
    return;
  }

  renderBenchmarkBars(summary);

  elements.holdingsGrid.innerHTML = summary.positions
    .map((position) => {
      const inflation = position.benchmark_comparisons.find((item) => item.label === "inflation");
      const plazoFijo = position.benchmark_comparisons.find((item) => item.label === "plazo_fijo");
      const ccl = position.benchmark_comparisons.find((item) => item.label === "ccl_usd");
      const ratioLine = position.cedear_ratio
        ? `<span class="tone-chip">Ratio ${position.cedear_ratio} · ${escapeText(toHeadline(position.cedear_ratio_source || "manual"))}</span>`
        : "";
      const noteList = position.notes.length
        ? `<ul class="warning-list compact-list">${position.notes.map((note) => `<li>${escapeText(note)}</li>`).join("")}</ul>`
        : "";
      return `
        <article class="holding-card">
          <div class="holding-head">
            <div>
              <p class="analysis-kicker">${toHeadline(position.instrument_type)}</p>
              <h3>${escapeText(position.symbol)}</h3>
              <p class="panel-caption">${escapeText(position.underlying_ticker)} · Compra ${escapeText(position.purchase_date)}</p>
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

const BENCHMARK_LABELS = {
  official_usd: "Oficial",
  mep_usd: "MEP",
  ccl_usd: "CCL",
  inflation: "Inflación",
  plazo_fijo: "Plazo Fijo"
};

function renderBenchmarkBars(summary) {
  if (!elements.benchmarkPanel || !elements.benchmarkBars) return;

  if (!summary || !summary.positions_count || !Array.isArray(summary.positions) || !summary.positions.length) {
    elements.benchmarkPanel.classList.add("is-hidden");
    elements.benchmarkBars.innerHTML = "";
    return;
  }

  // Aggregate tracked_value_ars per benchmark label across positions, and sum outperformance to derive a portfolio-level pct.
  const aggregates = new Map();
  let portfolioInvestedArs = 0;

  summary.positions.forEach((position) => {
    const comparisons = Array.isArray(position.benchmark_comparisons) ? position.benchmark_comparisons : [];
    comparisons.forEach((cmp) => {
      if (!cmp || typeof cmp.tracked_value_ars !== "number") return;
      const entry = aggregates.get(cmp.label) || { trackedArs: 0, outArs: 0 };
      entry.trackedArs += cmp.tracked_value_ars;
      entry.outArs += typeof cmp.outperformance_ars === "number" ? cmp.outperformance_ars : 0;
      aggregates.set(cmp.label, entry);
    });
  });

  // Portfolio value = average benchmark tracked + outperformance won't be exact across all benchmarks; instead use total_value_ars.
  const portfolioArs = typeof summary.total_value_ars === "number" ? summary.total_value_ars : 0;

  const benchmarkRows = Array.from(aggregates.entries())
    .filter(([label]) => BENCHMARK_LABELS[label])
    .map(([label, value]) => {
      const trackedArs = value.trackedArs;
      const outArs = portfolioArs - trackedArs;
      const outPct = trackedArs !== 0 ? outArs / Math.abs(trackedArs) : 0;
      return {
        key: label,
        label: BENCHMARK_LABELS[label],
        valueArs: trackedArs,
        outperformancePct: outPct,
        tone: outArs >= 0 ? "bull" : "bear"
      };
    });

  const rows = [
    ...benchmarkRows,
    {
      key: "__portfolio__",
      label: "Mi portfolio",
      valueArs: portfolioArs,
      outperformancePct: null,
      tone: "paper"
    }
  ];

  const maxValue = rows.reduce((acc, row) => Math.max(acc, Math.abs(row.valueArs)), 0) || 1;

  elements.benchmarkPanel.classList.remove("is-hidden");
  elements.benchmarkBars.innerHTML = rows
    .map((row) => {
      const widthPct = Math.max(2, (Math.abs(row.valueArs) / maxValue) * 100);
      const outChip = row.outperformancePct !== null
        ? `<span class="benchmark-out ${row.tone}">${formatPercent(row.outperformancePct)}</span>`
        : `<span class="benchmark-out paper">Tu valor</span>`;
      return `
        <div class="benchmark-row" data-row="${escapeText(row.key)}">
          <div class="benchmark-meta">
            <span class="benchmark-label">${escapeText(row.label)}</span>
            <span class="benchmark-value">${formatCurrency(row.valueArs, "ARS")}</span>
          </div>
          <div class="benchmark-track" role="presentation">
            <div class="benchmark-fill ${row.tone}" style="width:${widthPct.toFixed(2)}%"></div>
          </div>
          ${outChip}
        </div>
      `;
    })
    .join("");
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
  const rankings = await fetchJson(`/rankings?horizon=${state.horizon}&limit=6&cedear_only=true`, {
    auth: Boolean(state.accessToken)
  });
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
      const reasons = Array.isArray(item.why_for_you) ? item.why_for_you : [];
      const reasonsHtml = reasons.length
        ? `<div class="why-for-you">${reasons
            .map((reason) => `<span class="why-chip">${escapeText(reason)}</span>`)
            .join("")}</div>`
        : "";
      return `
        <button
          class="radar-card ${item.ticker === state.ticker ? "is-selected" : ""}"
          data-ticker="${escapeText(item.ticker)}"
          type="button"
        >
          <div class="radar-card-top">
            <span class="radar-chip">${label}</span>
            <strong>${escapeText(item.ticker)}</strong>
          </div>
          <h3>${toHeadline(item.action)} / ${item.regime}</h3>
          <p>Score ${item.rank_score.toFixed(2)} · Convicción ${(item.conviction * 100).toFixed(0)}% · CEDEAR ${item.is_cedear ? "sí" : "no"}</p>
          ${reasonsHtml}
        </button>
      `;
    })
    .join("");
}

function escapeText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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
  syncSelection();
  setLoading(true);
  primeContextLoading(ticker);
  setStatus(`Corriendo análisis real para ${ticker} en ${state.horizon}...`);

  try {
    const [analysisResult, marketResult, newsResult, earningsResult] = await Promise.allSettled([
      fetchJson("/analyze", {
        method: "POST",
        body: JSON.stringify({
          ticker,
          horizon: state.horizon
        })
      }),
      fetchJson(`/market/overview?ticker=${encodeURIComponent(ticker)}&horizon=${encodeURIComponent(state.horizon)}`),
      fetchJson(`/news/${ticker}?limit=6`),
      fetchJson(`/earnings/${ticker}?days_ahead=180`)
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
    const cedearMessage = state.universe.includes(ticker)
      ? "Ticker con CEDEAR disponible."
      : "Ticker fuera del universo CEDEAR sugerido. Se analiza igual, pero no se usará en rankings.";
    setStatus(`Análisis listo para ${ticker}. ${cedearMessage}`);
  } catch (error) {
    if (requestId !== state.analysisRequestId) return;
    renderErrorState(ticker, error);
    renderMarketOverviewError(error.message);
    renderNewsError(error.message);
    renderTickerEarningsError(error.message);
    setStatus(`No se pudo analizar ${ticker}: ${error.message}`);
  } finally {
    if (requestId === state.analysisRequestId) {
      setLoading(false);
    }
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

function renderMarketOverview(overview) {
  const regimeLabel = overview.regime === "risk_on"
    ? "Risk on"
    : overview.regime === "risk_off"
      ? "Risk off"
      : "Mixed";
  const breadthLabel = overview.breadth ? `Breadth ${toHeadline(overview.breadth)}` : "Breadth n/d";

  elements.marketOverviewTitle.textContent = `Tape general ${regimeLabel}`;
  elements.marketOverviewChip.textContent = breadthLabel;
  elements.marketOverviewSummary.textContent = overview.summary;

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
      const source = item.source_url
        ? `<a class="context-link" href="${escapeAttribute(item.source_url)}" target="_blank" rel="noreferrer">Fuente</a>`
        : "";
      return `<li>${escapeText(item.name)} ${chip} ${source}</li>`;
    })
    .join("");
}

function renderNewsCard(item) {
  const sentimentTone = item.sentiment >= 0.15 ? "bull" : item.sentiment <= -0.15 ? "bear" : "neutral";
  const confidencePct = Math.round((item.confidence || 0) * 100);
  const linkOpen = item.url
    ? `<a class="context-link" href="${escapeAttribute(item.url)}" target="_blank" rel="noreferrer">Abrir</a>`
    : `<span class="context-link is-muted">Sin link</span>`;
  const summary = item.summary ? `<p>${escapeText(item.summary)}</p>` : "";
  return `
    <article class="context-card">
      <div class="context-card-top">
        <span class="tone-chip">${escapeText(item.impact_category || "general")}</span>
        <span class="signal-chip ${sentimentTone}">${sentimentTone === "bull" ? "Bullish" : sentimentTone === "bear" ? "Bearish" : "Neutral"}</span>
      </div>
      <h4>${escapeText(item.title)}</h4>
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
    ? formatPercent(item.relative_to_sma20_pct)
    : "n/d";
  const sma50 = item.relative_to_sma50_pct !== null && item.relative_to_sma50_pct !== undefined
    ? formatPercent(item.relative_to_sma50_pct)
    : "n/d";
  const toneLabel = item.tone === "bull" ? "Constructivo" : item.tone === "bear" ? "Presión" : "Mixto";
  return `
    <article class="market-pulse-card ${escapeText(item.tone || "neutral")}">
      <div class="context-card-top">
        <span class="tone-chip">${escapeText(item.category)}</span>
        <span class="signal-chip ${escapeText(item.tone || "neutral")}">${toneLabel}</span>
      </div>
      <h4>${escapeText(item.label)}</h4>
      <p>${escapeText(item.note)}</p>
      <div class="context-meta">
        <span>Precio ${formatMacroValue(item.symbol, item.price)}</span>
        <span>Día ${formatPercent(item.day_change_pct)}</span>
        <span>vs SMA20 ${sma20}</span>
      </div>
      <div class="context-meta">
        <span>Símbolo ${escapeText(item.symbol)}</span>
        <span>vs SMA50 ${sma50}</span>
        <span>Tono ${toneLabel}</span>
      </div>
    </article>
  `;
}

function renderEarningsEventCard(event, options = {}) {
  const compact = Boolean(options.compact);
  const estimateLine = event.eps_estimate !== null && event.eps_estimate !== undefined
    ? `EPS est. ${event.eps_estimate}`
    : "EPS est. n/d";
  return `
    <article class="earnings-card ${compact ? "is-compact" : ""}">
      <div class="context-card-top">
        <span class="tone-chip">${escapeText(event.ticker)}</span>
        <span class="signal-chip neutral">${escapeText(event.report_time || "Time TBD")}</span>
      </div>
      <h4>${escapeText(formatDateLabel(event.report_date))}</h4>
      <p>${escapeText(estimateLine)}</p>
    </article>
  `;
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
});

elements.authForm.addEventListener("submit", handleAuthSubmit);
elements.profileForm.addEventListener("submit", handleProfileSubmit);
elements.logoutButton.addEventListener("click", handleLogout);
elements.portfolioImportForm.addEventListener("submit", handlePortfolioImportSubmit);
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
