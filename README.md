# DILG Supply Inventory

Django-based supply inventory and request tracker with custom staff interface, Bootstrap 5 UI, and Chart.js analytics.

## Features
- Staff (is_staff=True): manage supplies, record incoming stock, approve/reject requests, dashboard with top requested and monthly outgoing chart.
- Users: submit multi-item supply requests, track statuses (pending/approved/rejected).
- Business rules: requests cannot exceed available stock; approval auto-deducts inventory; rejection does not change stock.
- Auth: Django built-in login/logout; views protected by `login_required` and staff checks.

## Setup
1. Install dependencies (already installed: Django). Ensure the virtualenv is active or use the provided interpreter path: `C:/Users/Jezzy Dawn/dilg_invetory/.venv/Scripts/python.exe`.
2. Apply migrations (already run): `python manage.py migrate`.
3. Create a superuser to access staff features: `python manage.py createsuperuser` and set `is_staff=True`.
4. Run the dev server: `python manage.py runserver`.

## Usage
- Login at `/accounts/login/`.
- Staff home redirects to `/supplies/dashboard/`; users redirect to `/requests/new/`.
- Manage supplies at `/supplies/list/` and record incoming stock at `/supplies/incoming/`.
- Submit requests at `/requests/new/`; view all requests at `/requests/list/` (staff see all, users see their own). Approve/reject via action buttons.

## Tech Stack
- Python 3.x, Django 6.x, SQLite
- Django Templates, Bootstrap 5 (CDN), Chart.js (CDN)
