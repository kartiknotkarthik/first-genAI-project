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
    # 127.0.0.1 is often more stable than 'localhost' in Python network calls
    default_backend = "http://127.0.0.1:8000"
    if "BACKEND_URL" in st.secrets:
        default_backend = st.secrets["BACKEND_URL"]
    
    backend_url = st.text_input("Backend API URL", value=default_backend, help="Endpoint of your FastAPI service")
    
    # Check if we are likely on cloud and using a local address
    is_local_address = "127.0.0.1" in backend_url or "localhost" in backend_url
    if is_local_address and not os.path.exists(".git"): # Heuristic for cloud environment
        st.error("🚫 **Cloud Connection Error**")
        st.info("You are running on **Streamlit Cloud**, but your API URL is set to a local address. The cloud browser cannot see your laptop's 'localhost'.\n\n**To fix this:**\n1. Use a tool like **ngrok** on your laptop: `ngrok http 8000`\n2. Copy the public link and paste it above.")

    st.divider()
    st.header("Search Filters")
    
    # Try to fetch metadata for dropdowns
    available_cities = ["All"]
    available_cuisines = ["All"]
    try:
        # Use a longer timeout and specific transport if needed
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(f"{backend_url}/api/metadata")
            if resp.status_code == 200:
                meta = resp.json()
                available_cities += meta.get("cities", []) if isinstance(meta.get("cities"), list) else []
                available_cuisines += meta.get("cuisines", []) if isinstance(meta.get("cuisines"), list) else []
                st.success("✅ Connected to Backend")
            else:
                st.caption(f"⚠️ Backend returned status {resp.status_code}")
    except Exception as e:
        error_str = str(e)
        if "99" in error_str or "address" in error_str.lower():
            st.error("🚨 **Network Address Error (Errno 99)**")
            st.warning("The app is unable to reach the backend at this address. If you're on a corporate network or Streamlit Cloud, localhost/127.0.0.1 won't work.")
        else:
            st.caption(f"⚠️ Connection Status: {error_str}")
        st.info("Manual typing enabled in fields below.")

# Main Layout
col_input, col_results = st.columns([1, 1.5], gap="large")

with col_input:
    st.subheader("What are you in the mood for?")
    query = st.text_area(
        "Describe your craving...", 
        placeholder="e.g., I want a rooftop place with great pasta in Delhi, preferably with high ratings.",
        height=150,
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.subheader("Fine-tune Filters")
    city = st.selectbox("Select City", available_cities)
    cuisine = st.selectbox("Select Cuisine", available_cuisines)
    min_rating = st.slider("Minimum Rating", 0.0, 5.0, 3.5, 0.1)
    max_budget = st.slider("Max Budget for Two (INR)", 500, 2000, 2000, 100)
    limit = st.select_slider("Results Limit", options=[5, 10, 15, 20], value=10)
    
    generate_btn = st.button("Generate Recommendations", type="primary", use_container_width=True)

with col_results:
    if generate_btn:
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
    else:
        st.info("👈 Enter your preferences on the left and click 'Generate Recommendations' to see results here.")

# Footer
st.divider()
st.caption("Built for manual testing of the Zomato AI Service. Powered by Groq & Zomato Dataset.")
