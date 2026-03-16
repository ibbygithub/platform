import os
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# ---- Config from environment ----
GOOGLE_API_KEY         = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
PLACES_API_BASE        = os.getenv("GOOGLE_PLACES_BASE_URL", "https://places.googleapis.com/v1").strip()
DEFAULT_REGION         = os.getenv("DEFAULT_REGION_CODE", "US").strip().upper()
TEXT_SEARCH_FIELD_MASK = os.getenv(
    "GOOGLE_TEXTSEARCH_FIELDMASK",
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.googleMapsUri"
)
NEARBY_FIELD_MASK = os.getenv(
    "GOOGLE_NEARBY_FIELDMASK",
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.rating,places.userRatingCount,places.googleMapsUri"
)


def _require_api_key():
    if not GOOGLE_API_KEY:
        raise RuntimeError("Missing GOOGLE_PLACES_API_KEY in environment (.env)")


def google_places_text_search(text_query, lat, lng, radius_m, max_results, region_code, language_code):
    _require_api_key()
    url = f"{PLACES_API_BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": TEXT_SEARCH_FIELD_MASK,
    }
    body = {
        "textQuery": text_query,
        "maxResultCount": max_results,
        "languageCode": language_code,
        "regionCode": region_code,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def google_places_nearby_search(included_types, lat, lng, radius_m, max_results, region_code, language_code):
    _require_api_key()
    url = f"{PLACES_API_BASE}/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": NEARBY_FIELD_MASK,
    }
    body = {
        "includedTypes": included_types,
        "maxResultCount": max_results,
        "languageCode": language_code,
        "regionCode": region_code,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        },
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/v1/places/photo")
def v1_places_photo():
    """
    Proxy a Google Places photo to the caller without exposing the API key.
    Required param: name  -- the photo resource name from the places response
                             e.g. places/ChIJ.../photos/AXCi2Q...
    Optional params: maxHeightPx (default 600), maxWidthPx (default 800)
    """
    photo_name = request.args.get("name", "").strip()
    max_h      = int(request.args.get("maxHeightPx", 600))
    max_w      = int(request.args.get("maxWidthPx",  800))

    if not photo_name:
        return jsonify({"ok": False, "error": "Missing: name"}), 400

    _require_api_key()

    url    = f"{PLACES_API_BASE}/{photo_name}/media"
    params = {"maxHeightPx": max_h, "maxWidthPx": max_w, "key": GOOGLE_API_KEY}

    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code >= 400:
            return jsonify({"ok": False, "error": f"Google API returned {r.status_code}"}), r.status_code
        return Response(
            r.content,
            content_type=r.headers.get("Content-Type", "image/jpeg"),
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/v1/places/search_text")
def v1_places_search_text():
    body          = request.get_json(force=True, silent=False) or {}
    text_query    = (body.get("text_query") or "").strip()
    lat           = body.get("lat")
    lng           = body.get("lng")
    radius_m      = int(body.get("radius_m") or 2500)
    max_results   = int(body.get("max_results") or 15)
    region_code   = (body.get("region_code") or DEFAULT_REGION).strip().upper()
    language_code = (body.get("language_code") or "en").strip()

    if not text_query:
        return jsonify({"ok": False, "error": "Missing: text_query"}), 400
    if lat is None or lng is None:
        return jsonify({"ok": False, "error": "Missing: lat/lng (anchor required)"}), 400

    try:
        data = google_places_text_search(
            text_query=text_query, lat=float(lat), lng=float(lng),
            radius_m=radius_m, max_results=max_results,
            region_code=region_code, language_code=language_code,
        )
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/v1/places/nearby")
def v1_places_nearby():
    body           = request.get_json(force=True, silent=False) or {}
    included_types = body.get("included_types") or []
    lat            = body.get("lat")
    lng            = body.get("lng")
    radius_m       = int(body.get("radius_m") or 2500)
    max_results    = int(body.get("max_results") or 15)
    region_code    = (body.get("region_code") or DEFAULT_REGION).strip().upper()
    language_code  = (body.get("language_code") or "en").strip()

    if not isinstance(included_types, list) or not included_types:
        return jsonify({"ok": False, "error": "Missing: included_types (list)"}), 400
    if lat is None or lng is None:
        return jsonify({"ok": False, "error": "Missing: lat/lng (anchor required)"}), 400

    try:
        data = google_places_nearby_search(
            included_types=included_types, lat=float(lat), lng=float(lng),
            radius_m=radius_m, max_results=max_results,
            region_code=region_code, language_code=language_code,
        )
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    app.run(host="0.0.0.0", port=port)
