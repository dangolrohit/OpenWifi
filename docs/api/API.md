# WiFiRouter V2 API Documentation

Base URL: `http://192.168.16.2:8090/api/v1`

## Authentication

- `POST /auth/login`
  - Body: `{"username": "admin", "password": "..."}`
  - Response: Sets `oshin_session` HttpOnly cookie. Returns `{ ok, token, csrf_token, user }`.
- `POST /auth/logout`
  - Headers: `X-CSRF-Token: <token>`
  - Revokes active session.
- `GET /auth/me`
  - Returns current user profile and session token.
- `POST /auth/change-password`
  - Body: `{"current_password": "...", "new_password": "..."}`

## Dashboard

- `GET /dashboard/summary`
  - Returns aggregated telemetry (bandwidth, Wi-Fi status, health, device counters).

## Devices

- `GET /devices`
  - Returns array of discovered devices with nicknames, groups, QoS limits, and schedules.
- `PUT /devices/{ip}`
  - Updates nickname, group (`family`, `customer`, `staff`, `default`), speed limit, or curfew schedule.
- `POST /devices/{ip}/block`
  - Body: `{"blocked": true|false}`

## Bandwidth & QoS

- `GET /bandwidth/live`
  - Returns real-time RX/TX rates and cumulative bytes on `enp1s0`.
- `POST /bandwidth/shape`
  - Body: `{"ip": "192.168.16.105", "speed_limit_mbps": 5}`

## Guests & Hotspot

- `GET /guests/plans`
  - Lists all 5 hotspot access plans.
- `PUT /guests/plans`
  - Updates duration, speed limit, description, or active status.
- `GET /guests/vouchers`
  - Lists generated access vouchers.
- `POST /guests/vouchers`
  - Body: `{"plan_id": "standard", "code": "123456"}`
- `DELETE /guests/vouchers/{code}`
  - Deletes an unused voucher.
- `GET /guests/sessions`
  - Lists active guest sessions with expiration timestamps.
- `POST /guests/sessions/extend`
  - Body: `{"ip": "192.168.16.105", "minutes": 30}`
- `POST /guests/sessions/revoke`
  - Body: `{"ip": "192.168.16.105"}`

## Public Hotspot Endpoints

- `GET /guests/status`
  - Returns authorization status of requesting client IP.
- `POST /guests/connect`
  - Body: `{"plan_id": "starter"}` or `{"voucher": "123456"}`

