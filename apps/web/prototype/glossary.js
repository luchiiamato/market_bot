// Glossary data — lazy-loaded when the Learning surface activates for the
// first time. Splitting this out shaves ~50KB from the initial bundle.
// app.js injects this script on demand via createElement("script").

window.MARKET_BOT_GLOSSARY = [
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
  },

  // ─── Acronyms financieros + conceptos trending (2026) ──────────────────────
  {
    id: "ath",
    label: "ATH",
    category: "Acronym",
    short: "All-Time High — el precio más alto que jamás registró el activo.",
    detail: "All-Time High. Cuando un activo rompe ATH, sale a precio descubrimiento: no hay resistencia histórica arriba. Suele ser zona de FOMO compradora y también de toma de ganancias institucional."
  },
  {
    id: "atl",
    label: "ATL",
    category: "Acronym",
    short: "All-Time Low — el precio más bajo registrado.",
    detail: "All-Time Low. Inverso del ATH. Romper ATL suele ser señal técnica destructiva — todos los que compraron arriba están perdiendo y la presión vendedora aumenta. Cuidado con cuchillos cayendo."
  },
  {
    id: "cagr",
    label: "CAGR",
    category: "Acronym",
    short: "Tasa de crecimiento anual compuesta de una inversión.",
    detail: "Compound Annual Growth Rate. Es el rendimiento anualizado equivalente que tendría una inversión si creciera de manera uniforme. Útil para comparar instrumentos con horizontes distintos. Fórmula: (Vf/Vi)^(1/años) − 1."
  },
  {
    id: "ytd",
    label: "YTD",
    category: "Acronym",
    short: "Year-To-Date — desde el 1 de enero hasta hoy.",
    detail: "Year-To-Date. Mide el retorno acumulado en lo que va del año calendario. Es la referencia más usada para comparar performance contra índices (S&P 500 YTD, Merval YTD)."
  },
  {
    id: "mtd",
    label: "MTD",
    category: "Acronym",
    short: "Month-To-Date — desde el inicio del mes en curso.",
    detail: "Month-To-Date. Útil para evaluar performance reciente sin el ruido del año entero. Junto con YTD da una lectura rápida de cómo viene la cosa."
  },
  {
    id: "qtd",
    label: "QTD",
    category: "Acronym",
    short: "Quarter-To-Date — desde el inicio del trimestre.",
    detail: "Quarter-To-Date. Especialmente relevante porque las empresas reportan trimestrales (Q1, Q2, Q3, Q4) y los hedge funds rebalancean al cierre de cada Q."
  },
  {
    id: "fy",
    label: "FY26 / FY27",
    category: "Acronym",
    short: "Fiscal Year — año fiscal de la empresa, no necesariamente calendario.",
    detail: "Fiscal Year. Apple usa FY que termina en septiembre; Microsoft en junio. Cuando un analista dice 'FY27 EPS', se refiere al año fiscal proyectado, no al calendario. Importante para no confundir guidance."
  },
  {
    id: "q1-q4",
    label: "1Q26 / Q1 2026",
    category: "Acronym",
    short: "Cuarto trimestre fiscal. 1Q26 = primer trimestre del FY 2026.",
    detail: "Notación de earnings calls. 1Q26 = Q1 del fiscal year 2026 de la empresa. Cada trimestre tiene un earnings release: revenue, EPS, guidance forward. El movimiento post-earnings suele ser el catalyst más grande del año."
  },
  {
    id: "eps",
    label: "EPS",
    category: "Acronym",
    short: "Earnings Per Share — ganancia neta dividida acciones en circulación.",
    detail: "Earnings Per Share. EPS reportado vs EPS consensus es el dato clave en cada earnings call. Beat = reportado supera estimado. Miss = quedó debajo. La reacción del precio depende más del guidance forward que del EPS pasado."
  },
  {
    id: "pe-ratio",
    label: "P/E",
    category: "Acronym",
    short: "Price-to-Earnings — múltiplo de valuación clásico.",
    detail: "Price-to-Earnings ratio. Cuántos dólares pagás por cada dólar de ganancia anual. P/E alto = mercado paga premium por crecimiento (NVDA, TSLA). P/E bajo = value (XOM, F). Compará siempre contra peers de la misma industria."
  },
  {
    id: "peg",
    label: "PEG",
    category: "Acronym",
    short: "P/E ajustado por crecimiento esperado.",
    detail: "Price/Earnings to Growth. PEG = P/E / tasa de crecimiento %. Idea de Peter Lynch: si PEG < 1, la acción está barata relativa a su crecimiento. Más útil para growth stocks que P/E solo."
  },
  {
    id: "ev-ebitda",
    label: "EV/EBITDA",
    category: "Acronym",
    short: "Múltiplo de valor empresa sobre ganancia operativa.",
    detail: "Enterprise Value / EBITDA. Más limpio que P/E porque elimina el efecto de deuda y impuestos. Estándar para M&A y para comparar empresas con estructuras de capital distintas."
  },
  {
    id: "fcf",
    label: "FCF",
    category: "Acronym",
    short: "Free Cash Flow — caja libre que genera el negocio.",
    detail: "Free Cash Flow = operating cash flow − capex. Es la métrica preferida de inversores serios (Buffett-style) porque es plata real, no contable. FCF yield = FCF / market cap.",
    keywords: ["free cash flow", "fcf yield", "cash flow libre", "caja libre"]
  },
  {
    id: "ltm",
    label: "LTM",
    category: "Acronym",
    short: "Last Twelve Months — los últimos 12 meses móviles.",
    detail: "LTM se usa para mirar revenue, EBITDA, EPS o FCF sin depender del cierre exacto del año fiscal. Cuando ves EV/LTM EBITDA o P/LTM EPS, están annualizando con la ventana más reciente.",
    keywords: ["last twelve months", "ttm", "trailing twelve months", "ultimos 12 meses"]
  },
  {
    id: "roic",
    label: "ROIC",
    category: "Acronym",
    short: "Return on Invested Capital — retorno sobre el capital invertido.",
    detail: "ROIC mide cuánta ganancia operativa genera la empresa por cada dólar realmente invertido en el negocio. Suele usarse para detectar negocios de calidad: ROIC alto y sostenible suele apuntar a ventaja competitiva real.",
    keywords: ["return on invested capital", "retorno sobre capital invertido", "quality compounder"]
  },
  {
    id: "tam",
    label: "TAM",
    category: "Acronym",
    short: "Total Addressable Market — tamaño máximo del mercado.",
    detail: "Total Addressable Market. Cuánta plata podría generar la empresa si capturara el 100% del mercado. TAM grande + bajo penetration % = thesis típica de growth/AI."
  },
  {
    id: "arr",
    label: "ARR / MRR",
    category: "Acronym",
    short: "Annual / Monthly Recurring Revenue de un SaaS.",
    detail: "ARR = Annual Recurring Revenue. MRR = Monthly. Métricas clave para SaaS (Salesforce, Snowflake, CrowdStrike). Crecimiento de ARR > 30% YoY se considera alto. Net Revenue Retention (NRR) > 120% es excelente."
  },
  {
    id: "yoy",
    label: "YoY / QoQ",
    category: "Acronym",
    short: "Year-over-Year / Quarter-over-Quarter — comparación temporal.",
    detail: "YoY (Year over Year) compara el mismo trimestre vs el anterior año. QoQ (Quarter over Quarter) compara consecutivos. YoY es más confiable porque limpia estacionalidad. Headline siempre se reporta YoY."
  },
  {
    id: "guidance",
    label: "Guidance",
    category: "Concepto",
    short: "Proyección de resultados que la empresa publica.",
    detail: "Guidance es el outlook que da la empresa para el próximo trimestre o año fiscal. Un raise = sube la guía vs anterior. Cut = la baja. El precio reacciona MÁS al guidance que al beat/miss del trimestre reportado."
  },
  {
    id: "consensus",
    label: "Consensus",
    category: "Concepto",
    short: "Promedio de estimaciones de analistas para earnings/revenue.",
    detail: "Consensus estimate = el número que el mercado ya espera. Beat/miss se mide contra esto, no contra el año pasado. Whisper number = el número 'real' que se rumorea entre traders, suele ser más exigente que el consensus público."
  },
  {
    id: "buyback",
    label: "Buyback",
    category: "Concepto",
    short: "La empresa compra sus propias acciones en mercado.",
    detail: "Stock buyback / share repurchase. Reduce el número de acciones en circulación → sube EPS automáticamente. Apple, Meta y Google son los reyes del buyback. Suele ser señal de management confiando en su valuación."
  },
  {
    id: "dividend-yield",
    label: "Dividend Yield",
    category: "Concepto",
    short: "Dividendo anual dividido el precio actual.",
    detail: "Yield = dividend per share / price. Las empresas maduras pagan dividendos (KO, JPM, XOM). En Argentina, los CEDEARs también pagan, pero hay que considerar el FX y la retención del 10%."
  },
  {
    id: "moat",
    label: "Moat",
    category: "Concepto",
    short: "Ventaja competitiva sostenible que protege márgenes.",
    detail: "Economic moat. Término popularizado por Buffett. Tipos: network effect (Meta), switching costs (Microsoft), brand (Coca-Cola), low-cost (Costco), intangible assets (patentes). Sin moat, los márgenes se erosionan."
  },
  {
    id: "drawdown",
    label: "Drawdown",
    category: "Riesgo",
    short: "Caída desde el último máximo hasta el mínimo subsecuente.",
    detail: "Max Drawdown = peor caída pico-a-valle que sufrió una inversión. Para evaluar estrategias importa más que el retorno total: una estrategia con +40% retorno pero −60% drawdown probablemente no la tolerás. Calmar ratio = retorno / |max DD|."
  },
  {
    id: "sharpe",
    label: "Sharpe Ratio",
    category: "Riesgo",
    short: "Retorno ajustado por riesgo (volatilidad).",
    detail: "Sharpe = (retorno − tasa libre de riesgo) / desviación estándar. Sharpe > 1 = bueno. > 2 = excelente. > 3 = sospechoso. Mide eficiencia: dos estrategias con mismo retorno pero distinta volatilidad tienen Sharpe distinto."
  },
  {
    id: "beta",
    label: "Beta",
    category: "Riesgo",
    short: "Sensibilidad de un activo al movimiento del mercado.",
    detail: "Beta = covarianza(activo, mercado) / varianza(mercado). β = 1 → se mueve con el S&P. β > 1 → más volátil (NVDA ~1.7). β < 1 → más defensivo (KO ~0.6). β negativa es rara (oro a veces). No confundir con alpha."
  },
  {
    id: "vix",
    label: "VIX",
    category: "Riesgo",
    short: "Índice de volatilidad esperada del S&P 500.",
    detail: "VIX = 'fear index'. Mide volatilidad implícita de opciones del SPX a 30 días. VIX < 15 = mercado tranquilo. > 25 = stress. > 40 = pánico (COVID, 2008). VIX cae cuando el mercado sube, por eso es contrarian."
  },
  {
    id: "fomc",
    label: "FOMC",
    category: "Evento",
    short: "Reunión de la Fed donde se decide la tasa de interés.",
    detail: "Federal Open Market Committee. Se reúne ~8 veces al año. La decisión y el statement de Powell mueven todo: bonos, acciones, dólar, oro, cripto. Dot plot = proyección de tasas. Hawkish = sube tasas / restrictivo. Dovish = baja / acomodaticio."
  },
  {
    id: "cpi-ppi",
    label: "CPI / PPI",
    category: "Evento",
    short: "Inflación al consumidor / al productor — datos macro clave.",
    detail: "CPI (Consumer Price Index) sale mensualmente en USA. PPI (Producer Price Index) anticipa. Core CPI excluye comida y energía (más volátiles). Datos por arriba de expectativas → la Fed sube tasas → S&P baja. Es el calendario macro #1."
  },
  {
    id: "nfp",
    label: "NFP",
    category: "Evento",
    short: "Non-Farm Payrolls — empleo no agrícola de USA.",
    detail: "Sale el primer viernes de cada mes a las 8:30 ET. Mide jobs creados, unemployment rate y wage growth. Strong NFP → Fed hawkish → bonos caen. Weak NFP → posible recesión → flight to safety."
  },
  {
    id: "ai-bubble",
    label: "AI Capex",
    category: "Trending",
    short: "Inversión masiva en infraestructura de IA por hyperscalers.",
    detail: "Microsoft, Meta, Google, Amazon están gastando $200B+ por año en GPUs (NVDA), data centers y energía nuclear (SMR). Trade asociado: AVGO, ANET, VRT, CEG, NRG, ASML. Pregunta abierta: cuándo se monetiza ese capex."
  },
  {
    id: "magnificent-seven",
    label: "Mag 7",
    category: "Trending",
    short: "Las 7 mega-caps tech que mueven el S&P 500.",
    detail: "Magnificent Seven: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA. Pesan ~30% del S&P 500. Si bajan, baja todo el índice. Concentración récord — nunca antes 7 compañías representaron tanto del mercado."
  },
  {
    id: "etf-flows",
    label: "ETF Flows",
    category: "Trending",
    short: "Entradas/salidas netas de capital en ETFs.",
    detail: "ETF inflows = compradores netos pagando primas para entrar al fondo. Outflows = redenciones. SPY, QQQ, IBIT (Bitcoin), GLD son los más seguidos. Flows fuertes confirman tendencia o anticipan capitulación."
  },
  {
    id: "dxy",
    label: "DXY",
    category: "Trending",
    short: "Índice del dólar estadounidense vs canasta de monedas.",
    detail: "Dollar Index. DXY mide USD vs EUR, JPY, GBP, CAD, SEK, CHF. DXY sube → equity emergente (Argentina, Brasil) sufre, oro cae, cripto en general también. DXY < 100 = USD débil. > 105 = fuerte."
  },
  {
    id: "yield-curve",
    label: "Yield Curve",
    category: "Trending",
    short: "Curva de tasas del Tesoro USA por plazo.",
    detail: "Compara 2Y, 10Y, 30Y treasury yields. Inverted yield curve (2Y > 10Y) predijo todas las recesiones desde 1955. Steepening = mercado descuenta crecimiento. Flattening = desaceleración inminente. Hoy el 10Y rinde ~4.2%."
  },
  {
    id: "carry-trade",
    label: "Carry Trade",
    category: "Trending",
    short: "Pedís prestado barato en una moneda, invertís en otra de tasa alta.",
    detail: "Clásico: pedís yenes al 0.5%, invertís en pesos al 100%. Funciona si el FX se mantiene. Cuando el yen se aprecia rápido (2024 BoJ hike), el unwind del carry tira abajo todos los activos en simultáneo. Riesgo de tail."
  },
  {
    id: "dollar-cost-averaging",
    label: "DCA",
    category: "Concepto",
    short: "Dollar-Cost Averaging — comprar en cuotas regulares.",
    detail: "Invertir un monto fijo cada cierto intervalo (semanal/mensual) sin importar el precio. Reduce el riesgo de timing pero también el upside. Es la estrategia recomendada por defecto para inversores no profesionales."
  },
  {
    id: "rebalance",
    label: "Rebalance",
    category: "Concepto",
    short: "Re-ajustar pesos del portfolio a la asignación target.",
    detail: "Si planificaste 60% acciones / 40% bonos pero las acciones subieron y ahora son 70/30, rebalanceás vendiendo acciones y comprando bonos. Sistemático, no emocional. Frecuencia típica: trimestral o anual."
  }
];
window.dispatchEvent(new CustomEvent('market-bot:glossary-ready'));
