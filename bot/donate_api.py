from config.config import WATA_JWT_TOKEN, WATA_DONATE_URL, VPN_PRICE, BOT_LINK
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import httpx
import uuid

class DonateApi:
    def __init__(self):
        self.jwt_token = WATA_JWT_TOKEN
        self.base_url = WATA_DONATE_URL
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.jwt_token}"
        }

    async def create_donate_url(self, payment_id: int, amount=VPN_PRICE) -> Optional[Dict[str, Any]]:
        """
        Создает ссылку для оплаты через WATA
        payment_id используется как orderId для связи с webhook
        """
        print(f'{self.jwt_token}')
        print(f'{self.headers}')
        expire = datetime.utcnow() + timedelta(days=1)
        print(f'{expire.isoformat()}')

        content = {
            'amount': amount,
            'currency': 'RUB',
            'orderId': str(payment_id),
            'successRedirectUrl': BOT_LINK,
            'expirationDateTime': expire.isoformat() + 'Z'  # ISO формат с UTC
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url=f'{self.base_url}/links',
                    headers=self.headers,
                    json=content
                )
                print(response.text)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            print(f"Error creating donate url: {e}")
            return None

    async def find_donate_url(self, wata_id: uuid) -> Optional[Dict[str, Any]]:
        """Получает информацию о ссылке для оплаты по ID"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url=f'{self.base_url}/links/{wata_id}',
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            print(f"Error getting donate url with id {wata_id}: {e}")
            return None
