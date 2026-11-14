"""Session HTTP avec reprises, et authentification NASA Earthdata (EDL) limitée aux hôtes NASA.

Ordre de recherche des identifiants Earthdata :
  1. EARTHDATA_TOKEN (jeton « bearer » généré sur urs.earthdata.nasa.gov → Generate Token)
  2. EARTHDATA_USERNAME + EARTHDATA_PASSWORD
  3. ~/.netrc ou ~/_netrc (machine urs.earthdata.nasa.gov)
Les variables peuvent être placées dans un fichier .env à la racine du projet (jamais versionné).
"""
from __future__ import annotations

import netrc
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from .. import config

# hôtes NASA qui acceptent le jeton Earthdata (GES DISC, LP DAAC cloud…). Jamais les URL S3/CloudFront
# pré-signées vers lesquelles ils redirigent : rebuild_auth retire alors l'en-tête.
EDL_HOSTS = ("urs.earthdata.nasa.gov", ".earthdata.nasa.gov", ".eosdis.nasa.gov", ".earthdatacloud.nasa.gov")
USER_AGENT = "agbea-climat-data/0.1 (NASA Space Apps 2026)"


def load_dotenv() -> None:
    env = config.ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _is_edl_host(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == h.lstrip(".") or host.endswith(h) for h in EDL_HOSTS)


class EarthdataSession(requests.Session):
    """N'envoie les identifiants qu'aux hôtes NASA, y compris après redirection."""

    def __init__(self):
        super().__init__()
        load_dotenv()
        self.headers["User-Agent"] = USER_AGENT
        self.token = os.environ.get("EARTHDATA_TOKEN")
        user, pwd = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
        if not (user and pwd):
            for name in (".netrc", "_netrc"):
                p = Path.home() / name
                if p.exists():
                    try:
                        a = netrc.netrc(p).authenticators("urs.earthdata.nasa.gov")
                    except (netrc.NetrcParseError, OSError):
                        a = None
                    if a:
                        user, pwd = a[0], a[2]
                        break
        self.basic = (user, pwd) if user and pwd else None

    @property
    def has_credentials(self) -> bool:
        return bool(self.token or self.basic)

    def rebuild_auth(self, prepared_request, response):
        # Comportement par défaut : on retire l'Authorization en changeant d'hôte…
        headers = prepared_request.headers
        if "Authorization" in headers and not _is_edl_host(prepared_request.url):
            del headers["Authorization"]
        # …et on la remet si le nouvel hôte est un hôte NASA.
        if _is_edl_host(prepared_request.url):
            self._apply(prepared_request)

    def _apply(self, req):
        if self.token:
            req.headers["Authorization"] = f"Bearer {self.token}"
        elif self.basic and (urlparse(req.url).hostname or "") == "urs.earthdata.nasa.gov":
            req.prepare_auth(self.basic)

    def request(self, method, url, **kw):
        if self.token and _is_edl_host(url):
            kw.setdefault("headers", {})["Authorization"] = f"Bearer {self.token}"
        return super().request(method, url, **kw)


def get_with_retry(session: requests.Session, url: str, *, retries: int | None = None,
                   timeout: int | None = None, **kw) -> requests.Response:
    net = config.settings()["network"]
    retries = net["retries"] if retries is None else retries
    timeout = net["timeout_s"] if timeout is None else timeout
    last = None
    for attempt in range(retries + 1):
        try:
            r = session.get(url, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
            last = e
            if attempt < retries:
                time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"Échec après {retries + 1} tentatives : {url}\n{last}")
