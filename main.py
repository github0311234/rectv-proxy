import re, time, urllib.parse
from typing import Optional
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, Response

APP = FastAPI()
UA = "googleusercontent"
REF = "https://twitter.com/"
EXPIRE = 24 * 60 * 60  # 1 gün

CHANNELS = {
  "history":"https://tv.prectv53.lol/live/history.m3u8?token=7yEyEAgA9cC2fGNU9stTPA&tms=1755970567",
  "bbc":"https://tv.prectv53.lol/live/bbc.m3u8?token=7yEyEAgA9cC2fGNU9stTPA&tms=1755970567",

  "bsturk":"https://tv.prectv53.lol/live/bsturk.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "bsfamily":"https://tv.prectv53.lol/live/bsfamily.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "bsstars":"https://tv.prectv53.lol/live/bsstars.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "bspremier1":"https://tv.prectv53.lol/live/bspremier1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "box1":"https://tv.prectv53.lol/live/box1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "box2":"https://tv.prectv53.lol/live/box2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "mvturk":"https://tv.prectv53.lol/live/mvturk.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "sinema2":"https://tv.prectv53.lol/live/sinema2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "sinema1002":"https://tv.prectv53.lol/live/sinema1002.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",

  "bm1":"https://tv.prectv53.lol/live/bm1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "bm2":"https://tv.prectv53.lol/live/bm2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "smart1":"https://tv.prectv53.lol/live/smart1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "smart2":"https://tv.prectv53.lol/live/smart2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "t1":"https://tv.prectv53.lol/live/t1.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "t2":"https://tv.prectv53.lol/live/t2.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",
  "t3":"https://tv.prectv53.lol/live/t3.m3u8?token=zG78iOI-098GCudq5btv5g&tms=1755970502",

  "bsseries1":"https://tv.prectv53.lol/live/bsseries1.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
  "bsseries2":"https://tv.prectv53.lol/live/bsseries2.m3u8?token=lGr6X-A6wLyCvmf_dPsj0A&tms=1755970571",
}

def to_tpl(u:str)->str:
  if "{TMS}" in u: return u
  return re.sub(r"([?&])tms=\d+", r"\1tms={TMS}", u) if "tms=" in u else (u + ("&" if "?" in u else "?") + "tms={TMS}")

def with_tms(tpl:str)->str:
  return tpl.replace("{TMS}", str(int(time.time()) + EXPIRE))

CLIENT = httpx.AsyncClient(follow_redirects=True, timeout=15.0)

def h_for(url:str, extra:dict|None=None)->dict:
  o = urllib.parse.urlparse(url)
  h = {
    "User-Agent": UA,
    "Referer": REF,
    "Origin": f"{o.scheme}://{o.netloc}",
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
  }
  if extra: h.update(extra)
  return h

def rewrite(text:str, base_url:str, host_origin:str, cookie_str:str)->str:
  out=[]
  for line in text.splitlines():
    if not line or line.startswith("#"): out.append(line); continue
    absu = line if urllib.parse.urlparse(line).scheme else urllib.parse.urljoin(base_url, line)
    u = f"{host_origin}/relay?u={urllib.parse.quote(absu, safe='')}"
    if cookie_str: u += f"&ck={urllib.parse.quote(cookie_str, safe='')}"
    out.append(u)
  return "\n".join(out)

@APP.get("/playlist.m3u")
async def playlist(req:Request):
  origin = str(req.base_url).rstrip("/")
  lines=["#EXTM3U"]
  for k in CHANNELS:
    lines += [f"#EXTINF:-1, {k.upper()}", f"{origin}/{k}.m3u8"]
  return PlainTextResponse("\n".join(lines), media_type="application/vnd.apple.mpegurl")

@APP.get("/{name}.m3u8")
async def channel(name:str, req:Request):
  if name not in CHANNELS: return PlainTextResponse("Channel not found", status_code=404)
  tpl = to_tpl(CHANNELS[name]); final_url = with_tms(tpl)
  r = await CLIENT.get(final_url, headers=h_for(final_url, {"Accept":"application/vnd.apple.mpegurl,*/*"}))
  set_cookie = r.headers.get("set-cookie","")
  ck = "; ".join([c.split(";")[0] for c in set_cookie.split(",") if "=" in c]) if set_cookie else ""
  body = rewrite(r.text, final_url, str(req.base_url).rstrip("/"), ck)
  return PlainTextResponse(body, media_type="application/vnd.apple.mpegurl", headers={"Cache-Control":"no-store"})

@APP.get("/relay")
async def relay(u:str, ck: Optional[str]=None, req:Request):
  extra={}
  rng=req.headers.get("range")
  if rng: extra["Range"]=rng
  if ck: extra["Cookie"]=urllib.parse.unquote(ck)
  rr = await CLIENT.get(u, headers=h_for(u, extra))
  ct = rr.headers.get("Content-Type") or "application/octet-stream"
  return Response(content=rr.content, media_type=ct, headers={"Cache-Control":"no-store","Access-Control-Allow-Origin":"*"})
