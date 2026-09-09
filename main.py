"""Main FastAPI Application Entrypoint."""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pdf.email_sender import load_dotenv_if_exists

load_dotenv_if_exists()

from api.routes import router as pdf_router, jpeg_router

app = FastAPI(

    title="High-Fidelity Automated PDF & JPEG Text-Field Editor",
    description="Deterministic PDF and JPEG text editor that preserves all non-target content, images, logos, and layout geometry.",
    version="1.0.0"
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches uncaught exceptions and returns diagnostic JSON instead of blank 500 crashes."""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "details": str(exc), "type": type(exc).__name__}
    )


# Include API routes
app.include_router(pdf_router)
app.include_router(jpeg_router)

# Mount static web UI files
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
@app.get("/pdf")
@app.get("/pdf-editor")
@app.get("/jpeg")
@app.get("/jpeg-editor")
async def root():
    """Serves the primary web interface using HTMLResponse for serverless compatibility."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(content=content)
        except Exception:
            pass
    return {"message": "PDF & JPEG Text-Field Editor API is online. Access /docs for API documentation."}



if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
