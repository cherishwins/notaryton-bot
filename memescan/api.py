"""
API clients for DEX and blockchain data.
"""
import asyncio
import aiohttp
from typing import Optional
from datetime import datetime
import os

from .models import Token, Pool, WhaleMovement, SafetyLevel


class StonFiAPI:
    """STON.fi DEX API client - NO RATE LIMITS!"""

    BASE_URL = "https://api.ston.fi"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._asset_cache: dict[str, dict] = {}  # address -> asset info

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_assets(self, limit: int = 100) -> list[dict]:
        """Get all listed assets."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/v1/assets") as resp:
            if resp.status == 200:
                data = await resp.json()
                assets = data.get("asset_list", [])[:limit]
                # Cache for symbol lookups
                for asset in assets:
                    addr = asset.get("contract_address", "")
                    if addr:
                        self._asset_cache[addr] = asset
                return assets
            return []

    async def _ensure_asset_cache(self):
        """Load assets into cache if empty."""
        if not self._asset_cache:
            await self.get_assets(limit=500)

    def _get_symbol(self, address: str) -> str:
        """Get symbol for an address from cache."""
        asset = self._asset_cache.get(address, {})
        return asset.get("symbol", "?")

    async def get_pools(self, limit: int = 100) -> list[dict]:
        """Get all liquidity pools."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/v1/pools") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("pool_list", [])[:limit]
            return []

    async def get_pool(self, pool_address: str) -> Optional[dict]:
        """Get specific pool details."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/v1/pools/{pool_address}") as resp:
            if resp.status == 200:
                return await resp.json()
            return None

    async def get_dex_stats(self) -> dict:
        """Get overall DEX statistics."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/v1/stats/dex") as resp:
            if resp.status == 200:
                return await resp.json()
            return {}

    async def get_trending_pools(self, limit: int = 10) -> list[Pool]:
        """Get top pools by volume."""
        # Ensure we have asset symbols cached
        await self._ensure_asset_cache()

        pools_raw = await self.get_pools(limit=200)

        # Sort by volume (24h volume is better than TVL for trending)
        sorted_pools = sorted(
            pools_raw,
            key=lambda p: float(p.get("volume_24h_usd", 0) or 0),
            reverse=True
        )[:limit]

        pools = []
        for p in sorted_pools:
            try:
                token0_addr = p.get("token0_address", "")
                token1_addr = p.get("token1_address", "")

                pools.append(Pool(
                    address=p.get("address", ""),
                    dex="stonfi",
                    token0_address=token0_addr,
                    token0_symbol=self._get_symbol(token0_addr),
                    token1_address=token1_addr,
                    token1_symbol=self._get_symbol(token1_addr),
                    liquidity_usd=float(p.get("lp_total_supply_usd", 0) or 0),
                    volume_24h=float(p.get("volume_24h_usd", 0) or 0),
                ))
            except (ValueError, KeyError):
                continue

        return pools


class TonAPI:
    """TonAPI client for blockchain data."""

    BASE_URL = "https://tonapi.io/v2"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("TONAPI_KEY", "")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_jettons(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get list of jettons (tokens)."""
        session = await self._get_session()
        params = {"limit": limit, "offset": offset}
        async with session.get(f"{self.BASE_URL}/jettons", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("jettons", [])
            return []

    async def get_jetton_info(self, address: str) -> Optional[dict]:
        """Get specific jetton details."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/jettons/{address}") as resp:
            if resp.status == 200:
                return await resp.json()
            return None

    async def get_jetton_holders(self, address: str, limit: int = 100) -> list[dict]:
        """Get jetton holders."""
        session = await self._get_session()
        params = {"limit": limit}
        async with session.get(
            f"{self.BASE_URL}/jettons/{address}/holders",
            params=params
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("addresses", [])
            return []

    async def get_account_jettons(self, account: str) -> list[dict]:
        """Get all jettons held by an account (whale tracking)."""
        session = await self._get_session()
        async with session.get(f"{self.BASE_URL}/accounts/{account}/jettons") as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("balances", [])
            return []

    async def get_account_events(
        self,
        account: str,
        limit: int = 20
    ) -> list[dict]:
        """Get account events (transactions)."""
        session = await self._get_session()
        params = {"limit": limit}
        async with session.get(
            f"{self.BASE_URL}/accounts/{account}/events",
            params=params
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("events", [])
            return []


class GeckoTerminalAPI:
    """GeckoTerminal API - 30 calls/min free tier."""

    BASE_URL = "https://api.geckoterminal.com/api/v2"
    NETWORK = "ton"

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_call = 0
        self._min_interval = 2.0  # 30 calls/min = 2s between calls

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _rate_limit(self):
        """Respect rate limits."""
        import time
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_trending_pools(self, limit: int = 10) -> list[dict]:
        """Get trending pools on TON."""
        await self._rate_limit()
        session = await self._get_session()
        async with session.get(
            f"{self.BASE_URL}/networks/{self.NETWORK}/trending_pools"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])[:limit]
            return []

    async def get_new_pools(self, limit: int = 10) -> list[dict]:
        """Get newly created pools."""
        await self._rate_limit()
        session = await self._get_session()
        async with session.get(
            f"{self.BASE_URL}/networks/{self.NETWORK}/new_pools"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])[:limit]
            return []

    async def get_pool(self, pool_address: str) -> Optional[dict]:
        """Get specific pool details."""
        await self._rate_limit()
        session = await self._get_session()
        async with session.get(
            f"{self.BASE_URL}/networks/{self.NETWORK}/pools/{pool_address}"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data")
            return None

    async def get_token(self, token_address: str) -> Optional[dict]:
        """Get token details."""
        await self._rate_limit()
        session = await self._get_session()
        async with session.get(
            f"{self.BASE_URL}/networks/{self.NETWORK}/tokens/{token_address}"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data")
            return None

    async def get_top_pools(self, limit: int = 10) -> list[dict]:
        """Get top pools by liquidity."""
        await self._rate_limit()
        session = await self._get_session()
        async with session.get(
            f"{self.BASE_URL}/networks/{self.NETWORK}/pools",
            params={"page": 1}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("data", [])[:limit]
            return []


class MemeScanClient:
    """
    Unified client that combines all data sources.
    The main interface for the scanner.
    """

    def __init__(self, tonapi_key: str = ""):
        self.stonfi = StonFiAPI()
        self.tonapi = TonAPI(api_key=tonapi_key)
        self.gecko = GeckoTerminalAPI()

    async def close(self):
        await asyncio.gather(
            self.stonfi.close(),
            self.tonapi.close(),
            self.gecko.close()
        )

    async def get_trending(self, limit: int = 10) -> list[Token]:
        """Get trending meme coins from multiple sources."""
        # Fetch from GeckoTerminal (best for trending)
        gecko_pools = await self.gecko.get_trending_pools(limit=limit)

        tokens = []
        for pool in gecko_pools:
            attrs = pool.get("attributes", {})
            try:
                # Extract token data
                token = Token(
                    address=attrs.get("address", ""),
                    symbol=attrs.get("name", "?").split("/")[0].strip(),
                    name=attrs.get("name", "Unknown"),
                    price_usd=float(attrs.get("base_token_price_usd", 0) or 0),
                    price_change_24h=float(attrs.get("price_change_percentage", {}).get("h24", 0) or 0),
                    liquidity_usd=float(attrs.get("reserve_in_usd", 0) or 0),
                    volume_24h_usd=float(attrs.get("volume_usd", {}).get("h24", 0) or 0),
                )
                tokens.append(token)
            except (ValueError, KeyError, TypeError):
                continue

        return tokens

    async def get_new_launches(self, limit: int = 10) -> list[Token]:
        """Get newly launched tokens."""
        gecko_pools = await self.gecko.get_new_pools(limit=limit)

        tokens = []
        for pool in gecko_pools:
            attrs = pool.get("attributes", {})
            try:
                created_str = attrs.get("pool_created_at", "")
                created_at = None
                if created_str:
                    try:
                        created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    except:
                        pass

                token = Token(
                    address=attrs.get("address", ""),
                    symbol=attrs.get("name", "?").split("/")[0].strip(),
                    name=attrs.get("name", "Unknown"),
                    price_usd=float(attrs.get("base_token_price_usd", 0) or 0),
                    liquidity_usd=float(attrs.get("reserve_in_usd", 0) or 0),
                    created_at=created_at,
                )
                tokens.append(token)
            except (ValueError, KeyError, TypeError):
                continue

        return tokens

    async def analyze_token_safety(self, token_address: str) -> Token:
        """Analyze a token for safety (rug risk)."""
        # Get holder distribution from TonAPI
        holders = await self.tonapi.get_jetton_holders(token_address, limit=20)
        jetton_info = await self.tonapi.get_jetton_info(token_address)

        warnings = []
        safety_level = SafetyLevel.SAFE
        dev_percent = 0

        if jetton_info:
            total_supply = float(jetton_info.get("total_supply", 0) or 0)

            # Check top holder concentration
            if holders and total_supply > 0:
                top_holder_balance = float(holders[0].get("balance", 0) or 0)
                dev_percent = (top_holder_balance / total_supply) * 100

                if dev_percent > 50:
                    warnings.append(f"🚨 Top wallet holds {dev_percent:.0f}%")
                    safety_level = SafetyLevel.DANGER
                elif dev_percent > 20:
                    warnings.append(f"⚠️ Top wallet holds {dev_percent:.0f}%")
                    safety_level = SafetyLevel.WARNING

            # Check holder count
            holder_count = len(holders)
            if holder_count < 10:
                warnings.append(f"⚠️ Only {holder_count} holders")
                if safety_level == SafetyLevel.SAFE:
                    safety_level = SafetyLevel.WARNING

            metadata = jetton_info.get("metadata", {})

            return Token(
                address=token_address,
                symbol=metadata.get("symbol", "?"),
                name=metadata.get("name", "Unknown"),
                decimals=int(metadata.get("decimals", 9)),
                total_supply=total_supply,
                holder_count=holder_count,
                safety_level=safety_level,
                safety_warnings=warnings,
                dev_wallet_percent=dev_percent,
            )

        return Token(
            address=token_address,
            symbol="?",
            name="Unknown",
            safety_level=SafetyLevel.UNKNOWN,
            safety_warnings=["Could not analyze token"],
        )
