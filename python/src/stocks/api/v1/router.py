from fastapi import APIRouter

# Import endpoints routers
from stocks.api.v1.endpoints import (
    actions,
    agents,
    alerts,
    announcements,
    charts,
    conversations,
    eod,
    fundamentals,
    indicators,
    ml2_training,
    news,
    portfolio,
    screening,
    settings,
    setup,
    strategies,
    symbols,
    sync,
    trendlines,
    watchlists,
)

api_router = APIRouter(prefix="/api/v1")

# Mount sub-routers with clean prefixes
api_router.include_router(symbols.router)
api_router.include_router(charts.router)
api_router.include_router(indicators.router)
api_router.include_router(screening.router)
api_router.include_router(strategies.router)
api_router.include_router(actions.router)
api_router.include_router(sync.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)
api_router.include_router(settings.router)
api_router.include_router(setup.router)
api_router.include_router(portfolio.router)
api_router.include_router(alerts.router)
api_router.include_router(ml2_training.router)
api_router.include_router(watchlists.router)
api_router.include_router(fundamentals.router)
api_router.include_router(announcements.router)
api_router.include_router(news.router)
api_router.include_router(trendlines.router)
api_router.include_router(eod.router)
