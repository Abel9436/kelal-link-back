from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse
from . import models
import os

# Professional Admin Authentication Protocol
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        admin_username = os.getenv("ADMIN_USERNAME", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "studio-v1-master-2026")

        if username == admin_username and password == admin_password:
            request.session.update({"token": "studio_admin_session_active"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        return True

authentication_backend = AdminAuth(secret_key=os.getenv("SECRET_KEY", "studio-secret-v1-heritage-2026"))

# Model Views Configuration
class UserAdmin(ModelView, model=models.User):
    column_list = [models.User.id, models.User.name, models.User.email, models.User.username, models.User.created_at]
    column_searchable_list = [models.User.name, models.User.email, models.User.username]
    column_sortable_list = [models.User.id, models.User.created_at]
    icon = "fa-solid fa-user"
    category = "Accounts"
    name = "Creator"
    name_plural = "Creators"

class BundleAdmin(ModelView, model=models.Bundle):
    column_list = [models.Bundle.id, models.Bundle.title, models.Bundle.slug, models.Bundle.clicks, models.Bundle.created_at]
    column_searchable_list = [models.Bundle.title, models.Bundle.slug]
    column_sortable_list = [models.Bundle.clicks, models.Bundle.created_at]
    column_details_list = "__all__"
    icon = "fa-solid fa-layer-group"
    category = "Drops"
    name = "Bundle Drop"
    name_plural = "Bundle Drops"

class URLAdmin(ModelView, model=models.URL):
    column_list = [models.URL.id, models.URL.slug, models.URL.long_url, models.URL.clicks, models.URL.created_at]
    column_searchable_list = [models.URL.slug, models.URL.long_url]
    column_sortable_list = [models.URL.clicks, models.URL.created_at]
    icon = "fa-solid fa-link"
    category = "Drops"
    name = "Deep Link"
    name_plural = "Deep Links"

class ClickAdmin(ModelView, model=models.Click):
    column_list = [models.Click.id, models.Click.bundle_id, models.Click.referer, models.Click.device_type, models.Click.timestamp]
    column_filters = [models.Click.referer, models.Click.device_type]
    icon = "fa-solid fa-chart-line"
    category = "Intelligence"
    name = "Engagement Record"
    name_plural = "Engagement Records"

def setup_admin(app, engine):
    admin = Admin(
        app, 
        engine, 
        authentication_backend=authentication_backend,
        title="ቀላል Link | Intelligence Command",
        base_url="/admin",
        logo_url="https://jami.bio/favicon.ico" # Use your app icon
    )
    
    admin.add_view(UserAdmin)
    admin.add_view(BundleAdmin)
    admin.add_view(URLAdmin)
    admin.add_view(ClickAdmin)
    
    return admin
