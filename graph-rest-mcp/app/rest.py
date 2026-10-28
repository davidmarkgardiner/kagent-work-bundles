import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn

from app.models import ContextRequest, ContextResponse
from app.retrieval import retrieve


app = FastAPI(title="Synthetic graph context", version="1.0.0", description="Bounded metadata retrieval. No SQL or write operations.")


@app.middleware("http")
async def bound_request(request: Request, call_next):
    if request.method == "POST":
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 4096):
            return JSONResponse({"error_category": "request_oversize"}, status_code=413)
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 4096:
                return JSONResponse({"error_category": "request_oversize"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    return JSONResponse({"error_category": "invalid_request"}, status_code=422)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/get-context", response_model=ContextResponse)
def get_context(request: ContextRequest):
    try:
        result = retrieve(request)
        if len(result.model_dump_json().encode()) > 32768:
            return JSONResponse({"error_category": "result_oversize"}, status_code=502)
        return result
    except Exception:
        return JSONResponse({"error_category": "retrieval_unavailable"}, status_code=503)


if __name__ == "__main__":
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    uvicorn.run(app, host="0.0.0.0", port=8001, access_log=False, log_level="critical")
