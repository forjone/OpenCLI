# crosspost frontend

Vue3 + Vite + Element Plus.

## Dev

```bash
# Backend
cd ..
uvicorn web:app --reload --port 8000

# Frontend (in another shell)
npm install
npm run dev
# open http://localhost:5173
```

Vite proxies `/api/*` to the backend at `localhost:8000`.

## Production build

```bash
npm run build
# emits dist/, which can be served by any static host or by FastAPI itself
```
