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

# Custom CSS for the exact look from the screenshot
st.markdown("""
<style>
    /* Dark Theme Base */
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }
    
    [data-testid="stSidebar"] {
        background-color: #161b22;
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: white !important;
    }
    
    .label-text {
        font-size: 0.8rem;
        font-weight: 600;
        color: #8b949e;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
    }

    /* Input Styling */
    .stTextArea textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #0d1117 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: white !important;
    }
    
    /* Result Column Container */
    .results-container {
        background-color: #161b22;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #30363d;
        height: 85vh;
        overflow-y: auto;
    }

    /* Restaurant Card */
    .res-card {
        background-color: #0d1117;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid #30363d;
        position: relative;
    }
    
    .rating-star {
        position: absolute;
        top: 1.2rem;
        right: 1.2rem;
        color: #e3b341;
        font-weight: bold;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .cost-badge {
        background-color: #21262d;
        color: #e3b341;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 0.75rem;
        display: inline-block;
        margin-top: 0.5rem;
        border: 1px solid #30363d;
    }

    /* Buttons */
    .stButton>button {
        border-radius: 20px !important;
        font-weight: 600 !important;
    }
    
    /* Recommendations Button Glow */
    div.stButton > button:first-child[kind="primary"] {
        background: linear-gradient(90deg, #ff7e67 0%, #ff512f 100%) !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(255, 81, 47, 0.4) !important;
        color: white !important;
        padding: 0.6rem 2rem !important;
    }
    
    div.stButton > button:first-child[kind="secondary"] {
        background-color: #21262d !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
    }

    /* Custom labels like in photo */
    .photo-label {
        font-size: 0.7rem;
        background: #21262d;
        padding: 2px 8px;
        border-radius: 4px;
        color: #8b949e;
        border: 1px solid #30363d;
    }
</style>
""", unsafe_allow_html=True)

# Helper for labels
def custom_label(text):
    st.markdown(f'<p class="label-text">{text}</p>', unsafe_allow_html=True)

# Sidebar (Hidden Data Controls)
with st.sidebar:
    st.header("Admin Controls")
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

# --- METADATA FETCHING ---
available_cities = ["All"]
available_cuisines = ["All"]

if use_standalone:
    db_path = root_path / "phase1" / "zomato_phase1.sqlite"
    if db_path.exists():
        meta = get_metadata(db_url=f"sqlite:///{db_path}")
        available_cities += meta.get("cities", [])
        available_cuisines += meta.get("cuisines", [])
else:
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{backend_url}/api/metadata")
            if resp.status_code == 200:
                meta = resp.json()
                available_cities += meta.get("cities", [])
                available_cuisines += meta.get("cuisines", [])
    except: pass

# --- UI IMPLEMENTATION ---
l_col, r_col = st.columns([1, 1], gap="large")

with l_col:
    st.markdown("# Zomato-AI")
    st.markdown("Tell us what you're craving and get tailored restaurant picks powered by Groq.", help="Powered by Groq LPU")
    
    st.write("")
    custom_label("WHAT ARE YOU IN THE MOOD FOR?")
    query = st.text_area("craving", placeholder="pehle pet puja phir kaam duja", label_visibility="collapsed", height=100)
    
    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        custom_label("CITY")
        city = st.selectbox("city_sel", available_cities, label_visibility="collapsed")
    with row1_c2:
        custom_label("CUISINE")
        cuisine = st.selectbox("cuisine_sel", available_cuisines, label_visibility="collapsed")
        
    row2_c1, row2_c2 = st.columns(2)
    with row2_c1:
        custom_label("MINIMUM RATING")
        min_rating_val = st.selectbox("rating_sel", ["Any", "3.0+", "3.5+", "4.0+", "4.5+"], index=0, label_visibility="collapsed")
        # Convert to float
        min_rating = 0.0
        if "3.0" in min_rating_val: min_rating = 3.0
        elif "3.5" in min_rating_val: min_rating = 3.5
        elif "4.0" in min_rating_val: min_rating = 4.0
        elif "4.5" in min_rating_val: min_rating = 4.5
        
    with row2_c2:
        budget_label = f"BUDGET (UP TO {st.session_state.get('budget_slider', 2000)} INR)"
        custom_label(budget_label)
        max_budget = st.slider("budget_slider", 500, 2000, 2000, 100, label_visibility="collapsed", key="budget_slider")
        
    custom_label("HOW MANY RESULTS?")
    limit = st.selectbox("limit_sel", [5, 10, 15, 20], index=1, label_visibility="collapsed")
    
    # Dynamic Status state
    status_text = "Value empty"
    if "results" in st.session_state:
        status_text = "Results received"

    st.write("")
    btn_c1, btn_c2, btn_c3 = st.columns([1.5, 0.8, 1.2])
    with btn_c1:
        generate_btn = st.button("Get recommendations", type="primary", use_container_width=True)
    with btn_c2:
        if st.button("Reset", use_container_width=True):
            if "results" in st.session_state: del st.session_state["results"]
            st.rerun()
    with btn_c3:
        # This will be updated below if generate_btn is clicked
        status_placeholder = st.empty()
        status_placeholder.markdown(f'<p class="photo-label">{status_text}</p>', unsafe_allow_html=True)

with r_col:
    results_placeholder = st.empty()
    with results_placeholder.container():
        st.markdown('<div class="results-container">', unsafe_allow_html=True)
        
        # If button clicked, update status and process
        if generate_btn:
            status_placeholder.markdown('<p class="photo-label">Loading...</p>', unsafe_allow_html=True)
            
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
                    st.session_state["results"] = results
                    status_placeholder.markdown('<p class="photo-label">Results received</p>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error: {str(e)}")
                status_placeholder.markdown('<p class="photo-label">Error</p>', unsafe_allow_html=True)

        # Render Results from Session State
        if "results" in st.session_state:
            res = st.session_state["results"]
            st.markdown(f"### Recommended for you <small style='float:right; font-size:0.8rem; color:#8b949e'>{len(res.get('restaurants', []))} result(s) shown.</small>", unsafe_allow_html=True)
            
            # User choice summary (1-2 lines)
            summary = f"Searching for **{cuisine if cuisine != 'All' else 'any food'}** in **{city if city != 'All' else 'all cities'}** with a budget of ₹{max_budget}."
            st.markdown(f'<p style="color:#e3b341; font-size:0.95rem; margin-bottom:1rem;">{summary}</p>', unsafe_allow_html=True)
            
            st.markdown(f'<p style="color:#8b949e; font-size:0.9rem; line-height:1.4;">{res.get("explanation", "")}</p>', unsafe_allow_html=True)
            
            for rest in res.get("restaurants", []):
                rate_val = rest.get('rate', '').split('/')[0].strip() if '/' in str(rest.get('rate')) else rest.get('rate')
                st.markdown(f"""
                    <div class="res-card">
                        <div class="rating-star">★ {rate_val}</div>
                        <h4 style="margin:0; font-size:1.1rem">{rest.get('name', 'Unknown')}</h4>
                        <p style="color:#8b949e; font-size:0.85rem; margin:0.3rem 0;">
                            {rest.get('cuisines', '')} • {rest.get('location', rest.get('locality', ''))}
                        </p>
                        <div class="cost-badge">Approx Cost: {rest.get('approx_cost(for two people)', 'N/A')} INR</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("### Recommended for you")
            st.info("Hit the 'Get recommendations' button to see AI-powered suggestions here.")
            
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.divider()
st.caption("© 2026 Zomato-AI | Powered by Groq LPU Infrencing")

# Footer
st.divider()
st.caption("Built for manual testing of the Zomato AI Service. Powered by Groq & Zomato Dataset.")
