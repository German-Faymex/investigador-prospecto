"""HTTP client with TLS fingerprint impersonation for LinkedIn profile fetching.

Uses curl_cffi to impersonate real browser TLS signatures, bypassing
LinkedIn's authwall that blocks plain httpx/requests.

Adapted from Super Scraper's network layer.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field

from curl_cffi import requests as curl_requests


@dataclass
class TLSProfile:
    """Browser TLS profile with consistent headers."""
    name: str
    impersonate: str  # curl_cffi target (e.g. "chrome131")
    user_agent: str
    sec_ch_ua: str
    sec_ch_ua_platform: str
    sec_ch_ua_mobile: str = '"?0"'
    accept_language: str = "es-CL,es;q=0.9,en;q=0.8"
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    accept_encoding: str = "gzip, deflate, br, zstd"
    extra_headers: dict = field(default_factory=dict)

    def build_headers(self) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": self.accept,
            "Accept-Language": self.accept_language,
            "Accept-Encoding": self.accept_encoding,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        if self.sec_ch_ua:
            headers["Sec-CH-UA"] = self.sec_ch_ua
            headers["Sec-CH-UA-Mobile"] = self.sec_ch_ua_mobile
            headers["Sec-CH-UA-Platform"] = self.sec_ch_ua_platform
        headers.update(self.extra_headers)
        return headers


PROFILES: list[TLSProfile] = [
    TLSProfile(
        name="chrome_131_win",
        impersonate="chrome131",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        sec_ch_ua='"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    TLSProfile(
        name="chrome_136_win",
        impersonate="chrome136",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        sec_ch_ua='"Google Chrome";v="136", "Chromium";v="136", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"Windows"',
    ),
    TLSProfile(
        name="chrome_131_mac",
        impersonate="chrome131",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        sec_ch_ua='"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        sec_ch_ua_platform='"macOS"',
    ),
    TLSProfile(
        name="firefox_135_win",
        impersonate="firefox135",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        sec_ch_ua="",
        sec_ch_ua_platform="",
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    ),
    TLSProfile(
        name="safari_18_mac",
        impersonate="safari18_0",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        sec_ch_ua="",
        sec_ch_ua_platform="",
        accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        accept_encoding="gzip, deflate, br",
    ),
    TLSProfile(
        name="edge_101_win",
        impersonate="edge101",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.53",
        sec_ch_ua='"Microsoft Edge";v="101", "Chromium";v="101", "Not_A Brand";v="99"',
        sec_ch_ua_platform='"Windows"',
    ),
]


def get_random_profile() -> TLSProfile:
    return random.choice(PROFILES)


def _sync_fetch(url: str, profile: TLSProfile, timeout: int = 15) -> tuple[int, str]:
    """Synchronous fetch with TLS impersonation. Returns (status_code, html)."""
    headers = profile.build_headers()
    try:
        resp = curl_requests.get(
            url,
            headers=headers,
            impersonate=profile.impersonate,
            timeout=timeout,
            allow_redirects=True,
        )
        return resp.status_code, resp.text
    except Exception as e:
        print(f"[TLSClient] Error fetching {url}: {e}")
        return 0, ""


_last_profile_idx: int = -1


async def tls_fetch(url: str, timeout: int = 15) -> tuple[int, str]:
    """Async fetch with TLS fingerprint impersonation.

    Returns (status_code, html_text). Uses a rotating browser profile
    to bypass bot detection (LinkedIn authwall, CloudFlare, etc.).
    Each consecutive call uses a different profile to maximize bypass chance.
    """
    global _last_profile_idx
    _last_profile_idx = (_last_profile_idx + 1) % len(PROFILES)
    profile = PROFILES[_last_profile_idx]
    return await asyncio.to_thread(_sync_fetch, url, profile, timeout)
