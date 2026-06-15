# ============ FORCE PLAYWRIGHT BROWSER INSTALLATION ============
import subprocess
import sys
import os

# Set Playwright cache directory
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/opt/render/.cache/ms-playwright'

# Install browsers if not present
try:
    print("🔧 Checking/installing Playwright browsers...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], 
                   capture_output=False, check=True)
    print("✅ Playwright chromium installed")
except Exception as e:
    print(f"⚠️ Playwright install warning: {e}")

# ============ REGULAR IMPORTS ============
import re
import io
import time
import asyncio
import random
import string
import requests
import uuid
import json as _json
import base64 as _base64
import ssl
import threading
from urllib.parse import urlparse
from html.parser import HTMLParser
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import websocket as _websocket

# Custom adapter to ignore SSL verification
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_version'] = ssl.PROTOCOL_TLSv1_2
        kwargs['cert_reqs'] = ssl.CERT_NONE
        kwargs['assert_hostname'] = False
        return super().init_poolmanager(*args, **kwargs)

PASSWORD = "Test1234Abc!"
COGNITO_CLIENT_ID = "1kvg8re5bgu9ljqnnkjosu477k"
USER_POOL_ID = "eu-west-1_7hEawdalF"
GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"

CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH", None)

GPT_SIZE_TO_ASPECT = {
    "1080x1080": "1:1",
    "1280x720": "16:9",
    "720x1280": "9:16",
}

# ─── Temp email ──────────────────────────────────────────────────────────────
class TempEmail:
    def __init__(self):
        self.sid_token = None
        self.email_addr = None
        self.seq = 0
        self.seen_ids = set()

    def generate(self):
        r = requests.get(f"{GUERRILLA_API}?f=get_email_address", timeout=15)
        data = r.json()
        self.sid_token = data["sid_token"]
        self.seq = 0
        self.seen_ids = set()
        raw = data["email_addr"]
        at = raw.find("@")
        self.email_addr = (raw[:at + 1] if at != -1 else raw + "@") + "sharklasers.com"
        return self.email_addr

    def check_inbox(self):
        if not self.sid_token:
            return None
        try:
            r = requests.get(
                f"{GUERRILLA_API}?f=check_email&sid_token={self.sid_token}&seq={self.seq}",
                timeout=15,
            )
            data = r.json()
            if "seq" in data:
                self.seq = data["seq"]
            for email in data.get("list", []):
                if email["mail_id"] in self.seen_ids:
                    continue
                self.seen_ids.add(email["mail_id"])
                code = self._extract_code(email.get("mail_subject", ""))
                if not code:
                    code = self._fetch_body_code(email["mail_id"])
                if code:
                    return code
        except Exception:
            pass
        return None

    def _fetch_body_code(self, mail_id):
        try:
            r = requests.get(
                f"{GUERRILLA_API}?f=fetch_email&email_id={mail_id}&sid_token={self.sid_token}",
                timeout=15,
            )
            d = r.json()
            body = re.sub(r"<[^>]+>", "", d.get("mail_body", "") or "")
            return (
                self._extract_code(d.get("mail_subject", ""))
                or self._extract_code(body)
            )
        except Exception:
            return None

    @staticmethod
    def _extract_code(text):
        if not text:
            return None
        m = re.search(r"(\d{6})", text)
        if m:
            return m.group(1)
        m = re.search(r"(\d{5})", text)
        if m:
            return m.group(1)
        m = re.search(r"(\d{4})", text)
        return m.group(1) if m else None

    def wait_for_code(self, timeout=120, interval=3):
        deadline = time.time() + timeout
        while time.time() < deadline:
            code = self.check_inbox()
            if code:
                return code
            time.sleep(interval)
        return None

# ─── Cognito auth ─────────────────────────────────────────────────────────────
from pycognito import Cognito

def sign_up_with_cognito(email):
    try:
        cognito = Cognito(
            user_pool_id=USER_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
            username=email,
            user_pool_region="eu-west-1",
        )
        cognito.email = email
        cognito.given_name = "Bot"
        cognito.family_name = "User"
        cognito.register(username=email, password=PASSWORD)
        return {"status": "success", "message": "User signed up, waiting for confirmation"}
    except Exception as e:
        error_msg = str(e)
        if "User already exists" in error_msg or "UsernameExistsException" in error_msg:
            return {"status": "exists", "message": "User already exists"}
        raise RuntimeError(f"Sign-up failed: {error_msg}")

def confirm_sign_up_with_cognito(email, code):
    try:
        cognito = Cognito(
            user_pool_id=USER_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
            username=email,
            user_pool_region="eu-west-1",
        )
        cognito.confirm_sign_up(confirmation_code=code)
        return True
    except Exception as e:
        raise RuntimeError(f"Confirmation failed: {str(e)}")

def sign_in_with_cognito(email):
    try:
        cognito = Cognito(
            user_pool_id=USER_POOL_ID,
            client_id=COGNITO_CLIENT_ID,
            username=email,
            user_pool_region="eu-west-1",
        )
        cognito.authenticate(password=PASSWORD)
        id_token = cognito.id_token
        if not id_token:
            raise RuntimeError("Failed to get ID token after authentication")
        return id_token
    except Exception as e:
        error_msg = str(e)
        if "NEW_PASSWORD_REQUIRED" in error_msg:
            try:
                cognito = Cognito(
                    user_pool_id=USER_POOL_ID,
                    client_id=COGNITO_CLIENT_ID,
                    username=email,
                    user_pool_region="eu-west-1",
                )
                cognito.authenticate(password=PASSWORD)
                if hasattr(cognito, "new_password_required") and cognito.new_password_required:
                    cognito.set_new_password_challenge(PASSWORD)
                    cognito.authenticate(password=PASSWORD)
                return cognito.id_token
            except Exception as inner_e:
                raise RuntimeError(f"Failed to handle password change: {str(inner_e)}")
        raise RuntimeError(f"Authentication failed: {error_msg}")

# ─── Synthesia workspace ───────────────────────────────────────────────────────
def create_workspace(id_token):
    headers = {
        "Authorization": id_token,
        "Content-Type": "application/json",
    }
    res = requests.get("https://api.synthesia.io/workspaces?scope=public", headers=headers)
    res.raise_for_status()
    data = res.json()
    if data.get("results") and len(data["results"]) > 0:
        workspace_id = data["results"][0]["id"]
    else:
        res = requests.post(
            "https://api.synthesia.io/workspaces",
            headers=headers,
            json={"strict": True, "includeDemoVideos": False},
        )
        res.raise_for_status()
        workspace_id = res.json()["workspace"]["id"]

    try:
        requests.post(
            "https://api.synthesia.io/user/onboarding/setPreferredWorkspaceId",
            headers=headers,
            json={"workspaceId": workspace_id},
        )
    except Exception:
        pass

    try:
        requests.post(
            "https://api.synthesia.io/user/onboarding/initialize",
            headers=headers,
            json={
                "featureFlags": {"freemiumEnabled": True},
                "queryParams": {"paymentPlanType": "free"},
                "allowReinitialize": False,
            },
        )
    except Exception:
        pass

    for _ in range(5):
        try:
            res = requests.post(
                "https://api.synthesia.io/user/onboarding/completeCurrentStep",
                headers=headers,
                json={"featureFlags": {"freemiumEnabled": True}},
            )
            if res.status_code != 200:
                break
        except Exception:
            break

    try:
        requests.post(
            "https://api.synthesia.io/user/questionnaire",
            headers=headers,
            json={
                "company": {"size": "emerging", "industry": "professional_services"},
                "seniority": "individual_contributor",
                "persona": "marketing",
            },
        )
    except Exception:
        pass

    try:
        requests.post(
            "https://api.synthesia.io/user/signupForm",
            headers=headers,
            json={"analyticsCookies": {}},
        )
    except Exception:
        pass

    try:
        requests.post(
            f"https://api.synthesia.io/billing/self-serve/{workspace_id}/paywall",
            headers=headers,
            json={
                "targetPlan": "freemium",
                "redirectUrl": "https://app.synthesia.io/#/?plan_created=true&payment_plan=freemium",
            },
        )
    except Exception:
        pass

    time.sleep(30)
    return workspace_id

# ─── Synthesia media generation ───────────────────────────────────────────────
SIZE_TO_ASPECT_RATIO = {
    "1280x720": "16:9",
    "720x1280": "9:16",
    "1080x1080": "1:1",
}

VIDEO_MODELS = {"fal_veo3", "fal_veo3_fast"}

def start_synthesia_generation(token, workspace_id, prompt, size, model):
    try:
        aspect_ratio = SIZE_TO_ASPECT_RATIO.get(size, "16:9")

        if model in ("fal_veo3", "fal_veo3_fast"):
            model_request = {
                "modelName": model,
                "aspectRatio": aspect_ratio,
                "generateAudio": True,
            }
            media_type = "video"
        else:
            model_request = {
                "modelName": "nanobanana_pro",
                "aspectRatio": aspect_ratio,
            }
            media_type = "image"

        r = requests.post(
            "https://api.prd.synthesia.io/avatarServices/api/generatedMedia/stockFootage/bulk?numberOfResults=1",
            headers={"Authorization": token, "Content-Type": "application/json"},
            json={
                "mediaType": media_type,
                "modelRequest": model_request,
                "userPrompt": prompt,
                "workspaceId": workspace_id,
            },
            timeout=30,
        )
        r.raise_for_status()
        result = r.json()
        if not result or len(result) == 0:
            raise RuntimeError("No asset ID returned from Synthesia")
        return result[0]["mediaAssetId"]
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to start generation: {str(e)}")

def poll_synthesia(token, asset_id, timeout=600, interval=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(
                f"https://api.synthesia.io/assets/{asset_id}",
                headers={"Authorization": token},
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("uploadMetadata", {}).get("status", "unknown")
            if status == "ready":
                return data
            if status == "failed":
                raise RuntimeError("Generation failed on Synthesia side.")
            time.sleep(interval)
        except requests.exceptions.RequestException as e:
            print(f"Polling error: {e}, retrying...")
            time.sleep(interval)
    raise TimeoutError("Generation timed out after 10 minutes.")

def run_synthesia_generation(prompt: str, size: str, model: str) -> dict:
    temp = TempEmail()
    email = temp.generate()

    sign_up_with_cognito(email)

    code = temp.wait_for_code(timeout=120)
    if not code:
        raise RuntimeError("Timed out waiting for email verification code.")

    confirm_sign_up_with_cognito(email, code)
    token = sign_in_with_cognito(email)
    workspace_id = create_workspace(token)
    asset_id = start_synthesia_generation(token, workspace_id, prompt, size, model)
    result = poll_synthesia(token, asset_id)

    return {
        "url": result.get("url", ""),
        "download_url": result.get("downloadUrl", ""),
    }

# ─── GPT Image 2 Alt via Playwright (VisualGPT) ──────────────────────────────────────────
async def _run_gptimage2_async(prompt: str, aspect_ratio: str, ref_image_infos: list = None) -> dict:
    browser = None
    pw = None

    try:
        pw = await async_playwright().start()
        launch_kwargs = dict(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
            ],
        )
        if CHROMIUM_PATH:
            launch_kwargs["executable_path"] = CHROMIUM_PATH
        browser = await pw.chromium.launch(**launch_kwargs)
        page = await browser.new_page()
        page.set_default_timeout(90000)

        captured_urls = []

        def handle_response(response):
            url = response.url
            if "cdn.static-boost.com/temp/visualgpt/prediction_image" in url and url.endswith(".png"):
                captured_urls.append(url)

        page.on("response", handle_response)

        await page.goto(
            "https://visualgpt.io/ai-models/gpt-image-2",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)

        # Upload reference images
        if ref_image_infos:
            for disc_url, fname, mime in ref_image_infos:
                result = await page.evaluate(
                    """
                    async ([url, fname, mime]) => {
                        try {
                            const resp = await fetch(url, { mode: 'cors' });
                            if (!resp.ok) return { ok: false, error: 'HTTP ' + resp.status };
                            const blob = await resp.blob();
                            const file = new File([blob], fname, { type: mime || blob.type || 'image/jpeg' });
                            const input = document.querySelector('input[type="file"][accept=".jpg,.jpeg,.png,.webp"]');
                            if (!input) return { ok: false, error: 'file input not found' };
                            const dt = new DataTransfer();
                            for (const f of Array.from(input.files || [])) dt.items.add(f);
                            dt.items.add(file);
                            input.files = dt.files;
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            input.dispatchEvent(new Event('input',  { bubbles: true }));
                            return { ok: true, fileCount: dt.files.length };
                        } catch (e) {
                            return { ok: false, error: e.message };
                        }
                    }
                    """,
                    [disc_url, fname, mime],
                )
                if not result.get("ok"):
                    print(f"[gpt2] ref image upload warning: {result.get('error')}")
                await asyncio.sleep(15)

        # Enter prompt
        textarea_selectors = [
            'textarea[placeholder="Enter any ideas you want to organize..."]',
            'textarea[placeholder*="Enter any ideas"]',
            'textarea[placeholder*="Enter"]',
            "textarea",
        ]
        found = False
        for selector in textarea_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    await page.locator(selector).first.click()
                    await page.locator(selector).first.fill("")
                    found = True
                    break
            except Exception:
                continue
        if not found:
            raise RuntimeError("Could not find textarea on visualgpt.io")

        await page.type("textarea", prompt, delay=30)
        await asyncio.sleep(1.5)

        # Select aspect ratio
        if aspect_ratio:
            trigger_clicked = await page.evaluate("""
                () => {
                    const triggers = document.querySelectorAll('[id^="reka-popover-trigger"]');
                    for (const trigger of triggers) {
                        if (trigger.querySelector('.i-hugeicons\\\\:image-01')) {
                            trigger.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)

            if not trigger_clicked:
                print("[gpt2] Could not find aspect ratio trigger button")
            else:
                await asyncio.sleep(1)
                ratio_selected = await page.evaluate(f"""
                    (ratio) => {{
                        const buttons = document.querySelectorAll('button[role="radio"]');
                        for (const btn of buttons) {{
                            if (btn.getAttribute('aria-label')?.trim() === ratio) {{
                                btn.click();
                                return true;
                            }}
                        }}
                        const labels = document.querySelectorAll('label');
                        for (const label of labels) {{
                            const btn = label.querySelector('button[role="radio"]');
                            if (btn && btn.getAttribute('aria-label')?.trim() === ratio) {{
                                label.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """, aspect_ratio)

                if not ratio_selected:
                    print(f"[gpt2] Could not find aspect ratio button for: {aspect_ratio}")
                else:
                    await asyncio.sleep(1.5)

        # Click Generate button
        generate_clicked = await page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('button[type="button"]'));
                const genBtn = btns.find(b => {
                    const span = b.querySelector('span');
                    return span && span.innerText?.trim() === 'Generate';
                });
                if (genBtn) {
                    genBtn.removeAttribute('disabled');
                    genBtn.click();
                    return true;
                }
                return false;
            }
        """)

        if not generate_clicked:
            raise RuntimeError("Could not find Generate button on visualgpt.io")

        # Wait for generated image (8 minutes timeout)
        timeout_seconds = 480
        start_time = asyncio.get_event_loop().time()
        while len(captured_urls) == 0 and (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            await asyncio.sleep(4)

        if captured_urls:
            image_url = captured_urls[0]
            resp = requests.get(image_url, timeout=60)
            if resp.status_code != 200:
                raise RuntimeError(f"Failed to download GPT Image 2 result: HTTP {resp.status_code}")
            return {"url": image_url, "download_url": image_url, "_bytes": resp.content}

        # Fallback: try to find image in DOM
        images = await page.query_selector_all("img")
        for img in images:
            try:
                src = await img.get_attribute("src")
                if src and "cdn.static-boost.com/temp/visualgpt/prediction_image" in src and src.endswith(".png"):
                    resp = requests.get(src, timeout=60)
                    if resp.ok:
                        return {"url": src, "download_url": src, "_bytes": resp.content}
            except Exception:
                continue

        raise RuntimeError("GPT Image 2: no image URL captured from visualgpt.io")

    except Exception as e:
        print(f"[gpt2] Error: {e}")
        raise
    finally:
        if browser:
            await browser.close()
        if pw:
            await pw.stop()

def run_gptimage2_generation(prompt: str, aspect_ratio: str, ref_image_infos: list = None) -> dict:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_gptimage2_async(prompt, aspect_ratio, ref_image_infos))
    except Exception as e:
        print(f"[gpt2] Generation failed: {e}")
        raise
    finally:
        loop.close()

# ─── Nano Banana, Nano Banana Pro Alt & Nano Banana 2 (Vidofy) ───────────────────────────────────────────────────
NB2_API_BASE = "https://vidofy.ai"
NB2_WS_URL = "wss://vidofy.ai:2096/"
NB2_NOVITA_REHOST = "https://3000-i367mb7olbgfer4t20p2p-2e77fc33.sandbox.novita.ai/api/upload"
NB2_POOL_FILE = "nb2_pool.json"
NB2_POOL_TARGET = 3
NB2_POOL_MIN_DELAY = 90
NB2_CREDITS_PER_ACCOUNT = 10
_nb2_pool_lock = threading.Lock()
NB2_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
NB2_SEC_CH_UA = '"Not;A=Brand";v="24", "Chromium";v="128"'
NB2_SIZE_TO_RATIO = {
    "1080x1080": "1:1",
    "1280x720": "16:9",
    "720x1280": "9:16",
}

def _nb2_pool_load():
    try:
        if os.path.exists(NB2_POOL_FILE):
            with open(NB2_POOL_FILE, "r") as f:
                return _json.load(f)
    except Exception:
        pass
    return []

def _nb2_pool_save(pool):
    with open(NB2_POOL_FILE, "w") as f:
        _json.dump(pool, f, indent=2)

def _nb2_pool_pop():
    with _nb2_pool_lock:
        pool = _nb2_pool_load()
        if not pool:
            return None
        acct = pool.pop(0)
        _nb2_pool_save(pool)
        print(f"[nb2-pool] Popped account {acct.get('email')} — {len(pool)} remaining")
        return acct

def _nb2_pool_push(acct):
    with _nb2_pool_lock:
        pool = _nb2_pool_load()
        pool.append(acct)
        _nb2_pool_save(pool)
        print(f"[nb2-pool] Added {acct.get('email')} — pool size now {len(pool)}")

def _nb2_pool_size():
    try:
        with _nb2_pool_lock:
            return len(_nb2_pool_load())
    except Exception:
        return 0

def _nb2_pool_replenish_loop():
    print("[nb2-pool] Replenish loop started")
    _last_creation = 0.0
    while True:
        try:
            size = _nb2_pool_size()
            if size < NB2_POOL_TARGET:
                elapsed = time.time() - _last_creation
                if elapsed < NB2_POOL_MIN_DELAY:
                    time.sleep(NB2_POOL_MIN_DELAY - elapsed)
                print(f"[nb2-pool] Pool at {size}/{NB2_POOL_TARGET} — creating account…")
                try:
                    acct = _nb2_create_account()
                    _nb2_pool_push(acct)
                    _last_creation = time.time()
                except Exception as e:
                    print(f"[nb2-pool] Account creation failed: {e} — will retry in 120s")
                    time.sleep(120)
                    continue
            else:
                time.sleep(30)
        except Exception as e:
            print(f"[nb2-pool] Loop error: {e}")
            time.sleep(60)

def _nb2_headers(extra=None):
    h = {
        "accept-language": "en-US,en;q=0.9",
        "dnt": "1",
        "user-agent": NB2_UA,
        "sec-ch-ua": NB2_SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    if extra:
        h.update(extra)
    return h

def _nb2_scrape_secret_key(url, cookie=None):
    h = _nb2_headers({"accept": "text/html", "origin": NB2_API_BASE, "referer": NB2_API_BASE + "/"})
    if cookie:
        h["cookie"] = cookie
    res = requests.get(url, headers=h, timeout=30)
    html = res.text
    m = re.search(r'secret_key[^>]*value\s*=\s*["\']([a-f0-9]{64})["\']', html, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r'secret_key[^}]*?["\']([a-f0-9]{64})["\']', html, re.IGNORECASE)
    return m2.group(1) if m2 else None

def _nb2_mailtm_create():
    r = requests.get("https://api.mail.tm/domains", timeout=15)
    domain = r.json()["hydra:member"][0]["domain"]
    user = "".join(random.choices(string.ascii_lowercase, k=12))
    email = f"{user}@{domain}"
    pw = "".join(random.choices(string.ascii_letters + string.digits, k=16)) + "A1!"
    requests.post("https://api.mail.tm/accounts", json={"address": email, "password": pw}, timeout=15)
    tok_r = requests.post("https://api.mail.tm/token", json={"address": email, "password": pw}, timeout=15)
    token = tok_r.json().get("token")
    if not token:
        raise RuntimeError("Could not get mail.tm token")
    return email, pw, token

def _nb2_mailtm_wait_code(token, deadline):
    seen = set()
    hdrs = {"Authorization": f"Bearer {token}"}
    while time.time() < deadline:
        try:
            msgs = requests.get("https://api.mail.tm/messages", headers=hdrs, timeout=10).json()
            for msg in msgs.get("hydra:member", []):
                mid = msg["id"]
                if mid in seen:
                    continue
                seen.add(mid)
                if "vidofy" not in (msg.get("from", {}).get("address", "")).lower():
                    continue
                body_r = requests.get(f"https://api.mail.tm/messages/{mid}", headers=hdrs, timeout=10)
                body = re.sub(r"<[^>]+>", " ", body_r.json().get("html", [""])[0] or body_r.json().get("text", "") or "")
                m = re.search(r"/en/active-account/(\d+)", body, re.IGNORECASE)
                if m:
                    return m.group(1)
                m = re.search(r"\b(\d{7,12})\b", body)
                if m:
                    return m.group(1)
        except Exception:
            pass
        time.sleep(5)
    return None

def _nb2_guerrilla_create():
    r = requests.get("https://api.guerrillamail.com/ajax.php?f=get_email_address", timeout=15)
    data = r.json()
    raw = data["email_addr"]
    at = raw.find("@")
    email = (raw[:at + 1] if at != -1 else raw + "@") + "sharklasers.com"
    return email, data["sid_token"], 0

def _nb2_guerrilla_wait_code(sid_token, seq_ref, deadline):
    seen = set()
    while time.time() < deadline:
        try:
            r = requests.get(
                f"https://api.guerrillamail.com/ajax.php?f=check_email&seq={seq_ref[0]}&sid_token={sid_token}",
                timeout=15,
            )
            data = r.json()
            if "seq" in data:
                seq_ref[0] = data["seq"]
            for mail in data.get("list", []):
                if mail["mail_id"] in seen:
                    continue
                seen.add(mail["mail_id"])
                if "vidofy" not in (mail.get("mail_from") or "").lower():
                    continue
                fetch_r = requests.get(
                    f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={mail['mail_id']}&sid_token={sid_token}",
                    timeout=15,
                )
                body = re.sub(r"<[^>]+>", " ", fetch_r.json().get("mail_body", "") or "")
                m = re.search(r"/en/active-account/(\d+)", body, re.IGNORECASE)
                if m:
                    return m.group(1)
                m = re.search(r"\b(\d{7,12})\b", body)
                if m:
                    return m.group(1)
        except Exception:
            pass
        time.sleep(5)
    return None

def _nb2_do_signup(email, password, signup_key):
    signup_res = requests.post(
        f"{NB2_API_BASE}/en/signup",
        headers=_nb2_headers({
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": NB2_API_BASE,
            "referer": f"{NB2_API_BASE}/en/signup",
            "x-requested-with": "XMLHttpRequest",
        }),
        data={
            "firstname": "".join(random.choices(string.ascii_letters, k=6)).capitalize(),
            "email": email, "password": password,
            "b_name": "", "refresh": "data",
            "page_url_signup": f"{NB2_API_BASE}/en/signup",
            "secret_key": signup_key,
            "redirect_to": f"{NB2_API_BASE}/en/studio/text-to-image",
        },
        allow_redirects=False,
        timeout=30,
    )
    body = signup_res.text
    if "too many requests" in body.lower() or "rate" in body.lower():
        raise RuntimeError(f"RATE_LIMITED: {body[:120]}")
    set_cookie = signup_res.headers.get("set-cookie", "")
    m = re.search(r"vidofy_session_token=([^;]+)", set_cookie)
    if not m:
        raise RuntimeError(f"No session cookie: status={signup_res.status_code} body={body[:200]}")
    return m.group(1)

def _nb2_create_account():
    signup_key = _nb2_scrape_secret_key(f"{NB2_API_BASE}/en/signup")
    if not signup_key:
        raise RuntimeError("Could not scrape Vidofy signup key")

    last_err = None
    for attempt in range(5):
        if attempt > 0:
            wait = 30 * attempt
            print(f"[nb2] Signup attempt {attempt+1}/5, waiting {wait}s…")
            time.sleep(wait)

        use_mailtm = (attempt % 2 == 0)
        try:
            if use_mailtm:
                email, password, mailtm_token = _nb2_mailtm_create()
                get_code = lambda deadline: _nb2_mailtm_wait_code(mailtm_token, deadline)
            else:
                email, sid_token, seq = _nb2_guerrilla_create()
                seq_ref = [seq]
                password = "".join(random.choices(string.ascii_letters + string.digits, k=16)) + "A1!"
                get_code = lambda deadline: _nb2_guerrilla_wait_code(sid_token, seq_ref, deadline)
        except Exception as e:
            try:
                if use_mailtm:
                    email, sid_token, seq = _nb2_guerrilla_create()
                    seq_ref = [seq]
                    password = "".join(random.choices(string.ascii_letters + string.digits, k=16)) + "A1!"
                    get_code = lambda deadline: _nb2_guerrilla_wait_code(sid_token, seq_ref, deadline)
                else:
                    email, password, mailtm_token = _nb2_mailtm_create()
                    get_code = lambda deadline: _nb2_mailtm_wait_code(mailtm_token, deadline)
            except Exception as e2:
                last_err = e2
                continue

        try:
            session_token = _nb2_do_signup(email, password, signup_key)
        except RuntimeError as e:
            last_err = e
            print(f"[nb2] Signup failed (attempt {attempt+1}): {e}")
            continue

        cookie_hdr = f"vidofy_session_token={session_token}"
        verify_code = get_code(time.time() + 120)
        if not verify_code:
            last_err = RuntimeError("Vidofy verification email timed out")
            print(f"[nb2] Verification timed out (attempt {attempt+1})")
            continue

        requests.get(
            f"{NB2_API_BASE}/en/active-account/{verify_code}",
            headers=_nb2_headers({"accept": "text/html", "cookie": cookie_hdr}),
            timeout=30,
        )

        gen_key = _nb2_scrape_secret_key(f"{NB2_API_BASE}/en/studio/text-to-image", cookie_hdr)
        if not gen_key:
            last_err = RuntimeError("Could not scrape Vidofy generation key")
            print(f"[nb2] Gen key scrape failed (attempt {attempt+1})")
            continue

        print(f"[nb2] Account created: {email} (attempt {attempt+1})")
        return {"email": email, "password": password, "session_token": session_token, "gen_key": gen_key, "credits": NB2_CREDITS_PER_ACCOUNT}

    raise RuntimeError(f"Vidofy account creation failed after 5 attempts: {last_err}")

def _nb2_submit(session, prompt, ratio, image_input=None, model_type="nanobanana_2"):
    is_i2i = image_input is not None
    
    # Set model-specific parameters based on the model type
    if model_type == "nanobanana_pro_alt":
        model_key = "Nano_banana_pro_i2i" if is_i2i else "Nano_banana_pro_t2i"
        slug = "nano-banana-pro-i2i" if is_i2i else "nano-banana-pro-t2i"
        model_name = "Nano Banana Pro"
        output_format = "jpg"
        api_cheap = "poyo_ai"
        has_resolution_quality = True
    elif model_type == "nanobanana_2":
        model_key = "Nano_banana_2_i2i" if is_i2i else "Nano_banana_2_t2i"
        slug = "nano-banana-2-i2i" if is_i2i else "nano-banana-2-t2i"
        model_name = "Nano Banana 2"
        output_format = "jpg"
        api_cheap = "poyo_ai"
        has_resolution_quality = True
    elif model_type == "nanobanana":
        model_key = "Nano_banana_i2i" if is_i2i else "Nano_banana_t2i"
        slug = "nano-banana-i2i" if is_i2i else "nano-banana-t2i"
        model_name = "Nano Banana"
        output_format = "jpeg"
        api_cheap = "kie_ai"
        has_resolution_quality = False
    else:
        # Default to nanobanana_2
        model_key = "Nano_banana_2_i2i" if is_i2i else "Nano_banana_2_t2i"
        slug = "nano-banana-2-i2i" if is_i2i else "nano-banana-2-t2i"
        model_name = "Nano Banana 2"
        output_format = "jpg"
        api_cheap = "poyo_ai"
        has_resolution_quality = True
    
    mode = "image-to-image" if is_i2i else "text-to-image"
    referer = f"{NB2_API_BASE}/en/studio/{'image-to-image' if is_i2i else 'text-to-image'}"

    # Build data fields
    data_fields = [
        ("m_prompt", prompt),
        ("m_aspect_ratio", ratio),
        ("m_aspect_ratio_price", ratio),
        ("m_output_format", output_format),
        ("m_public", "on"),
        ("m_model_key", model_key),
        ("m_effect_key", ""),
        ("m_prefix", "google"),
        ("m_api_cheap", api_cheap),
        ("m_name", model_name),
        ("m_slug", slug),
        ("refresh", "data"),
        ("m_media_type", "image"),
        ("m_input_duration", "2"),
        ("m_mode", mode),
        ("page_url_ai_media", f"{NB2_API_BASE}/api/v1/generate/submit"),
        ("page_url_model_data", f"{NB2_API_BASE}/api/v1/info/model-info"),
        ("page_url_model_credits", f"{NB2_API_BASE}/api/v1/info/model-credits"),
        ("page_url_model_versions", f"{NB2_API_BASE}/api/v1/info/model-versions"),
        ("secret_key", session["gen_key"]),
        ("regen_source_map", ""),
    ]
    
    # Add resolution quality only for models that support it
    if has_resolution_quality:
        data_fields.insert(3, ("m_resolution_quality", "1K"))

    if is_i2i:
        img_bytes, img_filename, img_mime = image_input
        files = [
            ("m_image", ("", b"", "application/octet-stream")),
            ("m_multi_file_0", (img_filename, img_bytes, img_mime)),
            ("m_video", ("", b"", "application/octet-stream")),
            ("m_audio", ("", b"", "application/octet-stream")),
            ("m_first_frame", ("", b"", "application/octet-stream")),
            ("m_last_frame", ("", b"", "application/octet-stream")),
        ]
    else:
        files = [
            ("m_image", ("", b"", "application/octet-stream")),
            ("m_video", ("", b"", "application/octet-stream")),
            ("m_audio", ("", b"", "application/octet-stream")),
            ("m_first_frame", ("", b"", "application/octet-stream")),
            ("m_last_frame", ("", b"", "application/octet-stream")),
        ]

    res = requests.post(
        f"{NB2_API_BASE}/api/v1/generate/submit",
        headers=_nb2_headers({
            "accept": "application/json, text/javascript, */*; q=0.01",
            "origin": NB2_API_BASE, "referer": referer,
            "cookie": f"vidofy_session_token={session['session_token']}",
            "x-requested-with": "XMLHttpRequest",
            "sec-fetch-dest": "empty", "sec-fetch-mode": "cors", "sec-fetch-site": "same-origin",
        }),
        files=files,
        data=data_fields,
        timeout=60,
    )
    data = res.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Vidofy submit failed: {data}")
    return data["media_id"], data["ws_token"]

def _nb2_extract_image_url(html):
    m = re.search(r'data-src="(https://cdn\.vidofy\.ai/[^"]+\.(?:jpe?g|png|webp))"', html, re.IGNORECASE)
    if m:
        return m.group(1)
    fb = re.search(r'https://cdn\.vidofy\.ai/[^\s"\']+\.(?:jpe?g|png|webp)', html, re.IGNORECASE)
    return fb.group(0) if fb else None

def _nb2_ws_poll(media_id, ws_token, timeout=300):
    result = {"url": None, "error": None, "done": False}

    def on_open(ws):
        print(f"[nb2] WebSocket opened for media_id: {media_id}")
        ws.send(_json.dumps({"action": "subscribe", "job_id": media_id, "token": ws_token}))

    def on_message(ws, raw):
        try:
            msg = _json.loads(raw)
            print(f"[nb2] WebSocket message: {msg.get('event', msg.get('status', 'unknown'))}")
            if msg.get("type") == "ping":
                ws.send(_json.dumps({"type": "pong"}))
                return
            if msg.get("event") == "generation_completed" or (msg.get("data") or {}).get("status") == "completed":
                html = (msg.get("data") or {}).get("html", "")
                url = _nb2_extract_image_url(html)
                result["url"] = url
                if not url:
                    result["error"] = "No image URL in completed payload"
                result["done"] = True
                ws.close()
            elif msg.get("status") == "error" or (msg.get("data") or {}).get("status") == "error":
                result["error"] = "Generation error from Vidofy"
                result["done"] = True
                ws.close()
        except Exception as e:
            print(f"[nb2] WebSocket message error: {e}")

    def on_error(ws, err):
        print(f"[nb2] WebSocket error: {err}")
        result["error"] = str(err)
        result["done"] = True

    def on_close(ws, code, msg):
        print(f"[nb2] WebSocket closed: {code} - {msg}")
        result["done"] = True

    ws = _websocket.WebSocketApp(
        NB2_WS_URL,
        header={"Origin": NB2_API_BASE, "User-Agent": NB2_UA},
        on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close,
    )
    t = threading.Thread(target=lambda: ws.run_forever(), daemon=True)
    t.start()

    deadline = time.time() + timeout
    while time.time() < deadline:
        if result["done"]:
            break
        time.sleep(2)

    if not result["done"]:
        ws.close()
        print(f"[nb2] WebSocket timeout after {timeout}s")
        raise TimeoutError(f"WebSocket did not respond in time after {timeout}s")
    if result["error"]:
        raise RuntimeError(result["error"])
    return result["url"]

def _nb2_http_poll(session, media_id, timeout=300):
    cookie_hdr = f"vidofy_session_token={session['session_token']}"
    base_hdrs = _nb2_headers({"cookie": cookie_hdr, "accept": "application/json, text/javascript, */*; q=0.01", "x-requested-with": "XMLHttpRequest"})
    html_hdrs = _nb2_headers({"cookie": cookie_hdr, "accept": "text/html"})

    deadline = time.time() + timeout
    while time.time() < deadline:
        for url, method, payload in [
            (f"{NB2_API_BASE}/api/v1/generate/status", "POST", {"media_id": media_id}),
            (f"{NB2_API_BASE}/api/v1/media/{media_id}", "GET", None),
            (f"{NB2_API_BASE}/api/v1/generate/status?media_id={media_id}", "GET", None),
        ]:
            try:
                if method == "POST":
                    res = requests.post(url, headers=base_hdrs, json=payload, timeout=15)
                else:
                    res = requests.get(url, headers=base_hdrs, timeout=15)
                if res.status_code == 200:
                    try:
                        data = res.json()
                        status = data.get("status") or data.get("media_status") or ""
                        if status in ("completed", "ready", "done", "success"):
                            cdn = (data.get("url") or data.get("image_url") or
                                   data.get("media_url") or data.get("cdn_url") or "")
                            if cdn:
                                return cdn
                        html_blob = data.get("html") or data.get("content") or ""
                        if html_blob:
                            found = _nb2_extract_image_url(html_blob)
                            if found:
                                return found
                    except Exception:
                        found = _nb2_extract_image_url(res.text)
                        if found:
                            return found
            except Exception:
                pass

        for studio_path in ["/en/studio/text-to-image", "/en/studio/image-to-image"]:
            try:
                res = requests.get(f"{NB2_API_BASE}{studio_path}", headers=html_hdrs, timeout=15)
                if res.status_code == 200:
                    found = _nb2_extract_image_url(res.text)
                    if found:
                        return found
            except Exception:
                pass

        time.sleep(8)

    raise TimeoutError("Vidofy generation timed out (HTTP polling)")

def _nb2_rehost(image_url):
    try:
        origin = "https://3000-i367mb7olbgfer4t20p2p-2e77fc33.sandbox.novita.ai"
        res = requests.post(
            NB2_NOVITA_REHOST,
            headers=_nb2_headers({"accept": "*/*", "content-type": "application/json", "origin": origin, "referer": origin + "/"}),
            json={"url": image_url},
            timeout=30,
        )
        data = res.json()
        if data.get("success") and data.get("catboxUrl"):
            return data["catboxUrl"]
    except Exception:
        pass
    return image_url

def run_nanobanana_generation(prompt: str, size: str, image_input=None) -> dict:
    ratio = NB2_SIZE_TO_RATIO.get(size, "1:1")

    account = _nb2_pool_pop()
    if account is None:
        print("[nb2] Pool empty — creating account directly (this may take a moment)…")
        account = _nb2_create_account()

    media_id, ws_token = _nb2_submit(account, prompt, ratio, image_input, model_type="nanobanana")

    image_url = None
    try:
        image_url = _nb2_ws_poll(media_id, ws_token, timeout=300)
    except Exception as _ws_err:
        print(f"[nb2] WebSocket failed ({_ws_err}), switching to HTTP polling…")
        image_url = _nb2_http_poll(account, media_id, timeout=300)

    final_url = _nb2_rehost(image_url)
    return {"url": final_url, "download_url": final_url}

def run_nanobanana_pro_alt_generation(prompt: str, size: str, image_input=None) -> dict:
    ratio = NB2_SIZE_TO_RATIO.get(size, "1:1")

    account = _nb2_pool_pop()
    if account is None:
        print("[nb2] Pool empty — creating account directly (this may take a moment)…")
        account = _nb2_create_account()

    media_id, ws_token = _nb2_submit(account, prompt, ratio, image_input, model_type="nanobanana_pro_alt")

    image_url = None
    try:
        image_url = _nb2_ws_poll(media_id, ws_token, timeout=300)
    except Exception as _ws_err:
        print(f"[nb2] WebSocket failed ({_ws_err}), switching to HTTP polling…")
        image_url = _nb2_http_poll(account, media_id, timeout=300)

    final_url = _nb2_rehost(image_url)
    return {"url": final_url, "download_url": final_url}

def run_nanobanana2_generation(prompt: str, size: str, image_input=None) -> dict:
    ratio = NB2_SIZE_TO_RATIO.get(size, "1:1")

    account = _nb2_pool_pop()
    if account is None:
        print("[nb2] Pool empty — creating account directly (this may take a moment)…")
        account = _nb2_create_account()

    media_id, ws_token = _nb2_submit(account, prompt, ratio, image_input, model_type="nanobanana_2")

    image_url = None
    try:
        image_url = _nb2_ws_poll(media_id, ws_token, timeout=300)
    except Exception as _ws_err:
        print(f"[nb2] WebSocket failed ({_ws_err}), switching to HTTP polling…")
        image_url = _nb2_http_poll(account, media_id, timeout=300)

    final_url = _nb2_rehost(image_url)
    return {"url": final_url, "download_url": final_url}

# ─── Dispatch ─────────────────────────────────────────────────────────────────
def run_generation(prompt: str, size: str, model: str, ref_images: list = None, quality: str = None, thinking: str = None) -> dict:
    # GPT Image 2 uses ONLY VisualGPT - NO Dreamkrate
    if model == "gpt_image_2":
        aspect_ratio = GPT_SIZE_TO_ASPECT.get(size, "1:1")
        return run_gptimage2_generation(prompt, aspect_ratio, ref_images)
    if model == "gpt_image_2_alt":
        aspect_ratio = GPT_SIZE_TO_ASPECT.get(size, "1:1")
        return run_gptimage2_generation(prompt, aspect_ratio, ref_images)
    if model == "nanobanana":
        image_input = ref_images[0] if ref_images else None
        return run_nanobanana_generation(prompt, size, image_input)
    if model == "nanobanana_2":
        image_input = ref_images[0] if ref_images else None
        return run_nanobanana2_generation(prompt, size, image_input)
    if model == "nanobanana_pro_alt":
        image_input = ref_images[0] if ref_images else None
        return run_nanobanana_pro_alt_generation(prompt, size, image_input)
    return run_synthesia_generation(prompt, size, model)

# ============ API JOB STORAGE ============
jobs_db: Dict[str, dict] = {}

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    model: str = Field(..., description="nanobanana, nanobanana_pro, nanobanana_pro_alt, nanobanana_2, gpt_image_2, gpt_image_2_alt, fal_veo3, fal_veo3_fast")
    ref_image: Optional[str] = None
    size: Optional[str] = "1280x720"
    quality: Optional[str] = None
    thinking: Optional[str] = None

class GenerateResponse(BaseModel):
    status_id: str
    status: str
    message: str

class StatusResponse(BaseModel):
    status_id: str
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

# ============ FASTAPI APP WITH CORS ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    replenish_thread = threading.Thread(target=_nb2_pool_replenish_loop, daemon=True)
    replenish_thread.start()
    print("✅ API Started - GPT Image 2 uses VisualGPT only")
    print("✅ Nano Banana, Nano Banana Pro Alt & Nano Banana 2 use Vidofy")
    print("🌐 CORS enabled - All origins allowed")
    yield
    print("🛑 API Shutting down")

app = FastAPI(title="AI Media Generation API", lifespan=lifespan)

# ============ CORS MIDDLEWARE - Allow any website to call this API ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ROOT ENDPOINT FOR RENDER HEALTH CHECK ============
@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "AI Media Generation API is live",
        "version": "2.0.0",
        "endpoints": [
            "POST /generate",
            "GET /status/{job_id}",
            "GET /health",
            "GET /models"
        ]
    }

def process_ref_image(ref_image: str, model: str):
    if not ref_image:
        return None
    
    if model == "gpt_image_2" or model == "gpt_image_2_alt":
        if ref_image.startswith(('http://', 'https://')):
            return [(ref_image, "ref.jpg", "image/jpeg")]
        return None
    elif model in ["nanobanana", "nanobanana_2", "nanobanana_pro_alt"]:
        if ref_image.startswith(('http://', 'https://')):
            resp = requests.get(ref_image, timeout=30)
            resp.raise_for_status()
            return [(resp.content, "ref.jpg", "image/jpeg")]
    return None

def update_job(job_id: str, status: JobStatus, progress: int = None, message: str = None, result: dict = None, error: str = None):
    if job_id in jobs_db:
        jobs_db[job_id]["status"] = status
        jobs_db[job_id]["updated_at"] = datetime.now().isoformat()
        if progress is not None:
            jobs_db[job_id]["progress"] = progress
        if message is not None:
            jobs_db[job_id]["message"] = message
        if result is not None:
            jobs_db[job_id]["result"] = result
        if error is not None:
            jobs_db[job_id]["error"] = error
        if status == JobStatus.PROCESSING and not jobs_db[job_id].get("started_at"):
            jobs_db[job_id]["started_at"] = datetime.now().isoformat()
        if status in [JobStatus.SUCCESS, JobStatus.FAILED]:
            jobs_db[job_id]["completed_at"] = datetime.now().isoformat()

async def run_generation_background(job_id: str, request: GenerateRequest):
    try:
        update_job(job_id, JobStatus.PROCESSING, 5, "Processing request...")
        
        ref_images = None
        if request.ref_image:
            update_job(job_id, JobStatus.PROCESSING, 10, "Loading reference image...")
            ref_images = process_ref_image(request.ref_image, request.model)
        
        update_job(job_id, JobStatus.PROCESSING, 20, f"Running {request.model}...")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_generation(
                prompt=request.prompt,
                size=request.size,
                model=request.model,
                ref_images=ref_images,
                quality=request.quality,
                thinking=request.thinking
            )
        )
        
        update_job(job_id, JobStatus.SUCCESS, 100, "Generation complete!", result=result)
        
    except Exception as e:
        update_job(job_id, JobStatus.FAILED, None, f"Failed: {str(e)}", error=str(e))

@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    valid_models = ["nanobanana", "nanobanana_pro", "nanobanana_pro_alt", "nanobanana_2", "gpt_image_2", "gpt_image_2_alt", "fal_veo3", "fal_veo3_fast"]
    if request.model not in valid_models:
        raise HTTPException(400, f"Invalid model. Use: {valid_models}")
    
    valid_sizes = ["1080x1080", "1280x720", "720x1280"]
    if request.size not in valid_sizes:
        raise HTTPException(400, f"Invalid size. Use: {valid_sizes}")
    
    job_id = str(uuid.uuid4())
    
    jobs_db[job_id] = {
        "status_id": job_id,
        "status": JobStatus.PENDING,
        "progress": 0,
        "message": "Job submitted",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
        "request": request.dict()
    }
    
    background_tasks.add_task(run_generation_background, job_id, request)
    
    return GenerateResponse(
        status_id=job_id,
        status="pending",
        message="Job submitted successfully"
    )

@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    
    job = jobs_db[job_id]
    
    return StatusResponse(
        status_id=job["status_id"],
        status=job["status"].value if isinstance(job["status"], JobStatus) else job["status"],
        progress=job.get("progress"),
        message=job.get("message"),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        result=job.get("result"),
        error=job.get("error")
    )

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/models")
async def list_models():
    return {
        "models": [
            {"id": "nanobanana", "name": "Nano Banana", "type": "image", "generator": "Vidofy", "supports_ref": True, "api": "kie_ai", "format": "jpeg"},
            {"id": "nanobanana_pro", "name": "Nano Banana Pro", "type": "image", "generator": "Synthesia"},
            {"id": "nanobanana_pro_alt", "name": "Nano Banana Pro Alt", "type": "image", "generator": "Vidofy", "supports_ref": True, "api": "poyo_ai"},
            {"id": "nanobanana_2", "name": "Nano Banana 2", "type": "image", "generator": "Vidofy", "supports_ref": True, "api": "poyo_ai"},
            {"id": "gpt_image_2", "name": "GPT Image 2", "type": "image", "generator": "VisualGPT", "supports_ref": True},
            {"id": "gpt_image_2_alt", "name": "GPT Image 2 Alt", "type": "image", "generator": "VisualGPT", "supports_ref": True},
            {"id": "fal_veo3", "name": "Veo 3.1", "type": "video", "generator": "Synthesia"},
            {"id": "fal_veo3_fast", "name": "Veo 3.1 Fast", "type": "video", "generator": "Synthesia"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
