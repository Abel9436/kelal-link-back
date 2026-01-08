from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, Header
from fastapi.responses import RedirectResponse, Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete
from starlette.middleware.sessions import SessionMiddleware
from . import models, schemas, database, utils, admin
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
from typing import Optional, List
import httpx
import secrets

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
        "https://kelal.abelo.tech",
        FRONTEND_URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin Intelligence Command Session
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Initialize Masterpiece Admin (Top level for route priority)
admin.setup_admin(app, database.engine)


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
        
    from sqlalchemy import or_
    # 1. Find global collaborations (Global access to all drops)
    global_cols = await db.execute(select(models.Collaboration.owner_id).where(
        models.Collaboration.collaborator_id == user.id,
        models.Collaboration.bundle_id == None
    ))
    global_owner_ids = [row[0] for row in global_cols.fetchall()]
    
    # 2. Find bundle-specific collaborations
    specific_cols = await db.execute(select(models.Collaboration.bundle_id).where(
        models.Collaboration.collaborator_id == user.id,
        models.Collaboration.bundle_id != None
    ))
    shared_bundle_ids = [row[0] for row in specific_cols.fetchall()]
    
    # Retrieval logic
    all_eligible_owner_ids = [user.id] + global_owner_ids
    
    # Fetch URLs (Global owners + me)
    urls_res = await db.execute(select(models.URL).where(
        models.URL.user_id.in_(all_eligible_owner_ids)
    ).order_by(models.URL.created_at.desc()))
    
    # Fetch Bundles (Global owners + me + specific bundles)
    bundle_conditions = [models.Bundle.user_id.in_(all_eligible_owner_ids)]
    if shared_bundle_ids:
        bundle_conditions.append(models.Bundle.id.in_(shared_bundle_ids))
        
    bundles_res = await db.execute(select(models.Bundle).where(
        or_(*bundle_conditions)
    ).order_by(models.Bundle.created_at.desc()))
    
    return {
        "urls": [schemas.URLInfo.from_orm(u).dict() for u in urls_res.scalars().all()],
        "bundles": [schemas.BundleInfo.from_orm(b).dict() for b in bundles_res.scalars().all()]
    }

@app.put("/api/user/profile")
async def update_profile(
    data: dict,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    if "username" in data:
        username = data["username"].lower().strip()
        if not username:
             user.username = None
        else:
            # Simple regex for username
            import re
            if not re.match(r"^[a-z0-9_-]{3,20}$", username):
                raise HTTPException(status_code=400, detail="Username must be 3-20 chars (a-z, 0-9, _, -)")
            
            res = await db.execute(select(models.User).where(models.User.username == username, models.User.id != user.id))
            if res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Username already taken")
            user.username = username
    
    if "name" in data:
        user.name = data["name"]
        
    await db.commit()
    await db.refresh(user)
    return user

@app.get("/api/team")
async def get_team(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    if not user: raise HTTPException(status_code=401)
    
    # Collaborators I have invited
    res_owned = await db.execute(
        select(models.Collaboration, models.User, models.Bundle)
        .join(models.User, models.Collaboration.collaborator_id == models.User.id)
        .outerjoin(models.Bundle, models.Collaboration.bundle_id == models.Bundle.id)
        .where(models.Collaboration.owner_id == user.id)
    )
    owned = []
    for col, u, b in res_owned:
        owned.append({
            "id": col.id,
            "collaborator_name": u.name,
            "collaborator_username": u.username,
            "collaborator_email": u.email,
            "collaborator_pic": u.profile_pic,
            "bundle_id": col.bundle_id,
            "bundle_title": b.title if b else "Global",
            "role": col.role,
            "created_at": col.created_at
        })
        
    # Studios I have joined as a collaborator
    res_joined = await db.execute(
        select(models.Collaboration, models.User, models.Bundle)
        .join(models.User, models.Collaboration.owner_id == models.User.id)
        .outerjoin(models.Bundle, models.Collaboration.bundle_id == models.Bundle.id)
        .where(models.Collaboration.collaborator_id == user.id)
    )
    joined = []
    for col, u, b in res_joined:
        joined.append({
            "id": col.id,
            "owner_name": u.name,
            "owner_username": u.username,
            "owner_pic": u.profile_pic,
            "bundle_id": col.bundle_id,
            "bundle_title": b.title if b else "Global",
            "role": col.role,
            "created_at": col.created_at
        })
        
    return {"owned": owned, "joined": joined}

@app.post("/api/team/invite")
async def invite_collaborator(data: schemas.CollaborationCreate, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    if not user: raise HTTPException(status_code=401)
    
    # Discovery by email
    res = await db.execute(select(models.User).where(models.User.email == data.collaborator_email.lower()))
    collab_user = res.scalar_one_or_none()
    if not collab_user: raise HTTPException(status_code=404, detail="User with this email not found")
    if collab_user.id == user.id: raise HTTPException(status_code=400, detail="Cannot invite yourself")
    
    # Check if already invited for this specific studio
    existing = await db.execute(select(models.Collaboration).where(
        models.Collaboration.owner_id == user.id, 
        models.Collaboration.collaborator_id == collab_user.id,
        models.Collaboration.bundle_id == data.bundle_id
    ))
    if existing.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Already collaborator for this studio")
    
    new_col = models.Collaboration(
        owner_id=user.id, 
        collaborator_id=collab_user.id, 
        bundle_id=data.bundle_id,
        role=data.role
    )
    db.add(new_col)
    
    # Create notification for the invited user
    b_title = "Global"
    if data.bundle_id:
        b_res = await db.execute(select(models.Bundle.title).where(models.Bundle.id == data.bundle_id))
        b_title = b_res.scalar_one_or_none() or "Studio"
        
    notif = models.Notification(
        user_id=collab_user.id,
        type="invitation",
        title="Protocol Access Granted",
        message=f"{user.name or user.username} invited you to collaborate on '{b_title}'",
        link="/dashboard?tab=team"
    )
    db.add(notif)
    
    await db.commit()
    return {"message": "Protocol access granted"}

@app.get("/api/notifications", response_model=List[schemas.NotificationInfo])
async def get_notifications(user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Notification).where(models.Notification.user_id == user.id).order_by(models.Notification.created_at.desc()))
    return res.scalars().all()

@app.post("/api/notifications/{n_id}/read")
async def mark_notification_read(n_id: int, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Notification).where(models.Notification.id == n_id, models.Notification.user_id == user.id))
    notif = res.scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.commit()
    return {"status": "updated"}

@app.delete("/api/team/{col_id}")
async def remove_collaborator(col_id: int, user: models.User = Depends(get_current_user), db: AsyncSession = Depends(database.get_db)):
    if not user: raise HTTPException(status_code=401)
    res = await db.execute(select(models.Collaboration).where(models.Collaboration.id == col_id))
    col = res.scalar_one_or_none()
    if not col: raise HTTPException(status_code=404)
    
    # Only owner or collaborator can remove
    if col.owner_id != user.id and col.collaborator_id != user.id:
        raise HTTPException(status_code=403)
        
    await db.delete(col)
    await db.commit()
    return {"status": "devoiced"}

@app.get("/api/studio/{username}")
async def get_studio_hub(username: str, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.User).where(models.User.username == username.lower()))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Studio not found")
        
    bundles_res = await db.execute(select(models.Bundle).where(models.Bundle.user_id == user.id).order_by(models.Bundle.created_at.desc()))
    urls_res = await db.execute(select(models.URL).where(models.URL.user_id == user.id).order_by(models.URL.created_at.desc()))
    
    bundles = bundles_res.scalars().all()
    urls = urls_res.scalars().all()
    
    drops = []
    for b in bundles:
        drops.append({
            "type": "bundle",
            "slug": b.slug,
            "title": b.title,
            "description": b.description,
            "theme_color": b.theme_color,
            "created_at": b.created_at
        })
    for u in urls:
        drops.append({
            "type": "url",
            "slug": u.slug,
            "title": u.meta_title or u.slug,
            "description": u.meta_description,
            "theme_color": "#00f2ff", # Default for URLs
            "created_at": u.created_at
        })
        
    return {
        "user": {
            "name": user.name,
            "profile_pic": user.profile_pic,
            "username": user.username
        },
        "drops": sorted(drops, key=lambda x: x["created_at"], reverse=True)
    }

@app.delete("/api/drops/{slug}")
async def delete_drop(
    slug: str, 
    user: models.User = Depends(get_current_user), 
    db: AsyncSession = Depends(database.get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    # 1. Check Global Permissions (Owner or Global Collaborator)
    global_cols = await db.execute(select(models.Collaboration.owner_id).where(
        models.Collaboration.collaborator_id == user.id,
        models.Collaboration.bundle_id == None
    ))
    global_owner_ids = [row[0] for row in global_cols.fetchall()]
    all_eligible_owner_ids = [user.id] + global_owner_ids

    # Try URL (Global access only)
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id.in_(all_eligible_owner_ids)))
    url_obj = res.scalar_one_or_none()
    if url_obj:
        await db.delete(url_obj)
        await db.commit()
        return {"status": "purged"}

    # Try Bundle (Me or Global)
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug, models.Bundle.user_id.in_(all_eligible_owner_ids)))
    bundle_obj = res.scalar_one_or_none()
    
    if bundle_obj:
        await db.delete(bundle_obj)
        await db.commit()
        return {"status": "purged"}

    raise HTTPException(status_code=404, detail="Drop not found or unauthorized")
        
    raise HTTPException(status_code=404, detail="Drop not found or unauthorized")

@app.get("/api/drop/{slug}")
async def get_drop_details(
    slug: str,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    user_id = user.id if user else None
    
    if user_id:
        global_cols = await db.execute(select(models.Collaboration.owner_id).where(
            models.Collaboration.collaborator_id == user_id,
            models.Collaboration.bundle_id == None
        ))
        global_owner_ids = [row[0] for row in global_cols.fetchall()]
        all_eligible_owner_ids = [user_id] + global_owner_ids
    else:
        all_eligible_owner_ids = []

    # Try URL (Global only)
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id.in_(all_eligible_owner_ids)))
    url_obj = res.scalar_one_or_none()
    if url_obj:
        role = "owner" if url_obj.user_id == user_id else "manager"
        return {**schemas.URLInfo.from_orm(url_obj).dict(), "type": "url", "id": url_obj.id, "user_role": role}
        
    # Try Bundle (Check direct ownership/global collab first)
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle_obj = res.scalar_one_or_none()
    
    if bundle_obj:
        is_bundle_authorized = bundle_obj.user_id in all_eligible_owner_ids
        role = "owner" if bundle_obj.user_id == user_id else ("manager" if bundle_obj.user_id in all_eligible_owner_ids else None)
        
        if not is_bundle_authorized and user_id:
            # Check specific bundle collab
            specific_col_res = await db.execute(select(models.Collaboration.role).where(
                models.Collaboration.collaborator_id == user_id,
                models.Collaboration.bundle_id == bundle_obj.id
            ))
            spec_role = specific_col_res.scalar_one_or_none()
            if spec_role:
                is_bundle_authorized = True
                role = spec_role
        
        # If authorized OR if the level is not restricted, allow access
        if is_bundle_authorized or bundle_obj.access_level != "restricted":
            if not role: role = "viewer"
            return {**schemas.BundleInfo.from_orm(bundle_obj).dict(), "type": "bundle", "id": bundle_obj.id, "user_role": role}

    raise HTTPException(status_code=404, detail="Identity not found or unauthorized")

@app.put("/api/url/{slug}", response_model=schemas.URLInfo)
async def update_url(
    slug: str,
    data: schemas.URLUpdate,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    global_cols = await db.execute(select(models.Collaboration.owner_id).where(
        models.Collaboration.collaborator_id == user.id,
        models.Collaboration.bundle_id == None
    ))
    global_owner_ids = [row[0] for row in global_cols.fetchall()]
    all_eligible_owner_ids = [user.id] + global_owner_ids
    
    res = await db.execute(select(models.URL).where(models.URL.slug == slug, models.URL.user_id.in_(all_eligible_owner_ids)))
    url_obj = res.scalar_one_or_none()
    if not url_obj: raise HTTPException(status_code=404, detail="Identity not found or unauthorized")
    
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
    if data.is_cloaked is not None: url_obj.is_cloaked = data.is_cloaked
    
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
    user_id = user.id if user else None
    
    if user_id:
        global_cols = await db.execute(select(models.Collaboration.owner_id).where(
            models.Collaboration.collaborator_id == user_id,
            models.Collaboration.bundle_id == None
        ))
        global_owner_ids = [row[0] for row in global_cols.fetchall()]
        all_eligible_owner_ids = [user_id] + global_owner_ids
    else:
        all_eligible_owner_ids = []
    
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle_obj = res.scalar_one_or_none()
    
    if not bundle_obj: raise HTTPException(status_code=404, detail="Studio not found")

    is_authorized = bundle_obj.user_id in all_eligible_owner_ids
    role = "owner" if bundle_obj.user_id == user_id else ("manager" if is_authorized else None)
    
    if not is_authorized and user_id:
        # Check specific bundle collab
        specific_col = await db.execute(select(models.Collaboration.role).where(
            models.Collaboration.collaborator_id == user_id,
            models.Collaboration.bundle_id == bundle_obj.id
        ))
        col_role = specific_col.scalar_one_or_none()
        if col_role:
            is_authorized = True
            role = col_role

    # Roles that can edit content: owner, manager (not analyst)
    can_edit = role in ["owner", "manager"] or (not role and bundle_obj.access_level == "edit")
    
    if not can_edit:
        raise HTTPException(status_code=403, detail="Unauthorized access to this Studio")
    
    # Permission-locked fields (Owners/Managers only - Analyst cannot change these)
    # Note: role could be None if anyone with link can edit
    is_owner_or_manager = role in ["owner", "manager"]
    
    if is_owner_or_manager:
        if data.access_level is not None:
            bundle_obj.access_level = data.access_level
        
        if data.custom_slug and data.custom_slug != slug:
            check = await db.execute(select(models.URL).where(models.URL.slug == data.custom_slug))
            if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
            check = await db.execute(select(models.Bundle).where(models.Bundle.slug == data.custom_slug))
            if check.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Identity already exists")
            bundle_obj.slug = data.custom_slug

        if data.password:
            bundle_obj.password = hashlib.sha256(data.password.encode()).hexdigest()
            
        if data.max_clicks is not None: bundle_obj.max_clicks = data.max_clicks
        if data.expires_at: bundle_obj.expires_at = data.expires_at
        if data.is_cloaked is not None: bundle_obj.is_cloaked = data.is_cloaked

    # Content fields (Authorized users + Public Editors)
    if data.title: bundle_obj.title = data.title
    if data.description is not None: bundle_obj.description = data.description
    if data.items is not None:
        bundle_obj.items = [item.dict() for item in data.items]
    if data.theme_color: bundle_obj.theme_color = data.theme_color
    if data.bg_color: bundle_obj.bg_color = data.bg_color
    if data.text_color: bundle_obj.text_color = data.text_color
    if data.title_color: bundle_obj.title_color = data.title_color
    if data.card_color: bundle_obj.card_color = data.card_color
    if data.meta_title is not None: bundle_obj.meta_title = data.meta_title
    if data.meta_description is not None: bundle_obj.meta_description = data.meta_description
    if data.bg_image is not None: bundle_obj.bg_image = data.bg_image
    if data.profile_image is not None: bundle_obj.profile_image = data.profile_image
    
    # Safety: Ensure tokens exist
    if not bundle_obj.manager_token:
        bundle_obj.manager_token = secrets.token_urlsafe(16)
    if not bundle_obj.analyst_token:
        bundle_obj.analyst_token = secrets.token_urlsafe(16)
    
    await db.commit()
    await db.refresh(bundle_obj)
    return {
        **bundle_obj.__dict__, 
        "has_password": bundle_obj.password is not None,
        "user_role": role or "viewer",
        "type": "bundle"
    }

@app.post("/api/bundle/join/{slug}")
async def join_bundle(
    slug: str,
    token: str,
    user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    
    if not bundle:
        raise HTTPException(status_code=404, detail="Studio not found")
        
    if token == bundle.manager_token:
        final_role = "manager"
    elif token == bundle.analyst_token:
        final_role = "analyst"
    else:
        raise HTTPException(status_code=403, detail="Invalid invitation token")
        
    # Check if already joined
    existing = await db.execute(select(models.Collaboration).where(
        models.Collaboration.collaborator_id == user.id,
        models.Collaboration.bundle_id == bundle.id
    ))
    if existing.scalar_one_or_none():
        return {"status": "already_joined"}
        
    new_col = models.Collaboration(
        owner_id=bundle.user_id,
        collaborator_id=user.id,
        bundle_id=bundle.id,
        role=final_role
    )
    db.add(new_col)
    await db.commit()
    return {"status": "joined", "role": final_role}

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
            is_cloaked=data.is_cloaked,
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
            is_cloaked=data.is_cloaked,
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
        bg_image=data.bg_image,
        profile_image=data.profile_image,
        is_cloaked=data.is_cloaked,
        manager_token=secrets.token_urlsafe(16),
        analyst_token=secrets.token_urlsafe(16),
        user_id=user.id if user else None
    )
    db.add(new_bundle)
    await db.flush()
    if not slug:
        new_bundle.slug = "b-" + amharic.encode(new_bundle.id)
    
    await db.commit()
    await db.refresh(new_bundle)
    return {**new_bundle.__dict__, "has_password": new_bundle.password is not None}


@app.get("/api/bundle/{slug}", response_model=schemas.BundleInfo)
async def get_bundle(slug: str, db: AsyncSession = Depends(database.get_db)):
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    if not bundle: raise HTTPException(status_code=404, detail="Bundle not found")
    return bundle

@app.get("/api/stats/{slug}")
async def get_stats(
    slug: str,
    user: Optional[models.User] = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_db)
):
    user_id = user.id if user else None
    
    # 1. Try Bundle
    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    obj = res.scalar_one_or_none()
    is_bundle = True
    
    if obj:
        # Analytics are now public by default
        # "access_level" still controls the Studio Editor access in other endpoints
        pass
    else:
        # 2. Try URL
        res = await db.execute(select(models.URL).where(models.URL.slug == slug))
        obj = res.scalar_one_or_none()
        is_bundle = False
        if not obj: raise HTTPException(status_code=404, detail="Not found")
        
        # URL Stats are now public by default to ensure accessibility
        # "is_cloaked" only controls the redirect behavior, not the stats visibility.

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

@app.get("/{slug}")
async def redirect_url(slug: str, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(database.get_db)):
    # Absolute Route Guard for Admin and Internal Protocols
    if slug.lower().startswith("admin") or slug.lower() in ["api", "studio", "create", "dashboard", "stats"]:
        raise HTTPException(status_code=404)

    # Bot Intelligence Check
    user_agent = request.headers.get("User-Agent", "").lower()
    is_bot = any(bot in user_agent for bot in ["bot", "crawler", "spider", "whatsapp", "telegram", "facebook", "slack", "discord"])

    res = await db.execute(select(models.Bundle).where(models.Bundle.slug == slug))
    bundle = res.scalar_one_or_none()
    
    if bundle:
        # Check Expiration/Limits
        if (bundle.expires_at and bundle.expires_at < datetime.now(timezone.utc)) or (bundle.max_clicks and bundle.clicks >= bundle.max_clicks):
            return RedirectResponse(url=f"{FRONTEND_URL}/expired")
        
        # Stealth Cloaking Protocol
        if bundle.is_cloaked and is_bot:
            # Shield phase: Show SEO meta but hide target from bot scanners
            title = bundle.meta_title or bundle.title or "ቀላል Link - Studio"
            desc = bundle.meta_description or bundle.description or "Professional Identity Studio"
            return HTMLResponse(content=f"<html><head><title>{title}</title><meta name='description' content='{desc}'></head><body>{title}</body></html>")

        if bundle.password:
            return RedirectResponse(url=f"{FRONTEND_URL}/unlock/{slug}")

        # Meta-Header Redirection (SEO)
        if bundle.meta_title or bundle.meta_description:
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
                    <meta http-equiv="refresh" content="0;url={target_url}">
                    <script>window.location.href = "{target_url}";</script>
                </head>
                <body style="background: #0a0a0a;"></body>
            </html>
            """
            bundle.clicks += 1
            background_tasks.add_task(track_click, request, bundle_id=bundle.id)
            await db.commit()
            return HTMLResponse(content=meta_html)

        # Standard Redirect
        bundle.clicks += 1
        background_tasks.add_task(track_click, request, bundle_id=bundle.id)
        await db.commit()
        
        response = RedirectResponse(url=f"{FRONTEND_URL}/bundle/{slug}")
        if bundle.is_cloaked:
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    # Handle Single URLs
    result = await db.execute(select(models.URL).where(models.URL.slug == slug))
    url_obj = result.scalar_one_or_none()
    if not url_obj: raise HTTPException(status_code=404, detail="URL not found")
    
    if (url_obj.expires_at and url_obj.expires_at < datetime.now(timezone.utc)) or (url_obj.max_clicks and url_obj.clicks >= url_obj.max_clicks):
        return RedirectResponse(url=f"{FRONTEND_URL}/expired")
        
    # Stealth Cloaking Protocol for URLs
    if url_obj.is_cloaked and is_bot:
        title = url_obj.meta_title or "ቀላል Link"
        desc = url_obj.meta_description or "Secure Studio Drop"
        return HTMLResponse(content=f"<html><head><title>{title}</title><meta name='description' content='{desc}'></head><body>{title}</body></html>")

    if url_obj.password: return RedirectResponse(url=f"{FRONTEND_URL}/unlock/{slug}")
    
    target_url = url_obj.long_url
    url_obj.clicks += 1
    background_tasks.add_task(track_click, request, url_id=url_obj.id)
    await db.commit()

    if url_obj.meta_title or url_obj.meta_description:
        title = url_obj.meta_title or "ቀላል Link"
        desc = url_obj.meta_description or "Secure Studio Drop"
        meta_html = f"""
        <html>
            <head>
                <title>{title}</title>
                <meta name="description" content="{desc}">
                <meta property="og:title" content="{title}">
                <meta property="og:description" content="{desc}">
                <meta http-equiv="refresh" content="0;url={target_url}">
                <script>window.location.href = "{target_url}";</script>
            </head>
            <body style="background: #0a0a0a;"></body>
        </html>
        """
        return HTMLResponse(content=meta_html)

    response = RedirectResponse(url=target_url)
    if url_obj.is_cloaked:
        response.headers["Referrer-Policy"] = "no-referrer"
    return response

