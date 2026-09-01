# TickVendor - Complete Application Structure
# This file defines the core project layout

"""
TickVendor - Ticketing + Events + Community Engagement Platform

Core Philosophy: Discover → Ticket → Attend → Verify → Participate → Contribute → Earn Impact → Reach Milestone → Gain Recognition

Brand: TickVendor
Domain: tickvendor.com
"""

import os
from datetime import datetime, timedelta
from decimal import Decimal

# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

def load_env():
    """Load environment variables from .env file."""
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ[key.strip()] = value.strip()

load_env()

# ============================================================
# DATABASE SETTINGS
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tickvendor.db")
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
SQLITE_ECHO = os.getenv("SQLITE_ECHO", "false").lower() == "true"

# ============================================================
# PAYMENT PROVIDER SETTINGS
# ============================================================

PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "paystack")  # paystack, flutterwave, stripe
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
FLUTTERWAVE_PUBLIC_KEY = os.getenv("FLUTTERWAVE_PUBLIC_KEY", "")
FLUTTERWAVE_SECRET_KEY = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")

# ============================================================
# GEOFENCE SETTINGS
# ============================================================

DEFAULT_GEOFENCE_RADIUS_METERS = int(os.getenv("DEFAULT_GEOFENCE_RADIUS_METERS", "100"))
ATTENDANCE_CHECKIN_WINDOW_MINUTES = int(os.getenv("ATTENDANCE_CHECKIN_WINDOW_MINUTES", "30"))
ATTENDANCE_CHECKOUT_WINDOW_MINUTES = int(os.getenv("ATTENDANCE_CHECKOUT_WINDOW_MINUTES", "30"))

# ============================================================
# IMPACT POINT SETTINGS
# ============================================================

# These are configurable via admin, not hard-coded
IMPACT_POINTS_DEFAULTS = {
    "attendance": 10,
    "task_completion": 20,
    "peer_verification": 2,
    "leadership_activity": 30,
    "volunteer_activity": 15,
}

# ============================================================
# NOTIFICATION SETTINGS
# ============================================================

NOTIFY_EMAIL_ON_ATTENDANCE = os.getenv("NOTIFY_EMAIL_ON_ATTENDANCE", "true").lower() == "true"
NOTIFY_ON_MILESTONE = os.getenv("NOTIFY_ON_MILESTONE", "true").lower() == "true"
NOTIFY_ON_BADGE = os.getenv("NOTIFY_ON_BADGE", "true").lower() == "true"

# ============================================================
# COMMUNITY SETTINGS
# ============================================================

DEFAULT_COMMUNITY_ROLE = os.getenv("DEFAULT_COMMUNITY_ROLE", "member")
MAX_COMMUNITIES_PER_USER = int(os.getenv("MAX_COMMUNITIES_PER_USER", "5"))

# ============================================================
# RANK SYSTEM
# ============================================================

# Rank thresholds are configurable via admin, these are defaults
DEFAULT_RANK_THRESHOLDS = [
    {"min_points": 0, "max_points": 49, "name": "Starter", "icon": "🌱"},
    {"min_points": 50, "max_points": 149, "name": "Active Member", "icon": "👤"},
    {"min_points": 150, "max_points": 299, "name": "Contributor", "icon": "💪"},
    {"min_points": 300, "max_points": 499, "name": "Community Builder", "icon": "🏗️"},
    {"min_points": 500, "max_points": 799, "name": "Community Leader", "icon": "👑"},
    {"min_points": 800, "max_points": 999999, "name": "Impact Champion", "icon": "⭐"},
]

# ============================================================
# BADGE CATEGORIES
# ============================================================

BADGE_CATEGORIES = [
    "attendance",
    "task",
    "contribution",
    "leadership",
    "milestone",
    "special",
]

# ============================================================
# EVENT CATEGORIES (configurable)
# ============================================================

DEFAULT_EVENT_CATEGORIES = [
    "technology",
    "education",
    "business",
    "community",
    "agriculture",
    "entertainment",
    "sports",
    "training",
    "conference",
    "workshop",
    "networking",
    "volunteer",
    "fundraising",
]

# ============================================================
# TIMEZONE SETTINGS
# ============================================================

DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Africa/Lagos")

# ============================================================
# CURRENCY SETTINGS
# ============================================================

DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "NGN")  # Nigerian Naira
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "₦")

# ============================================================
# SECURITY SETTINGS
# ============================================================

SECRET_KEY = os.getenv("SECRET_KEY", "tickvendor-development-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

# ============================================================
# GEOLOCATION SETTINGS
# ============================================================

GEOLOCATION_TIMEOUT_SECONDS = int(os.getenv("GEOLOCATION_TIMEOUT_SECONDS", "10"))
GEOLOCATION_MAX_ACCURACY_METERS = int(os.getenv("GEOLOCATION_MAX_ACCURACY_METERS", "50"))

# ============================================================
# PEER VERIFICATION SETTINGS
# ============================================================

PEER_CONFIRMATION_DEADLINE_DAYS = int(os.getenv("PEER_CONFIRMATION_DEADLINE_DAYS", "7"))
PEER_MAX_CONFIRMATIONS_PER_USER = int(os.getenv("PEER_MAX_CONFIRMATIONS_PER_USER", "10"))
PEER_MIN_CONFIRMATIONS_REQUIRED = int(os.getenv("PEER_MIN_CONFIRMATIONS_REQUIRED", "3"))

# ============================================================
# MILESTONE REQUIREMENTS (configurable)
# ============================================================

DEFAULT_MILESTONE_REQUIREMENTS = {
    "first_step": {
        "name": "First Step",
        "requirements": {
            "attendance_count": 1,
        },
        "reward": {"badge": "first_step", "impact_points": 50},
    },
    "community_builder": {
        "name": "Community Builder",
        "requirements": {
            "attendance_count": 10,
            "task_count": 5,
            "impact_points": 300,
        },
        "reward": {"badge": "community_builder", "impact_points": 100},
    },
    "impact_champion": {
        "name": "Impact Champion",
        "requirements": {
            "impact_points": 1000,
        },
        "reward": {"badge": "impact_champion", "impact_points": 200},
    },
}

# ============================================================
# ADMIN SETTINGS
# ============================================================

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@tickvendor.com")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Super Administrator")

# ============================================================
# API VERSIONING
# ============================================================

API_V1_PREFIX = "/api/v1"
API_V2_PREFIX = "/api/v2"

# ============================================================
# CORS SETTINGS
# ============================================================

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
).split(",")

# ============================================================
# LOGGING SETTINGS
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/tickvendor.log")

# ============================================================
# PWA SETTINGS
# ============================================================

PWA_NAME = os.getenv("PWA_NAME", "TickVendor")
PWA_SHORT_NAME = os.getenv("PWA_SHORT_NAME", "TickVendor")
PWA_DESCRIPTION = os.getenv("PWA_DESCRIPTION", "Discover. Attend. Participate. Achieve.")
PWA_ORIENTATION = os.getenv("PWA_ORIENTATION", "portrait-primary")
PWA_BACKGROUND_COLOR = os.getenv("PWA_BACKGROUND_COLOR", "#1a1a2e")
PWA_THEME_COLOR = os.getenv("PWA_THEME_COLOR", "#6366f1")
PWA_DISPLAY = os.getenv("PWA_DISPLAY", "standalone")
PWA_SCOPE = os.getenv("PWA_SCOPE", "/")
PWA_START_URL = os.getenv("PWA_START_URL", "/")
PWA_STATUS_BAR_COLOR = os.getenv("PWA_STATUS_BAR_COLOR", "default")

# ============================================================
# Feature Flags
# ============================================================

FEATURE_PEER_VERIFICATION = os.getenv("FEATURE_PEER_VERIFICATION", "true").lower() == "true"
FEATURE_GEOFENCED_ATTENDANCE = os.getenv("FEATURE_GEOFENCED_ATTENDANCE", "true").lower() == "true"
FEATURE_TASKS = os.getenv("FEATURE_TASKS", "true").lower() == "true"
FEATURE_CONTRIBUTIONS = os.getenv("FEATURE_CONTRIBUTIONS", "true").lower() == "true"
FEATURE_RANKS = os.getenv("FEATURE_RANKS", "true").lower() == "true"
FEATURE_BADGES = os.getenv("FEATURE_BADGES", "true").lower() == "true"
FEATURE_MILESTONES = os.getenv("FEATURE_MILESTONES", "true").lower() == "true"
FEATURE_NOTIFICATIONS = os.getenv("FEATURE_NOTIFICATIONS", "true").lower() == "true"
FEATURE_LEADERBOARDS = os.getenv("FEATURE_LEADERBOARDS", "true").lower() == "true"