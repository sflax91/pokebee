import io
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PokéBee")
st.title("PokéBee")

# Fetch today's NYT Spelling Bee letters via Apify
@st.cache_data(ttl=3600)
def fetch_nyt_puzzle(token):
    subdomain = "jindrich-bar--nyt-games-api"
    domain = "apify.actor"
    endpoint = "spelling-bee"
    url = f"https://{subdomain}.{domain}/{endpoint}"
    response = requests.get(url, params={"token": token})
    response.raise_for_status()
    return response.json()

# Load your Google Sheet of Pokémon names
@st.cache_data(ttl=86400)
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
