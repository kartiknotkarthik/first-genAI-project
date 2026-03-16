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

# Custom CSS for Dashboard "Smart Home" Style with Zomato Branding
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #F7F7F7;
    }
    
    /* Global Card Style */
    .block-card {
        background: white;
        border-radius: 24px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        border: none;
    }

    /* Left Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111111 !important;
        min-width: 350px !important;
    }
    
    .sidebar-header {
        background: linear-gradient(135deg, #E23744 0%, #FF5A66 100%);
        padding: 2.5rem 1.5rem;
        border-radius: 0 0 30px 30px;
        margin: -1rem -1rem 2rem -1rem;
        color: white;
    }

    /* Pill Buttons for Categories */
    .pill {
        background-color: white;
        color: #111111;
        padding: 8px 24px;
        border-radius: 50px;
        border: 1px solid #EEE;
        font-weight: 600;
        display: inline-block;
        margin: 4px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .pill.active {
        background-color: #E23744;
        color: white;
        border-color: #E23744;
    }

    /* Restaurant "Device" Blocks */
    .rest-block {
        background-color: #F0F0F0;
        border-radius: 20px;
        padding: 1.2rem;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border: 2px solid transparent;
        transition: all 0.3s;
    }
    .rest-block:hover {
        background-color: white;
        border-color: #E23744;
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(226, 55, 68, 0.1);
    }
    .rest-block.active {
        background: linear-gradient(135deg, #E23744 0%, #FF5A66 100%);
        color: white !important;
    }
    .rest-block.active p, .rest-block.active h4 {
        color: white !important;
    }

    /* Rating Circle */
    .rating-circle {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 4px solid #FFD700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
        font-weight: bold;
        font-size: 1.2rem;
        color: #111111;
        background: white;
    }

    /* Utility */
    .stButton>button {
        border-radius: 12px !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar - Dashboard Left Pane
with st.sidebar:
    st.markdown("""
        <div class="sidebar-header">
            <h4 style="margin:0; opacity:0.8">hi hunger!</h4>
            <h1 style="margin:0; font-size:2.4rem">Welcome to <br>Zomato AI.</h1>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("Last Search Preference")
    
    # Simple Circular Gauge visualization for Budget
    st.markdown(f"""
        <div style="text-align:center; padding: 1rem; background:#222; border-radius:30px; margin-bottom: 2rem;">
            <p style="color:#888; margin:0">MAX BUDGET</p>
            <h2 style="color:#FFD700; margin:0.5rem 0">₹{max_budget if 'max_budget' in locals() else '2000'}</h2>
            <div style="width:100%; height:4px; background:#444; border-radius:2px">
                <div style="width:{((max_budget if 'max_budget' in locals() else 2000)-500)/1500*100}%; height:100%; background:#E23744; border-radius:2px"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Standalone manager
    use_standalone = st.toggle("Standalone Mode", value=STANDALONE_SUPPORTED)
    if use_standalone:
        db_path = root_path / "phase1" / "zomato_phase1.sqlite"
        if not db_path.exists():
            if st.button("Download & Initialize Data", use_container_width=True):
                with st.spinner("Initializing..."):
                    try:
                        sys.path.append(str(root_path / "phase1"))
                        from zomato_ingestion.ingest import ingest_dataset
                        ingest_dataset()
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
    else:
        backend_url = st.text_input("Backend URL", value="http://127.0.0.1:8000")

# Main Application Logic
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
    except: pass

# Top Search Bar
st.markdown("### Search Preferences")
q_col1, q_col2 = st.columns([3, 1])
with q_col1:
    query = st.text_input("What are you craving?", placeholder="e.g. Best pizza in Bangalore...", label_visibility="collapsed")
with q_col2:
    generate_btn = st.button("Find Restaurants", type="primary", use_container_width=True)

# Main Dashboard Content
content_left, content_right = st.columns([1.2, 3], gap="large")

with content_left:
    st.markdown("#### MY FILTERS")
    with st.container(border=True):
        city = st.selectbox("Current City", available_cities)
        cuisine = st.selectbox("Favorite Cuisine", available_cuisines)
        min_rating = st.slider("Minimum Rating", 0.0, 5.0, 3.5, 0.1)
        max_budget = st.slider("Max Budget (INR)", 500, 2000, 2000, 100)
        limit = st.select_slider("Results Limit", options=[5, 10, 15, 20], value=10)
    
    st.markdown("#### RATING GAUGE")
    st.markdown(f"""
        <div class="rating-circle">
            {min_rating}★
        </div>
    """, unsafe_allow_html=True)

with content_right:
    st.markdown("#### DISCOVERY BLOCKS")
    
    if generate_btn:
        parts = []
        if query: parts.append(query)
        if city != "All": parts.append(f"in city {city}")
        if cuisine != "All": parts.append(f"serving {cuisine}")
        if min_rating > 0: parts.append(f"at least {min_rating} stars")
        parts.append(f"budget up to {max_budget} INR")
        user_message = ", ".join(parts)            
        
        try:
            results = {}
            if use_standalone:
                import groq
                g_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
                from orchestrator.groq_client import GroqClient
                client = GroqClient(api_key=g_key)
                req = RecommendationRequest(
                    city=city if city != "All" else None,
                    cuisine=cuisine if cuisine != "All" else None,
                    min_rating=min_rating,
                    max_price_range=max_budget,
                    limit=limit
                )
                db_uri = f"sqlite:///{db_path}"
                res_list = get_recommendations(req, db_url=db_uri)
                explanation = generate_explanation(user_message, res_list, groq_client=client)
                results = {"restaurants": res_list, "explanation": explanation}
            else:
                payload = {"user_message": user_message, "limit": limit}
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(f"{backend_url}/api/recommendations", json=payload)
                if response.status_code == 200: results = response.json()

            if results:
                st.markdown(f'<div class="explanation-box"><b>AI Reasoning:</b><br>{results.get("explanation", "")}</div>', unsafe_allow_html=True)
                
                # Grid of Blocks
                r_cols = st.columns(2)
                for idx, rest in enumerate(results.get("restaurants", [])):
                    rate_val = rest.get('rate', '').split('/')[0].strip() if '/' in str(rest.get('rate')) else rest.get('rate')
                    with r_cols[idx % 2]:
                        # Cycle color logic: first one is "active" (red gradient)
                        is_active = "active" if idx == 0 else ""
                        st.markdown(f"""
                        <div class="rest-block {is_active}">
                            <div>
                                <h4 style="margin:0; font-weight:bold">{rest.get('name', 'Unknown')}</h4>
                                <p style="margin:0.2rem 0; font-size:0.8rem; opacity:0.8">{rest.get('cuisines', '')}</p>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center">
                                <span style="font-weight:bold">₹{rest.get('approx_cost(for two people)', 'N/A')}</span>
                                <span class="rating-badge">★ {rate_val}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.write("") # Spacer
        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.info("Choose your filters and click 'Find Restaurants' to see your Discovery Blocks.")

# Footer
st.divider()
st.caption("Built for manual testing of the Zomato AI Service. Powered by Groq & Zomato Dataset.")
