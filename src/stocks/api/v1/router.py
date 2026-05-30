from fastapi import APIRouter

# Import endpoints routers
from stocks.api.v1.endpoints import actions, agents, charts, indicators, screening, symbols, sync

api_router = APIRouter(prefix="/api/v1")

# Mount sub-routers with clean prefixes
api_router.include_router(symbols.router)
api_router.include_router(charts.router)
api_router.include_router(indicators.router)
api_router.include_router(screening.router)
api_router.include_router(actions.router)
api_router.include_router(sync.router)
api_router.include_router(agents.router)
