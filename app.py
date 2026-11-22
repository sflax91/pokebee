import io
import re
import json
import time
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PokéBee")
st.title("PokéBee")
st.caption("Fan project, not affiliated with Nintendo, Game Freak, or The New York Times.")


# ---------- NYT Spelling Bee fetch (Apify, with direct-NYT fallback) ----------
def fetch_from_apify(token):
    subdomain = "jindrich-bar--nyt-games-api"
    domain = "apify.actor"
    endpoint = "spelling-bee"
    url = f"https://{subdomain}.{domain}/{endpoint}"
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(url, params={"token": token}, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Apify failed after 3 tries: {last_err}")


def fetch_from_nyt():
    r = requests.get(
        "https://www.nytimes.com/puzzles/spelling-bee",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    r.raise_for_status()
    m = re.search(r"window\.gameData\s*=\s*(\{.*?\})</script>", r.text, re.S)
    if not m:
        raise RuntimeError("Couldn't find puzzle data in NYT page")
    today = json.loads(m.group(1))["today"]
    return {
        "centerLetter": today["centerLetter"],
        "outerLetters": today["outerLetters"],
        "displayDate": today["displayDate"],
    }


@st.cache_data(ttl=900)
def fetch_nyt_puzzle(token):
    try:
        return fetch_from_apify(token)
    except Exception as apify_err:
        try:
            return fetch_from_nyt()
        except Exception as nyt_err:
            raise RuntimeError(f"Apify: {apify_err} | NYT direct: {nyt_err}")


# ---------- Pokémon list ----------
@st.cache_data(ttl=86400)
def load_pokemon():
    sheet_id = "1_SHkcM0Zfb3CRP8tXs0pC8giQQGtRGlynVmz0soLJow"
    sheet_name = "Sheet1"
    host = "docs." + "google.com"
    google_sheet = f"https://{host}/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    resp = requests.get(google_sheet, timeout=15)
    resp.raise_for_status()
    pokes = pd.read_csv(io.StringIO(resp.text))
    pokes["strip_name"] = (
        pokes["Name"].str.lower().str.replace(r"[^a-zA-Z]", "", regex=True)
    )
    return pokes


def spelling_bee(letter, string, pokes_df):
    allowed = set(string + letter)
    mask = pokes_df["strip_name"].apply(lambda s: letter in s and set(s) <= allowed)
    out = pokes_df.loc[mask].copy()
    out["label"] = out["strip_name"].str.upper() + " (" + out["Name"] + ")"
    return out


# Hook for sprites later (assumes the sheet's ID is the national Pokédex number)
def sprite_url(poke_id):
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{int(poke_id)}.png"


# ---------- UI ----------
mode = st.radio("Letters:", ["Today's NYT Puzzle", "Custom Letters"], horizontal=True)

if mode == "Today's NYT Puzzle":
    try:
        api_token = st.secrets["APIFY_TOKEN"]
        data = fetch_nyt_puzzle(api_token)
        target_letter = data.get("centerLetter", "").lower()
        target_string = "".join(data.get("outerLetters", [])).lower()
        st.caption(f"Date: {data.get('displayDate')}")
    except Exception as e:
        st.error(f"Could not fetch NYT puzzle: {e}. Try Custom Letters instead.")
        st.stop()
else:
    col1, col2 = st.columns(2)
    target_letter = col1.text_input("Center Letter", value="t", max_chars=1).lower().strip()
    target_string = col2.text_input("Outer Letters (6)", value="ygloep", max_chars=6).lower().strip()

if target_letter and target_string:
    st.subheader(f"Center: **{target_letter.upper()}** | Outer: **{target_string.upper()}**")
    try:
        pokes = load_pokemon()
    except Exception as e:
        st.error(f"Could not load the Pokémon list: {e}")
        st.stop()

    matches = spelling_bee(target_letter, target_string, pokes)

    if matches.empty:
        st.info("No pokemon matches today :(")
    else:
        st.success(f"Found {len(matches)} Pokémon:")
        for _, row in matches.iterrows():
            c1, c2 = st.columns([1, 6])
            c1.image(sprite_url(row["ID"]), width=64)
            c2.write(f"**{row['label']}**")
