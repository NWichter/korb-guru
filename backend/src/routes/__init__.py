# API routes — all routers exported for main.py
from .admin import router as admin_router
from .budget import router as budget_router
from .examples import router as examples_router
from .grocery import router as grocery_router
from .health import router as health_router
from .hello import router as hello_router
from .households import router as households_router
from .ingest import router as ingest_router
from .me import router as me_router
from .meal_plans import router as meal_plans_router
from .messages import router as messages_router
from .notifications import router as notifications_router
from .polls import router as polls_router
from .products import router as products_router
from .receipts import router as receipts_router
from .recipes import router as recipes_router
from .route import router as route_router
from .status import router as status_router
from .stores import router as stores_router
from .users import router as users_router

__all__ = [
    "admin_router",
    "budget_router",
    "examples_router",
    "grocery_router",
    "health_router",
    "hello_router",
    "households_router",
    "ingest_router",
    "me_router",
    "meal_plans_router",
    "messages_router",
    "notifications_router",
    "polls_router",
    "products_router",
    "receipts_router",
    "recipes_router",
    "route_router",
    "status_router",
    "stores_router",
    "users_router",
]
