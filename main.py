# main.py
import re
import time
import urllib.parse
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

APP = FastAPI()

# Kaynak sunucu başlıkları (Cloudstream'in kullandığına uyumlu)
UA = "googleusercontent"
REF = "https://twitter.com/"
EXPIRE = 24 * 60 * 60  # tms = şimdi + 1 gün

# ---- KANALLAR: senin verdiğin URL'ler ----
CHANNELS = {
    "history": "https://tv.prectv53.lol/live/history.m3u8?token=7yEyEAgA9cC2fGNU9stTPA&tms=1755970567",
    "bbc": "https://tv.prectv53.lol/live/bbc.m3u8?token=7yEyEAgA9cC2fGNU9stTPA&tms=1755970567",

    "bsturk": "https://tv.prectv53.lol/live/bsturk.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "bsfamily": "https://tv.prectv53.lol/live/bsfamily.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "bsstars": "https://tv.prectv53.lol/live/bsstars.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "bspremier1": "https://tv.prectv53.lol/live/bspremier1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "box1": "https://tv.prectv53.lol/live/box1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "box2": "https://tv.prectv53.lol/live/box2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "mvturk": "https://tv.prectv53.lol/live/mvturk.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "sinema2": "https://tv.prectv53.lol/live/sinema2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "sinema1002": "https://tv.prectv53.lol/live/sinema1002.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",

    "bm1": "https://tv.prectv53.lol/live/bm1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "bm2": "https://tv.prectv53.lol/live/bm2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "smart1": "https://tv.prectv53.lol/live/smart1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "smart2": "https://tv.prectv53.lol/live/smart2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "t1": "https://tv.prectv53.lol/live/t1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "t2": "https://tv.prectv53.lol/live/t2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
    "t3": "https://tv.prectv53.lol/live/t3.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",

    "bsseries1": "https://tv.prectv53.lol/live/bsseries1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
    "bsseries2": "https://tv.prectv53.lol/live/bsseries2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
}
# -------------------------------------------

def to_tpl(u: str) -> str:
    """URL'de tms sabitse {TMS} şablonuna çevirir."""
    if "{TMS}" in u:
        return u
    if "tms=" in u:
        return re.sub(r"([?&])tms=\d+", r"\1tms={TMS}", u)
    joiner = "&" if "?" in u else "?"
    return u + f"{joiner}tms={{TMS}}"

def with_tms(tpl: str) -> str:
    """{TMS} yerine şimdi+EXPIRE koyar."""
    return tpl.replace("{TMS}", str(int(time.time()) + EXPIRE))

# Tek bir AsyncClient, follow_redirects açık.
CLIENT = httpx.AsyncClient(follow_redirects=True, timeout=20.0)

def h_for(url: str, extra: Optional[dict] = None) -> dict:
    """Kaynağa giden isteklerde kullanılacak header seti."""
    o = urllib.parse.urlparse(url)
    headers = {
        "User-Agent": UA,
        "Referer": REF,
        "Origin": f"{o.scheme}://{o.netloc}",
        "Accept": "*/*",
        "Connection": "keep-alive",
        "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    }
    if extra:
        headers.update(extra)
    return headers

def rewrite_manifest(text: str, base_url: str, host_origin: str, cookie_str: str) -> str:
    """
    Manifest içindeki göreli/abs tüm medya URL'lerini kendi /relay endpoint'imize çevirir.
    Cookie gerekirse ck param'ıyla taşır.
    """
    out_lines = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            out_lines.append(line)
            continue
        # satır URL değilse (boşluk vs) olduğu gibi ekle
        parsed = urllib.parse.urlparse(line)
        abs_url = line if parsed.scheme else urllib.parse.urljoin(base_url, line)

        proxied = f"{host_origin}/relay?u={urllib.parse.quote(abs_url, safe='')}"
        if cookie_str:
            proxied += f"&ck={urllib.parse.quote(cookie_str, safe='')}"
        out_lines.append(proxied)
    return "\n".join(out_lines)

@APP.get("/playlist.m3u")
async def playlist(req: Request):
    origin = str(req.base_url).rstrip("/")
    lines = ["#EXTM3U"]
    for key in CHANNELS:
        lines.append(f"#EXTINF:-1,{key.upper()}")
        lines.append(f"{origin}/{key}.m3u8")
    return PlainTextResponse("\n".join(lines), media_type="application/vnd.apple.mpegurl")

@APP.get("/{name}.m3u8")
async def channel(name: str, req: Request):
    if name not in CHANNELS:
        return PlainTextResponse("Channel not found", status_code=404)

    # 1) Güncel tms üret
    tpl = to_tpl(CHANNELS[name])
    src_url = with_tms(tpl)

    # 2) Kaynak manifesti çek
    r = await CLIENT.get(src_url, headers=h_for(src_url, {"Accept": "application/vnd.apple.mpegurl,*/*"}))

    # 3) Set-Cookie varsa yakala (segmentlerde bazı CDN'ler cookie ister)
    set_cookie = r.headers.get("set-cookie", "")
    cookie_str = ""
    if set_cookie:
        # çoklu Set-Cookie başlıklarını kaba şekilde birleştir
        cookie_str = "; ".join([c.split(";")[0] for c in set_cookie.split(",") if "=" in c])

    # 4) Linkleri /relay üstünden geçecek şekilde yeniden yaz
    body = rewrite_manifest(r.text, src_url, str(req.base_url).rstrip("/"), cookie_str)

    return PlainTextResponse(
        body,
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-store"},
    )

@APP.get("/relay")
async def relay(u: str, req: Request, ck: Optional[str] = None):
    """
    Segment/alt-manifest taşımak için proxy.
    - Range başlığını forward eder (VLC/ExoPlayer için kritik)
    - Cookie gerekiyorsa ck param'ından taşınır
    """
    extra = {}
    rng = req.headers.get("range")
    if rng:
        extra["Range"] = rng
    if ck:
        extra["Cookie"] = urllib.parse.unquote(ck)

    rr = await CLIENT.get(u, headers=h_for(u, extra))
    ct = rr.headers.get("Content-Type") or "application/octet-stream"

    # Önemli bazı başlıkları aynen geçir
    passthrough = {}
    if "Content-Range" in rr.headers:
        passthrough["Content-Range"] = rr.headers["Content-Range"]
    if "Accept-Ranges" in rr.headers:
        passthrough["Accept-Ranges"] = rr.headers["Accept-Ranges"]
    if "Content-Length" in rr.headers:
        passthrough["Content-Length"] = rr.headers["Content-Length"]

    passthrough["Cache-Control"] = "no-store"
    passthrough["Access-Control-Allow-Origin"] = "*"

    return Response(content=rr.content, media_type=ct, headers=passthrough)
