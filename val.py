import os
import re
import json
import math
import base64
import textwrap
from io import BytesIO

import requests
import urllib3
from PIL import Image, ImageDraw, ImageFont

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =========================
# CONFIG
# =========================
LOCKFILE_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "Riot Games",
    "Riot Client",
    "Config",
    "lockfile"
)

SHOOTER_LOG_PATH = os.path.join(
    os.environ["LOCALAPPDATA"],
    "VALORANT",
    "Saved",
    "Logs",
    "ShooterGame.log"
)

CLIENT_PLATFORM = "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
SKINS_TYPE_UUID = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"
SKIN_CHROMAS_TYPE_UUID = "3ad1b2b2-acdb-4524-852f-954a76ddae0a"
AGENTS_TYPE_UUID = "01bb38e1-da47-4e6a-9b3d-945fe4655707"
PLAYER_TITLES_TYPE_UUID = "de7caa6b-adf7-4588-bbd1-143831e786c6"
PLAYER_CARDS_TYPE_UUID = "3f296c07-64c3-494c-923b-fe692a4fa1bd"
SPRAYS_TYPE_UUID = "d5f120f8-ff8c-4aac-92ea-f2b5acbe9475"
BUDDY_LEVELS_TYPE_UUID = "dd3bf334-87f3-40bd-b043-682a57a8dc3a"

BG_COLOR = (18, 18, 22)
HEADER_COLOR = (245, 245, 245)
TEXT_COLOR = (255, 255, 255)
SUBTEXT_COLOR = (185, 185, 190)
CARD_YELLOW = (191, 154, 61)
CARD_ORANGE = (180, 108, 56)
CARD_PINK = (170, 83, 143)
CARD_BLUE = (60, 113, 176)
CARD_GREEN = (64, 134, 90)
CARD_DEFAULT = (76, 84, 96)
CARD_AGENT = (122, 83, 158)
CARD_CARD = (58, 124, 140)
CARD_SPRAY = (154, 78, 92)
CARD_BUDDY = (144, 104, 58)
CARD_TITLE = (82, 90, 110)
CARD_LOCKED = (78, 78, 82)

RARITY_ULTRA = "ultra_or_melee"
RARITY_EXCLUSIVE = "exclusive"
RARITY_PREMIUM = "premium"
RARITY_DELUXE = "deluxe"
RARITY_SELECT = "select"
RARITY_OTHER = "other"

RARITY_PRIORITY = {
    RARITY_ULTRA: 0,
    RARITY_EXCLUSIVE: 1,
    RARITY_PREMIUM: 2,
    RARITY_DELUXE: 3,
    RARITY_SELECT: 4,
    RARITY_OTHER: 5,
}

RARITY_COLORS = {
    RARITY_ULTRA: CARD_YELLOW,
    RARITY_EXCLUSIVE: CARD_ORANGE,
    RARITY_PREMIUM: CARD_PINK,
    RARITY_DELUXE: CARD_BLUE,
    RARITY_SELECT: CARD_GREEN,
    RARITY_OTHER: CARD_DEFAULT,
}

COLS = 5
CARD_W = 270
CARD_H = 168
PADDING = 14
HEADER_H = 90
FOOTER_H = 20
IMAGE_CACHE = {}


# =========================
# HELPERS
# =========================
def safe_get(url, headers=None, timeout=15, verify=False):
    r = requests.get(url, headers=headers, timeout=timeout, verify=verify)
    r.raise_for_status()
    return r


def get_font(size: int):
    candidates = [
        "C:\\Windows\\Fonts\\segoeuib.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap_text(text: str, width: int = 24):
    parts = textwrap.wrap(text, width=width)
    return parts[:2] if parts else [text]


def resolve_rarity_group(weapon_name: str, tier_display_name: str):
    weapon = (weapon_name or "").lower()
    tier = (tier_display_name or "").lower()

    if weapon == "melee" or "ultra" in tier:
        return RARITY_ULTRA
    if "exclusive" in tier:
        return RARITY_EXCLUSIVE
    if "premium" in tier:
        return RARITY_PREMIUM
    if "deluxe" in tier:
        return RARITY_DELUXE
    if "select" in tier:
        return RARITY_SELECT
    return RARITY_OTHER


def card_color(rarity_group: str):
    return RARITY_COLORS.get(rarity_group, CARD_DEFAULT)


def load_image_from_url(url: str):
    if not url:
        return None
    if url in IMAGE_CACHE:
        return IMAGE_CACHE[url].copy()

    r = requests.get(url, timeout=20)
    r.raise_for_status()
    image = Image.open(BytesIO(r.content)).convert("RGBA")
    IMAGE_CACHE[url] = image
    return image.copy()


def format_vp(value):
    if value is None:
        return "N/A"
    return f"{int(value):,}".replace(",", " ")


def parse_lockfile():
    if not os.path.exists(LOCKFILE_PATH):
        raise FileNotFoundError(f"Не найден lockfile: {LOCKFILE_PATH}")

    with open(LOCKFILE_PATH, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    parts = raw.split(":")
    if len(parts) != 5:
        raise RuntimeError(f"Неправильный формат lockfile: {raw}")

    name, pid, port, password, protocol = parts
    return {
        "name": name,
        "pid": pid,
        "port": port,
        "password": password,
        "protocol": protocol,
    }


def make_local_headers(password: str):
    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    return {"Authorization": f"Basic {auth}"}


def get_tokens(port: str, local_headers: dict):
    r = safe_get(
        f"https://127.0.0.1:{port}/entitlements/v1/token",
        headers=local_headers,
        verify=False,
    )
    data = r.json()
    return {
        "access_token": data["accessToken"],
        "entitlements_token": data["token"],
        "subject": data["subject"],
    }


def get_sessions(port: str, local_headers: dict):
    r = safe_get(
        f"https://127.0.0.1:{port}/product-session/v1/external-sessions",
        headers=local_headers,
        verify=False,
    )
    return r.json()


def find_valorant_session(sessions):
    if isinstance(sessions, dict):
        for _, value in sessions.items():
            if not isinstance(value, dict):
                continue
            blob = json.dumps(value).lower()
            if "valorant" in blob or "ares" in blob:
                return value
    raise RuntimeError("Не нашёл активную сессию Valorant. Открой игру до меню.")


def extract_region(valorant_session: dict):
    args = valorant_session.get("launchConfiguration", {}).get("arguments", [])
    args_text = " ".join(args)

    region_match = re.search(r"-ares-deployment=([a-zA-Z0-9_-]+)", args_text)
    if not region_match:
        raise RuntimeError("Не удалось определить region из launch args.")

    region = region_match.group(1).lower()

    region_to_shard = {
        "na": "na",
        "latam": "na",
        "br": "na",
        "eu": "eu",
        "ap": "ap",
        "kr": "kr",
        "pbe": "pbe",
    }
    shard = region_to_shard.get(region)
    if not shard:
        raise RuntimeError(f"Неизвестный region: {region}")

    return region, shard


def get_client_version_from_session(valorant_session: dict):
    candidates = [
        valorant_session.get("launchConfiguration", {}).get("version"),
        valorant_session.get("patchline"),
        valorant_session.get("productVersion"),
        valorant_session.get("version"),
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c.strip()
    return None


def get_client_version_from_log():
    if not os.path.exists(SHOOTER_LOG_PATH):
        return None

    try:
        with open(SHOOTER_LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return None

    patterns = [
        r'"branch":"[^"]+","buildVersion":"([^"]+)"',
        r'"buildVersion":"([^"]+)"',
        r'CI server version: ([0-9.]+(?:-[A-Za-z0-9]+(?:-shipping)?)?)',
        r'Version: ([0-9.]+(?:-[A-Za-z0-9]+(?:-shipping)?)?)',
    ]

    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, content))

    if matches:
        # берём последнее найденное значение
        return matches[-1].strip()

    return None


def make_pd_headers(access_token: str, entitlements_token: str, client_version: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Riot-Entitlements-JWT": entitlements_token,
        "X-Riot-ClientVersion": client_version,
        "X-Riot-ClientPlatform": CLIENT_PLATFORM,
    }


def get_owned_skin_ids(subject: str, shard: str, pd_headers: dict):
    url = f"https://pd.{shard}.a.pvp.net/store/v1/entitlements/{subject}/{SKINS_TYPE_UUID}"
    r = requests.get(url, headers=pd_headers, timeout=20, verify=False)

    print("Store status:", r.status_code)
    print("Store text preview:", r.text[:400])

    r.raise_for_status()
    data = r.json()
    return [x["ItemID"] for x in data.get("Entitlements", [])]


def get_owned_item_ids_by_type(subject: str, shard: str, pd_headers: dict, item_type_uuid: str, label: str):
    url = f"https://pd.{shard}.a.pvp.net/store/v1/entitlements/{subject}/{item_type_uuid}"
    r = requests.get(url, headers=pd_headers, timeout=20, verify=False)
    print(f"{label} status:", r.status_code)
    r.raise_for_status()
    data = r.json()
    return [x["ItemID"] for x in data.get("Entitlements", [])]


def get_live_offer_prices(shard: str, pd_headers: dict):
    urls = [
        f"https://pd.{shard}.a.pvp.net/store/v1/offers",
        f"https://pd.{shard}.a.pvp.net/store/v1/offers/",
    ]

    for url in urls:
        try:
            r = requests.get(url, headers=pd_headers, timeout=20, verify=False)
        except Exception:
            continue

        if r.status_code != 200:
            continue

        data = r.json()
        offers = data.get("Offers", [])
        prices = {}
        for offer in offers:
            offer_id = (offer.get("OfferID") or "").lower()
            cost_obj = offer.get("Cost") or {}
            cost_values = [v for v in cost_obj.values() if isinstance(v, int)]
            if offer_id and cost_values:
                prices[offer_id] = max(cost_values)
        return prices

    return {}


def estimate_skin_price_vp(weapon_name: str, tier_display_name: str, rarity_group: str):
    tier = (tier_display_name or "").lower()
    weapon = (weapon_name or "").lower()

    if weapon == "melee":
        if "ultra" in tier:
            return 5350
        if "exclusive" in tier:
            return 4350
        if "premium" in tier:
            return 3550
        if "deluxe" in tier:
            return 2550
        if "select" in tier:
            return 1750
        return 3550

    prices_by_rarity = {
        RARITY_ULTRA: 2475,
        RARITY_EXCLUSIVE: 2175,
        RARITY_PREMIUM: 1775,
        RARITY_DELUXE: 1275,
        RARITY_SELECT: 875,
    }
    return prices_by_rarity.get(rarity_group)


def attach_skin_prices(skins: list, live_offer_prices: dict):
    total_vp = 0
    priced_count = 0
    live_count = 0
    estimated_count = 0

    for skin in skins:
        matched_ids = skin.get("matched_ids", [])
        price_vp = None
        price_source = "unknown"

        for item_id in matched_ids:
            candidate_price = live_offer_prices.get((item_id or "").lower())
            if candidate_price is not None:
                price_vp = candidate_price
                price_source = "live_offer"
                live_count += 1
                break

        if price_vp is None:
            price_vp = estimate_skin_price_vp(
                skin.get("weapon", ""),
                skin.get("tier_name", ""),
                skin.get("rarity_group", RARITY_OTHER),
            )
            if price_vp is not None:
                price_source = "tier_estimate"
                estimated_count += 1

        skin["price_vp"] = price_vp
        skin["price_source"] = price_source

        if price_vp is not None:
            priced_count += 1
            total_vp += int(price_vp)

    return {
        "total_vp": total_vp,
        "priced_count": priced_count,
        "unknown_count": max(0, len(skins) - priced_count),
        "live_count": live_count,
        "estimated_count": estimated_count,
    }


def get_weapon_skins_catalog():
    weapons = safe_get("https://valorant-api.com/v1/weapons").json()["data"]
    tiers_data = safe_get("https://valorant-api.com/v1/contenttiers").json().get("data", [])

    tiers_by_uuid = {}
    for tier in tiers_data:
        tier_uuid = (tier.get("uuid") or "").lower()
        if tier_uuid:
            tiers_by_uuid[tier_uuid] = tier.get("displayName", "")

    result = []
    for weapon in weapons:
        weapon_name = weapon.get("displayName", "Unknown Weapon")
        for skin in weapon.get("skins", []):
            candidate_ids = set()

            skin_uuid = (skin.get("uuid") or "").lower()
            if skin_uuid:
                candidate_ids.add(skin_uuid)

            levels = skin.get("levels", []) or []
            for level in levels:
                level_uuid = (level.get("uuid") or "").lower()
                if level_uuid:
                    candidate_ids.add(level_uuid)

            chromas = skin.get("chromas", []) or []
            for chroma in chromas:
                chroma_uuid = (chroma.get("uuid") or "").lower()
                if chroma_uuid:
                    candidate_ids.add(chroma_uuid)

            icon = skin.get("displayIcon")
            if not icon:
                if chromas:
                    icon = chromas[0].get("displayIcon")
            if not icon:
                if levels:
                    icon = levels[0].get("displayIcon")

            content_tier_uuid = (skin.get("contentTierUuid") or "").lower()
            tier_display_name = tiers_by_uuid.get(content_tier_uuid, "")
            rarity_group = resolve_rarity_group(weapon_name, tier_display_name)

            result.append({
                "uuid": skin.get("uuid", ""),
                "name": skin["displayName"],
                "icon": icon,
                "weapon": weapon_name,
                "content_tier_uuid": content_tier_uuid,
                "tier_name": tier_display_name,
                "rarity_group": rarity_group,
                "candidate_ids": list(candidate_ids),
            })
    return result


def get_agents_catalog():
    data = safe_get("https://valorant-api.com/v1/agents?isPlayableCharacter=true").json().get("data", [])
    result = []
    for agent in data:
        agent_uuid = (agent.get("uuid") or "").lower()
        if not agent_uuid:
            continue

        icon = (
            agent.get("fullPortrait")
            or agent.get("displayIcon")
            or agent.get("displayIconSmall")
            or agent.get("bustPortrait")
        )
        role_name = (agent.get("role") or {}).get("displayName", "")
        result.append({
            "name": agent.get("displayName", "Unknown Agent"),
            "icon": icon,
            "subtitle": role_name,
            "card_color": CARD_AGENT,
            "candidate_ids": [agent_uuid],
        })
    return result


def get_player_cards_catalog():
    data = safe_get("https://valorant-api.com/v1/playercards").json().get("data", [])
    result = []
    for card in data:
        card_uuid = (card.get("uuid") or "").lower()
        if not card_uuid:
            continue

        icon = card.get("largeArt") or card.get("wideArt") or card.get("smallArt") or card.get("displayIcon")
        result.append({
            "name": card.get("displayName", "Unknown Card"),
            "icon": icon,
            "subtitle": "",
            "card_color": CARD_CARD,
            "candidate_ids": [card_uuid],
        })
    return result


def get_sprays_catalog():
    data = safe_get("https://valorant-api.com/v1/sprays").json().get("data", [])
    result = []
    for spray in data:
        candidate_ids = set()

        spray_uuid = (spray.get("uuid") or "").lower()
        if spray_uuid:
            candidate_ids.add(spray_uuid)

        levels = spray.get("levels", []) or []
        for level in levels:
            level_uuid = (level.get("uuid") or "").lower()
            if level_uuid:
                candidate_ids.add(level_uuid)

        if not candidate_ids:
            continue

        icon = spray.get("fullTransparentIcon") or spray.get("fullIcon") or spray.get("displayIcon")
        if not icon and levels:
            icon = levels[0].get("displayIcon")

        category_raw = spray.get("category")
        if isinstance(category_raw, dict):
            category_name = category_raw.get("displayName", "")
        elif isinstance(category_raw, str):
            category_name = category_raw
        else:
            category_name = ""
        result.append({
            "name": spray.get("displayName", "Unknown Spray"),
            "icon": icon,
            "subtitle": category_name,
            "card_color": CARD_SPRAY,
            "candidate_ids": list(candidate_ids),
        })
    return result


def get_buddies_catalog():
    data = safe_get("https://valorant-api.com/v1/buddies").json().get("data", [])
    result = []
    for buddy in data:
        candidate_ids = set()

        buddy_uuid = (buddy.get("uuid") or "").lower()
        if buddy_uuid:
            candidate_ids.add(buddy_uuid)

        levels = buddy.get("levels", []) or []
        for level in levels:
            level_uuid = (level.get("uuid") or "").lower()
            if level_uuid:
                candidate_ids.add(level_uuid)

        if not candidate_ids:
            continue

        icon = buddy.get("displayIcon")
        if not icon and levels:
            icon = levels[0].get("displayIcon")

        result.append({
            "name": buddy.get("displayName", "Unknown Buddy"),
            "icon": icon,
            "subtitle": "",
            "card_color": CARD_BUDDY,
            "candidate_ids": list(candidate_ids),
        })
    return result


def get_player_titles_catalog():
    data = safe_get("https://valorant-api.com/v1/playertitles").json().get("data", [])
    result = []
    for title in data:
        title_uuid = (title.get("uuid") or "").lower()
        if not title_uuid:
            continue

        title_text = (title.get("titleText") or "").strip()
        display_name = (title.get("displayName") or "").strip()
        result.append({
            "name": title_text or display_name or "Unknown Title",
            "icon": None,
            "subtitle": "",
            "card_color": CARD_TITLE,
            "candidate_ids": [title_uuid],
        })
    return result


def filter_owned_collection(catalog: list, owned_ids: list):
    owned_set = {(x or "").lower() for x in owned_ids}
    result = []
    for item in catalog:
        candidate_ids = set(item.get("candidate_ids", []))
        matched_ids = sorted(candidate_ids.intersection(owned_set))
        if matched_ids:
            item_copy = dict(item)
            item_copy["matched_ids"] = matched_ids
            result.append(item_copy)

    result.sort(key=lambda x: x.get("name", "").lower())
    return result


def build_agents_overview(catalog: list, owned_agent_ids: list):
    owned_set = {(x or "").lower() for x in owned_agent_ids}
    result = []
    owned_count = 0

    for item in catalog:
        candidate_ids = set(item.get("candidate_ids", []))
        is_owned = bool(candidate_ids.intersection(owned_set))
        item_copy = dict(item)
        item_copy["is_owned"] = is_owned
        item_copy["locked_gray"] = not is_owned

        if is_owned:
            owned_count += 1
            item_copy["card_color"] = CARD_AGENT
        else:
            item_copy["card_color"] = CARD_LOCKED

        result.append(item_copy)

    result.sort(key=lambda x: (0 if x.get("is_owned") else 1, x.get("name", "").lower()))
    return result, owned_count


def render_collection(items: list, output_path: str, title: str, subtitle: str):
    title_font = get_font(26)
    small_font = get_font(15)
    name_font = get_font(16)

    rows = math.ceil(len(items) / COLS) if items else 1
    img_w = COLS * CARD_W + (COLS + 1) * PADDING
    img_h = HEADER_H + rows * CARD_H + (rows + 1) * PADDING + FOOTER_H

    canvas = Image.new("RGB", (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    draw.text((PADDING, 16), f"{title}: {len(items)}", font=title_font, fill=HEADER_COLOR)
    draw.text((PADDING, 47), subtitle, font=small_font, fill=SUBTEXT_COLOR)

    for i, item in enumerate(items):
        col = i % COLS
        row = i // COLS

        x = PADDING + col * (CARD_W + PADDING)
        y = HEADER_H + PADDING + row * (CARD_H + PADDING)
        x2 = x + CARD_W
        y2 = y + CARD_H

        draw.rounded_rectangle([x, y, x2, y2], radius=14, fill=item.get("card_color", CARD_DEFAULT))

        icon = None
        try:
            icon = load_image_from_url(item.get("icon"))
            if icon:
                if item.get("locked_gray"):
                    icon = icon.convert("LA").convert("RGBA")
                icon.thumbnail((CARD_W - 26, 84))
                icon_x = x + (CARD_W - icon.width) // 2
                icon_y = y + 10
                canvas.paste(icon, (icon_x, icon_y), icon)
        except Exception:
            icon = None

        name_fill = TEXT_COLOR if not item.get("locked_gray") else SUBTEXT_COLOR
        extra_fill = HEADER_COLOR if not item.get("locked_gray") else SUBTEXT_COLOR

        if icon:
            text_y = y + CARD_H - 52
            for idx, line in enumerate(wrap_text(item.get("name", "Unknown"), width=26)):
                draw.text((x + 10, text_y + idx * 16), line, font=name_font, fill=name_fill)

            extra = (item.get("subtitle") or "").strip()
            if extra:
                draw.text((x + 10, y + CARD_H - 20), wrap_text(extra, width=28)[0], font=small_font, fill=extra_fill)
        else:
            text_y = y + 30
            for idx, line in enumerate(wrap_text(item.get("name", "Unknown"), width=24)):
                draw.text((x + 10, text_y + idx * 20), line, font=name_font, fill=name_fill)

            extra = (item.get("subtitle") or "").strip()
            if extra:
                for idx, line in enumerate(wrap_text(extra, width=28)):
                    draw.text((x + 10, y + CARD_H - 45 + idx * 16), line, font=small_font, fill=extra_fill)

        if item.get("locked_gray"):
            draw.text((x + CARD_W - 78, y + 10), "LOCKED", font=small_font, fill=SUBTEXT_COLOR)

    canvas.save(output_path)
    return output_path


def filter_owned_skins(catalog: list, owned_skin_ids: list):
    owned_set = {(x or "").lower() for x in owned_skin_ids}
    skins = []
    matches = []

    for item in catalog:
        candidate_set = set(item.get("candidate_ids", []))
        found = sorted(candidate_set.intersection(owned_set))
        if found:
            matches.append({
                "skin": item.get("name", "Unknown"),
                "weapon": item.get("weapon", "Unknown"),
                "matched_ids": found,
            })
            if item.get("icon"):
                skin_copy = dict(item)
                skin_copy["matched_ids"] = found
                skins.append(skin_copy)

    def sort_key(x):
        rarity_group = x.get("rarity_group", RARITY_OTHER)
        rarity_rank = RARITY_PRIORITY.get(rarity_group, 99)
        melee_rank = 0 if x.get("weapon", "").lower() == "melee" else 1
        return (rarity_rank, melee_rank, x["weapon"].lower(), x["name"].lower())

    skins.sort(key=sort_key)
    return skins, matches


def print_mapping_diagnostics(owned_skin_ids: list, catalog: list, matches: list):
    owned_preview = [(x or "").lower() for x in owned_skin_ids[:10]]
    print("Diagnostic owned_skin_ids (first 10):", owned_preview)

    candidate_ids = []
    seen = set()
    for item in catalog:
        for candidate_id in item.get("candidate_ids", []):
            if candidate_id not in seen:
                seen.add(candidate_id)
                candidate_ids.append(candidate_id)
            if len(candidate_ids) >= 10:
                break
        if len(candidate_ids) >= 10:
            break
    print("Diagnostic catalog candidate IDs (first 10):", candidate_ids)

    matched_ids = []
    for match in matches:
        matched_ids.extend(match.get("matched_ids", []))
    uniq_matched_ids = []
    used = set()
    for candidate_id in matched_ids:
        if candidate_id not in used:
            used.add(candidate_id)
            uniq_matched_ids.append(candidate_id)
        if len(uniq_matched_ids) >= 10:
            break
    print("Diagnostic matched IDs (first 10):", uniq_matched_ids)


def render_inventory(skins: list, output_path="inventory.png", total_vp=0):
    title_font = get_font(26)
    small_font = get_font(15)
    name_font = get_font(16)

    rows = math.ceil(len(skins) / COLS) if skins else 1
    img_w = COLS * CARD_W + (COLS + 1) * PADDING
    img_h = HEADER_H + rows * CARD_H + (rows + 1) * PADDING + FOOTER_H

    canvas = Image.new("RGB", (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    draw.text((PADDING, 16), f"Weapon skins: {len(skins)}", font=title_font, fill=HEADER_COLOR)
    draw.text((PADDING, 47), f"Total inventory value: {format_vp(total_vp)} VP", font=small_font, fill=HEADER_COLOR)
    draw.text((PADDING, 66), "Generated from local Riot client session", font=small_font, fill=SUBTEXT_COLOR)

    for i, skin in enumerate(skins):
        col = i % COLS
        row = i // COLS

        x = PADDING + col * (CARD_W + PADDING)
        y = HEADER_H + PADDING + row * (CARD_H + PADDING)

        x2 = x + CARD_W
        y2 = y + CARD_H

        draw.rounded_rectangle(
            [x, y, x2, y2],
            radius=14,
            fill=card_color(skin.get("rarity_group", RARITY_OTHER)),
        )

        try:
            icon = load_image_from_url(skin["icon"])
            icon.thumbnail((CARD_W - 26, 84))

            icon_x = x + (CARD_W - icon.width) // 2
            icon_y = y + 10
            canvas.paste(icon, (icon_x, icon_y), icon)
        except Exception:
            pass

        lines = wrap_text(skin["name"], width=26)
        text_y = y + CARD_H - 52
        for idx, line in enumerate(lines):
            draw.text((x + 10, text_y + idx * 16), line, font=name_font, fill=TEXT_COLOR)

        price_vp = skin.get("price_vp")
        price_text = f"{format_vp(price_vp)} VP" if price_vp is not None else "N/A"
        draw.text((x + 10, y + CARD_H - 20), price_text, font=small_font, fill=HEADER_COLOR)

    canvas.save(output_path)
    return output_path


def main():
    print("Reading lockfile...")
    lock = parse_lockfile()

    print("Getting local auth...")
    local_headers = make_local_headers(lock["password"])

    print("Getting tokens...")
    tokens = get_tokens(lock["port"], local_headers)

    print("Reading sessions...")
    sessions = get_sessions(lock["port"], local_headers)
    valorant_session = find_valorant_session(sessions)

    print("Extracting region / shard...")
    region, shard = extract_region(valorant_session)

    print("Getting client version...")
    client_version = get_client_version_from_session(valorant_session)

    if not client_version:
        print("Client version not found in session, trying ShooterGame.log...")
        client_version = get_client_version_from_log()

    if not client_version:
        raise RuntimeError(
            "Не удалось получить X-Riot-ClientVersion ни из session, ни из ShooterGame.log"
        )

    print("Region:", region)
    print("Shard:", shard)
    print("Client version:", client_version)

    pd_headers = make_pd_headers(
        tokens["access_token"],
        tokens["entitlements_token"],
        client_version,
    )

    print("Getting owned skin IDs...")
    owned_skin_level_ids = get_owned_skin_ids(tokens["subject"], shard, pd_headers)
    owned_skin_chroma_ids = get_owned_item_ids_by_type(
        tokens["subject"],
        shard,
        pd_headers,
        SKIN_CHROMAS_TYPE_UUID,
        "Skin chromas",
    )
    owned_skin_ids = list(dict.fromkeys(owned_skin_level_ids + owned_skin_chroma_ids))
    print("Owned skin entitlements (levels + chromas):", len(owned_skin_ids))

    print("Downloading weapons catalog...")
    skin_catalog = get_weapon_skins_catalog()

    print("Filtering owned skins...")
    owned_skins, matches = filter_owned_skins(skin_catalog, owned_skin_ids)
    print("Prepared skins for render:", len(owned_skins))

    if not owned_skins:
        print_mapping_diagnostics(owned_skin_ids, skin_catalog, matches)

    print("Getting live offer prices...")
    live_offer_prices = get_live_offer_prices(shard, pd_headers)
    print("Live offer prices loaded:", len(live_offer_prices))

    print("Applying prices...")
    pricing_summary = attach_skin_prices(owned_skins, live_offer_prices)
    print(
        "Priced skins:",
        pricing_summary["priced_count"],
        "| live:",
        pricing_summary["live_count"],
        "| estimated:",
        pricing_summary["estimated_count"],
        "| unknown:",
        pricing_summary["unknown_count"],
    )
    print("Total inventory value (VP):", pricing_summary["total_vp"])

    outputs = []

    print("Rendering skins image...")
    skins_out = render_inventory(owned_skins, "inventory.png", total_vp=pricing_summary["total_vp"])
    outputs.append(skins_out)
    print("Saved:", skins_out)

    print("Getting owned agents...")
    owned_agent_ids = get_owned_item_ids_by_type(tokens["subject"], shard, pd_headers, AGENTS_TYPE_UUID, "Agents")
    agent_catalog = get_agents_catalog()
    agents_overview, owned_agents_count = build_agents_overview(agent_catalog, owned_agent_ids)
    agents_out = render_collection(
        agents_overview,
        "agents.png",
        f"Agents (Owned {owned_agents_count}/{len(agents_overview)})",
        "Owned agents are colored, locked agents are gray",
    )
    outputs.append(agents_out)
    print("Prepared agents (all):", len(agents_overview))
    print("Owned agents:", owned_agents_count)
    print("Saved:", agents_out)

    print("Getting owned player cards...")
    owned_card_ids = get_owned_item_ids_by_type(tokens["subject"], shard, pd_headers, PLAYER_CARDS_TYPE_UUID, "Player cards")
    card_catalog = get_player_cards_catalog()
    owned_cards = filter_owned_collection(card_catalog, owned_card_ids)
    cards_out = render_collection(
        owned_cards,
        "player_cards.png",
        "Player Cards",
        "Owned player cards from local Riot client session",
    )
    outputs.append(cards_out)
    print("Prepared player cards:", len(owned_cards))
    print("Saved:", cards_out)

    print("Getting owned sprays...")
    owned_spray_ids = get_owned_item_ids_by_type(tokens["subject"], shard, pd_headers, SPRAYS_TYPE_UUID, "Sprays")
    spray_catalog = get_sprays_catalog()
    owned_sprays = filter_owned_collection(spray_catalog, owned_spray_ids)
    sprays_out = render_collection(
        owned_sprays,
        "sprays.png",
        "Sprays",
        "Owned sprays from local Riot client session",
    )
    outputs.append(sprays_out)
    print("Prepared sprays:", len(owned_sprays))
    print("Saved:", sprays_out)

    print("Getting owned buddies...")
    owned_buddy_ids = get_owned_item_ids_by_type(
        tokens["subject"],
        shard,
        pd_headers,
        BUDDY_LEVELS_TYPE_UUID,
        "Buddy levels",
    )
    buddy_catalog = get_buddies_catalog()
    owned_buddies = filter_owned_collection(buddy_catalog, owned_buddy_ids)
    buddies_out = render_collection(
        owned_buddies,
        "buddies.png",
        "Buddies",
        "Owned gun buddies from local Riot client session",
    )
    outputs.append(buddies_out)
    print("Prepared buddies:", len(owned_buddies))
    print("Saved:", buddies_out)

    print("Getting owned titles...")
    owned_title_ids = get_owned_item_ids_by_type(
        tokens["subject"],
        shard,
        pd_headers,
        PLAYER_TITLES_TYPE_UUID,
        "Player titles",
    )
    title_catalog = get_player_titles_catalog()
    owned_titles = filter_owned_collection(title_catalog, owned_title_ids)
    titles_out = render_collection(
        owned_titles,
        "titles.png",
        "Titles",
        "",
    )
    outputs.append(titles_out)
    print("Prepared titles:", len(owned_titles))
    print("Saved:", titles_out)

    print("All generated files:")
    for path in outputs:
        print(" -", path)


if __name__ == "__main__":
    main()
