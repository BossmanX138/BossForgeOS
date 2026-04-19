# Onboarding Endpoints

- Live onboarding endpoints detected in Control Hall API.
- Extension onboarding wizard is wired to these routes:
  - `POST /api/onboarding` with `{ "step": "workspace_check" | "security_baseline" | "model_gateway" }`
  - `GET /api/onboarding/status`
- Default base URL is `http://127.0.0.1:5005` (override with `BOSSFORGE_CONTROL_HALL_URL`).
