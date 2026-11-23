# Orderly frontend

Frontend-only React 18 application using Vite, Tailwind CSS, React Router, Axios, Recharts, and Lucide React. No backend code or business datasets are included in this project.

## Run locally

```powershell
cd .\frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev
```

Set `VITE_API_BASE_URL` to the backend origin (default: `http://localhost:8000`, without an `/api` suffix). Configure the backend's allowed CORS origins to include the Vite origin and allow credentials for the HttpOnly refresh cookie. The frontend does not contain Domo credentials.

Build and preview:

```powershell
npm.cmd run build
npm.cmd run preview
```

## Backend contract

The route paths, request fields, response structures, authentication behavior, and unimplemented navigation sections are documented in [API_INTEGRATION_REFERENCE.md](./API_INTEGRATION_REFERENCE.md). A subset of routes has been exercised against the local backend; integration gaps and untested behavior are listed in [FRONTEND_BACKEND_INTEGRATION_TEST_REPORT.md](./FRONTEND_BACKEND_INTEGRATION_TEST_REPORT.md).

## Sample data

Only the order-trend chart uses mock data because the backend has no trend endpoint. `src/data/mockOrders.js` contains clearly labeled fallback records used only when the order endpoint cannot be reached; these examples are not business data and include no inferred shipment or production relationships. Dashboard metrics and assistant responses are never replaced with successful-looking mock responses.
