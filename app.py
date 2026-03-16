import streamlit as st
import httpx
import json
import os
from dotenv import load_dotenv

# Load environment variables if present
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Zomato AI - Intelligent Restaurant Discovery",
    page_icon="🍴",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a premium look
st.markdown("""
<style>
    :root {
        --primary-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        --card-bg: #1e293b;
    }
    
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    .stTitle {
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        background: var(--primary-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem !important;
        padding-bottom: 2rem;
    }
    
    .restaurant-card {
        background-color: var(--card-bg);
        border-radius: 1rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid #334155;
        transition: transform 0.2s, border-color 0.2s;
    }
    
    .restaurant-card:hover {
        transform: translateY(-4px);
        border-color: #6366f1;
    }
    
    .rating-badge {
        background: var(--primary-gradient);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 0.5rem;
        font-weight: bold;
        display: inline-block;
    }
    
    .price-tag {
        color: #94a3b8;
        font-size: 0.9rem;
    }
    
    .explanation-box {
        background-color: #1e293b;
        border-left: 4px solid #6366f1;
        padding: 1.5rem;
        border-radius: 0 0.5rem 0.5rem 0;
        margin-bottom: 2rem;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# App branding
st.title("Zomato AI")
st.markdown("### Discover your next favorite meal with AI-powered recommendations")

# Backend API Configuration
# On Streamlit Cloud, the user will need to provide the public URL of the backend
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/bd/Zomato_Logo.svg", width=100)
    st.header("Settings")
    
    # Prioritize st.secrets for BACKEND_URL
    default_backend = "http://localhost:8000"
    if "BACKEND_URL" in st.secrets:
        default_backend = st.secrets["BACKEND_URL"]
    
    backend_url = st.text_input("Backend API URL", value=default_backend, help="Endpoint of your FastAPI service")
    
    # Check if we are likely on cloud and using localhost
    if "localhost" in backend_url and not os.path.exists(".git"): # Heuristic for cloud
        st.warning("⚠️ You appear to be running on the cloud but targeting 'localhost'. This will not work unless you use a tunnel like ngrok.")

    st.divider()
    st.header("Search Filters")
    
    # Try to fetch metadata for dropdowns
    available_cities = ["All"]
    available_cuisines = ["All"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{backend_url}/api/metadata")
            if resp.status_code == 200:
                meta = resp.json()
                available_cities += meta.get("cities", [])
                available_cuisines += meta.get("cuisines", [])
            else:
                st.caption(f"⚠️ Backend returned status {resp.status_code}")
    except Exception as e:
        st.caption(f"⚠️ Could not fetch metadata: {str(e)}")
        st.info("Manual typing enabled.")

    city = st.selectbox("Select City", available_cities)
    cuisine = st.selectbox("Select Cuisine", available_cuisines)
    
    min_rating = st.slider("Minimum Rating", 0.0, 5.0, 3.5, 0.1)
    max_budget = st.slider("Max Budget for Two (INR)", 500, 2000, 2000, 100)
    limit = st.select_slider("Results Limit", options=[5, 10, 15, 20], value=10)

# Main query area
query = st.text_area("What are you in the mood for?", placeholder="e.g., I want a rooftop place with great pasta in Delhi, preferably with high ratings.")

if st.button("Generate Recommendations", type="primary", use_container_width=True):
    if not query and city == "All" and cuisine == "All":
        st.warning("Please provide some search criteria or a query.")
    else:
        # Construct the user message
        parts = []
        if query: parts.append(query)
        if city != "All": parts.append(f"in city {city}")
        if cuisine != "All": parts.append(f"serving {cuisine}")
        if min_rating > 0: parts.append(f"at least {min_rating} stars")
        parts.append(f"budget up to {max_budget} INR")
        
        user_message = ", ".join(parts)
        
        with st.spinner("🧠 Groq AI is analyzing the Zomato dataset..."):
            try:
                payload = {
                    "user_message": user_message,
                    "limit": limit
                }
                
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(f"{backend_url}/api/recommendations", json=payload)
                    
                if response.status_code == 200:
                    data = response.json()
                    
                    # Display AI Explanation
                    st.markdown("#### 🤖 Why these recommendations?")
                    st.markdown(f'<div class="explanation-box">{data.get("explanation", "No explanation provided.")}</div>', unsafe_allow_html=True)
                    
                    # Display Restaurants
                    st.markdown("#### 📍 Top Match Restaurants")
                    
                    restaurants = data.get("restaurants", [])
                    if not restaurants:
                        st.info("No restaurants found matching your criteria. Try widening your search!")
                    else:
                        for rest in restaurants:
                            # Helper to format rating
                            rate_val = rest.get('rate', '')
                            if isinstance(rate_val, str) and '/' in rate_val:
                                rate_val = rate_val.split('/')[0].strip()
                            
                            with st.container():
                                st.markdown(f"""
                                <div class="restaurant-card">
                                    <div style="display: flex; justify-content: space-between; align-items: start;">
                                        <div>
                                            <h3 style="margin: 0;">{rest.get('name', 'Unknown Restaurant')}</h3>
                                            <p style="color: #6366f1; margin: 0.2rem 0;">{rest.get('cuisines', 'Various Cuisines')}</p>
                                            <p class="price-tag">📍 {rest.get('location', rest.get('locality', 'Various'))}, {rest.get('city', '')}</p>
                                        </div>
                                        <div style="text-align: right;">
                                            <div class="rating-badge">⭐ {rate_val if rate_val else 'N/A'}</div>
                                            <p style="margin-top: 0.5rem; font-weight: bold;">₹{rest.get('approx_cost(for two people)', 'N/A')}</p>
                                            <p style="font-size: 0.8rem; color: #94a3b8;">(for two)</p>
                                        </div>
                                    </div>
                                    <hr style="border: 0.5px solid #334155; margin: 1rem 0;">
                                    <div style="font-size: 0.9rem;">
                                        <span>🛒 Order Online: <b>{rest.get('online_order', 'N/A')}</b></span>
                                        <span style="margin-left: 2rem;">📅 Book Table: <b>{rest.get('book_table', 'N/A')}</b></span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                else:
                    st.error(f"Error from backend API: {response.status_code}")
                    st.json(response.json())
            except Exception as e:
                st.error(f"Could not connect to the backend API at {backend_url}. Please ensure your FastAPI server is running and accessible.")
                st.exception(e)

# Footer
st.divider()
st.caption("Built for manual testing of the Zomato AI Service. Powered by Groq & Zomato Dataset.")
