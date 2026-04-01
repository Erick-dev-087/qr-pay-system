# AGENT.md

## Project Identity

QR-Pay-System is a Python backend-focused payment project for initiating payments through scanning QR codes and generating QR codes.

In practice, this project provides:
- Merchant onboarding and QR code generation
- User authentication and payment initiation
- M-Pesa (Daraja) integration for STK push payment flows
- Admin analytics and transaction monitoring

## What This Codebase Is About

The backend is a Flask API that powers a QR payment workflow:
- Vendors generate CBK/EMVCo-aligned payment QR codes
- Users scan QR codes and initiate payments
- The backend validates requests, records transaction state, and integrates with payment providers

Primary implementation is in the backend folder.

## Key Locations

- `backend/app.py`: Flask app factory, extension setup, blueprint registration, health endpoint
- `backend/routes/`: API route modules (auth, user, vendor, qr, payment, admin)
- `backend/models.py`: SQLAlchemy models
- `backend/config.py`: environment and runtime configuration
- `backend/manage.py`: Flask CLI helpers for migration flow
- `backend/utils/`: helper services including Daraja/payment-related utilities
- `backend/tests/`: test suite and focused test scripts

## Build, Run, and Test

From the repository root:

1. Install dependencies
- `pip install -r requirements.txt`
- `pip install -r backend/requirements.txt`

2. Run backend API (development)
- `python backend/app.py`

3. Alternative: run with Flask CLI entrypoint
- `python backend/manage.py`

4. Database migration helpers (from backend context)
- `python backend/manage.py db_init`
- `python backend/manage.py db_migrate`
- `python backend/manage.py db_upgrade`

5. Run tests
- `pytest backend/tests -q`
- Optional targeted tests: `python backend/test_stk_push.py`, `python backend/test_qr_utils.py`

## Agent Working Conventions

- Favor edits in backend modules unless task explicitly targets Android/mobile or infrastructure files.
- Keep app factory pattern in `backend/app.py` intact.
- Register new endpoints as blueprints under `backend/routes/` and wire them through `routes/__init__.py`.
- Keep business logic out of route handlers when possible; place reusable logic in `backend/utils/`.
- Preserve existing API response style (JSON with explicit status and message fields).
- Use environment variables for secrets and provider credentials; never hardcode keys or tokens.

## Common Pitfalls

- Daraja transaction type mismatch can cause 400 errors (PayBill vs BuyGoods require proper PartyB/till setup).
- Ensure `.env` values are present before testing payment endpoints.
- Maintain JWT configuration consistency when adding protected routes.
- Avoid changing model fields without creating and applying migrations.

## Existing Documentation (Link, Do Not Duplicate)

- `backend/API_DOCUMENTATION.md`: endpoint-level API behavior and payload contracts
- `backend/DARAJA_IMPLEMENTATION.md`: payment provider behavior, transaction type details, troubleshooting

## If You Are Automating Changes

Before large changes:
1. Read `backend/API_DOCUMENTATION.md`.
2. Inspect related route module in `backend/routes/`.
3. Verify model impact in `backend/models.py` and migration impact via `backend/manage.py` commands.

After changes:
1. Run focused tests for touched areas.
2. Run `pytest backend/tests -q`.
3. Confirm `/api/health` remains operational.
