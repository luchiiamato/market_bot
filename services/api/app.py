from __future__ import annotations

import os
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[2]
ENGINE_SRC = ROOT_DIR / "packages" / "engine" / "src"
IDENTITY_SRC = ROOT_DIR / "packages" / "identity" / "src"
PORTFOLIO_SRC = ROOT_DIR / "packages" / "portfolio" / "src"
REFERENCE_SRC = ROOT_DIR / "packages" / "reference_data" / "src"
CHAT_SRC = ROOT_DIR / "packages" / "chat" / "src"
FRONTEND_DIR = ROOT_DIR / "apps" / "web" / "prototype"

for source_dir in (ENGINE_SRC, IDENTITY_SRC, PORTFOLIO_SRC, REFERENCE_SRC, CHAT_SRC):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from market_bot import Horizon, MarketBotService, ProfileFilter  # noqa: E402
from market_bot.config import is_cedear_ticker  # noqa: E402
from market_bot.data import MarketDataError  # noqa: E402
from market_bot.utils import TTLCache  # noqa: E402
from market_identity import (  # noqa: E402
    AuthenticatedUser,
    IdentityService,
    list_decisions,
    record_decision,
)
from market_identity.service import IdentityError  # noqa: E402
from market_portfolio import BalanzImportSkip, PortfolioError, PortfolioService, parse_balanz_extract  # noqa: E402
from market_reference import (  # noqa: E402
    ArgentinaBenchmarkError,
    ArgentinaBenchmarkService,
    fetch_earnings_history,
    fetch_news,
    upcoming_earnings,
)

from .schemas import (  # noqa: E402
    AnalyzeRequest,
    BalanzImportResponse,
    BalanzImportSkipResponse,
    CreatePositionRequest,
    DecisionRequest,
    DecisionResponse,
    EarningsEventResponse,
    EarningsHistoryEventResponse,
    EarningsHistoryResponse,
    HealthResponse,
    InvestorProfileResponse,
    LoginRequest,
    MarketOverviewResponse,
    MarketPulseItemResponse,
    NewsItemResponse,
    PeriodBenchmarkResponse,
    PortfolioSummaryResponse,
    PositionValuationResponse,
    ProfileUpdateRequest,
    RankingItemResponse,
    RegisterRequest,
    ReliabilityBinResponse,
    SessionResponse,
    TickerAnalysisResponse,
    UpdatePositionRequest,
    UniverseItemResponse,
    ValidationReportResponse,
)

app = FastAPI(
    title="Market Bot API",
    version="0.2.0",
    description="API inicial para analisis, perfil inversor y portfolio CEDEAR-aware.",
)

benchmark_service = ArgentinaBenchmarkService()
service = MarketBotService()
identity_service = IdentityService()
portfolio_service = PortfolioService(benchmark_service=benchmark_service)

MARKET_OVERVIEW_UNIVERSE = (
    {"symbol": "SPY", "label": "S&P 500", "category": "indices"},
    {"symbol": "QQQ", "label": "Nasdaq 100", "category": "indices"},
    {"symbol": "IWM", "label": "Russell 2000", "category": "breadth"},
    {"symbol": "^VIX", "label": "VIX", "category": "volatility"},
    {"symbol": "BTC-USD", "label": "Bitcoin", "category": "crypto"},
    {"symbol": "CL=F", "label": "Crude Oil", "category": "macro"},
    {"symbol": "^TNX", "label": "UST 10Y", "category": "rates"},
)

# CORS origins are configurable via env vars so production can lock down the
# allowed domains while local dev keeps the permissive default. Preview
# deployments on Vercel need regex support because Starlette does not expand
# wildcard subdomains inside ``allow_origins``.
_raw_cors = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
if _raw_cors == "*" or not _raw_cors:
    _cors_origins: list[str] = ["*"]
else:
    _cors_origins = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]
_cors_origin_regex = os.getenv("CORS_ALLOW_ORIGIN_REGEX", "").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON request logging + per-request UUID. Middleware order is
# innermost-first, so attaching this **after** CORS means it logs every HTTP
# request (including CORS preflights).
from .logging_config import (  # noqa: E402
    auth_failure_retry_after,
    clear_auth_failures,
    install_request_logging,
    record_auth_failure,
    rate_limit,
)

install_request_logging(app)

# Boot log so we can confirm deploy-time configuration without digging.
from .logging_config import configure_logger  # noqa: E402

configure_logger().info(
    "boot",
    extra={
        "db_path": os.getenv("MARKET_BOT_DB_PATH", "<default>"),
        "cors_origins": _cors_origins,
        "cors_origin_regex": _cors_origin_regex,
        "fly_region": os.getenv("FLY_REGION", "local"),
        "fly_app": os.getenv("FLY_APP_NAME", ""),
    },
)

api_logger = configure_logger()


@app.on_event("startup")
def _warm_rankings_cache() -> None:
    """Pre-compute the default landing ranking in a background thread so the
    first visitor (a tester!) gets an instant cached result instead of waiting
    ~60s for 57 tickers to be analyzed cold. Best-effort: any failure is
    swallowed; the cache just stays cold and the normal request path fills it.
    """
    import sys
    import threading
    import time as _time

    # Don't warm during the test suite: the daemon thread races with tests
    # that reload market_bot.config / clear caches, causing flaky failures.
    # Also allow an explicit opt-out for environments that don't want it.
    if "pytest" in sys.modules or os.getenv("MARKET_BOT_WARM_RANKINGS", "1") == "0":
        return

    def _warm() -> None:
        # Re-warm every 8 min — under the 600s ranking cache TTL — so the
        # cache never goes cold while a tester is exploring the app.
        from market_bot.config import SUGGESTION_UNIVERSE

        # Top tickers to pre-analyze individually so the first "Analizar setup"
        # for these is a cache hit (~instant) instead of cold ML inference.
        TOP_TICKERS_TO_ANALYZE = SUGGESTION_UNIVERSE[:10]

        while True:
            # Warm BOTH modes for both horizons. "opportunities" was the last
            # cold path a tester could hit (default + analysis are already warm),
            # so warming it here closes the gap WITHOUT a fast-path model that
            # would make the ranking's numbers diverge from the detail view.
            # (See docs/plan-tester-ready.md — decision against 1A.3.)
            for horizon in (Horizon.SHORT, Horizon.LONG):
                for warm_mode in ("default", "opportunities"):
                    try:
                        started = _time.perf_counter()
                        service.rank_universe(
                            horizon, limit=6, cedear_only=True, mode=warm_mode
                        )
                        elapsed = int((_time.perf_counter() - started) * 1000)
                        api_logger.info(
                            "rankings warmup done",
                            extra={
                                "horizon": horizon.value,
                                "mode": warm_mode,
                                "elapsed_ms": elapsed,
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        api_logger.info(
                            "rankings warmup failed",
                            extra={"horizon": horizon.value, "mode": warm_mode, "error": str(exc)},
                        )

            # Pre-analyze top tickers with full context so the first individual
            # analysis request from the tester hits the cache.
            for ticker in TOP_TICKERS_TO_ANALYZE:
                try:
                    service.analyze_ticker(ticker, Horizon.SHORT)
                    api_logger.info("analyze warmup done", extra={"ticker": ticker})
                except Exception as exc:  # noqa: BLE001
                    api_logger.info("analyze warmup failed", extra={"ticker": ticker, "error": str(exc)})

            _time.sleep(480)

    threading.Thread(target=_warm, name="rankings-warmup", daemon=True).start()


MARKET_OVERVIEW_CACHE: TTLCache[MarketOverviewResponse] = TTLCache(ttl_seconds=180)
NEWS_CACHE: TTLCache[list[NewsItemResponse]] = TTLCache(ttl_seconds=300)
EARNINGS_CACHE: TTLCache[list[EarningsEventResponse]] = TTLCache(ttl_seconds=900)
# Historical surprise grid is immutable once a quarter is reported and the
# upstream call is expensive (one yfinance fetch + price history). Cache for 24h
# in a dedicated bucket so it never collides with the upcoming-events cache.
EARNINGS_HISTORY_CACHE: TTLCache[EarningsHistoryResponse] = TTLCache(ttl_seconds=24 * 60 * 60)

# Rate limit dependencies — declared once so the same instances are reused.
REGISTER_RATE_LIMIT = rate_limit(key="auth_register", max_hits=3, window_seconds=60 * 60)
ANALYZE_RATE_LIMIT = rate_limit(key="analyze", max_hits=30, window_seconds=60)

app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


def _frontend_entrypoint_exists() -> bool:
    return (FRONTEND_DIR / "index.html").exists()


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization requerida.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token invalido.")
    return token.strip()


def get_current_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> AuthenticatedUser:
    token = _extract_bearer_token(authorization)
    try:
        return identity_service.authenticate(token)
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def get_optional_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> Optional[AuthenticatedUser]:
    """Resolve a logged-in user when an Authorization header is present,
    otherwise return ``None``. Lets endpoints personalise themselves
    without forcing auth on anonymous traffic."""
    if not authorization:
        return None
    try:
        token = _extract_bearer_token(authorization)
        return identity_service.authenticate(token)
    except (HTTPException, IdentityError):
        return None


def _log_endpoint_timing(name: str, started_at: float, **extra) -> None:
    api_logger.info(
        "endpoint_timing",
        extra={
            "endpoint": name,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
            **extra,
        },
    )


def _news_items_response(items, limit: int | None = None) -> list[NewsItemResponse]:
    selected = items[:limit] if limit is not None else items
    return [
        NewsItemResponse(
            ticker=item.ticker,
            title=item.title,
            url=item.url,
            source=item.source,
            summary=item.summary,
            sentiment=item.sentiment,
            impact_category=item.impact_category,
            confidence=item.confidence,
            published_at=item.published_at,
            fetched_at=item.fetched_at,
        )
        for item in selected
    ]


def _earnings_events_response(events) -> list[EarningsEventResponse]:
    return [
        EarningsEventResponse(
            ticker=event.ticker,
            report_date=event.report_date,
            report_time=event.report_time,
            eps_estimate=event.eps_estimate,
            eps_actual=event.eps_actual,
            revenue_estimate=event.revenue_estimate,
            revenue_actual=event.revenue_actual,
        )
        for event in events
    ]


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    if _frontend_entrypoint_exists():
        return RedirectResponse(url="/app/")
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — always returns 200 if the process is up."""
    return HealthResponse(status="ok", service="market-bot-api")


@app.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    """Readiness probe — verifies the DB is queryable.

    Fly.io and most orchestrators check this to decide if the instance can
    receive traffic. We keep it cheap (one PRAGMA), but if the DB volume
    isn't mounted yet, this fails and the deploy is rolled back.
    """
    from market_identity.store import connection

    try:
        with connection() as conn:
            conn.execute("PRAGMA quick_check").fetchone()
    except Exception as exc:  # noqa: BLE001 — broad catch is intentional here
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"DB no esta disponible: {exc}",
        ) from exc
    return HealthResponse(status="ready", service="market-bot-api")


@app.post(
    "/auth/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(REGISTER_RATE_LIMIT)],
)
def register(request: RegisterRequest) -> SessionResponse:
    try:
        session = identity_service.register_user(
            username=request.username,
            password=request.password,
            display_name=request.display_name,
            investor_profile=request.investor_profile,
            preferred_horizon=request.preferred_horizon,
            preferred_instrument_types=request.preferred_instrument_types,
            risk_tolerance=request.risk_tolerance,
            benchmark_preference=request.benchmark_preference,
        )
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SessionResponse(
        access_token=session.access_token,
        expires_at=session.expires_at,
        profile=InvestorProfileResponse.model_validate(session.profile, from_attributes=True),
    )


@app.post(
    "/auth/login",
    response_model=SessionResponse,
)
def login(request: LoginRequest, http_request: Request) -> SessionResponse:
    retry_after = auth_failure_retry_after(
        key="auth_login_failed",
        request=http_request,
        subject=request.username,
        max_hits=5,
        window_seconds=15 * 60,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit excedido. Volve a intentar en unos segundos.",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        session = identity_service.login_user(request.username, request.password)
    except IdentityError as exc:
        record_auth_failure(
            key="auth_login_failed",
            request=http_request,
            subject=request.username,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    clear_auth_failures(
        key="auth_login_failed",
        request=http_request,
        subject=request.username,
    )
    return SessionResponse(
        access_token=session.access_token,
        expires_at=session.expires_at,
        profile=InvestorProfileResponse.model_validate(session.profile, from_attributes=True),
    )


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> Response:
    token = _extract_bearer_token(authorization)
    identity_service.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/profile", response_model=InvestorProfileResponse)
def profile(current_user: AuthenticatedUser = Depends(get_current_user)) -> InvestorProfileResponse:
    profile = identity_service.get_profile(current_user.user_id)
    return InvestorProfileResponse.model_validate(profile, from_attributes=True)


@app.put("/profile", response_model=InvestorProfileResponse)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> InvestorProfileResponse:
    profile = identity_service.update_profile(
        current_user.user_id,
        display_name=request.display_name,
        investor_profile=request.investor_profile,
        preferred_horizon=request.preferred_horizon,
        preferred_instrument_types=request.preferred_instrument_types,
        risk_tolerance=request.risk_tolerance,
        benchmark_preference=request.benchmark_preference,
    )
    return InvestorProfileResponse.model_validate(profile, from_attributes=True)


@app.post("/portfolio/positions", response_model=PositionValuationResponse, status_code=status.HTTP_201_CREATED)
def create_position(
    request: CreatePositionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PositionValuationResponse:
    profile = identity_service.get_profile(current_user.user_id)
    try:
        position = portfolio_service.add_position(
            user_id=current_user.user_id,
            instrument_type=request.instrument_type,
            symbol=request.symbol,
            quantity=request.quantity,
            purchase_date=request.purchase_date,
            purchase_price=request.purchase_price,
            purchase_currency=request.purchase_currency,
            benchmark_preference=profile.benchmark_preference,
            risk_tolerance=profile.risk_tolerance,
            underlying_ticker=request.underlying_ticker,
            cedear_ratio=request.cedear_ratio,
            notes=request.notes,
        )
    except (PortfolioError, ArgentinaBenchmarkError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PositionValuationResponse.model_validate(position, from_attributes=True)


@app.put("/portfolio/positions/{position_id}", response_model=PositionValuationResponse)
def update_position(
    position_id: int,
    request: UpdatePositionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PositionValuationResponse:
    profile = identity_service.get_profile(current_user.user_id)
    try:
        position = portfolio_service.update_position(
            position_id=position_id,
            user_id=current_user.user_id,
            instrument_type=request.instrument_type,
            symbol=request.symbol,
            quantity=request.quantity,
            purchase_date=request.purchase_date,
            purchase_price=request.purchase_price,
            purchase_currency=request.purchase_currency,
            benchmark_preference=profile.benchmark_preference,
            risk_tolerance=profile.risk_tolerance,
            underlying_ticker=request.underlying_ticker,
            cedear_ratio=request.cedear_ratio,
            notes=request.notes,
        )
    except (PortfolioError, ArgentinaBenchmarkError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PositionValuationResponse.model_validate(position, from_attributes=True)


@app.get("/portfolio/positions", response_model=list[PositionValuationResponse])
def list_positions(current_user: AuthenticatedUser = Depends(get_current_user)) -> list[PositionValuationResponse]:
    profile = identity_service.get_profile(current_user.user_id)
    positions = portfolio_service.list_positions(
        current_user.user_id,
        profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )
    return [PositionValuationResponse.model_validate(item, from_attributes=True) for item in positions]


@app.delete("/portfolio/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    portfolio_service.delete_position(position_id, current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary(current_user: AuthenticatedUser = Depends(get_current_user)) -> PortfolioSummaryResponse:
    profile = identity_service.get_profile(current_user.user_id)
    summary = portfolio_service.portfolio_summary(
        current_user.user_id,
        profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )
    return PortfolioSummaryResponse.model_validate(summary, from_attributes=True)


@app.get("/portfolio/benchmarks/custom")
def portfolio_custom_benchmark(
    ticker: str = Query(..., min_length=1, max_length=14),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Compute hypothetical portfolio value if the user had bought TICKER on
    each purchase date instead of the actual stocks. Powers the ad-hoc
    benchmark feature in the UI ("¿qué hubiera pasado con SPY en lugar de
    estas acciones?")."""
    profile = identity_service.get_profile(current_user.user_id)
    try:
        return portfolio_service.custom_benchmark_comparison(
            current_user.user_id,
            ticker=ticker,
            benchmark_preference=profile.benchmark_preference,
            risk_tolerance=profile.risk_tolerance,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.get("/portfolio/diagnostics")
def portfolio_diagnostics(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Per-position raw valuation data — used to investigate why a number
    looks off. Surfaces local BYMA price, ratio, implied FX, and drift vs CCL."""
    profile = identity_service.get_profile(current_user.user_id)
    return portfolio_service.diagnostics(
        current_user.user_id,
        benchmark_preference=profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )


@app.post("/portfolio/import/balanz", response_model=BalanzImportResponse)
async def import_balanz_extract(
    request: Request,
    replace_existing: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> BalanzImportResponse:
    profile = identity_service.get_profile(current_user.user_id)
    raw_file = await request.body()
    try:
        parsed = parse_balanz_extract(raw_file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not parsed.positions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El extracto no contiene posiciones importables de CEDEARs o stocks.",
        )

    if replace_existing:
        portfolio_service.clear_positions(current_user.user_id)

    imported_symbols: list[str] = []
    skipped_rows = list(parsed.skipped)
    for draft in parsed.positions:
        try:
            portfolio_service.add_position(
                user_id=current_user.user_id,
                instrument_type=draft.instrument_type,
                symbol=draft.symbol,
                quantity=draft.quantity,
                purchase_date=draft.purchase_date,
                purchase_price=draft.purchase_price,
                purchase_currency=draft.purchase_currency,
                benchmark_preference=profile.benchmark_preference,
                risk_tolerance=profile.risk_tolerance,
                underlying_ticker=draft.underlying_ticker,
                notes=draft.notes,
                purchase_ccl=getattr(draft, "purchase_ccl", None),
                purchase_mep=getattr(draft, "purchase_mep", None),
                purchase_official=getattr(draft, "purchase_official", None),
            )
        except (PortfolioError, ArgentinaBenchmarkError) as exc:
            skipped_rows.append(
                BalanzImportSkip(
                    row_number=draft.row_number,
                    ticker=draft.symbol,
                    reason=str(exc),
                )
            )
            continue
        imported_symbols.append(draft.symbol)

    summary = portfolio_service.portfolio_summary(
        current_user.user_id,
        profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )
    return BalanzImportResponse(
        source_sheet=parsed.source_sheet,
        imported_count=len(imported_symbols),
        skipped_count=len(skipped_rows),
        replace_existing=replace_existing,
        positions_count_after=summary.positions_count,
        imported_symbols=sorted(set(imported_symbols)),
        skipped_rows=[
            BalanzImportSkipResponse(
                row_number=item.row_number,
                ticker=item.ticker,
                reason=item.reason,
            )
            for item in skipped_rows[:12]
        ],
    )


@app.get("/benchmarks/current", response_model=PeriodBenchmarkResponse)
def current_benchmarks(
    from_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PeriodBenchmarkResponse:
    del current_user
    try:
        period = benchmark_service.build_period_snapshot(
            start_date=PathDateParser.parse(from_date),
            end_date=PathDateParser.today(),
        )
    except ArgentinaBenchmarkError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PeriodBenchmarkResponse.model_validate(period, from_attributes=True)


@app.post(
    "/analyze",
    response_model=TickerAnalysisResponse,
    dependencies=[Depends(ANALYZE_RATE_LIMIT)],
)
def analyze(request: AnalyzeRequest) -> TickerAnalysisResponse:
    started_at = time.perf_counter()
    try:
        analysis = service.analyze_ticker(request.ticker.upper(), Horizon(request.horizon))
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _log_endpoint_timing("analyze", started_at, ticker=request.ticker.upper(), horizon=request.horizon)
    return TickerAnalysisResponse.model_validate(analysis, from_attributes=True)


@app.get("/rankings", response_model=list[RankingItemResponse])
def rankings(
    horizon: str = Query(default="short", pattern="^(short|long)$"),
    limit: int = Query(default=6, ge=1, le=25),
    cedear_only: bool = Query(default=True),
    mode: str = Query(
        default="default",
        pattern="^(default|opportunities)$",
        description=(
            "default: ranking estándar con boost por catalysts. "
            "opportunities: solo nombres con catalyst / volumen / volatilidad altos, "
            "sin index ETFs."
        ),
    ),
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> list[RankingItemResponse]:
    started_at = time.perf_counter()
    profile_filter = None
    if current_user is not None:
        profile = identity_service.get_profile(current_user.user_id)
        profile_filter = ProfileFilter(
            investor_profile=profile.investor_profile,
            risk_tolerance=profile.risk_tolerance,
            preferred_horizon=profile.preferred_horizon,
            preferred_instrument_types=profile.preferred_instrument_types,
        )
    try:
        ranked = service.rank_universe(
            Horizon(horizon),
            limit=limit,
            cedear_only=cedear_only,
            profile=profile_filter,
            mode=mode,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _log_endpoint_timing(
        "rankings",
        started_at,
        horizon=horizon,
        limit=limit,
        cedear_only=cedear_only,
        mode=mode,
        personalized=bool(profile_filter),
        result_count=len(ranked),
    )

    return [
        RankingItemResponse(
            ticker=analysis.ticker,
            action=analysis.actions[0].action.value if analysis.actions else "hold",
            direction=analysis.deterministic.direction.value,
            rank_score=score,
            conviction=analysis.probabilistic.confidence,
            price=analysis.indicators.price,
            regime=analysis.deterministic.regime,
            is_cedear=is_cedear_ticker(analysis.ticker),
            why_for_you=reasons,
        )
        for analysis, score, reasons in ranked
    ]


@app.get("/validation/{ticker}", response_model=ValidationReportResponse)
def validation_report(
    ticker: str,
    horizon: str = Query(default="short", pattern="^(short|long)$"),
    horizon_days: Optional[int] = Query(default=None, ge=1, le=60),
    warmup: int = Query(default=60, ge=10, le=400),
    step_days: int = Query(default=5, ge=1, le=20),
) -> ValidationReportResponse:
    """Run walk-forward calibration for ``ticker`` and return Brier metrics.

    Public on purpose — it's a "track record of the engine" view that helps
    a sceptical user decide whether to trust the model at all.

    Sprint 9.1: if ``horizon_days`` is omitted, it defaults to the SAME horizon
    the model predicts (``target_horizon_bars``) so the Brier reflects the real
    target, not next-bar.
    """
    from market_bot.models import target_horizon_bars  # local import, avoids cycle

    resolved_horizon_days = (
        horizon_days if horizon_days is not None else target_horizon_bars(Horizon(horizon))
    )
    try:
        result = service.validate_ticker(
            ticker.upper(),
            Horizon(horizon),
            warmup=warmup,
            horizon_days=resolved_horizon_days,
            step_days=step_days,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ValidationReportResponse(
        ticker=ticker.upper(),
        horizon=horizon,
        warmup=warmup,
        horizon_days=resolved_horizon_days,
        step_days=step_days,
        sample_size=result.sample_size,
        brier_score=result.brier_score,
        reliability_bins=[
            ReliabilityBinResponse(
                bin_lower=b.bin_lower,
                bin_upper=b.bin_upper,
                sample_size=b.sample_size,
                mean_predicted=b.mean_predicted,
                fraction_positive=b.fraction_positive,
            )
            for b in result.reliability_bins
        ],
    )


@app.post("/decisions", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
def create_decision(
    request: DecisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DecisionResponse:
    """Record a user-confirmed decision against a fresh analysis snapshot.

    We re-run :meth:`MarketBotService.analyze_ticker` here rather than trust
    the client to hand us the snapshot. The persisted JSON becomes the
    ground-truth input for the future calibration pipeline.
    """
    try:
        analysis = service.analyze_ticker(request.ticker.upper(), Horizon(request.horizon))
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    primary_action = analysis.actions[0] if analysis.actions else None
    conviction = float(primary_action.conviction) if primary_action is not None else None

    snapshot_payload = TickerAnalysisResponse.model_validate(analysis, from_attributes=True).model_dump(mode="json")
    record = record_decision(
        user_id=current_user.user_id,
        ticker=request.ticker.upper(),
        horizon=request.horizon,
        action_taken=request.action_taken,
        analysis_snapshot=snapshot_payload,
        conviction=conviction,
        rationale=request.rationale,
    )
    return DecisionResponse(
        decision_id=record.decision_id,
        ticker=record.ticker,
        horizon=record.horizon,
        action_taken=record.action_taken,
        conviction=record.conviction,
        rationale=record.rationale,
        decided_at=record.decided_at,
        realized_return=record.realized_return,
        realized_at=record.realized_at,
        analysis_snapshot=record.analysis_snapshot,
    )


@app.get("/decisions", response_model=list[DecisionResponse])
def list_my_decisions(
    since: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    ticker: Optional[str] = Query(default=None, min_length=1, max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[DecisionResponse]:
    since_date = PathDateParser.parse(since) if since else None
    records = list_decisions(
        current_user.user_id,
        since=since_date,
        ticker=ticker.upper() if ticker else None,
        limit=limit,
    )
    return [
        DecisionResponse(
            decision_id=record.decision_id,
            ticker=record.ticker,
            horizon=record.horizon,
            action_taken=record.action_taken,
            conviction=record.conviction,
            rationale=record.rationale,
            decided_at=record.decided_at,
            realized_return=record.realized_return,
            realized_at=record.realized_at,
            analysis_snapshot=record.analysis_snapshot,
        )
        for record in records
    ]


@app.get("/news/{ticker}", response_model=list[NewsItemResponse])
def news_for_ticker(
    ticker: str,
    limit: int = Query(default=12, ge=1, le=50),
) -> list[NewsItemResponse]:
    started_at = time.perf_counter()
    normalized_ticker = ticker.upper()
    cache_key = ("news", normalized_ticker)
    cached = NEWS_CACHE.get(cache_key)
    cache_hit = cached is not None
    if cached is None:
        cached = _news_items_response(fetch_news(normalized_ticker))
        NEWS_CACHE.set(cache_key, cached)
    _log_endpoint_timing("news", started_at, ticker=normalized_ticker, limit=limit, cache_hit=cache_hit)
    return cached[:limit]


@app.get("/earnings/{ticker}", response_model=list[EarningsEventResponse])
def earnings_for_ticker(
    ticker: str,
    days_ahead: int = Query(default=180, ge=1, le=365),
) -> list[EarningsEventResponse]:
    started_at = time.perf_counter()
    normalized_ticker = ticker.upper()
    cache_key = ("ticker", normalized_ticker, days_ahead)
    cached = EARNINGS_CACHE.get(cache_key)
    cache_hit = cached is not None
    if cached is None:
        events = upcoming_earnings([normalized_ticker], days_ahead=days_ahead)
        cached = _earnings_events_response(events)
        EARNINGS_CACHE.set(cache_key, cached)
    _log_endpoint_timing(
        "earnings_ticker",
        started_at,
        ticker=normalized_ticker,
        days_ahead=days_ahead,
        cache_hit=cache_hit,
    )
    return cached


@app.get("/earnings/{ticker}/history", response_model=EarningsHistoryResponse)
def earnings_history_for_ticker(
    ticker: str,
    limit: int = Query(default=12, ge=1, le=24),
) -> EarningsHistoryResponse:
    """Last ``limit`` reported quarters with EPS surprise and next-day return.

    Public (matches the rest of the earnings surface). Soft-fails: if the
    upstream data source has nothing (recent IPO, ticker typo, network hiccup)
    we return ``{"ticker": X, "events": []}`` with HTTP 200 — the UI shows the
    empty state. Cached 24h per ticker+limit because reported quarters don't
    change retroactively.
    """
    started_at = time.perf_counter()
    normalized_ticker = ticker.upper()
    cache_key = ("history", normalized_ticker, limit)
    cached = EARNINGS_HISTORY_CACHE.get(cache_key)
    cache_hit = cached is not None
    if cached is None:
        try:
            rows = fetch_earnings_history(normalized_ticker, limit=limit)
        except Exception:  # pragma: no cover — defensive, adapter already soft-fails
            rows = []
        events = [EarningsHistoryEventResponse(**row) for row in rows]
        cached = EarningsHistoryResponse(ticker=normalized_ticker, events=events)
        EARNINGS_HISTORY_CACHE.set(cache_key, cached)
    _log_endpoint_timing(
        "earnings_history",
        started_at,
        ticker=normalized_ticker,
        limit=limit,
        cache_hit=cache_hit,
    )
    return cached


@app.get("/market/overview", response_model=MarketOverviewResponse)
def market_overview(
    ticker: Optional[str] = Query(default=None, min_length=1, max_length=16),
    horizon: str = Query(default="short", pattern="^(short|long)$"),
) -> MarketOverviewResponse:
    started_at = time.perf_counter()
    normalized_ticker = ticker.upper() if ticker else None
    cache_key = (normalized_ticker, horizon)
    cached = MARKET_OVERVIEW_CACHE.get(cache_key)
    cache_hit = cached is not None
    if cached is not None:
        _log_endpoint_timing(
            "market_overview",
            started_at,
            ticker=normalized_ticker,
            horizon=horizon,
            cache_hit=cache_hit,
        )
        return cached
    try:
        overview = _build_market_overview(
            ticker=normalized_ticker,
            horizon=Horizon(horizon),
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    MARKET_OVERVIEW_CACHE.set(cache_key, overview)
    _log_endpoint_timing(
        "market_overview",
        started_at,
        ticker=normalized_ticker,
        horizon=horizon,
        cache_hit=cache_hit,
    )
    return overview


@app.get("/earnings/upcoming", response_model=list[EarningsEventResponse])
def earnings_upcoming(
    days_ahead: int = Query(default=60, ge=1, le=365),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[EarningsEventResponse]:
    started_at = time.perf_counter()
    profile = identity_service.get_profile(current_user.user_id)
    positions = portfolio_service.list_positions(
        current_user.user_id,
        profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )
    tickers = sorted({position.underlying_ticker for position in positions})
    if not tickers:
        tickers = service.suggested_cedear_universe()
    cache_key = ("upcoming", current_user.user_id, days_ahead, tuple(tickers))
    cached = EARNINGS_CACHE.get(cache_key)
    cache_hit = cached is not None
    if cached is None:
        events = upcoming_earnings(tickers, days_ahead=days_ahead)
        cached = _earnings_events_response(events)
        EARNINGS_CACHE.set(cache_key, cached)
    _log_endpoint_timing(
        "earnings_upcoming",
        started_at,
        user_id=current_user.user_id,
        days_ahead=days_ahead,
        tickers=len(tickers),
        cache_hit=cache_hit,
    )
    return cached


@app.get("/universe", response_model=list[UniverseItemResponse])
def universe(cedear_only: bool = Query(default=True)) -> list[UniverseItemResponse]:
    if cedear_only:
        return [
            UniverseItemResponse(ticker=ticker, is_cedear=True)
            for ticker in service.suggested_cedear_universe()
        ]

    return [
        UniverseItemResponse(ticker=ticker, is_cedear=is_cedear_ticker(ticker))
        for ticker in service.suggested_cedear_universe()
    ]


def _build_market_overview(
    ticker: Optional[str],
    horizon: Horizon,
) -> MarketOverviewResponse:
    instruments: list[MarketPulseItemResponse] = []
    loader_notes: list[str] = []

    for item in MARKET_OVERVIEW_UNIVERSE:
        try:
            history = service.adapter.get_price_history(item["symbol"], Horizon.LONG)
        except Exception:
            loader_notes.append(f"No se pudo cargar {item['label']}.")
            continue
        instruments.append(_build_market_pulse_item(item, history.frame))

    if not instruments:
        raise MarketDataError("No se pudo construir el overview del mercado.")

    regime, breadth, summary, warnings = _summarize_market_regime(instruments, ticker, horizon)
    return MarketOverviewResponse(
        generated_at=datetime.utcnow(),
        ticker=ticker,
        horizon=horizon.value,
        regime=regime,
        breadth=breadth,
        summary=summary,
        warnings=[*warnings, *loader_notes],
        instruments=instruments,
    )


def _build_market_pulse_item(item: dict[str, str], frame) -> MarketPulseItemResponse:
    closes = frame["Close"].tail(60)
    price = float(closes.iloc[-1])
    previous_close = float(closes.iloc[-2]) if len(closes) > 1 else price
    day_change_pct = ((price - previous_close) / previous_close) if previous_close else 0.0
    sma20 = float(closes.tail(20).mean()) if len(closes) >= 20 else None
    sma50 = float(closes.tail(50).mean()) if len(closes) >= 50 else None
    relative_to_sma20_pct = ((price - sma20) / sma20) if sma20 else None
    relative_to_sma50_pct = ((price - sma50) / sma50) if sma50 else None
    tone = _market_item_tone(
        item["symbol"],
        price,
        day_change_pct,
        relative_to_sma20_pct,
        relative_to_sma50_pct,
    )
    note = _market_item_note(
        item["symbol"],
        day_change_pct,
        relative_to_sma20_pct,
        relative_to_sma50_pct,
    )
    return MarketPulseItemResponse(
        symbol=item["symbol"],
        label=item["label"],
        category=item["category"],
        price=price,
        day_change_pct=day_change_pct,
        relative_to_sma20_pct=relative_to_sma20_pct,
        relative_to_sma50_pct=relative_to_sma50_pct,
        tone=tone,
        note=note,
    )


def _market_item_tone(
    symbol: str,
    price: float,
    day_change_pct: float,
    relative_to_sma20_pct: Optional[float],
    relative_to_sma50_pct: Optional[float],
) -> str:
    if symbol == "^VIX":
        if price >= 22 or day_change_pct >= 0.03:
            return "bear"
        if price <= 18 and day_change_pct <= 0:
            return "bull"
        return "neutral"
    if symbol == "^TNX":
        if day_change_pct >= 0.025 and (relative_to_sma20_pct or 0) > 0:
            return "bear"
        if day_change_pct <= -0.02:
            return "bull"
        return "neutral"
    if symbol == "CL=F":
        if day_change_pct >= 0.03 and (relative_to_sma20_pct or 0) > 0:
            return "bear"
        if day_change_pct <= -0.02:
            return "bull"
        return "neutral"
    if (relative_to_sma20_pct or 0) > 0 and day_change_pct >= 0:
        return "bull"
    if (relative_to_sma50_pct or 0) < 0 and day_change_pct <= 0:
        return "bear"
    return "neutral"


def _market_item_note(
    symbol: str,
    day_change_pct: float,
    relative_to_sma20_pct: Optional[float],
    relative_to_sma50_pct: Optional[float],
) -> str:
    if symbol == "^VIX":
        if (relative_to_sma20_pct or 0) > 0:
            return "Volatilidad en ascenso; el mercado puede castigar setups frágiles."
        return "Volatilidad contenida; favorece continuidad si el resto del tape acompaña."
    if symbol == "BTC-USD":
        if day_change_pct <= -0.04:
            return "Cripto cayendo fuerte; suele contagiar el apetito por riesgo."
        if day_change_pct >= 0.03:
            return "Cripto firme; suele ayudar al sesgo risk-on."
        return "Cripto lateral; hoy aporta poco edge macro."
    if symbol == "CL=F":
        if day_change_pct >= 0.03:
            return "Petróleo acelerando; puede reabrir presión inflacionaria."
        return "Petróleo sin shock visible; el frente inflacionario no domina hoy."
    if symbol == "^TNX":
        if day_change_pct >= 0.025:
            return "La tasa larga sube; suele comprimir múltiplos de growth."
        if day_change_pct <= -0.02:
            return "La tasa larga afloja; le quita presión a valuaciones exigentes."
        return "Las tasas largas están estables; el foco vuelve a earnings y tape."
    if (relative_to_sma20_pct or 0) > 0 and (relative_to_sma50_pct or 0) > 0:
        return "Cotiza arriba de medias cortas e intermedias; el liderazgo técnico sigue sano."
    if (relative_to_sma50_pct or 0) < 0:
        return "Sigue debajo de la media intermedia; todavía no confirma recuperación amplia."
    return "Lectura mixta; la dirección existe, pero la convicción del tape no es total."


def _summarize_market_regime(
    instruments: list[MarketPulseItemResponse],
    ticker: Optional[str],
    horizon: Horizon,
) -> tuple[str, str, str, list[str]]:
    by_symbol = {item.symbol: item for item in instruments}
    warnings: list[str] = []
    risk_on_votes = 0
    risk_off_votes = 0

    for symbol in ("SPY", "QQQ", "IWM"):
        item = by_symbol.get(symbol)
        if not item:
            continue
        if (item.relative_to_sma20_pct or 0) > 0:
            risk_on_votes += 1
        else:
            risk_off_votes += 1

    vix = by_symbol.get("^VIX")
    if vix:
        if vix.price >= 22 or vix.day_change_pct >= 0.03:
            risk_off_votes += 2
            warnings.append("VIX elevado: el mercado está más sensible a sorpresas y gaps.")
        elif vix.price <= 18 and vix.day_change_pct <= 0:
            risk_on_votes += 1

    btc = by_symbol.get("BTC-USD")
    if btc:
        if btc.day_change_pct <= -0.05:
            risk_off_votes += 1
            warnings.append("Bitcoin cae fuerte y puede contagiar apetito por riesgo.")
        elif btc.day_change_pct >= 0.03:
            risk_on_votes += 1

    oil = by_symbol.get("CL=F")
    if oil and oil.day_change_pct >= 0.03:
        warnings.append("Petróleo subiendo con fuerza: posible presión extra sobre inflación y tasas.")

    rates = by_symbol.get("^TNX")
    if rates and rates.day_change_pct >= 0.025:
        risk_off_votes += 1
        warnings.append("La tasa del Treasury a 10Y acelera: growth y múltiplos altos suelen sufrir.")

    breadth_positive = sum(
        1
        for symbol in ("SPY", "QQQ", "IWM")
        if by_symbol.get(symbol) and (by_symbol[symbol].relative_to_sma20_pct or 0) > 0
    )
    breadth = "amplio" if breadth_positive == 3 else "selectivo" if breadth_positive == 2 else "estrecho"
    if breadth == "estrecho":
        warnings.append("La participación es angosta: pocos índices sostienen el movimiento.")

    if risk_on_votes >= risk_off_votes + 2:
        regime = "risk_on"
        summary = "El tape general acompaña: índices firmes y volatilidad controlada sostienen un sesgo constructivo."
    elif risk_off_votes >= risk_on_votes + 2:
        regime = "risk_off"
        summary = "El mercado está defensivo: la macro pesa más y los setups débiles se rompen más fácil."
    else:
        regime = "mixed"
        summary = "La lectura macro está mezclada: conviene exigir más confirmación antes de sobreponderar un trade."

    if ticker:
        summary = f"{summary} Para {ticker}, conviene operar sólo si su tesis va a favor del régimen."
    if horizon == Horizon.LONG:
        summary = f"{summary} En largo plazo pesa más la estructura de índices y tasas que el ruido intradía."

    return regime, breadth, summary, warnings


class PathDateParser:
    @staticmethod
    def parse(raw_value: str):
        from datetime import date

        return date.fromisoformat(raw_value)

    @staticmethod
    def today():
        from datetime import date

        return date.today()


CHAT_PORTFOLIO_KEYWORDS = (
    "portfolio",
    "cartera",
    "posiciones",
    "posicion",
    "exposicion",
    "rendimiento",
    "ganancia",
    "pnl",
    "benchmark",
    "benchmarks",
    "cartera",
    "holding",
    "holdings",
)


def _normalize_chat_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value or "").lower())
    return normalized.encode("ascii", "ignore").decode("ascii")


def _message_needs_portfolio_context(message_content: str) -> bool:
    normalized = _normalize_chat_text(message_content)
    return any(keyword in normalized for keyword in CHAT_PORTFOLIO_KEYWORDS)


def _format_chat_money(value: float, currency: str) -> str:
    prefix = "US$" if currency.upper() == "USD" else "$"
    return f"{prefix}{value:,.2f}"


def _format_chat_pct(value: float) -> str:
    # `value` is a ratio (0.1234 -> "12.34%"). All callers pass ratios.
    return f"{value * 100:.2f}%"


def _build_chat_profile_context(user_id: int) -> str:
    profile = identity_service.get_profile(user_id)
    return "\n".join(
        [
            "PERFIL DEL USUARIO:",
            f"- Nombre visible: {profile.display_name}",
            f"- Perfil inversor: {profile.investor_profile}",
            f"- Horizonte preferido: {profile.preferred_horizon}",
            f"- Instrumentos preferidos: {profile.preferred_instrument_types}",
            f"- Tolerancia al riesgo: {profile.risk_tolerance}",
            f"- Benchmark preferido: {profile.benchmark_preference}",
            f"- Moneda local: {profile.local_currency}",
        ]
    )


def _build_chat_portfolio_context(user_id: int) -> str:
    profile = identity_service.get_profile(user_id)
    summary = portfolio_service.portfolio_summary(
        user_id,
        profile.benchmark_preference,
        risk_tolerance=profile.risk_tolerance,
    )
    if summary.positions_count == 0:
        return "PORTFOLIO DEL USUARIO:\n- No hay posiciones cargadas todavia."

    top_positions = sorted(summary.positions, key=lambda item: item.current_value_ars, reverse=True)[:3]
    top_sectors = summary.sector_exposure[:3]
    top_regions = summary.region_exposure[:3]

    lines = [
        "PORTFOLIO DEL USUARIO:",
        f"- Posiciones cargadas: {summary.positions_count}",
        f"- Valor total ARS: {_format_chat_money(summary.total_value_ars, 'ARS')}",
        f"- Valor total USD: {_format_chat_money(summary.total_value_usd, 'USD')}",
        f"- P&L ARS: {_format_chat_money(summary.total_pnl_ars, 'ARS')} ({_format_chat_pct(summary.total_return_pct_ars)})",
        f"- P&L USD: {_format_chat_money(summary.total_pnl_usd, 'USD')} ({_format_chat_pct(summary.total_return_pct_usd)})",
        f"- Retorno real vs inflacion: {_format_chat_pct(summary.total_real_return_pct)}",
        f"- Retorno vs benchmark preferido ({summary.preferred_benchmark_label}): {_format_chat_pct(summary.total_preferred_benchmark_return_pct)}",
    ]

    if top_positions:
        lines.append("- Principales posiciones por peso actual:")
        for position in top_positions:
            weight = (position.current_value_ars / summary.total_value_ars) if summary.total_value_ars else 0.0
            lines.append(
                f"  - {position.symbol}: {_format_chat_money(position.current_value_ars, 'ARS')} | "
                f"P&L {_format_chat_pct(position.return_pct_ars)} | peso {_format_chat_pct(weight)}"
            )

    if top_sectors:
        sectors = ", ".join(f"{item.label} {_format_chat_pct(item.pct)}" for item in top_sectors)
        lines.append(f"- Exposicion sectorial principal: {sectors}")

    if top_regions:
        regions = ", ".join(f"{item.label} {_format_chat_pct(item.pct)}" for item in top_regions)
        lines.append(f"- Exposicion geografica principal: {regions}")

    return "\n".join(lines)


def _build_chat_system_prompt(current_user: AuthenticatedUser, message_content: str) -> str:
    sections = [
        SYSTEM_PROMPT_BASELINE,
        _build_chat_profile_context(current_user.user_id),
    ]
    # Inject the portfolio context whenever the user actually has positions —
    # the keyword gate missed obvious questions ("cuál es mi P&L?") and left the
    # bot answering "no tengo tus datos", which is confusing. The context is
    # ~600 tokens, so always-on is cheap and makes the assistant reliably aware.
    # If the user has no positions we skip it (nothing useful to add) unless the
    # message explicitly asks about portfolio (so the bot can say "cargá posiciones").
    try:
        portfolio_context = _build_chat_portfolio_context(current_user.user_id)
        has_positions = "No hay posiciones cargadas" not in portfolio_context
        if has_positions or _message_needs_portfolio_context(message_content):
            sections.append(portfolio_context)
            sections.append(
                "INSTRUCCION DE USO DEL CONTEXTO: si el usuario pregunta por su portfolio, "
                "P&L, rendimiento, posiciones o exposicion, usa estos datos como fuente de "
                "verdad y evita responder de forma generica."
            )
    except Exception as exc:  # noqa: BLE001
        if _message_needs_portfolio_context(message_content):
            sections.append(
                "PORTFOLIO DEL USUARIO:\n"
                f"- No se pudo cargar el resumen del portfolio en este momento ({exc})."
            )
    return "\n\n".join(section for section in sections if section)


# ---------------------------------------------------------------------------
# Chat (Sprint 8 + 8.5) — multi-provider chat with persistence, rate limit,
# audit log and cost tracking. Providers and the router are imported lazily
# so an environment without the SDKs still boots the API (the only effect is
# ``/chat/providers`` reports ``configured: false`` for every entry).
# ---------------------------------------------------------------------------
from market_chat import (  # noqa: E402
    ChatMessage,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatProviderInfo,
    ChatRouter,
    ChatRouterError,
    ChatThreadCreateRequest,
    ChatThreadUpdateRequest,
    ChatThreadResponse,
    ChatUsageResponse,
    SYSTEM_PROMPT_BASELINE,
    append_message,
    create_thread,
    delete_thread,
    ensure_chat_schema,
    get_thread,
    list_messages,
    list_threads,
    update_thread_title,
    usage_for_user,
)
from market_chat.schemas import ChatSendResponse  # noqa: E402

chat_router = ChatRouter()
ensure_chat_schema()

CHAT_MESSAGE_RATE_LIMIT = rate_limit(key="chat_message", max_hits=20, window_seconds=60 * 60)


@app.get("/chat/providers", response_model=list[ChatProviderInfo])
def chat_providers() -> list[ChatProviderInfo]:
    """Public listing of configured providers — never exposes API keys."""

    return [ChatProviderInfo(**entry) for entry in chat_router.available_providers()]


@app.post("/chat/threads", response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
def create_chat_thread(
    request: ChatThreadCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatThreadResponse:
    thread = create_thread(
        user_id=current_user.user_id,
        title=request.title or "Nueva conversación",
        provider=request.provider,
        model=request.model,
    )
    return ChatThreadResponse.model_validate(thread, from_attributes=True)


@app.get("/chat/threads", response_model=list[ChatThreadResponse])
def list_chat_threads(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[ChatThreadResponse]:
    threads = list_threads(current_user.user_id)
    return [ChatThreadResponse.model_validate(t, from_attributes=True) for t in threads]


@app.patch("/chat/threads/{thread_id}", response_model=ChatThreadResponse)
def patch_chat_thread(
    thread_id: int,
    request: ChatThreadUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatThreadResponse:
    thread = update_thread_title(thread_id, current_user.user_id, request.title)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada.",
        )
    return ChatThreadResponse.model_validate(thread, from_attributes=True)


@app.delete("/chat/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chat_thread(
    thread_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    deleted = delete_thread(thread_id, current_user.user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/chat/threads/{thread_id}/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    thread_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    if get_thread(thread_id, current_user.user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada.",
        )
    rows = list_messages(thread_id, current_user.user_id)
    return [ChatMessageResponse.model_validate(row, from_attributes=True) for row in rows]


@app.post(
    "/chat/threads/{thread_id}/messages",
    response_model=ChatSendResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(CHAT_MESSAGE_RATE_LIMIT)],
)
def post_chat_message(
    thread_id: int,
    request: ChatMessageRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ChatSendResponse:
    """Send a user message; persist user + assistant turns; return both.

    Flow: persist the user message → ask the router for a provider → call the
    SDK → persist the assistant reply with usage metadata → return both rows
    plus a per-message usage block for the UI.
    """

    thread = get_thread(thread_id, current_user.user_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada.",
        )

    # Resolve provider: explicit > thread default > router default.
    try:
        if request.provider:
            provider = chat_router.get_provider(request.provider)
        elif thread.provider:
            provider = chat_router.get_provider(thread.provider)
        else:
            provider = chat_router.default_provider()
    except ChatRouterError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    chosen_model = request.model or thread.model or provider.default_model

    # Persist the inbound user turn BEFORE calling the provider. If the SDK
    # call fails the user's message is still in the history, which matches the
    # mental model of "I said something, the bot didn't answer".
    user_row = append_message(
        thread_id=thread_id,
        role=request.role,
        content=request.content,
        provider=None,
        model=None,
    )

    # Rebuild conversation history (oldest first) for the provider.
    history_rows = list_messages(thread_id, current_user.user_id)
    history = [
        ChatMessage(role=row.role, content=row.content)
        for row in history_rows
        if row.role in {"user", "assistant", "system"}
    ]
    system_prompt = _build_chat_system_prompt(current_user, request.content)

    try:
        response = provider.chat(
            messages=history,
            system=system_prompt,
            model=chosen_model,
        )
    except Exception as exc:  # noqa: BLE001 — surface SDK / network errors as 502
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El provider falló: {exc}",
        ) from exc

    assistant_row = append_message(
        thread_id=thread_id,
        role="assistant",
        content=response.text,
        provider=response.provider,
        model=response.model,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        latency_ms=response.latency_ms,
    )

    return ChatSendResponse(
        user_message=ChatMessageResponse.model_validate(user_row, from_attributes=True),
        assistant_message=ChatMessageResponse.model_validate(assistant_row, from_attributes=True),
        usage={
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "provider": response.provider,
            "model": response.model,
        },
    )


@app.get("/chat/usage", response_model=ChatUsageResponse)
def chat_usage(current_user: AuthenticatedUser = Depends(get_current_user)) -> ChatUsageResponse:
    """Aggregate spend per provider + day/month for the current user."""

    payload = usage_for_user(current_user.user_id)
    return ChatUsageResponse.model_validate(payload)
