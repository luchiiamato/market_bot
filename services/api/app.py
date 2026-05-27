from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[2]
ENGINE_SRC = ROOT_DIR / "packages" / "engine" / "src"
IDENTITY_SRC = ROOT_DIR / "packages" / "identity" / "src"
PORTFOLIO_SRC = ROOT_DIR / "packages" / "portfolio" / "src"
REFERENCE_SRC = ROOT_DIR / "packages" / "reference_data" / "src"
FRONTEND_DIR = ROOT_DIR / "apps" / "web" / "prototype"

for source_dir in (ENGINE_SRC, IDENTITY_SRC, PORTFOLIO_SRC, REFERENCE_SRC):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from market_bot import Horizon, MarketBotService  # noqa: E402
from market_bot.config import is_cedear_ticker  # noqa: E402
from market_bot.data import MarketDataError  # noqa: E402
from market_identity import AuthenticatedUser, IdentityService  # noqa: E402
from market_identity.service import IdentityError  # noqa: E402
from market_portfolio import PortfolioError, PortfolioService  # noqa: E402
from market_reference import (  # noqa: E402
    ArgentinaBenchmarkError,
    ArgentinaBenchmarkService,
)

from .schemas import (  # noqa: E402
    AnalyzeRequest,
    CreatePositionRequest,
    HealthResponse,
    InvestorProfileResponse,
    LoginRequest,
    PeriodBenchmarkResponse,
    PortfolioSummaryResponse,
    PositionValuationResponse,
    ProfileUpdateRequest,
    RankingItemResponse,
    RegisterRequest,
    SessionResponse,
    TickerAnalysisResponse,
    UniverseItemResponse,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


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


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app/")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="market-bot-api")


@app.post("/auth/register", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
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


@app.post("/auth/login", response_model=SessionResponse)
def login(request: LoginRequest) -> SessionResponse:
    try:
        session = identity_service.login_user(request.username, request.password)
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
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
    positions = portfolio_service.list_positions(current_user.user_id, profile.benchmark_preference)
    return [PositionValuationResponse.model_validate(item, from_attributes=True) for item in positions]


@app.delete("/portfolio/positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(position_id: int, current_user: AuthenticatedUser = Depends(get_current_user)) -> Response:
    portfolio_service.delete_position(position_id, current_user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
def portfolio_summary(current_user: AuthenticatedUser = Depends(get_current_user)) -> PortfolioSummaryResponse:
    profile = identity_service.get_profile(current_user.user_id)
    summary = portfolio_service.portfolio_summary(current_user.user_id, profile.benchmark_preference)
    return PortfolioSummaryResponse.model_validate(summary, from_attributes=True)


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


@app.post("/analyze", response_model=TickerAnalysisResponse)
def analyze(request: AnalyzeRequest) -> TickerAnalysisResponse:
    try:
        analysis = service.analyze_ticker(request.ticker.upper(), Horizon(request.horizon))
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TickerAnalysisResponse.model_validate(analysis, from_attributes=True)


@app.get("/rankings", response_model=list[RankingItemResponse])
def rankings(
    horizon: str = Query(default="short", pattern="^(short|long)$"),
    limit: int = Query(default=6, ge=1, le=25),
    cedear_only: bool = Query(default=True),
) -> list[RankingItemResponse]:
    try:
        ranked = service.rank_universe(Horizon(horizon), limit=limit, cedear_only=cedear_only)
    except MarketDataError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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
        )
        for analysis, score in ranked
    ]


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


class PathDateParser:
    @staticmethod
    def parse(raw_value: str):
        from datetime import date

        return date.fromisoformat(raw_value)

    @staticmethod
    def today():
        from datetime import date

        return date.today()
