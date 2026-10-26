import uvicorn

from settings import settings


def start_server():
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=settings.dev_reload, workers=1)
