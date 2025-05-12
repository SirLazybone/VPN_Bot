from fastapi import FastAPI
from bot.handlers.payment import webhook_router

app = FastAPI(title="VPN Bot API")
app.include_router(webhook_router, prefix="/webhook")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
