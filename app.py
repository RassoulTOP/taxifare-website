import streamlit as st
import requests
from datetime import datetime, time
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MeasureControl
import json
import time as time_module

# --- Configuration de la page ---
st.set_page_config(
    page_title="Taxi Fare Predictor 🚖",
    page_icon="🚖",
    layout="wide"
)

# --- Fonction de géocodage (adresse → coordonnées) ---
def geocode_address(address):
    """Convertit une adresse en coordonnées GPS"""
    if not address:
        return None, None, None
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "accept-language": "fr"
        }
        headers = {"User-Agent": "TaxiFarePredictor/1.0"}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                display_name = data[0].get('display_name', address)
                return lat, lon, display_name
        return None, None, None
    except Exception as e:
        return None, None, None

# --- Fonction de géocodage inverse (coordonnées → adresse) ---
def reverse_geocode(lat, lon):
    """Convertit des coordonnées en adresse"""
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "accept-language": "fr"
        }
        headers = {"User-Agent": "TaxiFarePredictor/1.0"}
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'display_name' in data:
                return data['display_name']
        return None
    except:
        return None

# --- Fonction de suggestions d'adresses ---
def get_address_suggestions(query, limit=5):
    """
    Récupère des suggestions d'adresses en temps réel
    Utilise l'API Nominatim de OpenStreetMap
    """
    if not query or len(query) < 3:
        return []
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": limit,
            "addressdetails": 1,
            "accept-language": "fr",
            "countrycodes": "us",  # Limite aux États-Unis
            "bounded": 1,
            "viewbox": "-74.25,40.90,-73.90,40.50"  # Zone New York
        }
        headers = {"User-Agent": "TaxiFarePredictor/1.0"}
        
        response = requests.get(url, params=params, headers=headers, timeout=3)
        
        if response.status_code == 200:
            data = response.json()
            suggestions = []
            for item in data:
                display_name = item.get('display_name', '')
                # Nettoyer l'affichage
                parts = display_name.split(',')
                # Prendre les 3 premières parties
                short_name = ', '.join(parts[:3])
                suggestions.append({
                    'display_name': display_name,
                    'short_name': short_name,
                    'lat': float(item['lat']),
                    'lon': float(item['lon'])
                })
            return suggestions
        return []
    except Exception as e:
        return []

# --- Initialisation des variables de session ---
if 'pickup_lat' not in st.session_state:
    st.session_state.pickup_lat = 40.783282
    st.session_state.pickup_lon = -73.950655
    st.session_state.pickup_address = "New York, États-Unis"
if 'dropoff_lat' not in st.session_state:
    st.session_state.dropoff_lat = 40.748442
    st.session_state.dropoff_lon = -73.984365
    st.session_state.dropoff_address = "New York, États-Unis"
if 'step' not in st.session_state:
    st.session_state.step = 'pickup'
if 'search_mode' not in st.session_state:
    st.session_state.search_mode = 'address'
if 'pickup_suggestions' not in st.session_state:
    st.session_state.pickup_suggestions = []
if 'dropoff_suggestions' not in st.session_state:
    st.session_state.dropoff_suggestions = []
if 'pickup_query' not in st.session_state:
    st.session_state.pickup_query = ""
if 'dropoff_query' not in st.session_state:
    st.session_state.dropoff_query = ""

# --- En-tête ---
st.title("🚖 Prédiction du prix d'une course de taxi")
st.markdown("""
Bienvenue sur l'application de prédiction des prix de taxi à New York !
**Recherchez une adresse** (avec suggestions automatiques) ou **cliquez sur la carte**.
""")

# --- Fonction pour gérer la sélection d'une suggestion ---
def select_pickup_suggestion(lat, lon, address):
    st.session_state.pickup_lat = lat
    st.session_state.pickup_lon = lon
    st.session_state.pickup_address = address
    st.session_state.pickup_query = address
    st.session_state.pickup_suggestions = []
    st.rerun()

def select_dropoff_suggestion(lat, lon, address):
    st.session_state.dropoff_lat = lat
    st.session_state.dropoff_lon = lon
    st.session_state.dropoff_address = address
    st.session_state.dropoff_query = address
    st.session_state.dropoff_suggestions = []
    st.rerun()

# --- Barre latérale ---
with st.sidebar:
    st.header("📋 Paramètres de la course")
    
    # Mode de recherche
    st.subheader("🔍 Mode de recherche")
    search_mode = st.radio(
        "Comment définir les positions ?",
        ["📍 Rechercher une adresse", "👆 Cliquer sur la carte"],
        index=0 if st.session_state.search_mode == 'address' else 1,
        key="search_mode_radio"
    )
    
    if search_mode == "📍 Rechercher une adresse":
        st.session_state.search_mode = 'address'
    else:
        st.session_state.search_mode = 'click'
    
    st.divider()
    
    # --- MODE RECHERCHE D'ADRESSE AVEC SUGGESTIONS ---
    if st.session_state.search_mode == 'address':
        st.subheader("🔎 Recherche d'adresse")
        st.caption("💡 Tapez au moins 3 caractères pour voir les suggestions")
        
        # --- PRISE EN CHARGE ---
        st.markdown("**🚩 Prise en charge**")
        
        # Champ de recherche
        pickup_query = st.text_input(
            "Adresse de départ",
            value=st.session_state.pickup_query,
            placeholder="Ex: Times Square, New York",
            key="pickup_search_input",
            help="Tapez une adresse pour voir les suggestions"
        )
        
        # Mettre à jour la requête
        if pickup_query != st.session_state.pickup_query:
            st.session_state.pickup_query = pickup_query
            if len(pickup_query) >= 3:
                with st.spinner("Recherche..."):
                    suggestions = get_address_suggestions(pickup_query + ", New York")
                    st.session_state.pickup_suggestions = suggestions
            else:
                st.session_state.pickup_suggestions = []
        
        # Afficher les suggestions
        if st.session_state.pickup_suggestions:
            st.write("**Suggestions :**")
            for i, suggestion in enumerate(st.session_state.pickup_suggestions):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"📍 {suggestion['short_name']}")
                with col2:
                    if st.button("✅", key=f"pickup_sug_{i}"):
                        select_pickup_suggestion(
                            suggestion['lat'],
                            suggestion['lon'],
                            suggestion['display_name']
                        )
            st.divider()
        
        # Afficher l'adresse sélectionnée
        if st.session_state.pickup_address:
            st.success(f"📍 {st.session_state.pickup_address[:60]}...")
        
        st.divider()
        
        # --- DÉPOSE ---
        st.markdown("**🏁 Dépose**")
        
        dropoff_query = st.text_input(
            "Adresse d'arrivée",
            value=st.session_state.dropoff_query,
            placeholder="Ex: Central Park, New York",
            key="dropoff_search_input",
            help="Tapez une adresse pour voir les suggestions"
        )
        
        # Mettre à jour la requête
        if dropoff_query != st.session_state.dropoff_query:
            st.session_state.dropoff_query = dropoff_query
            if len(dropoff_query) >= 3:
                with st.spinner("Recherche..."):
                    suggestions = get_address_suggestions(dropoff_query + ", New York")
                    st.session_state.dropoff_suggestions = suggestions
            else:
                st.session_state.dropoff_suggestions = []
        
        # Afficher les suggestions
        if st.session_state.dropoff_suggestions:
            st.write("**Suggestions :**")
            for i, suggestion in enumerate(st.session_state.dropoff_suggestions):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.caption(f"📍 {suggestion['short_name']}")
                with col2:
                    if st.button("✅", key=f"dropoff_sug_{i}"):
                        select_dropoff_suggestion(
                            suggestion['lat'],
                            suggestion['lon'],
                            suggestion['display_name']
                        )
            st.divider()
        
        # Afficher l'adresse sélectionnée
        if st.session_state.dropoff_address:
            st.success(f"📍 {st.session_state.dropoff_address[:60]}...")
    
    # --- MODE CLIC SUR LA CARTE ---
    else:
        st.subheader("🎯 Mode sélection sur carte")
        mode = st.radio(
            "Choisir le point à placer :",
            ["🚩 Prise en charge", "🏁 Dépose"],
            index=0 if st.session_state.step == 'pickup' else 1,
            key="mode_selection"
        )
        
        if mode == "🚩 Prise en charge":
            st.session_state.step = 'pickup'
            st.info("👆 Clique sur la carte pour définir la **prise en charge**")
        else:
            st.session_state.step = 'dropoff'
            st.info("👆 Clique sur la carte pour définir la **dépose**")
    
    st.divider()
    
    # --- Date et heure ---
    st.subheader("📅 Date et heure")
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input(
            "Date",
            value=datetime.now().date(),
            format="DD/MM/YYYY"
        )
    with col2:
        heure = st.time_input(
            "Heure",
            value=datetime.now().time()
        )
    
    date_time = datetime.combine(date, heure)
    st.caption(f"📆 {date_time.strftime('%d/%m/%Y à %H:%M')}")
    
    st.divider()
    
    # --- Coordonnées actuelles ---
    st.subheader("📍 Coordonnées actuelles")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "🚩 Prise en charge",
            f"{st.session_state.pickup_lat:.6f}",
            f"{st.session_state.pickup_lon:.6f}",
            help="Latitude / Longitude"
        )
        st.caption(f"📍 {st.session_state.pickup_address[:30]}...")
    with col2:
        st.metric(
            "🏁 Dépose",
            f"{st.session_state.dropoff_lat:.6f}",
            f"{st.session_state.dropoff_lon:.6f}",
            help="Latitude / Longitude"
        )
        st.caption(f"📍 {st.session_state.dropoff_address[:30]}...")
    
    st.divider()
    
    # --- Passagers ---
    st.subheader("👥 Passagers")
    passenger_count = st.number_input(
        "Nombre de passagers",
        min_value=1,
        max_value=8,
        value=1,
        step=1
    )
    
    # --- Réinitialisation ---
    if st.button("🔄 Réinitialiser", use_container_width=True):
        st.session_state.pickup_lat = 40.783282
        st.session_state.pickup_lon = -73.950655
        st.session_state.pickup_address = "New York, États-Unis"
        st.session_state.dropoff_lat = 40.748442
        st.session_state.dropoff_lon = -73.984365
        st.session_state.dropoff_address = "New York, États-Unis"
        st.session_state.pickup_query = ""
        st.session_state.dropoff_query = ""
        st.session_state.pickup_suggestions = []
        st.session_state.dropoff_suggestions = []
        st.rerun()

# --- Colonnes principales ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺 Carte interactive")
    
    # Créer la carte
    center_lat = (st.session_state.pickup_lat + st.session_state.dropoff_lat) / 2
    center_lon = (st.session_state.pickup_lon + st.session_state.dropoff_lon) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
        attr='Google Maps'
    )
    
    # Marqueur prise en charge
    folium.Marker(
        [st.session_state.pickup_lat, st.session_state.pickup_lon],
        popup=f"""
        <b>🚩 Prise en charge</b><br>
        {st.session_state.pickup_address}<br>
        Lat: {st.session_state.pickup_lat:.6f}<br>
        Lon: {st.session_state.pickup_lon:.6f}
        """,
        tooltip="🚩 Prise en charge",
        icon=folium.Icon(color='green', icon='play', prefix='fa')
    ).add_to(m)
    
    # Marqueur dépose
    folium.Marker(
        [st.session_state.dropoff_lat, st.session_state.dropoff_lon],
        popup=f"""
        <b>🏁 Dépose</b><br>
        {st.session_state.dropoff_address}<br>
        Lat: {st.session_state.dropoff_lat:.6f}<br>
        Lon: {st.session_state.dropoff_lon:.6f}
        """,
        tooltip="🏁 Dépose",
        icon=folium.Icon(color='red', icon='stop', prefix='fa')
    ).add_to(m)
    
    # Ligne du trajet
    folium.PolyLine(
        locations=[
            [st.session_state.pickup_lat, st.session_state.pickup_lon],
            [st.session_state.dropoff_lat, st.session_state.dropoff_lon]
        ],
        color='blue',
        weight=5,
        opacity=0.7,
        popup='Trajet'
    ).add_to(m)
    
    # Cercles
    folium.Circle(
        [st.session_state.pickup_lat, st.session_state.pickup_lon],
        radius=50, color='green', fill=True, fillOpacity=0.2
    ).add_to(m)
    folium.Circle(
        [st.session_state.dropoff_lat, st.session_state.dropoff_lon],
        radius=50, color='red', fill=True, fillOpacity=0.2
    ).add_to(m)
    
    MeasureControl().add_to(m)
    
    # Afficher la carte
    st_data = st_folium(m, width=700, height=500, key="map_click")
    
    # Traiter les clics
    if st.session_state.search_mode == 'click' and st_data and st_data.get('last_clicked'):
        lat = st_data['last_clicked']['lat']
        lng = st_data['last_clicked']['lng']
        address = reverse_geocode(lat, lng)
        
        if st.session_state.step == 'pickup':
            st.session_state.pickup_lat = lat
            st.session_state.pickup_lon = lng
            if address:
                st.session_state.pickup_address = address
                st.session_state.pickup_query = address
            st.session_state.step = 'dropoff'
        else:
            st.session_state.dropoff_lat = lat
            st.session_state.dropoff_lon = lng
            if address:
                st.session_state.dropoff_address = address
                st.session_state.dropoff_query = address
            st.session_state.step = 'pickup'
        st.rerun()
    
    # Adresses
    col1_1, col1_2 = st.columns(2)
    with col1_1:
        st.caption(f"🚩 **Départ:** {st.session_state.pickup_address[:50]}...")
        st.caption(f"📍 ({st.session_state.pickup_lat:.6f}, {st.session_state.pickup_lon:.6f})")
    with col1_2:
        st.caption(f"🏁 **Arrivée:** {st.session_state.dropoff_address[:50]}...")
        st.caption(f"📍 ({st.session_state.dropoff_lat:.6f}, {st.session_state.dropoff_lon:.6f})")
    
    # Distance
    from math import radians, sin, cos, sqrt, asin
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return R * c
    
    distance_km = haversine(
        st.session_state.pickup_lat,
        st.session_state.pickup_lon,
        st.session_state.dropoff_lat,
        st.session_state.dropoff_lon
    )
    st.caption(f"📏 Distance estimée: **{distance_km:.2f} km**")

with col2:
    st.subheader("💰 Estimation du prix")
    
    st.info(f"""
    📅 {date_time.strftime('%d/%m/%Y %H:%M')}
    👥 {passenger_count} passager{'s' if passenger_count > 1 else ''}
    📏 {distance_km:.1f} km
    """)
    
    # Paramètres
    pickup_datetime_str = date_time.strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "pickup_datetime": pickup_datetime_str,
        "pickup_longitude": st.session_state.pickup_lon,
        "pickup_latitude": st.session_state.pickup_lat,
        "dropoff_longitude": st.session_state.dropoff_lon,
        "dropoff_latitude": st.session_state.dropoff_lat,
        "passenger_count": passenger_count
    }
    
    # Choix API
    use_local = st.toggle("🔧 API locale", value=False)
    url = "http://localhost:8000/predict" if use_local else "https://taxifare.lewagon.ai/predict"
    
    if st.button("🚀 Prédire le prix", use_container_width=True, type="primary"):
        with st.spinner("Calcul en cours..."):
            try:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    prediction = response.json().get("fare") or response.json().get("prediction")
                    if prediction:
                        st.balloons()
                        st.success(f"💰 **${prediction:.2f}**")
                        st.metric("Prix estimé", f"${prediction:.2f}", f"{prediction - 15:.2f} $ vs moyenne")
                        if prediction < 15:
                            st.info("✅ Prix très compétitif !")
                            st.progress(0.3)
                        elif prediction < 30:
                            st.info("👍 Prix raisonnable")
                            st.progress(0.6)
                        else:
                            st.warning("⚠️ Prix élevé")
                            st.progress(0.9)
                else:
                    st.error(f"❌ Erreur {response.status_code}")
            except Exception as e:
                st.error(f"❌ Erreur: {str(e)}")

# --- Détails ---
with st.expander("🔧 Détails techniques"):
    st.json(params)
    st.caption(f"URL: {url}")

# --- Exemples ---
with st.expander("📍 Charger un exemple"):
    cols = st.columns(3)
    examples = [
        ("🗽 Times Square → Central Park", 40.7580, -73.9855, 40.7829, -73.9654),
        ("✈️ JFK → Manhattan", 40.6413, -73.7781, 40.7589, -73.9851),
        ("🌉 Brooklyn → Statue", 40.7061, -73.9969, 40.6892, -74.0445)
    ]
    for i, (label, lat1, lon1, lat2, lon2) in enumerate(examples):
        with cols[i]:
            if st.button(label, use_container_width=True):
                st.session_state.pickup_lat = lat1
                st.session_state.pickup_lon = lon1
                st.session_state.dropoff_lat = lat2
                st.session_state.dropoff_lon = lon2
                st.rerun()

# --- Pied de page ---
st.divider()
st.caption("🚖 Taxi Fare Predictor - Le Wagon © 2026 | Powered by OpenStreetMap Nominatim")