from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Header
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete
from . import models, schemas, database, utils
from .utils import amharic
import redis.asyncio as redis
from datetime import datetime, timedelta, timezone
import os
import hashlib
import qrcode
from io import BytesIO
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import JWTError, jwt
from typing import Optional
import httpx

# Configuration
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
SECRET_KEY = os.getenv("SECRET_KEY", "studio-secret-v1-heritage-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    await database.engine.dispose()

app = FastAPI(title="ቀላል Link - Pro Studio", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        FRONTEND_URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Utilities
async def get_current_user(
    authorization: Optional[str] = Header(None), 
    db: AsyncSession = Depends(database.get_db)
) -> Optional[models.User]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
        
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/auth/google", response_model=schemas.AuthToken)
async def google_auth(data: schemas.GoogleAuth, db: AsyncSession = Depends(database.get_db)):
    try:
        if data.id_token:
            # Verify via ID Token (GSI / GoogleOneTap)
            idinfo = id_token.verify_oauth2_token(data.id_token, google_requests.Request(), GOOGLE_CLIENT_ID)
            email = idinfo['email']
            name = idinfo.get('name')
            picture = idinfo.get('picture')
            google_id = idinfo['sub']
        elif data.access_token:
            # Verify via Access Token (useGoogleLogin hook)
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://www.googleapis.com/oauth2/v3/userinfo", 
                                       headers={"Authorization": f"Bearer {data.access_token}"})
                if res.status_code != 200:
                    raise HTTPException(status_code=400, detail="Invalid access token")
                userinfo = res.json()
                email = userinfo['email']
                name = userinfo.get('name')
                picture = userinfo.get('picture')
                google_id = userinfo['sub']
        else:
            raise HTTPException(status_code=400, detail="No token provided")
        
        # Check if user exists
        result = await db.execute(select(models.User).where(models.User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            user = models.User(
                email=email,
                name=name,
                profile_pic=picture,
                google_id=google_id
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            # Update user info if it changed
            user.name = name
            user.profile_pic = picture
            await db.commit()
            await db.refresh(user)
            
        access_token = create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "user": user
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")

# Dashboard Endpoints
@app.get("/api/me/drops")
async def get_my_drops(
    user: models.User = Depends(get_current_user), 
    db: AsyncSession = Depends(database.get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    urls_res = await db.execute(select(models.URL).where(models.URL.user_id == user.id).order_by(models.URL.created_at.desc()))
    bundles_res = await db.execute(select(models.Bundle).where(models.Bundle.user_id == user.id).order_by(models.Bundle.created_at.desc()))
    
    return {
        "urls": urls_res.scalars().all(),
        "bundles": bundles_res.scalars().all()
    }

@app.delete("/api/drops/{slug}")
async def delete_drop(
    slug: str, 
    user: models.User = Depends(get_current_user), 
    db: AsyncSession = Depends(database.get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    # Try URL first
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id == user.id))
    url_obj = res.scalar_one_or_none()
    if url_obj:
        await db.delete(url_obj)
        await db.commit()
        return {"status": "purged"}
        
    # Try Bundle
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug, models.Bundle.user_id == user.id))
    bundle_obj = res.scalar_one_or_none()
    if bundle_obj:
        await db.delete(bundle_obj)
        await db.commit()
        return {"status": "purged"}
        
    raise HTTPException(status_code=404, detail="Drop not found or unauthorized")

@app.get("/api/drop/{slug}")
async def get_drop_details(
    slug: str,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    # Try URL
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id == user.id))
    url_obj = res.scalar_one_or_none()
    if url_obj:
        return {**schemas.URLInfo.from_orm(url_obj).dict(), "type": "url"}
        
    # Try Bundle
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug, models.Bundle.user_id == user.id))
    bundle_obj = res.scalar_one_or_none()
    if bundle_obj:
        return {**schemas.BundleInfo.from_orm(bundle_obj).dict(), "type": "bundle"}
        
    raise HTTPException(status_code=404, detail="Identity not found")

@app.put("/api/url/{slug}", response_model=schemas.URLInfo)
async def update_url(
    slug: str,
    data: schemas.URLUpdate,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id == user.id))
    url_obj = res.scalar_one_or_none()
    if not url_obj: raise HTTPException(status_code=404, detail="Identity not found")
    
    if data.custom_slug and data.custom_slug != slug:
        check = await db.execute(select(models.URL).where(models.URL.slug == data.custom_slug))
        if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
        check = await db.execute(select(models.Bundle).where(models.Bundle.slug == data.custom_slug))
        if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
        url_obj.slug = data.custom_slug

    if data.long_url: url_obj.long_url = str(data.long_url)
    if data.max_clicks is not None: url_obj.max_clicks = data.max_clicks
    if data.expires_at: url_obj.expires_at = data.expires_at
    if data.password: url_obj.password = hashlib.sha256(data.password.encode()).hexdigest()
    if data.meta_title is not None: url_obj.meta_title = data.meta_title
    if data.meta_description is not None: url_obj.meta_description = data.meta_description
    
    await db.commit()
    await db.refresh(url_obj)
    return {**url_obj.__dict__, "has_password": url_obj.password is not None}

@app.put("/api/bundle/{slug}", response_model=schemas.BundleInfo)
async def update_bundle(
    slug: str,
    data: schemas.BundleUpdate,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug, models.Bundle.user_id == user.id))
    bundle_obj = res.scalar_one_or_none()
    if not bundle_obj: raise HTTPException(status_code=404, detail="Studio not found")
    
    if data.custom_slug and data.custom_slug != slug:
        check = await db.execute(select(models.URL).where(models.URL.slug == data.custom_slug))
        if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
        check = await db.execute(select(models.Bundle).where(models.Bundle.slug == data.custom_slug))
        if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
        bundle_obj.slug = data.custom_slug

    if data.title: bundle_obj.title = data.title
    if data.description is not None: bundle_obj.description = data.description
    if data.items: bundle_obj.items = [{"label": item.label, "url": str(item.url)} for item in data.items]
    if data.theme_color: bundle_obj.theme_color = data.theme_color
    if data.bg_color: bundle_obj.bg_color = data.bg_color
    if data.text_color: bundle_obj.text_color = data.text_color
    if data.title_color: bundle_obj.title_color = data.title_color
    if data.card_color: bundle_obj.card_color = data.card_color
    if data.max_clicks is not None: bundle_obj.max_clicks = data.max_clicks
    if data.expires_at: bundle_obj.expires_at = data.expires_at
    if data.password: bundle_obj.password = hashlib.sha256(data.password.encode()).hexdigest()
    if data.meta_title is not None: bundle_obj.meta_title = data.meta_title
    if data.meta_description is not None: bundle_obj.meta_description = data.meta_description
    
    await db.commit()
    await db.refresh(bundle_obj)
    return {**bundle_obj.__dict__, "has_password": bundle_obj.password is not None}

# Existing Core Logic (Updated with User association)
async def track_click(request: Request, url_id: int = None, bundle_id: int = None):
    user_agent = request.headers.get("user-agent", "").lower()
    device_type = "Desktop"
    if "mobile" in user_agent: device_type = "Mobile"
    elif "tablet" in user_agent or "ipad" in user_agent: device_type = "Tablet"
    
    async with database.async_session() as db:
        click = models.Click(url_id=url_id, bundle_id=bundle_id, referer=request.headers.get("referer"), user_agent=user_agent, device_type=device_type)
        db.add(click)
        await db.commit()

@app.post("/shorten", response_model=schemas.URLInfo)
async def shorten_url(
    data: schemas.URLCreate, 
    user: Optional[models.User] = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    expires_at = data.expires_at
    if not expires_at and data.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.expires_in)

    hashed_password = hashlib.sha256(data.password.encode()).hexdigest() if data.password else None

    if data.custom_slug:
        slug = data.custom_slug
        res_url = await db.execute(select(models.URL).where(models.URL.slug == slug))
        res_bundle = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
        if res_url.scalar_one_or_none() or res_bundle.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Custom alias already taken")
        
        new_url = models.URL(
            long_url=str(data.long_url), 
            slug=slug,
            max_clicks=data.max_clicks,
            expires_at=expires_at,
            password=hashed_password,
            meta_title=data.meta_title,
            meta_description=data.meta_description,
            user_id=user.id if user else None
        )
        db.add(new_url)
        await db.commit()
    else:
        new_url = models.URL(
            long_url=str(data.long_url), 
            slug="",
            max_clicks=data.max_clicks,
            expires_at=expires_at,
            password=hashed_password,
            meta_title=data.meta_title,
            meta_description=data.meta_description,
            user_id=user.id if user else None
        )
        db.add(new_url)
        await db.commit()
        await db.refresh(new_url)
        new_url.slug = amharic.encode(new_url.id)
        await db.commit()

    return {**new_url.__dict__, "has_password": data.password is not None}

@app.post("/bundle", response_model=schemas.BundleInfo)
async def create_bundle(
    data: schemas.BundleCreate,
    user: Optional[models.User] = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    slug = data.custom_slug
    if slug:
        res_url = await db.execute(select(models.URL).where(models.URL.slug == slug))
        res_bundle = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
        if res_url.scalar_one_or_none() or res_bundle.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Custom alias already taken")
    
    expires_at = data.expires_at
    if data.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.expires_in)

    new_bundle = models.Bundle(
        title=data.title,
        description=data.description,
        items=[{"label": item.label, "url": str(item.url)} for item in data.items],
        theme_color=data.theme_color,
        bg_color=data.bg_color,
        text_color=data.text_color,
        title_color=data.title_color,
        card_color=data.card_color,
        slug=slug or "",
        max_clicks=data.max_clicks,
        expires_at=expires_at,
        password=hashlib.sha256(data.password.encode()).hexdigest() if data.password else None,
        meta_title=data.meta_title,
        meta_description=data.meta_description,
        user_id=user.id if user else None
    )
    db.add(new_bundle)
    await db.flush()
    if not slug:
        new_bundle.slug = "b-" + amharic.encode(new_bundle.id)
    
    await db.commit()
    await db.refresh(new_bundle)
    return {**new_bundle.__dict__, "has_password": new_bundle.password is not None}

@app.get("/{slug}")
async def redirect_url(slug: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    meta_html = ""
    if bundle and (bundle.meta_title or bundle.meta_description):
        title = bundle.meta_title or bundle.title or "ቀላል Link - Studio"
        desc = bundle.meta_description or bundle.description or "Professional Identity Studio"
        target_url = f"{FRONTEND_URL}/bundle/{slug}"
        meta_html = f"""
        <html>
            <head>
                <title>{title}</title>
                <meta name="description" content="{desc}">
                <meta property="og:title" content="{title}">
                <meta property="og:description" content="{desc}">
                <meta property="og:type" content="website">
                <meta property="og:url" content="{request.url}">
                <meta name="twitter:card" content="summary_large_image">
                <meta name="twitter:title" content="{title}">
                <meta name="twitter:description" content="{desc}">
                <meta http-equiv="refresh" content="0;url={target_url}">
            </head>
            <body style="background: #0a0a0a; color: #fff; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
                <div style="text-align: center;">
                    <div style="width: 50px; height: 50px; border: 4px solid #00f2ff; border-top-color: transparent; border-radius: 50%; animate: spin 1s linear infinite;"></div>
                    <script>window.location.href = "{target_url}";</script>
                </div>
            </body>
        </html>
        """
        bundle.clicks += 1
        background_tasks.add_task(track_click, request, bundle_id=bundle.id)
        await db.commit()
        return HTMLResponse(content=meta_html)

    if bundle:
        if (bundle.expires_at and bundle.expires_at < datetime.now(timezone.utc)) or (bundle.max_clicks and bundle.clicks >= bundle.max_clicks):
            return RedirectResponse(url=f"{FRONTEND_URL}/expired")
        if bundle.password:
            return RedirectResponse(url=f"{FRONTEND_URL}/unlock/{slug}")
        bundle.clicks += 1
        background_tasks.add_task(track_click, request, bundle_id=bundle.id)
        await db.commit()
        return RedirectResponse(url=f"{FRONTEND_URL}/bundle/{slug}")

    result = await db.execute(select(models.URL).where(models.URL.slug == slug))
    url_obj = result.scalar_one_or_none()
    if not url_obj: raise HTTPException(status_code=404, detail="URL not found")
    
    if (url_obj.expires_at and url_obj.expires_at < datetime.now(timezone.utc)) or (url_obj.max_clicks and url_obj.clicks >= url_obj.max_clicks):
        return RedirectResponse(url=f"{FRONTEND_URL}/expired")
    if url_obj.password: return RedirectResponse(url=f"{FRONTEND_URL}/unlock/{slug}")
    
    if url_obj.meta_title or url_obj.meta_description:
        title = url_obj.meta_title or "ቀላል Link"
        desc = url_obj.meta_description or "Secure Studio Drop"
        target_url = url_obj.long_url
        meta_html = f"""
        <html>
            <head>
                <title>{title}</title>
                <meta name="description" content="{desc}">
                <meta property="og:title" content="{title}">
                <meta property="og:description" content="{desc}">
                <meta property="og:type" content="website">
                <meta property="og:url" content="{request.url}">
                <meta name="twitter:card" content="summary_large_image">
                <meta name="twitter:title" content="{title}">
                <meta name="twitter:description" content="{desc}">
                <meta http-equiv="refresh" content="0;url={target_url}">
            </head>
            <body style="background: #0a0a0a; color: #fff; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh;">
                <div style="text-align: center;">
                    <script>window.location.href = "{target_url}";</script>
                </div>
            </body>
        </html>
        """
        url_obj.clicks += 1
        background_tasks.add_task(track_click, request, url_id=url_obj.id)
        await db.commit()
        return HTMLResponse(content=meta_html)

    url_obj.clicks += 1
    background_tasks.add_task(track_click, request, url_id=url_obj.id)
    await db.commit()
    return RedirectResponse(url=url_obj.long_url)

@app.get("/api/bundle/{slug}", response_model=schemas.BundleInfo)
async def get_bundle(slug: str, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    if not bundle: raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle

@app.get("/api/stats/{slug}")
async def get_stats(slug: str, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    obj = res.scalar_one_or_none()
    is_bundle = True
    if not obj:
        res = await db.execute(select(models.URL).where(models.URL.slug == slug))
        obj = res.scalar_one_or_none()
        is_bundle = False
    if not obj: raise HTTPException(status_code=404, detail="Not found")

    clicks_expr = func.date_trunc('hour', models.Click.timestamp)
    clicks_res = await db.execute(select(clicks_expr.label('h'), func.count(models.Click.id)).where(models.Click.bundle_id == obj.id if is_bundle else models.Click.url_id == obj.id).group_by(clicks_expr).order_by('h'))
    clicks_history = [{"date": str(row[0]), "count": row[1]} for row in clicks_res.fetchall()]

    devices_res = await db.execute(select(models.Click.device_type, func.count(models.Click.id)).where(models.Click.bundle_id == obj.id if is_bundle else models.Click.url_id == obj.id).group_by(models.Click.device_type))
    device_stats = [{"device": row[0] or "Unknown", "count": row[1]} for row in devices_res.fetchall()]

    referers_res = await db.execute(select(models.Click.referer, func.count(models.Click.id)).where(models.Click.bundle_id == obj.id if is_bundle else models.Click.url_id == obj.id).group_by(models.Click.referer).limit(5))
    top_referers = [{"referer": row[0] or "Direct", "count": row[1]} for row in referers_res.fetchall()]

    return {"title": getattr(obj, "title", obj.slug), "total_clicks": obj.clicks, "clicks_history": clicks_history, "device_stats": device_stats, "top_referers": top_referers}

@app.get("/api/qr/{slug}")
async def get_qr(slug: str, color: str = "black", bg: str = "white"):
    url = f"{FRONTEND_URL}/{slug}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color=color, back_color=bg)
    buf = BytesIO(); img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

@app.post("/unlock/{slug}")
async def unlock_url(slug: str, data: dict, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    if bundle:
        if hashlib.sha256(data.get("password", "").encode()).hexdigest() != bundle.password:
            raise HTTPException(status_code=401, detail="Incorrect cipher key")
        return {"long_url": f"{FRONTEND_URL}/bundle/{slug}"}

    result = await db.execute(select(models.URL).where(models.URL.slug == slug))
    url_obj = result.scalar_one_or_none()
    if not url_obj: raise HTTPException(status_code=404, detail="Not found")
    if hashlib.sha256(data.get("password", "").encode()).hexdigest() != url_obj.password:
        raise HTTPException(status_code=401, detail="Incorrect cipher key")
    return {"long_url": url_obj.long_url}
