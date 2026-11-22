# LIFE Savers

**Every Drop Counts. Every Life Matters.**

Connecting blood donors with patients in **Wah Cantt and Taxila**.

A family posts a blood request, a moderator checks it's genuine, and the app finds
nearby donors who are compatible and eligible to donate. Contact details are shared
only after a donor accepts.

> Rebuild of my original 2019 Django project, starting from scratch with a proper data model,
> privacy-first design and production security settings.

## Status

| Phase | What | State |
|---|---|---|
| 1 | Foundation: models, matching logic, admin, settings, tests, CI | ✅ Done |
| 2 | Donor accounts (phone + OTP), Tailwind + HTMX UI, Urdu | ⏳ Next |
| 3 | Request flow, donor alerts (push / email, later WhatsApp) | |
| 4 | Security hardening, deploy (Render + Neon) | |
| 5 | PWA, analytics dashboard | |

## How it works

- **Blood compatibility:** red cell rules in `apps/core/blood.py`. Exact group first, then other
  compatible groups, with O- last so universal donors aren't asked every time.
- **Eligibility:** age range, 90-day gap since last donation, availability/pause, and a
  recent self-check. All rules are configurable in settings.
- **Matching:** `apps/blood_requests/matching.py` filters eligible, compatible donors within a
  radius (default 15 km) of the hospital and ranks them by group priority and distance.
- **Request lifecycle:** `pending_review → open → fulfilled`, or `rejected / cancelled / expired`.
  Run `python manage.py expire_requests` on a schedule.

## Privacy by design

The app does **not** store disease history, HIV/hepatitis status, medications, house address or
full date of birth. Donors complete a self-check whose answers are never saved; the blood bank
does the real screening. Location is approximate (area level). The attendant's phone number is
visible only to the requester, moderators, and donors who accepted.

## Tech

Django 5.2 LTS · PostgreSQL (Neon) · django-environ · django-phonenumber-field · WhiteNoise ·
Ruff · GitHub Actions. Coming next: Tailwind CSS, HTMX, PWA.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                 # then put a real SECRET_KEY in .env
python manage.py migrate
python manage.py seed_demo           # fake donors + one demo request (DEBUG only)
python manage.py createsuperuser     # log in with a phone number, e.g. 03001234567
python manage.py runserver
```

Admin: http://127.0.0.1:8000/manage-ls/ (path set by `ADMIN_URL`).

In the admin, open **Blood requests**, select the demo request and run
**"Approve and notify matching donors"** to see matching in action.

## Tests

```bash
python manage.py test
ruff check .
```

## Project layout

```
config/settings/   base.py · dev.py · prod.py
apps/accounts/     custom User (phone number login)
apps/core/         City, Area, Hospital, blood + geo helpers, seed commands
apps/donors/       DonorProfile, Donation, eligibility rules
apps/blood_requests/  BloodRequest, DonorResponse, matching service
```
