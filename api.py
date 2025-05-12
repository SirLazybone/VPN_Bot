from fastapi import FastAPI
from bot.handlers.payment import router as payment_router

app = FastAPI(title="VPN Bot API")
app.include_router(payment_router, prefix="/webhook")

# Подключаем роутер для платежей
# app.include_router(payment_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)