import streamlit as st
import httpx
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project phases to path for standalone imports
root_path = Path(__file__).parent
sys.path.append(str(root_path / "phase2"))
sys.path.append(str(root_path / "phase3"))

try:
    from recommender.engine import RecommendationRequest, get_recommendations, get_metadata
    from orchestrator.orchestrator import recommend, parse_intent, generate_explanation
    STANDALONE_SUPPORTED = True
except ImportError:
    STANDALONE_SUPPORTED = False

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Zomato AI - Intelligent Restaurant Discovery",
    page_icon="🍴",
    layout="wide"
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
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/b/bd/Zomato_Logo.svg", width=100)
    st.header("Settings")
    
    # Mode selection
    use_standalone = st.toggle("Standalone Mode (Direct DB Access)", value=STANDALONE_SUPPORTED)
    
    if not use_standalone:
        backend_url = st.text_input("Backend API URL", value="http://127.0.0.1:8000")
    else:
        db_path = root_path / "phase1" / "zomato_phase1.sqlite"
        if not db_path.exists():
            st.error("📂 Database not found!")
            if st.button("Download & Initialize Data"):
                with st.spinner("Downloading Zomato dataset (this may take a minute)..."):
                    try:
                        # Call the ingestion logic directly
                        sys.path.append(str(root_path / "phase1"))
                        from zomato_ingestion.ingest import ingest_dataset
                        ingest_dataset()
                        st.success("Database initialized!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to seed data: {e}")
        else:
            st.success("✅ Database Connected")

    st.divider()
    st.header("Search Filters")
    
    # Metadata fetching
    available_cities = ["All"]
    available_cuisines = ["All"]
    
    if use_standalone and db_path.exists():
        meta = get_metadata(db_url=f"sqlite:///{db_path}")
        available_cities += meta.get("cities", [])
        available_cuisines += meta.get("cuisines", [])
    elif not use_standalone:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{backend_url}/api/metadata")
                if resp.status_code == 200:
                    meta = resp.json()
                    available_cities += meta.get("cities", [])
                    available_cuisines += meta.get("cuisines", [])
        except:
            st.caption("⚠️ API Offline. Using manual inputs.")

    city = st.selectbox("Select City", available_cities)
    cuisine = st.selectbox("Select Cuisine", available_cuisines)
    min_rating = st.slider("Minimum Rating", 0.0, 5.0, 3.5, 0.1)
    max_budget = st.slider("Max Budget for Two (INR)", 500, 2000, 2000, 100)
    limit = st.select_slider("Results Limit", options=[5, 10, 15, 20], value=10)
    
    generate_btn = st.button("Generate Recommendations", type="primary", use_container_width=True)

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
                    results = {}
                    if use_standalone:
                        # Direct call to logic
                        import groq
                        # Use streamlit secrets if available
                        g_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
                        from orchestrator.groq_client import GroqClient
                        client = GroqClient(api_key=g_key)
                        
                        # Phase 2 request
                        req = RecommendationRequest(
                            city=city if city != "All" else None,
                            cuisine=cuisine if cuisine != "All" else None,
                            min_rating=min_rating,
                            max_price_range=max_budget,
                            limit=limit
                        )
                        
                        # Phase 3 logic
                        db_uri = f"sqlite:///{db_path}"
                        res_list = get_recommendations(req, db_url=db_uri)
                        explanation = generate_explanation(user_message, res_list, groq_client=client)
                        results = {"restaurants": res_list, "explanation": explanation}
                    else:
                        payload = {"user_message": user_message, "limit": limit}
                        with httpx.Client(timeout=60.0) as client:
                            response = client.post(f"{backend_url}/api/recommendations", json=payload)
                        if response.status_code == 200:
                            results = response.json()
                        else:
                            st.error(f"Backend Error: {response.status_code}")

                    if results:
                        # Display AI Explanation
                        st.markdown("#### 🤖 Why these recommendations?")
                        st.markdown(f'<div class="explanation-box">{results.get("explanation", "No explanation.")}</div>', unsafe_allow_html=True)
                        
                        # Display Restaurants
                        st.markdown("#### 📍 Top Match Restaurants")
                        for rest in results.get("restaurants", []):
                            rate_val = rest.get('rate', '')
                            if isinstance(rate_val, str) and '/' in rate_val:
                                rate_val = rate_val.split('/')[0].strip()
                            
                            with st.container():
                                st.markdown(f"""
                                <div class="restaurant-card">
                                    <div style="display: flex; justify-content: space-between; align-items: start;">
                                        <div>
                                            <h3 style="margin: 0;">{rest.get('name', 'Unknown')}</h3>
                                            <p style="color: #6366f1; margin: 0.2rem 0;">{rest.get('cuisines', 'Cuisine')}</p>
                                            <p class="price-tag">📍 {rest.get('location', rest.get('locality', ''))}, {rest.get('city', '')}</p>
                                        </div>
                                        <div style="text-align: right;">
                                            <div class="rating-badge">⭐ {rate_val if rate_val else 'N/A'}</div>
                                            <p style="margin-top: 0.5rem; font-weight: bold;">₹{rest.get('approx_cost(for two people)', 'N/A')}</p>
                                        </div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Service Error: {str(e)}")
                    st.exception(e)
    else:
        st.info("👈 Enter your preferences on the left and click 'Generate Recommendations' to see results here.")

# Footer
st.divider()
st.caption("Built for manual testing of the Zomato AI Service. Powered by Groq & Zomato Dataset.")
