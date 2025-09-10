"""
Admin UI router for the PaddockPulse application.
Provides endpoints for admin dashboard, posts, analytics, and settings.
Production version using real database.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
import csv
from io import StringIO
import os
import math

from fastapi import APIRouter, Depends, HTTPException, Request, status, Response, File, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from paddock_pulse.config.settings import settings
from paddock_pulse.db.session import get_db
from paddock_pulse.db.models import (
    User, Post, Media, DailyMetric, PostAnalytics, PerformanceMetric, 
    Schedule, Content
)
from paddock_pulse.services.analytics import AnalyticsService
from paddock_pulse.services.poster import ContentPoster
from paddock_pulse.services.composer import ContentComposer
from paddock_pulse.services.media import MediaService
from .auth import (
    authenticate_user, create_access_token, get_current_active_user,
    admin_required, Token, User
)

# Helper function to create pagination data
def create_pagination(page: int, limit: int, total: int):
    """Create pagination data for templates."""
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    # Ensure current page is within valid range
    page = max(1, min(page, total_pages))
    
    # Calculate page ranges to show
    show_pages = 5  # Number of page links to show
    start_page = max(1, page - show_pages // 2)
    end_page = min(total_pages, start_page + show_pages - 1)
    
    # Adjust start_page if we're near the end
    if end_page - start_page + 1 < show_pages:
        start_page = max(1, end_page - show_pages + 1)
    
    return {
        "current": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous": page - 1 if page > 1 else None,
        "next": page + 1 if page < total_pages else None,
        "pages": list(range(start_page, end_page + 1)),
        "total_items": total,
        "start_item": (page - 1) * limit + 1 if total > 0 else 0,
        "end_item": min(page * limit, total),
    }

# Initialize router
router = APIRouter()

# Set up templates
templates = Jinja2Templates(directory="paddock_pulse/admin_ui/templates")

# Authentication endpoints
@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    username: str,
    password: str
):
    """Authenticate user and return access token."""
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Dashboard routes
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    """Admin dashboard homepage."""
    analytics_service = AnalyticsService()
    poster_service = ContentPoster()
    composer_service = ContentComposer()
    
    # Get data for dashboard
    stats = {
        "total_content": await composer_service.get_total_content(db),
        "total_posts": await poster_service.get_total_posts(db),
        "scheduled_posts": await poster_service.get_scheduled_posts_count(db),
        "total_engagement": await analytics_service.get_total_engagement(db)
    }
    
    recent_activity = await composer_service.get_recent_activity(db, limit=5)
    performance_data = await analytics_service.get_performance_data(db, days=30)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": "Admin Dashboard",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "env": settings.app_env,
            "daily_budget": 2.35,  # Mock data for now
            "budget_cap": settings.daily_budget_cap,
            "post_count": 12,  # Mock data for now
            "api_calls": 87,  # Mock data for now
            "last_race": "Monaco Grand Prix",  # Mock data for now
            "stats": stats,
            "recent_activity": recent_activity,
            "performance_data": performance_data,
            "user": {"username": "Admin"}
        },
    )

@router.get("/posts", response_class=HTMLResponse)
async def admin_posts(
    request: Request,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Admin posts management page."""
    poster_service = ContentPoster()
    posts, total = await poster_service.get_posts(
        db=db,
        platform=platform,
        status=status,
        search=search,
        skip=(page - 1) * limit,
        limit=limit
    )
    
    # Create pagination data
    pagination = create_pagination(page, limit, total)
    
    # Define platform options
    platforms = [
        {"value": "instagram", "label": "Instagram"},
        {"value": "twitter", "label": "Twitter"},
        {"value": "facebook", "label": "Facebook"},
        {"value": "linkedin", "label": "LinkedIn"},
        {"value": "tiktok", "label": "TikTok"}
    ]
    
    # Define status options
    statuses = [
        {"value": "draft", "label": "Draft"},
        {"value": "scheduled", "label": "Scheduled"},
        {"value": "published", "label": "Published"},
        {"value": "failed", "label": "Failed"}
    ]
    
    return templates.TemplateResponse(
        "posts.html",
        {
            "request": request,
            "title": "Manage Posts",
            "posts": posts,
            "total": total,
            "page": page,
            "limit": limit,
            "pagination": pagination,
            "platforms": platforms,
            "statuses": statuses,
            "filters": {
                "platform": platform,
                "status": status,
                "search": search
            },
            "user": {"username": "Admin"}
        },
    )

@router.post("/posts/manual", response_class=JSONResponse)
async def manual_post(
    request: Request,
    platform: str = Form(...),
    content: str = Form(...),
    title: str = Form(...),
    media_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Handle manual post creation."""
    poster_service = ContentPoster()
    post_data = {
        "platform": platform,
        "content": content,
        "title": title,
    }
    
    result = await poster_service.manual_post(db, post_data, media_file)
    return result

@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(
    request: Request,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Admin analytics page."""
    analytics_service = AnalyticsService()
    metrics = await analytics_service.get_metrics(db, days=days)
    engagement_data = await analytics_service.get_engagement_data(db, days=days)
    platform_data = await analytics_service.get_platform_distribution(db, days=days)
    top_content = await analytics_service.get_top_content(db, limit=10, days=days)
    
    # Time period options
    time_periods = [
        {"value": "7", "label": "Last 7 days"},
        {"value": "30", "label": "Last 30 days"},
        {"value": "90", "label": "Last 90 days"},
        {"value": "180", "label": "Last 6 months"},
        {"value": "365", "label": "Last year"}
    ]
    
    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "title": "Analytics",
            "metrics": metrics,
            "engagement_data": engagement_data,
            "platform_data": platform_data,
            "top_content": top_content,
            "days": days,
            "time_periods": time_periods,
            "user": {"username": "Admin"}
        },
    )

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Admin settings page."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Settings",
            "api_keys_configured": bool(settings.openai_api_key),
            "instagram_configured": bool(settings.instagram_api_key),
            "user": {"username": "Admin"}
        },
    )

@router.get("/login", response_class=HTMLResponse)
async def admin_login(request: Request):
    """Admin login page."""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Admin Login",
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "env": settings.app_env,
            "user": {"username": "Admin"}
        },
    )

@router.get("/content", response_class=HTMLResponse)
async def content_management(
    request: Request,
    content_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Render the content management page."""
    composer_service = ContentComposer()
    content, total = await composer_service.get_content(
        db=db,
        content_type=content_type,
        status=status,
        search=search,
        skip=(page - 1) * limit,
        limit=limit
    )
    
    # Create pagination data
    pagination = create_pagination(page, limit, total)
    
    # Define content type options
    content_types = [
        {"value": "post", "label": "Post"},
        {"value": "article", "label": "Article"},
        {"value": "video", "label": "Video"},
        {"value": "story", "label": "Story"}
    ]
    
    # Define status options
    statuses = [
        {"value": "draft", "label": "Draft"},
        {"value": "published", "label": "Published"},
        {"value": "archived", "label": "Archived"}
    ]
    
    return templates.TemplateResponse(
        "content.html",
        {
            "request": request,
            "title": "Content Management",
            "content": content,
            "total": total,
            "page": page,
            "limit": limit,
            "pagination": pagination,
            "content_types": content_types,
            "statuses": statuses,
            "filters": {
                "content_type": content_type,
                "status": status,
                "search": search
            },
            "user": {"username": "Admin"}
        },
    )

@router.get("/media", response_class=HTMLResponse)
async def media_management(
    request: Request,
    media_type: Optional[str] = None,
    style: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 12,
    db: Session = Depends(get_db)
):
    """Render the media management page."""
    media_service = MediaService()
    media, total = await media_service.get_media(
        db=db,
        media_type=media_type,
        style=style,
        search=search,
        skip=(page - 1) * limit,
        limit=limit
    )
    
    # Get media types and styles for the filter dropdowns
    media_types = await media_service.get_media_types()
    styles = await media_service.get_media_styles()
    
    # Create pagination data
    pagination = create_pagination(page, limit, total)
    
    return templates.TemplateResponse(
        "media.html",
        {
            "request": request,
            "title": "Media Library",
            "media": media,
            "total": total,
            "page": page,
            "limit": limit,
            "pagination": pagination,
            "media_types": media_types,
            "styles": styles,
            "filters": {
                "media_type": media_type,
                "style": style,
                "search": search
            },
            "user": {"username": "Admin"}
        },
    )

@router.post("/media/upload", response_class=JSONResponse)
async def upload_media(
    request: Request,
    title: str = Form(...),
    media_type: str = Form(...),
    style: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    media_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Handle media upload."""
    media_service = MediaService()
    
    try:
        media = await media_service.upload_media(
            db=db,
            title=title,
            description=description,
            media_type=media_type,
            style=style,
            media_file=media_file
        )
        
        return {
            "id": media.id,
            "url": media.url,
            "title": media.title,
            "message": "Media uploaded successfully"
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": f"Error uploading media: {str(e)}"}
        )

@router.get("/schedules", response_class=HTMLResponse)
async def schedules_management(
    request: Request,
    schedule_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Render the schedule management page."""
    poster_service = ContentPoster()
    schedules, total = await poster_service.get_schedules(
        db=db,
        schedule_type=schedule_type,
        status=status,
        search=search,
        skip=(page - 1) * limit,
        limit=limit
    )
    
    # Create pagination data
    pagination = create_pagination(page, limit, total)
    
    # Define schedule type options
    schedule_types = [
        {"value": "one-time", "label": "One-time"},
        {"value": "recurring", "label": "Recurring"}
    ]
    
    # Define status options
    statuses = [
        {"value": "active", "label": "Active"},
        {"value": "paused", "label": "Paused"},
        {"value": "completed", "label": "Completed"}
    ]
    
    # Define platform options for new schedules
    platforms = [
        {"value": "instagram", "label": "Instagram"},
        {"value": "twitter", "label": "Twitter"},
        {"value": "facebook", "label": "Facebook"},
        {"value": "linkedin", "label": "LinkedIn"},
        {"value": "tiktok", "label": "TikTok"}
    ]
    
    return templates.TemplateResponse(
        "schedules.html",
        {
            "request": request,
            "title": "Schedule Management",
            "schedules": schedules,
            "total": total,
            "page": page,
            "limit": limit,
            "pagination": pagination,
            "schedule_types": schedule_types,
            "statuses": statuses,
            "platforms": platforms,
            "filters": {
                "schedule_type": schedule_type,
                "status": status,
                "search": search
            },
            "user": {"username": "Admin"}
        },
    ) 