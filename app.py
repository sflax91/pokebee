import io, re, json, time
import requests
import pandas as pd
import streamlit as st

def fetch_from_apify(token):
    url = "https://jindrich-bar--nyt-games-api.apify.actor/spelling-bee"
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
    # NYT embeds today's puzzle as JSON in the page source
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
def load_pokemon():
    sheet_id = "1_SHkcM0Zfb3CRP8tXs0pC8giQQGtRGlynVmz0soLJow"
    sheet_name = "Sheet1"
    host = "docs." + "google.com"
    google_sheet = f"https://{host}/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    pokes = pd.read_csv(io.StringIO(requests.get(google_sheet).text))
    pokes["Name"] = pokes["Name"].str.lower()
    pokes["Name"] = pokes["Name"].str.replace(r"[^a-zA-Z]", "", regex=True)
    return pokes

def spelling_bee(letter, string, pokes_df):
    poke_list = []
    allowed = string + letter
    for poke in pokes_df["Name"]:
        if letter in poke:
            has_extra_letters = any(char not in allowed for char in poke)
            if not has_extra_letters:
                poke_list.append(poke)
    return poke_list

mode = st.radio("Letters:", ["Today's NYT Puzzle", "Custom Letters"], horizontal=True)

if mode == "Today's NYT Puzzle":
    try:
        api_token = st.secrets["APIFY_TOKEN"]
        data = fetch_nyt_puzzle(api_token)
        target_letter = data.get("centerLetter", "").lower()
        target_string = "".join(data.get("outerLetters", [])).lower()
        st.caption(f"Date: {data.get('displayDate')}")
    except Exception as e:
        st.error(f"Could not fetch NYT puzzle: {e}")
        st.stop()
else:
    col1, col2 = st.columns(2)
    target_letter = col1.text_input("Center Letter", value="t", max_chars=1).lower().strip()
    target_string = col2.text_input("Outer Letters (6)", value="ygloep", max_chars=6).lower().strip()

if target_letter and target_string:
    st.subheader(f"Center: **{target_letter.upper()}** | Outer: **{target_string.upper()}**")
    pokes = load_pokemon()
    matches = spelling_bee(target_letter, target_string, pokes)

    if len(matches) == 0:
        st.info("No pokemon matches today :(")
    else:
        st.success(f"Found {len(matches)} Pokémon:")
        for p in matches:
            st.write(f"• **{p.capitalize()}**")
