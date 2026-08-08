from fastapi import APIRouter

from app.api.v1 import admin, auth, events, products, recommendations

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(admin.router)
api_router.include_router(events.router)
api_router.include_router(recommendations.router)
