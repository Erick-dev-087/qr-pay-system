# QR-Pay-System API Documentation

## Overview

**QR-Pay-System** is a comprehensive mobile payment platform built with Flask that enables QR code-based payments integrated with M-Pesa (Safaricom's mobile money service) & later even bank payments(Compliant to the CBK rules for QR codes). The system supports two types of users:

- **Users (Consumers)**: Make payments by scanning vendor QR codes
- **Vendors (Merchants)**: Generate QR codes and receive payments

### Technology Stack

| Component | Technology |
|-----------|------------|
| Backend Framework | Flask (Python) |
| Database | PostgreSQL |
| Authentication | JWT (Flask-JWT-Extended) |
| ORM | SQLAlchemy |
| Payment Gateway | M-Pesa/Daraja API |
| QR Standard | CBK-compliant (EMVCo format) |

---

## Table of Contents

1. [Authentication](#1-authentication-api)
2. [User Management](#2-user-management-api)
3. [Vendor Management](#3-vendor-management-api)
4. [QR Code Management](#4-qr-code-management-api)
5. [Payment Processing](#5-payment-processing-api)
6. [Admin Analytics](#6-admin-analytics-api)
7. [Data Models](#7-data-models)
8. [Utility Components](#8-utility-components)
9. [Error Handling](#9-error-handling)
10. [Configuration](#10-configuration)

---

## Base URL

```
http://localhost:5000/api
```

## Authentication Header

All protected endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <access_token>
```

---

## 1. Authentication API

**Base Path:** `/api/auth`

The authentication module handles registration, login, and logout for both Users and Vendors. It uses JWT tokens with custom claims to differentiate user types.

### 1.1 Register User

Creates a new consumer account.

**Endpoint:** `POST /api/auth/register/user`

**Authentication:** None required

**Request Body:**
```json
{
    "name": "John Doe",
    "phone_number": "254712345678",
    "email": "john@example.com",
    "password": "securepass123"
}
```

**Validation Rules:**
- All fields required
- Email must contain `@`
- Phone number minimum 10 characters
- Password minimum 8 characters
- Email and phone must be unique

**Success Response (201):**
```json
{
    "message": "User registered successfully",
    "access_token": "eyJhbGciOiJS...",
    "user": {
        "id": 1,
        "name": "John Doe",
        "phone": "254712345678",
        "email": "john@example.com"
    }
}
```

**Error Responses:**
- `400` - Missing/invalid fields
- `409` - Email or phone already exists

**Related Components:**
- Uses `User` model from `models.py`
- Password hashed via Werkzeug's `generate_password_hash()`

---

### 1.2 Register Vendor

Creates a new merchant account with business details.

**Endpoint:** `POST /api/auth/register/vendor`

**Authentication:** None required

**Request Body:**
```json
{
    "name": "Jane Smith",
    "business_shortcode": "123456",
    "merchant_id": "MID001",
    "mcc": "5411",
    "store_label": "Downtown Store",
    "email": "jane@business.com",
    "phone": "254798765432",
    "password": "vendorpass123",
    "psp_id": "PSP001",
    "psp_name": "Safaricom"
}
```

**Field Descriptions:**
| Field | Description |
|-------|-------------|
| `business_shortcode` | Till/Paybill/Pochi number |
| `merchant_id` | CBK/PSP routing identifier |
| `mcc` | Merchant Category Code (4 or 8 characters) |
| `store_label` | Physical store location/name |
| `psp_id` | Payment Service Provider ID |
| `psp_name` | PSP name (e.g., Safaricom) |

**Success Response (201):**
```json
{
    "message": "Vendor registered successful",
    "access_token": "eyJhbGciOiJS...",
    "vendor": {
        "id": 1,
        "name": "Jane Smith",
        "business_shortcode": "123456",
        "merchant_id": "MID001",
        "mcc": "5411",
        "store_label": "Downtown Store",
        "email": "jane@business.com",
        "phone": "254798765432",
        "psp_id": "PSP001",
        "psp_name": "Safaricom"
    }
}
```

**Error Responses:**
- `400` - Missing/invalid fields, MCC invalid length
- `409` - Email, phone, or business_shortcode already exists

**Related Components:**
- Uses `Vendor` model from `models.py`
- MCC codes mapped in `utils/mcc_categories.json`

---

### 1.3 Login (Universal)

Authenticates both users and vendors via email.

**Endpoint:** `POST /api/auth/login`

**Authentication:** None required

**Request Body:**
```json
{
    "email": "user@example.com",
    "password": "password123"
}
```

**Success Response - User (200):**
```json
{
    "message": "Login successful",
    "access_token": "eyJhbGciOiJS...",
    "user_type": "user",
    "user": {
        "id": 1,
        "email": "user@example.com",
        "name": "John Doe",
        "phone": "254712345678"
    }
}
```

**Success Response - Vendor (200):**
```json
{
    "message": "Login successful",
    "access_token": "eyJhbGciOiJS...",
    "user_type": "vendor",
    "vendor": {
        "id": 1,
        "name": "Jane Smith",
        "business_shortcode": "123456",
        "merchant_id": "MID001",
        "mcc": "5411",
        "store_label": "Downtown Store",
        "email": "jane@business.com",
        "phone": "254798765432",
        "psp_id": "PSP001",
        "psp_name": "Safaricom"
    }
}
```

**JWT Token Claims:**
```json
{
    "sub": "1",
    "user_type": "user|vendor",
    "phone": "254...",
    "email": "...",
    "business_shortcode": "..." // vendor only
}
```

**Error Responses:**
- `400` - Missing fields
- `401` - Invalid credentials

---

### 1.4 Logout

Logs out the current user/vendor.

**Endpoint:** `POST /api/auth/logout`

**Authentication:** Required (JWT)

**Success Response (200):**
```json
{
    "message": "Logged out successfully",
    "user_type": "user",
    "timestamp": "2025-02-28T12:00:00"
}
```

**Note:** JWT token invalidation is client-side (delete token from storage). Server logs the logout event for security monitoring.

---

## 2. User Management API

**Base Path:** `/api/user`

Handles user profile management, transaction history, and spending analytics.

### 2.1 Get User Profile

Retrieves the authenticated user's profile.

**Endpoint:** `GET /api/user/profile`

**Authentication:** Required (JWT - user only)

**Success Response (200):**
```json
{
    "message": "User profile retrieved successfully",
    "user": {
        "id": 1,
        "name": "John Doe",
        "phone_number": "254712345678",
        "email": "john@example.com",
        "is_active": true,
        "created_at": "2025-01-15T10:30:00",
        "updated_at": "2025-02-28T14:00:00"
    }
}
```

**Error Responses:**
- `403` - Not a user account
- `404` - User not found

---

### 2.2 Update User Profile

Updates user profile fields.

**Endpoint:** `PUT /api/user/profile`

**Authentication:** Required (JWT - user only)

**Request Body (all fields optional):**
```json
{
    "name": "John Updated",
    "phone_number": "254712345999",
    "email": "john.new@example.com"
}
```

**Success Response (200):**
```json
{
    "message": "User profile updated successfully",
    "user": {
        "id": 1,
        "name": "John Updated",
        "phone_number": "254712345999",
        "email": "john.new@example.com",
        "updated_at": "2025-02-28T14:30:00"
    }
}
```

**Error Responses:**
- `400` - Empty field values
- `409` - Email or phone already in use

---

### 2.3 Update User Password

Changes the user's password.

**Endpoint:** `PUT /api/user/password`

**Authentication:** Required (JWT - user only)

**Request Body:**
```json
{
    "current_password": "oldpass123",
    "new_password": "newpass456"
}
```

**Validation:**
- New password minimum 6 characters

**Success Response (200):**
```json
{
    "message": "Password updated successfully"
}
```

**Error Responses:**
- `400` - Missing fields or password too short
- `401` - Current password incorrect

---

### 2.4 Get User Transactions

Retrieves paginated transaction history.

**Endpoint:** `GET /api/user/transactions`

**Authentication:** Required (JWT - user only)

**Query Parameters:**
| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `page` | 1 | - | Page number |
| `per_page` | 20 | 100 | Items per page |

**Success Response (200):**
```json
{
    "message": "Transaction history retrieved successfully",
    "transactions": [
        {
            "id": 1,
            "amount": 500,
            "currency": "404",
            "status": "success",
            "mpesa_receipt": "QGK123ABC",
            "phone": "254712345678",
            "initiated_at": "2025-02-28T10:00:00",
            "completed_at": "2025-02-28T10:01:00",
            "vendor_id": 5,
            "qrcode_id": 3
        }
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 45,
        "pages": 3,
        "has_next": true,
        "has_prev": false
    }
}
```

---

### 2.5 Get Specific Transaction

Retrieves details of a single transaction.

**Endpoint:** `GET /api/user/transactions/{transaction_id}`

**Authentication:** Required (JWT - user only)

**Success Response (200):**
```json
{
    "message": "Transaction retrieved successfully",
    "transaction": {
        "id": 1,
        "amount": 500,
        "currency": "404",
        "status": "success",
        "mpesa_receipt": "QGK123ABC",
        "phone": "254712345678",
        "callback_response": { ... },
        "initiated_at": "2025-02-28T10:00:00",
        "completed_at": "2025-02-28T10:01:00",
        "vendor_id": 5,
        "qrcode_id": 3
    }
}
```

**Error Response:**
- `404` - Transaction not found or access denied

---

### 2.6 Get User Analytics

Retrieves comprehensive spending analytics dashboard.

**Endpoint:** `GET /api/user/analytics`

**Authentication:** Required (JWT - user only)

**Query Parameters:**
| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `days` | 30 | 365 | Analysis period in days |
| `months` | 3 | 12 | Months for trend analysis |
| `weeks` | 4 | 52 | Weeks for weekly analysis |

**Success Response (200):**
```json
{
    "message": "User analytics retrieved successfully",
    "generated_at": "2025-02-28T15:00:00",
    "user_id": 1,
    "user_name": "John Doe",
    "analytics": {
        "overview": {
            "Period_days": 30,
            "total_spent": "15000.00",
            "transaction_count": 25,
            "average_transaction": "600.00"
        },
        "top_merchants": {
            "period_days": 30,
            "top_by_amount": [...],
            "top_by_frequency": [...]
        },
        "weekday_patterns": {
            "period_days": 30,
            "by_weekday": {
                "Monday": {"total": "2000.00", "count": 5, "average": "400.00"},
                ...
            }
        },
        "monthly_trends": {
            "period_months": 3,
            "monthly_breakdown": [...],
            "trend": "increasing|decreasing|stable"
        },
        "weekly_breakdown": [...],
        "largest_transactions": [...],
        "insights": {...}
    }
}
```

**Related Utilities:**
- `get_user_spending_summary()` - Total spent and count
- `get_user_top_merchants()` - Favorite vendors
- `get_user_daily_trends_by_weekday()` - Weekday patterns
- `get_user_spending_trends()` - Monthly trends
- `get_user_weekly_spending()` - Weekly breakdown
- `get_user_largest_transactions()` - Biggest payments
- `get_user_spending_insights()` - AI-generated insights

All functions located in `utils/user_analytics_utils.py`

---

## 3. Vendor Management API

**Base Path:** `/api/merchant`

Handles vendor profile management, transaction history, and business analytics.

### 3.1 Get Vendor Profile

Retrieves the authenticated vendor's profile.

**Endpoint:** `GET /api/merchant/profile`

**Authentication:** Required (JWT - vendor only)

**Success Response (200):**
```json
{
    "message": "Vendor profile retrieved successfully",
    "vendor": {
        "id": 1,
        "name": "Jane Smith",
        "business_shortcode": "123456",
        "merchant_id": "MID001",
        "mcc": "5411",
        "store_label": "Downtown Store",
        "email": "jane@business.com",
        "phone": "254798765432",
        "is_active": true,
        "created_at": "2025-01-10T08:00:00",
        "updated_at": "2025-02-28T16:00:00"
    }
}
```

---

### 3.2 Update Vendor Profile

Updates vendor profile fields.

**Endpoint:** `PUT /api/merchant/profile`

**Authentication:** Required (JWT - vendor only)

**Request Body (all fields optional):**
```json
{
    "name": "Jane Updated",
    "business_shortcode": "654321",
    "email": "jane.new@business.com",
    "phone": "254798765999"
}
```

**Success Response (200):**
```json
{
    "message": "Vendor profile updated successfully",
    "vendor": { ... }
}
```

**Error Responses:**
- `400` - Empty field values
- `409` - Email, phone, or business_shortcode already in use

---

### 3.3 Update Vendor Password

Changes the vendor's password.

**Endpoint:** `PUT /api/merchant/password`

**Authentication:** Required (JWT - vendor only)

**Request Body:**
```json
{
    "current_password": "oldpass123",
    "new_password": "newpass456"
}
```

---

### 3.4 Get Vendor Transactions

Retrieves paginated transaction history for the vendor.

**Endpoint:** `GET /api/merchant/transactions`

**Authentication:** Required (JWT - vendor only)

**Query Parameters:**
| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `page` | 1 | - | Page number |
| `per_page` | 20 | 100 | Items per page |

**Success Response (200):**
```json
{
    "message": "Transaction history retrieved successfully",
    "transactions": [
        {
            "id": 10,
            "amount": 1500,
            "currency": "404",
            "status": "success",
            "mpesa_receipt": "QGK456DEF",
            "phone": "254712345678",
            "initiated_at": "2025-02-28T11:00:00",
            "completed_at": "2025-02-28T11:02:00",
            "vendor_id": 1,
            "qrcode_id": 5
        }
    ],
    "pagination": { ... }
}
```

---

### 3.5 Get Specific Transaction (Vendor)

Retrieves details of a single transaction for the vendor.

**Endpoint:** `GET /api/merchant/transactions/{transaction_id}`

**Authentication:** Required (JWT - vendor only)

**Security:** Only returns transactions where `vendor_id` matches authenticated vendor.

---

### 3.6 Get Vendor Analytics

Retrieves comprehensive business analytics dashboard.

**Endpoint:** `GET /api/merchant/analytics`

**Authentication:** Required (JWT - vendor only)

**Query Parameters:**
| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `days` | 30 | 365 | Analysis period in days |
| `weeks` | 4 | 52 | Weeks for performance analysis |

**Success Response (200):**
```json
{
    "message": "Vendor analytics retrieved successfully",
    "generated_at": "2025-02-28T17:00:00",
    "vendor_id": 1,
    "business_name": "Downtown Store",
    "analytics": {
        "cash_flow": {
            "incoming": {"total": "50000.00", "count": 100},
            "outgoing": {"total": "5000.00", "count": 10}
        },
        "net_flow": {
            "net_revenue": "45000.00",
            "profit_margin": "90.00%"
        },
        "top_customers": [...],
        "largest_transactions": [...],
        "outflow_breakdown": {
            "refund": {"total": "2000.00", "count": 4},
            "transfer": {"total": "1500.00", "count": 3},
            "platform_fee": {"total": "1500.00", "count": 3}
        },
        "spending_ratio": {...},
        "weekly_performance": [...]
    }
}
```

**Related Utilities (from `utils/vendor_analytics_utils.py`):**
- `get_vendor_cash_flow()` - Incoming vs outgoing money
- `get_vendor_net_flow()` - Profit/loss calculation
- `get_vendor_top_customers()` - Best customers
- `get_vendor_largest_transactions()` - Biggest payments received
- `get_vendor_outflow_breakdown()` - Where money goes (refunds, fees, etc.)
- `get_vendor_spending_ratio()` - Retention rate
- `get_vendor_weekly_performance()` - Week-by-week analysis

---

## 4. QR Code Management API

**Base Path:** `/api/qr`

Handles QR code generation, scanning, and validation. QR codes follow CBK (Central Bank of Kenya) compliance standards using EMVCo format.

### 4.1 Generate QR Code

Generates a new QR code for the authenticated vendor.

**Endpoint:** `POST /api/qr/generate`

**Authentication:** Required (JWT - vendor only)

**Request Body:**
```json
{
    "qr_type": "STATIC",
    "amount": 500  // Required only for DYNAMIC
}
```

**QR Code Types:**
| Type | Description | Amount |
|------|-------------|--------|
| `STATIC` | Permanent QR, customer enters amount | Not required |
| `DYNAMIC` | Single-use QR with fixed amount | Required |

**Business Rules:**
- Only ONE active static QR per vendor
- If static QR exists, returns existing QR (200)
- Dynamic QRs can have multiple active codes

**Success Response (201):**
```json
{
    "message": "QR code generated successfully",
    "qr_code": {
        "id": 1,
        "payload": "00020101021102150123456789012340302...",
        "type": "static"
    }
}
```

**Existing Static QR Response (200):**
```json
{
    "message": "Active static QR code already exists",
    "qr_code": {
        "id": 1,
        "payload": "00020101021102150123456789012340302...",
        "type": "static"
    }
}
```

**Error Responses:**
- `400` - Invalid QR type or missing amount for dynamic
- `403` - Not a vendor account or vendor inactive
- `404` - Vendor not found

**Related Utilities (from `utils/qr_utils.py`):**
- `QR_utils.generate_merchant_qr()` - Static QR generation
- `QR_utils.generate_transaction_qr()` - Dynamic QR generation
- CBK-compliant payload with CRC-16-CCITT checksum

---

### 4.2 Scan QR Code

Scans and validates a QR code, logs the scan, and returns vendor info.

**Endpoint:** `POST /api/qr/scan`

**Authentication:** Required (JWT - user or vendor)

**Request Body:**
```json
{
    "payload": "00020101021102150123456789012340302..."
}
```

**Processing Steps:**
1. Validate CRC checksum
2. Parse EMVCo payload to extract fields
3. Find vendor by business_shortcode
4. Verify vendor is active
5. Find QR record in database
6. Check QR status is active
7. Prevent vendor from scanning own QR
8. Create scan log entry
9. Update QR `last_scanned_at` timestamp

**Success Response (200):**
```json
{
    "message": "QR scanned successfully",
    "vendor": {
        "id": 5,
        "name": "Coffee Shop",
        "business_shortcode": "123456",
        "store_label": "Main Street Branch"
    },
    "qr_code": {
        "id": 3,
        "type": "static",
        "amount": null,
        "reference": null,
        "currency": "404"
    },
    "next_step": "Use /api/payment/initiate to complete the payment"
}
```

**Error Responses:**
- `400` - Missing payload, invalid checksum, invalid format, QR inactive/expired
- `403` - Vendor inactive, vendor scanning own QR
- `404` - Vendor not found, QR not found

**Related Models:**
- `ScanLog` - Stores scan events
- `ScanStatus` enum: `SCANNED_ONLY`, `PAYMENT_INITIATED`, `PAYMENT_SUCCESS`, `PAYMENT_FAILED`

---

### 4.3 Validate QR Code

Validates a QR code without logging a scan (read-only check).

**Endpoint:** `POST /api/qr/validate`

**Authentication:** Required (JWT)

**Request Body:**
```json
{
    "payload": "00020101021102150123456789012340302..."
}
```

**Use Cases:**
- Pre-validation before payment
- QR code testing
- Display vendor info without creating scan records

**Success Response (200):**
```json
{
    "message": "QR code is valid and ready for payment",
    "valid": true,
    "vendor": {
        "id": 5,
        "name": "Coffee Shop",
        "business_shortcode": "123456",
        "store_label": "Main Street Branch"
    },
    "qr_code": {
        "id": 3,
        "type": "static",
        "amount": null,
        "reference": null,
        "currency": "KES"
    }
}
```

---

## 5. Payment Processing API

**Base Path:** `/api/payment`

Handles payment initiation via M-Pesa STK Push and processes Daraja callbacks.

### 5.1 Initiate Payment

Initiates an M-Pesa STK Push payment to a vendor.

**Endpoint:** `POST /api/payment/initiate`

**Authentication:** Required (JWT - user or vendor)

**Request Body:**
```json
{
    "qr_code_id": 3,
    "amount": 500  // Required only for Static QR
}
```

**Processing Flow:**
1. Validate payer (user or vendor, but vendors can't pay themselves)
2. Retrieve QR code and verify it's active
3. Get payee vendor and verify active status
4. Determine amount:
   - **Dynamic QR**: Amount from QR payload
   - **Static QR**: Amount from request body
5. Validate amount (1 - 500,000 KES)
6. Create `Transaction` record (status: PENDING)
7. Create `PaymentSession` record
8. Initiate M-Pesa STK Push via Daraja API
9. Return transaction ID and checkout request ID

**Transaction Types (automatically determined):**
- `CustomerPayBillOnline` - Bill Payment (default)
- `CustomerBuyGoodsOnline` - Goods/Services

**Success Response (201):**
```json
{
    "message": "Payment initiated successfully",
    "transaction_id": 42,
    "checkout_request_id": "ws_CO_123456789",
    "amount": 500,
    "vendor": {
        "name": "Coffee Shop",
        "business_shortcode": "123456"
    },
    "transaction_type": "CustomerPayBillOnline",
    "status": "Pending",
    "instructions": "Please check your phone and enter your M-Pesa PIN to complete the payment"
}
```

**Error Responses:**
- `400` - Missing QR ID, invalid amount, QR inactive, vendor inactive
- `401` - Account not found
- `404` - QR code not found, vendor not found
- `500` - M-Pesa service failure

**Related Components:**
- `DarajaService` - Real M-Pesa integration (`utils/daraja_service.py`)
- `MockMpesaService` - Development fallback (`utils/mpese_mock.py`)
- `Transaction` model with `TransactionStatus` enum
- `PaymentSession` model with `PaymentStatus` enum

---

### 5.2 Daraja Callback (M-Pesa Confirmation)

Receives payment confirmation from M-Pesa/Daraja.

**Endpoint:** `POST /api/payment/confirm`

**Authentication:** None (called by Safaricom servers)

**Request Body (from Daraja):**
```json
{
    "Body": {
        "stkCallback": {
            "MerchantRequestID": "MR_123",
            "CheckoutRequestID": "ws_CO_123456789",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 500},
                    {"Name": "MpesaReceiptNumber", "Value": "QGK123ABC"},
                    {"Name": "TransactionDate", "Value": 20250228120000},
                    {"Name": "PhoneNumber", "Value": 254712345678}
                ]
            }
        }
    }
}
```

**Processing Steps:**
1. Extract callback data from nested structure
2. Get phone and amount from metadata
3. Find matching pending transaction
4. **Idempotency check**: Skip if already processed
5. Update transaction status based on `ResultCode`:
   - `0` = SUCCESS (store receipt number)
   - Other = FAILED
6. Update `PaymentSession` status
7. Store full callback for audit
8. Always return 200 to Daraja (avoid retries)

**Result Codes:**
| Code | Status | Description |
|------|--------|-------------|
| 0 | SUCCESS | Payment completed |
| 1 | FAILED | Insufficient balance |
| 1032 | CANCELLED | User cancelled |
| 1037 | TIMED_OUT | User didn't respond |

**Response (always 200):**
```json
{
    "ResultCode": 0,
    "ResultDesc": "Callback processed successfully"
}
```

---

### 5.3 Get Transaction Status

Checks the status of a specific transaction.

**Endpoint:** `GET /api/payment/{transaction_id}/status`

**Authentication:** Required (JWT - owner only)

**Authorization Rules:**
- Users can only view their initiated transactions
- Vendors can only view their received transactions

**Success Response (200):**
```json
{
    "id": 42,
    "status": "success",
    "amount": 500,
    "phone": "254712345678",
    "mpesa_receipt": "QGK123ABC",
    "initiated_at": "2025-02-28T12:00:00",
    "completed_at": "2025-02-28T12:01:30"
}
```

**Error Responses:**
- `403` - Unauthorized (not transaction owner)
- `404` - Transaction not found

---

### 5.4 Callback Ping (Health Check)

Tests if the callback endpoint is publicly accessible.

**Endpoint:** `GET /api/payment/ping`

**Authentication:** None

**Success Response (200):**
```json
{
    "status": "ok",
    "message": "Callback endpoint is reachable",
    "endpoint": "/api/payment/confirm"
}
```

**Use Case:** Verify that ngrok/public URL is working for Daraja callbacks.

---

## 6. Admin Analytics API

**Base Path:** `/api/admin`

Provides platform-wide analytics and monitoring for administrators.

> **Note:** Admin role verification is not yet implemented. Currently uses JWT authentication only.

### 6.1 Dashboard Overview

Returns complete admin dashboard with all platform metrics.

**Endpoint:** `GET /api/admin/metrics/overview`

**Authentication:** Required (JWT)

**Query Parameters:**
| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `days` | 30 | 365 | Analysis period |

**Success Response (200):**
```json
{
    "message": "Dashboard data retrieved successfully",
    "dashboard": {
        "total_users": 150,
        "total_vendors": 45,
        "total_transactions": 2500,
        "total_volume": "1250000.00",
        "success_rate": 94.5,
        ...
    }
}
```

**Related Utility:** `get_admin_dashboard_summary()` from `utils/admin_analytics.py`

---

### 6.2 Merchant Insights

Returns detailed vendor/merchant analytics.

**Endpoint:** `GET /api/admin/metrics/merchants`

**Authentication:** Required (JWT)

**Query Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | 10 | Max results per category |

**Success Response (200):**
```json
{
    "message": "Merchant insights retrieved",
    "data": {
        "top_by_volume": [
            {
                "vendor_id": 1,
                "vendor_name": "Coffee Shop",
                "business_name": "Java House",
                "transaction_amount": 250000,
                "transaction_count": 500
            }
        ],
        "top_by_success": [
            {
                "vendor_id": 2,
                "vendor_name": "Grocery Store",
                "success_count": 480,
                "total_transactions": 500,
                "success_rate": 96.0
            }
        ],
        "total_merchants": 45
    }
}
```

**Related Utilities:**
- `get_top_vendors_by_transaction_count_amount()`
- `get_vendors_by_success_rate()`
- `get_active_vendors()`

---

### 6.3 User Insights

Returns detailed user analytics.

**Endpoint:** `GET /api/admin/metrics/users`

**Authentication:** Required (JWT)

**Query Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `days` | 30 | Analysis period |
| `limit` | 10 | Max results |

**Success Response (200):**
```json
{
    "message": "User insights retrieved",
    "data": {
        "growth_chart": [
            {"date": "2025-02-01", "new_users": 5},
            {"date": "2025-02-02", "new_users": 8}
        ],
        "top_by_activity": [...],
        "top_by_spending": [...],
        "total_users": 150
    }
}
```

**Related Utilities:**
- `get_user_growth_over_time()`
- `get_top_users_by_transaction_count()`
- `get_top_users_by_spending()`
- `get_total_users()`

---

## 7. Data Models

### 7.1 User Model

Consumer/customer who makes payments.

```python
User {
    id: Integer (PK)
    name: String(100)
    phone_number: String(20) - UNIQUE
    email: String(120) - UNIQUE
    password_hash: String(256)
    created_at: DateTime
    updated_at: DateTime
    is_active: Boolean (default: True)
}
```

**Relationships:**
- `transactions` → Transaction (one-to-many)
- `payment_sessions` → PaymentSession (one-to-many)
- `scan_logs` → ScanLog (one-to-many)

---

### 7.2 Vendor Model

Merchant who receives payments.

```python
Vendor {
    id: Integer (PK)
    name: String(100)
    business_name: String(150) - optional
    business_shortcode: String(20) - UNIQUE (Till/Paybill/Pochi)
    merchant_id: String(100) - CBK/PSP routing
    mcc: String(8) - Merchant Category Code
    country_code: String(2) - default: "KE"
    currency_code: String(3) - default: "404" (KES)
    store_label: String(50) - Store location
    email: String(120) - UNIQUE
    phone: String(20) - UNIQUE
    password_hash: String(256)
    psp_id: String(100) - Payment Service Provider ID
    psp_name: String(150) - PSP name
    created_at: DateTime
    updated_at: DateTime
    is_active: Boolean (default: True)
}
```

**Methods:**
- `get_display_name()` → Returns `business_name` or falls back to `name`
- `get_category()` → Returns category from MCC code via `mcc_categories.json`

**Relationships:**
- `transactions` → Transaction (one-to-many)
- `qr_code` → QRCode (one-to-one)

---

### 7.3 Transaction Model

Payment transaction record.

```python
Transaction {
    id: Integer (PK)
    amount: Integer
    currency: String(3) - default: "404"
    type: TransactionType - INCOMING|OUTGOING
    status: TransactionStatus - PENDING|SUCCESS|FAILED|CANCELLED
    outflow_reason: OutflowReason - nullable (for OUTGOING only)
    mpesa_receipt: String(150) - indexed
    phone: String(20) - payer phone
    callback_response: JSON - full Daraja callback
    initated_at: DateTime
    completed_at: DateTime
    user_id: Integer (FK → users) - nullable
    vendor_id: Integer (FK → vendors) - nullable
    qrcode_id: Integer (FK → qr_codes) - nullable
}
```

**Enums:**

```python
TransactionStatus = PENDING | SUCCESS | FAILED | CANCELLED

TransactionType = INCOMING | OUTGOING

OutflowReason = REFUND | TRANSFER | PAYOUT | SETTLEMENT | PLATFORM_FEE | ADJUSTMENT
```

---

### 7.4 QRCode Model

QR code record for payments.

```python
QRCode {
    id: Integer (PK)
    payload_data: Text - EMVCo encoded string
    payload_json: JSON - parsed payload data
    qr_type: QR_Type - STATIC|DYNAMIC
    status: QRStatus - ACTIVE|INACTIVE|EXPIRED
    created_at: DateTime
    vendor_id: Integer (FK → vendors)
    currency_code: String(3) - default: "404"
    reference_number: String(50) - nullable
    last_scanned_at: DateTime
}
```

**Relationships:**
- `vendor` → Vendor (many-to-one)
- `transactions` → Transaction (one-to-many)
- `scan_logs` → ScanLog (one-to-many)
- `payment_sessions` → PaymentSession (one-to-many)

---

### 7.5 ScanLog Model

Logs QR code scan events.

```python
ScanLog {
    id: Integer (PK)
    status: ScanStatus
    timestamp: DateTime
    qr_id: Integer (FK → qr_codes)
    user_id: Integer (FK → users)
}
```

**ScanStatus Enum:**
- `SCANNED_ONLY` - QR scanned but no payment
- `PAYMENT_INITIATED` - Payment started
- `PAYMENT_SUCCESS` - Payment completed
- `PAYMENT_FAILED` - Payment failed

---

### 7.6 PaymentSession Model

Tracks payment session lifecycle.

```python
PaymentSession {
    id: Integer (PK)
    amount: Integer
    status: PaymentStatus
    started_at: DateTime
    expired_at: DateTime
    qr_id: Integer (FK → qr_codes)
    user_id: Integer (FK → users)
    transaction_id: Integer (FK → transactions) - nullable
}
```

**PaymentStatus Enum:**
- `PAYMENT_INITIATED` - Session started
- `PAYMENT_PENDING` - Awaiting confirmation
- `PAYMENT_EXPIRED` - Session timed out

---

## 8. Utility Components

### 8.1 QR Utils (`utils/qr_utils.py`)

CBK-compliant QR code generator following EMVCo format.

**Class:** `QR_utils`

**Key Methods:**

| Method | Description |
|--------|-------------|
| `generate_merchant_qr()` | Static QR without amount (customer enters) |
| `generate_fixed_amount_qr()` | Static QR with fixed amount |
| `generate_transaction_qr()` | Dynamic QR for specific transaction |
| `calculate_crc()` | CRC-16-CCITT checksum (static) |
| `validate_crc()` | Verify payload checksum (static) |
| `parse_payload()` | Extract fields from EMVCo string (static) |

**Payload Fields:**
| Field ID | Description |
|----------|-------------|
| 00 | Payload format indicator |
| 01 | Point of initiation |
| 02 | Business shortcode |
| 52 | MCC (Merchant Category Code) |
| 53 | Currency code (404 = KES) |
| 54 | Amount |
| 58 | Country code (KE) |
| 59 | Merchant name |
| 60 | Store label |
| 61 | Postal code |
| 62 | Reference number |
| 63 | CRC checksum |

---

### 8.2 Daraja Service (`utils/daraja_service.py`)

M-Pesa/Safaricom STK Push integration.

**Class:** `DarajaService`

**Key Methods:**

| Method | Description |
|--------|-------------|
| `initiate_stk_push()` | Send STK push to customer phone |
| `query_transaction_status()` | Check payment status |
| `_get_access_token()` | OAuth2 token management |
| `_get_password()` | Generate M-Pesa password |

**Transaction Types:**
```python
TransactionType.BILL_PAYMENT    # CustomerPayBillOnline
TransactionType.BUY_GOODS       # CustomerBuyGoodsOnline
```

**Environment Variables:**
```
DARAJA_CONSUMER_KEY
DARAJA_CONSUMER_SECRET
DARAJA_BASE_URL
DARAJA_SHORTCODE
DARAJA_PASSKEY
DARAJA_CALLBACK_URL
```

---

### 8.3 Mock M-Pesa Service (`utils/mpese_mock.py`)

Development/testing fallback for M-Pesa integration.

**Class:** `MockMpesaService`

**Methods:**
- `initiate_stk_push()` - Simulates STK push response
- `simulate_callback()` - Generates test callback data

---

### 8.4 User Analytics (`utils/user_analytics_utils.py`)

Spending analytics for consumers.

**Functions:**
| Function | Description |
|----------|-------------|
| `get_user_spending_summary()` | Total spent, count, average |
| `get_user_top_merchants()` | Favorite vendors by amount/frequency |
| `get_user_daily_trends_by_weekday()` | Weekday spending patterns |
| `get_user_spending_trends()` | Monthly trends with direction |
| `get_user_largest_transactions()` | Biggest payments |
| `get_user_weekly_spending()` | Week-by-week breakdown |
| `get_user_spending_insights()` | AI-generated insights |

---

### 8.5 Vendor Analytics (`utils/vendor_analytics_utils.py`)

Business analytics for merchants.

**Functions:**
| Function | Description |
|----------|-------------|
| `get_vendor_cash_flow()` | Incoming vs outgoing breakdown |
| `get_vendor_net_flow()` | Net revenue calculation |
| `get_vendor_top_customers()` | Best customers |
| `get_vendor_largest_transactions()` | Biggest received payments |
| `get_vendor_outflow_breakdown()` | Refunds, fees, etc. |
| `get_vendor_spending_ratio()` | Retention percentage |
| `get_vendor_weekly_performance()` | Week-by-week analysis |
| `get_cumulative_total()` | All-time totals |
| `get_monthly_trends()` | Monthly breakdown |
| `get_best_worst_days()` | Top/bottom performing days |
| `get_kpis()` | Key performance indicators |
| `get_hourly_distribution()` | Peak hours analysis |
| `get_transaction_status_breakdown()` | Success/fail rates |

---

### 8.6 Admin Analytics (`utils/admin_analytics.py`)

Platform-wide analytics for administrators.

**Functions:**
| Function | Description |
|----------|-------------|
| `get_admin_dashboard_summary()` | Complete platform overview |
| `get_active_vendors()` | Total vendor count |
| `get_top_vendors_by_transaction_count_amount()` | Top merchants |
| `get_vendors_by_success_rate()` | Reliability rankings |
| `get_user_growth_over_time()` | User signups chart |
| `get_total_users()` | Total user count |
| `get_top_users_by_transaction_count()` | Most active users |
| `get_top_users_by_spending()` | Highest spenders |

---

## 9. Error Handling

### Standard Error Response Format

```json
{
    "error": "Error Type",
    "message": "Human-readable description",
    "details": "Technical details (dev mode only)"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Success |
| 201 | Created | Resource created |
| 400 | Bad Request | Missing/invalid fields |
| 401 | Unauthorized | Invalid credentials |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Duplicate entry |
| 500 | Server Error | Internal failure |

---

## 10. Configuration

### 10.1 Database Configuration (`config.py`)

```python
class DatabaseConfigs:
    SQLALCHEMY_DATABASE_URL = "postgresql://user:pass@host:port/db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
```

### 10.2 JWT Configuration

```python
class JWTConfig:
    JWT_SECRET_KEY = "your-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES = 3600        # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = 2592000    # 30 days
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
```

### 10.3 Daraja API Configuration

```python
class DarajaAPIConfigs:
    DARAJA_CONSUMER_KEY = "..."
    DARAJA_CONSUMER_SECRET = "..."
    DARAJA_BASE_URL = "https://sandbox.safaricom.co.ke"
    DARAJA_SHORTCODE = "..."
    DARAJA_PASSKEY = "..."
    DARAJA_CALLBACK_URL = "https://yourdomain.com/confirm"
```

### 10.4 Environment Variables (`.env`)

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/qr_payment_db

# Flask
SECRET_KEY=your-flask-secret
DEBUG=True

# JWT
JWT_SECRET_KEY=your-jwt-secret

# Daraja
DARAJA_CONSUMER_KEY=your-consumer-key
DARAJA_CONSUMER_SECRET=your-consumer-secret
DARAJA_SHORTCODE=123456
DARAJA_PASSKEY=your-passkey
DARAJA_CALLBACK_URL=https://your-public-url.com/api/payment/confirm
```

---

## API Route Summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| **Authentication** |
| POST | `/api/auth/register/user` | No | Register new user |
| POST | `/api/auth/register/vendor` | No | Register new vendor |
| POST | `/api/auth/login` | No | Login (user/vendor) |
| POST | `/api/auth/logout` | JWT | Logout |
| **User** |
| GET | `/api/user/profile` | JWT | Get profile |
| PUT | `/api/user/profile` | JWT | Update profile |
| PUT | `/api/user/password` | JWT | Change password |
| GET | `/api/user/transactions` | JWT | List transactions |
| GET | `/api/user/transactions/{id}` | JWT | Get transaction |
| GET | `/api/user/analytics` | JWT | Get analytics |
| **Vendor** |
| GET | `/api/merchant/profile` | JWT | Get profile |
| PUT | `/api/merchant/profile` | JWT | Update profile |
| PUT | `/api/merchant/password` | JWT | Change password |
| GET | `/api/merchant/transactions` | JWT | List transactions |
| GET | `/api/merchant/transactions/{id}` | JWT | Get transaction |
| GET | `/api/merchant/analytics` | JWT | Get analytics |
| **QR Code** |
| POST | `/api/qr/generate` | JWT | Generate QR code |
| POST | `/api/qr/scan` | JWT | Scan QR code |
| POST | `/api/qr/validate` | JWT | Validate QR code |
| **Payment** |
| POST | `/api/payment/initiate` | JWT | Start payment |
| POST | `/api/payment/confirm` | No | Daraja callback |
| GET | `/api/payment/{id}/status` | JWT | Check status |
| GET | `/api/payment/ping` | No | Health check |
| **Admin** |
| GET | `/api/admin/metrics/overview` | JWT | Dashboard |
| GET | `/api/admin/metrics/merchants` | JWT | Merchant stats |
| GET | `/api/admin/metrics/users` | JWT | User stats |

---

## System Architecture Diagram

```
┌─────────────────┐     ┌─────────────────┐
│   Mobile App    │     │   POS System    │
│  (User/Vendor)  │     │   (Vendor)      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Flask API Server    │
         │                       │
         │  ┌─────────────────┐  │
         │  │  Auth Routes    │  │
         │  ├─────────────────┤  │
         │  │  User Routes    │  │
         │  ├─────────────────┤  │
         │  │  Vendor Routes  │  │
         │  ├─────────────────┤  │
         │  │  QR Routes      │  │
         │  ├─────────────────┤  │
         │  │  Payment Routes │  │
         │  ├─────────────────┤  │
         │  │  Admin Routes   │  │
         │  └─────────────────┘  │
         │           │           │
         │  ┌────────┴────────┐  │
         │  │     Utils       │  │
         │  │  - qr_utils     │  │
         │  │  - daraja       │  │
         │  │  - analytics    │  │
         │  └─────────────────┘  │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │     │   M-Pesa API    │
│   (Database)    │     │   (Daraja)      │
└─────────────────┘     └─────────────────┘
```

---

## Payment Flow Sequence

```
User                    QR-Pay API              Daraja/M-Pesa
  │                         │                         │
  │ 1. Scan QR Code         │                         │
  │────────────────────────>│                         │
  │                         │                         │
  │ 2. Return vendor info   │                         │
  │<────────────────────────│                         │
  │                         │                         │
  │ 3. Initiate payment     │                         │
  │────────────────────────>│                         │
  │                         │ 4. STK Push             │
  │                         │────────────────────────>│
  │                         │                         │
  │                         │ 5. Push to user phone   │
  │<──────────────────────────────────────────────────│
  │                         │                         │
  │ 6. Enter PIN            │                         │
  │──────────────────────────────────────────────────>│
  │                         │                         │
  │                         │ 7. Callback             │
  │                         │<────────────────────────│
  │                         │                         │
  │ 8. Payment confirmed    │                         │
  │<────────────────────────│                         │
```

---

*Documentation generated on February 28, 2025*
*QR-Pay-System v1.0*
