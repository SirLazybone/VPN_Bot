import httpx
from typing import Optional, Dict, Any, List, Union
from config.config import API_TOKEN, API_URL
from datetime import datetime, timedelta

class VPNClient:
    def __init__(self):
        self.api_token = API_TOKEN
        self.base_url = API_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    async def create_vpn_config(
        self, 
        username: str,
        data_limit: int = 0,
        expire_days: int = 30,
        inbounds: Optional[Dict[str, List[str]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new VPN configuration for a user
        
        Args:
            username: Username for the VPN account
            data_limit: Data limit in bytes (0 for unlimited)
            expire_days: Number of days until expiration
            inbounds: Dictionary of inbounds to enable
        """

        expire_timestamp = int((datetime.now() + timedelta(days=expire_days)).timestamp())
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/user",
                    headers=self.headers,
                    json={
                        "username": username,
                        "data_limit": data_limit,
                        "data_limit_reset_strategy": "no_reset",
                        "expire": expire_timestamp,
                        "inbounds": {
                            "vless": ["VLESS TCP REALITY"]
                        },
                        "next_plan": {
                            "add_remaining_traffic": False,
                            "data_limit": 0,
                            "expire": 0,
                            "fire_on_either": True
                        },
                        "note": "",
                        "on_hold_expire_duration": 0,
                        "on_hold_timeout": datetime.now().isoformat(),
                        "proxies": {
                            "vless": {
                                "id": self._generate_uuid()
                            }
                        },
                        "status": "active"
                    }
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            print(f"Error creating VPN config: {e}")
            return None

    async def get_vpn_config(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get existing VPN configuration for a user
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            print(f"Error getting VPN config: {e}")
            return None

    def _generate_uuid(self) -> str:
        """Generate a UUID for VMess proxy"""
        import uuid
        return str(uuid.uuid4())

    async def update_vpn_config(
        self,
        username: str,
        status: Optional[str] = None,
        expire: Optional[int] = None,
        data_limit: Optional[int] = None,
        data_limit_reset_strategy: Optional[str] = None,
        proxies: Optional[Dict[str, Any]] = None,
        inbounds: Optional[Dict[str, List[str]]] = None,
        note: Optional[str] = None,
        on_hold_timeout: Optional[str] = None,
        on_hold_expire_duration: Optional[int] = None,
        next_plan: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing VPN user configuration
        
        Args:
            username: Username of the user to update
            status: New status ('active', 'disabled', 'on_hold', 'limited', 'expired')
            expire: UTC timestamp for new expiration (0 for unlimited)
            data_limit: New data limit in bytes (0 for unlimited)
            data_limit_reset_strategy: New reset strategy ('daily', 'weekly', 'monthly', 'no_reset')
            proxies: New protocol settings
            inbounds: New protocol tags for inbound connections
            note: New note text
            on_hold_timeout: UTC timestamp for on_hold status
            on_hold_expire_duration: Duration in seconds for on_hold status
            next_plan: Next user plan settings
        """
        update_data = {}
        
        if status is not None:
            update_data["status"] = status
        if expire is not None:
            update_data["expire"] = expire
        if data_limit is not None:
            update_data["data_limit"] = data_limit
        if data_limit_reset_strategy is not None:
            update_data["data_limit_reset_strategy"] = data_limit_reset_strategy
        if proxies is not None:
            update_data["proxies"] = proxies
        if inbounds is not None:
            update_data["inbounds"] = inbounds
        if note is not None:
            update_data["note"] = note
        if on_hold_timeout is not None:
            update_data["on_hold_timeout"] = on_hold_timeout
        if on_hold_expire_duration is not None:
            update_data["on_hold_expire_duration"] = on_hold_expire_duration
        if next_plan is not None:
            update_data["next_plan"] = next_plan

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.headers,
                    json=update_data
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            print(f"Error updating VPN config: {e}")
            return None

    # async def activate_user(self, username: str) -> Optional[Dict[str, Any]]:
    #     """
    #     Convenience method to activate a user
    #     """
    #     return await self.update_vpn_config(
    #         username=username,
    #         status="active",
    #         expire=30
    #     )

    async def delete_user(self, username: str):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    url=f"{self.base_url}/api/user/{username}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.status_code
        except httpx.HTTPError as e:
            print(f"Error deleting VPN config: {e}")
            return None
