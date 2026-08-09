"""
Run:
    uvicorn app:app --reload --port 3000
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

app = FastAPI(title="Agentic Recommendation Platform — Frontend")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def render(request: Request, template: str, **context):
    return templates.TemplateResponse(
        request, template, {"api_base_url": API_BASE_URL, **context}
    )


# ---------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------

@app.get("/")
async def home(request: Request):
    return render(request, "home.html", active_nav="home")


@app.get("/login")
async def login_page(request: Request):
    return render(request, "login.html", active_nav="login")


@app.get("/register")
async def register_page(request: Request):
    return render(request, "register.html", active_nav="register")


@app.get("/products")
async def products_page(request: Request):
    return render(request, "products.html", active_nav="products")


@app.get("/products/{product_id}")
async def product_detail_page(request: Request, product_id: str):
    return render(
        request,
        "product_detail.html",
        active_nav="products",
        product_id=product_id,
    )


@app.get("/search")
async def search_page(request: Request):
    """Search results reuse the products listing UI — the query string
    (?search=...) is read client-side by products.js on page load."""
    return render(request, "products.html", active_nav="products")


@app.get("/recommendations")
async def recommendations_page(request: Request):
    return render(request, "recommendations.html", active_nav="recommendations")


@app.get("/profile")
async def profile_page(request: Request):
    return render(request, "profile.html", active_nav="profile")


# ---------------------------------------------------------------------
# Admin pages
# ---------------------------------------------------------------------

@app.get("/admin")
async def admin_dashboard_page(request: Request):
    return render(request, "admin/dashboard.html", active_nav="admin")


@app.get("/admin/products")
async def admin_products_page(request: Request):
    return render(request, "admin/products.html", active_nav="admin-products")


@app.get("/admin/products/create")
async def admin_product_create_page(request: Request):
    return render(request, "admin/product_create.html", active_nav="admin-products")


@app.get("/admin/products/{product_id}/edit")
async def admin_product_edit_page(request: Request, product_id: str):
    return render(
        request,
        "admin/product_edit.html",
        active_nav="admin-products",
        product_id=product_id,
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}
