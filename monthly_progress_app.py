# monthly_progress_app
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import json
import plotly.express as px
import plotly.graph_objects as go
from firebase_config import initialize_firebase, get_firestore_client
import firebase_admin
from firebase_admin import firestore, auth
import base64

# Page configuration
st.set_page_config(
    page_title="GWD Monthly Progress Monitoring",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Main styling */
    .main-header {
        background: linear-gradient(135deg, #1e5799 0%, #207cca 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    
    .district-card {
        background: #f0f8ff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #1e5799;
        margin-bottom: 10px;
    }
    
    .approved-badge {
        background-color: #28a745;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        display: inline-block;
        margin-left: 10px;
    }
    
    .pending-badge {
        background-color: #ffc107;
        color: #212529;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        display: inline-block;
        margin-left: 10px;
    }
    
    .rejected-badge {
        background-color: #dc3545;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        display: inline-block;
        margin-left: 10px;
    }
    
    .kpi-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        margin: 5px;
    }
    
    .data-table {
        font-size: 12px;
    }
    
    /* Form styling */
    .stNumberInput input, .stTextInput input, .stTextArea textarea {
        font-size: 14px !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize Firebase
try:
    db, auth_module = initialize_firebase()
except:
    st.warning("Firebase not initialized. Running in demo mode.")
    db = None

# ==================== SESSION STATE ====================
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_id = None
    st.session_state.user_district = None
    st.session_state.current_page = "login"

if 'form_data' not in st.session_state:
    st.session_state.form_data = {}

# ==================== DATA STRUCTURE ====================
# This structure can be easily replaced later
MONTHLY_CATEGORIES = {
    "Surveys & Investigations": {
        "description": "Geophysical surveys, hydrogeological studies",
        "fields": [
            {"id": "surveys_conducted", "label": "Number of surveys conducted", "type": "number", "unit": "nos"},
            {"id": "area_covered", "label": "Area covered", "type": "number", "unit": "sq km"},
            {"id": "surveys_type", "label": "Type of surveys", "type": "dropdown", 
             "options": ["VES", "GPR", "Electrical", "Magnetic", "Others"]},
            {"id": "surveys_remarks", "label": "Remarks", "type": "text"}
        ]
    },
    "Drilling Works": {
        "description": "Borewell drilling, piezometer installation",
        "fields": [
            {"id": "borewells_completed", "label": "Bore wells completed", "type": "number", "unit": "nos"},
            {"id": "average_depth", "label": "Average depth achieved", "type": "number", "unit": "meters"},
            {"id": "drilling_expenditure", "label": "Expenditure incurred", "type": "number", "unit": "₹"},
            {"id": "drilling_type", "label": "Type of drilling", "type": "dropdown",
             "options": ["Rotary", "Percussion", "DTH", "Auger"]},
            {"id": "drilling_remarks", "label": "Remarks", "type": "text"}
        ]
    },
    "Monitoring Activities": {
        "description": "Groundwater level monitoring, quality assessment",
        "fields": [
            {"id": "obs_wells_monitored", "label": "Observation wells monitored", "type": "number", "unit": "nos"},
            {"id": "water_level_measurements", "label": "Water level measurements taken", "type": "number", "unit": "nos"},
            {"id": "avg_water_level", "label": "Average water level", "type": "number", "unit": "meters"},
            {"id": "water_samples_collected", "label": "Water samples collected", "type": "number", "unit": "nos"},
            {"id": "monitoring_remarks", "label": "Remarks", "type": "text"}
        ]
    },
    "Recharge Structures": {
        "description": "Artificial recharge works",
        "fields": [
            {"id": "recharge_structures", "label": "Recharge structures completed", "type": "number", "unit": "nos"},
            {"id": "recharge_capacity", "label": "Total recharge capacity", "type": "number", "unit": "MCM"},
            {"id": "recharge_expenditure", "label": "Expenditure incurred", "type": "number", "unit": "₹"},
            {"id": "recharge_type", "label": "Type of structure", "type": "dropdown",
             "options": ["Percolation Tank", "Check Dam", "Recharge Shaft", "Others"]},
            {"id": "recharge_remarks", "label": "Remarks", "type": "text"}
        ]
    },
    "Public Awareness": {
        "description": "Training programs, workshops, campaigns",
        "fields": [
            {"id": "training_programs", "label": "Training programs conducted", "type": "number", "unit": "nos"},
            {"id": "participants_trained", "label": "Participants trained", "type": "number", "unit": "nos"},
            {"id": "awareness_camps", "label": "Awareness camps organized", "type": "number", "unit": "nos"},
            {"id": "publications", "label": "Publications distributed", "type": "number", "unit": "nos"},
            {"id": "awareness_remarks", "label": "Remarks", "type": "text"}
        ]
    }
}

# District list (14 districts)
DISTRICTS = [
    "District 1", "District 2", "District 3", "District 4", "District 5",
    "District 6", "District 7", "District 8", "District 9", "District 10",
    "District 11", "District 12", "District 13", "District 14"
]

# ==================== FIREBASE FUNCTIONS ====================
def create_user(email, password, district, role="district_user"):
    """Create new user in Firebase Authentication"""
    try:
        user = auth_module.create_user(
            email=email,
            password=password,
            display_name=district
        )
        
        # Store user details in Firestore
        user_ref = db.collection('users').document(user.uid)
        user_ref.set({
            'email': email,
            'district': district,
            'role': role,
            'created_at': firestore.SERVER_TIMESTAMP,
            'is_active': True,
            'can_edit': True if role == "district_user" else True
        })
        
        return True, f"User created successfully: {email}"
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def authenticate_user(email, password):
    """Authenticate user (simplified - in production use Firebase Auth directly)"""
    # In production, use Firebase Auth SDK
    # For demo, we'll use a simplified approach
    if db:
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1).get()
        
        if len(query) > 0:
            user_data = query[0].to_dict()
            # In production: verify password with Firebase Auth
            st.session_state.authenticated = True
            st.session_state.user_id = query[0].id
            st.session_state.user_role = user_data.get('role', 'district_user')
            st.session_state.user_district = user_data.get('district', 'Unknown')
            return True
    return False

def save_monthly_data(district, month, year, data, status="draft"):
    """Save monthly data to Firestore"""
    if db is None:
        return False, "Firestore not connected (db is None)"
    try:
        doc_id = f"{district}_{year}_{month:02d}"
        
        monthly_data = {
            'district': district,
            'month': month,
            'year': year,
            'data': data,
            'status': status,
            'submitted_by': st.session_state.user_id,
            'submitted_at': firestore.SERVER_TIMESTAMP,
            'last_modified': firestore.SERVER_TIMESTAMP
        }
        
        # Add approval fields if submitted
        if status == "submitted":
            monthly_data['submission_date'] = firestore.SERVER_TIMESTAMP
        
        db.collection('monthly_reports').document(doc_id).set(monthly_data)
        return True, "Data saved successfully"
    except Exception as e:
        return False, f"Error saving data: {str(e)}"

def get_district_data(district, month=None, year=None):
    """Get monthly data for a district"""
    try:
        reports_ref = db.collection('monthly_reports')
        
        if month and year:
            # Get specific month
            doc_id = f"{district}_{year}_{month:02d}"
            doc = reports_ref.document(doc_id).get()
            if doc.exists:
                return [doc.to_dict()]
        else:
            # Get all data for district
            query = reports_ref.where('district', '==', district).order_by('year').order_by('month')
            docs = query.get()
            return [doc.to_dict() for doc in docs]
    
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def get_all_districts_data(year=None, month=None):
    """Get data for all districts (State Admin only)"""
    try:
        reports_ref = db.collection('monthly_reports')
        
        if year and month:
            query = reports_ref.where('year', '==', year).where('month', '==', month)
        elif year:
            query = reports_ref.where('year', '==', year)
        else:
            query = reports_ref
        
        docs = query.get()
        return [doc.to_dict() for doc in docs]
    
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def update_data_status(doc_id, status, remarks=""):
    """Update approval status of monthly data"""
    try:
        update_data = {
            'status': status,
            'reviewed_at': firestore.SERVER_TIMESTAMP,
            'reviewed_by': st.session_state.user_id
        }
        
        if remarks:
            update_data['review_remarks'] = remarks
        
        db.collection('monthly_reports').document(doc_id).update(update_data)
        return True, f"Status updated to {status}"
    except Exception as e:
        return False, f"Error updating status: {str(e)}"

# ==================== PAGE: LOGIN ====================
def login_page():
    """Login page for all users"""
    st.markdown("""
    <div class="main-header">
        <h1>💧 Ground Water Department</h1>
        <h3>Monthly Progress Monitoring System</h3>
        <p>Government of [State Name]</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container(border=True):
            st.subheader("🔐 Login")
            
            # Demo mode toggle
            demo_mode = st.checkbox("Use Demo Mode (No Firebase required)")
            
            if demo_mode:
                role = st.selectbox("Select Role", ["District User", "State Admin"])
                district = st.selectbox("Select District", DISTRICTS) if role == "District User" else None
                
                if st.button("Login with Demo", use_container_width=True):
                    st.session_state.authenticated = True
                    st.session_state.user_role = "district_user" if role == "District User" else "state_admin"
                    st.session_state.user_district = district
                    st.session_state.user_id = "demo_user"
                    st.rerun()
            
            else:
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                
                if st.button("Login", use_container_width=True):
                    if authenticate_user(email, password):
                        st.success(f"Welcome {st.session_state.user_district}!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

# ==================== PAGE: DISTRICT USER DASHBOARD ====================
def district_dashboard():
    """Dashboard for district users"""
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title(f"📊 {st.session_state.user_district}")
        st.caption(f"Monthly Progress Monitoring | User: {st.session_state.user_id}")
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    
    # Tabs for different functionalities
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 New Entry", 
        "📋 View Submissions", 
        "📈 Progress Summary",
        "⚙️ Profile"
    ])
    
    # ===== TAB 1: NEW ENTRY =====
    with tab1:
        st.header("New Monthly Entry")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            month = st.selectbox("Month", list(range(1, 13)), format_func=lambda x: datetime(2024, x, 1).strftime('%B'))
        with col2:
            current_year = datetime.now().year
            years = list(range(current_year - 5, current_year + 1))
            year = st.selectbox("Year", years)
        with col3:
            reporting_date = st.date_input("Reporting Date", value=date.today())
        
        # Check if entry already exists
        existing_data = get_district_data(st.session_state.user_district, month, year)
        if existing_data:
            st.warning(f"⚠️ Entry for {datetime(year, month, 1).strftime('%B %Y')} already exists")
        
            if existing_data[0]['status'] == 'approved':
                st.error("❌ This entry has been approved and cannot be modified")
                st.info("You can view this report under 'View Submissions'")
                st.stop()

            elif st.button("Edit Existing Entry"):
                st.session_state.edit_mode = True
                st.session_state.existing_data = existing_data[0]
        
        # Form header
        with st.container(border=True):
            st.subheader("Reporting Officer Details")
            col1, col2 = st.columns(2)
            with col1:
                officer_name = st.text_input("Name of Reporting Officer")
                designation = st.text_input("Designation")
            with col2:
                contact = st.text_input("Contact Number")
                email = st.text_input("Email")
        
        # Main data entry form
        st.subheader("Monthly Progress Data")
        
        form_data = {}
        for category, details in MONTHLY_CATEGORIES.items():
            with st.expander(f"📁 {category} - {details['description']}", expanded=True):
                st.caption(details['description'])
                
                cols = st.columns(2)
                col_index = 0
                
                for field in details['fields']:
                    with cols[col_index % 2]:
                        field_id = f"{category}_{field['id']}"
                        
                        if field['type'] == 'number':
                            value = st.number_input(
                                f"{field['label']} ({field.get('unit', '')})",
                                min_value=0,
                                value=0,
                                key=field_id
                            )
                        elif field['type'] == 'dropdown':
                            value = st.selectbox(
                                field['label'],
                                options=field['options'],
                                key=field_id
                            )
                        elif field['type'] == 'text':
                            value = st.text_area(
                                field['label'],
                                key=field_id,
                                height=100
                            )
                        
                        form_data[field_id] = value
                    col_index += 1
        
        # Submission buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 Save Draft", use_container_width=True):
                success, message = save_monthly_data(
                    st.session_state.user_district,
                    month,
                    year,
                    form_data,
                    status="draft"
                )
                if success:
                    st.success("Draft saved successfully!")
                else:
                    st.error(message)
        
        with col2:
            if st.button("📤 Submit for Approval", use_container_width=True):
                success, message = save_monthly_data(
                    st.session_state.user_district,
                    month,
                    year,
                    form_data,
                    status="submitted"
                )
                if success:
                    st.success("Submitted for approval!")
                    st.balloons()
                else:
                    st.error(message)
        
        with col3:
            if st.button("🔄 Reset Form", use_container_width=True):
                st.rerun()
    
    # ===== TAB 2: VIEW SUBMISSIONS =====
    with tab2:
        st.header("Previous Submissions")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_year = st.selectbox("Filter by Year", ["All"] + list(range(2020, datetime.now().year + 1)), key="filter_year")
        with col2:
            filter_month = st.selectbox("Filter by Month", ["All"] + list(range(1, 13)), 
                                       format_func=lambda x: datetime(2024, x, 1).strftime('%B') if x != "All" else "All",
                                       key="filter_month")
        with col3:
            filter_status = st.selectbox("Filter by Status", ["All", "draft", "submitted", "approved", "rejected"])
        
        # Get data
        all_data = get_district_data(st.session_state.user_district)
        
        if not all_data:
            st.info("No submissions found")
        else:
            # Filter data
            filtered_data = []
            for entry in all_data:
                if filter_year != "All" and entry.get('year') != int(filter_year):
                    continue
                if filter_month != "All" and entry.get('month') != int(filter_month):
                    continue
                if filter_status != "All" and entry.get('status') != filter_status:
                    continue
                filtered_data.append(entry)
            
            # Display in table
            display_data = []
            for entry in filtered_data:
                display_data.append({
                    'Month-Year': f"{datetime(entry['year'], entry['month'], 1).strftime('%B %Y')}",
                    'Status': entry['status'],
                    'Submitted On': entry.get('submitted_at', 'N/A'),
                    'Last Modified': entry.get('last_modified', 'N/A'),
                    'Remarks': entry.get('review_remarks', '')
                })
            
            if display_data:
                df = pd.DataFrame(display_data)
                
                # Add status badges
                def format_status(status):
                    badge_class = {
                        'draft': 'pending-badge',
                        'submitted': 'pending-badge',
                        'approved': 'approved-badge',
                        'rejected': 'rejected-badge'
                    }.get(status, '')
                    
                    if badge_class:
                        return f'<span class="{badge_class}">{status.upper()}</span>'
                    return status
                
                # Convert DataFrame to HTML with badges
                html = df.to_html(escape=False, index=False)
                html = html.replace('<td>draft</td>', '<td><span class="pending-badge">DRAFT</span></td>')
                html = html.replace('<td>submitted</td>', '<td><span class="pending-badge">SUBMITTED</span></td>')
                html = html.replace('<td>approved</td>', '<td><span class="approved-badge">APPROVED</span></td>')
                html = html.replace('<td>rejected</td>', '<td><span class="rejected-badge">REJECTED</span></td>')
                
                st.markdown(html, unsafe_allow_html=True)
                
                # Allow editing of drafts
                st.subheader("Edit Entry")
                edit_options = [f"{entry['month']}/{entry['year']} - {entry['status']}" for entry in filtered_data]
                selected_edit = st.selectbox("Select entry to edit", edit_options)
                
                if selected_edit and st.button("Edit Selected Entry"):
                    selected_index = edit_options.index(selected_edit)
                    selected_entry = filtered_data[selected_index]
                    
                    if selected_entry['status'] == 'approved':
                        st.error("Approved entries cannot be edited")
                    else:
                        st.session_state.edit_mode = True
                        st.session_state.edit_entry = selected_entry
                        st.info("Switch to 'New Entry' tab to edit")
            else:
                st.info("No data matching the filters")
    
    # ===== TAB 3: PROGRESS SUMMARY =====
    with tab3:
        st.header("Progress Summary")
        
        # Get all data for the district
        all_data = get_district_data(st.session_state.user_district)
        
        if not all_data:
            st.info("No data available for analysis")
        else:
            # Convert to DataFrame for analysis
            analysis_data = []
            for entry in all_data:
                if entry.get('status') == 'approved':  # Only use approved data
                    row = {
                        'month_year': f"{entry['year']}-{entry['month']:02d}",
                        'year': entry['year'],
                        'month': entry['month']
                    }
                    
                    # Extract key metrics
                    data = entry.get('data', {})
                    for key, value in data.items():
                        if isinstance(value, (int, float)):
                            row[key] = value
                    
                    analysis_data.append(row)
            
            if analysis_data:
                df = pd.DataFrame(analysis_data)
                df['date'] = pd.to_datetime(df['month_year'], format='%Y-%m')
                df = df.sort_values('date')
                
                # KPIs
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_surveys = df.get('Surveys & Investigations_surveys_conducted', pd.Series([0])).sum()
                    st.metric("Total Surveys", f"{int(total_surveys):,}")
                
                with col2:
                    total_borewells = df.get('Drilling Works_borewells_completed', pd.Series([0])).sum()
                    st.metric("Borewells Completed", f"{int(total_borewells):,}")
                
                with col3:
                    total_recharge = df.get('Recharge Structures_recharge_structures', pd.Series([0])).sum()
                    st.metric("Recharge Structures", f"{int(total_recharge):,}")
                
                with col4:
                    total_trained = df.get('Public Awareness_participants_trained', pd.Series([0])).sum()
                    st.metric("People Trained", f"{int(total_trained):,}")
                
                # Charts
                tab1, tab2 = st.tabs(["📈 Monthly Trends", "📊 Category Breakdown"])
                
                with tab1:
                    # Line chart for key metrics
                    metric_options = [
                        'Surveys & Investigations_surveys_conducted',
                        'Drilling Works_borewells_completed',
                        'Monitoring Activities_obs_wells_monitored',
                        'Recharge Structures_recharge_structures'
                    ]
                    
                    selected_metric = st.selectbox("Select Metric", metric_options,
                                                  format_func=lambda x: x.split('_')[0])
                    
                    if selected_metric in df.columns:
                        fig = px.line(df, x='date', y=selected_metric,
                                     title=f"Monthly Trend: {selected_metric.split('_')[0]}")
                        st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    # Bar chart for latest month
                    latest = df.iloc[-1] if len(df) > 0 else None
                    
                    if latest is not None:
                        categories = []
                        values = []
                        
                        for cat in MONTHLY_CATEGORIES.keys():
                            # Find a numeric field in each category
                            for field in MONTHLY_CATEGORIES[cat]['fields']:
                                col_name = f"{cat}_{field['id']}"
                                if col_name in df.columns and pd.notna(latest[col_name]):
                                    categories.append(cat)
                                    values.append(latest[col_name])
                                    break
                        
                        if categories:
                            fig = px.bar(x=categories, y=values,
                                        title="Latest Month Performance by Category")
                            st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No approved data available for analysis")
    
    # ===== TAB 4: PROFILE =====
    with tab4:
        st.header("User Profile")
        
        with st.container(border=True):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("District", st.session_state.user_district)
                st.metric("Role", "District User")
            with col2:
                st.metric("User ID", st.session_state.user_id)
                st.metric("Status", "Active")
        
        # Change password (simplified)
        st.subheader("Change Password")
        with st.form("change_password"):
            current = st.text_input("Current Password", type="password")
            new = st.text_input("New Password", type="password")
            confirm = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password"):
                if new == confirm:
                    st.success("Password updated successfully!")
                else:
                    st.error("Passwords do not match")

# ==================== PAGE: STATE ADMIN DASHBOARD ====================
def state_admin_dashboard():
    """Dashboard for State Admin/Super Admin"""
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("🏛️ State Administration")
        st.caption("Ground Water Department | Super Admin Panel")
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", 
        "👥 User Management", 
        "✅ Approvals",
        "📈 Analytics",
        "📄 Reports"
    ])
    
    # ===== TAB 1: DASHBOARD =====
    with tab1:
        st.header("State Overview Dashboard")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_year = st.selectbox("Year", 
                                        list(range(2020, datetime.now().year + 1)),
                                        key="state_year")
        with col2:
            selected_month = st.selectbox("Month", 
                                         list(range(1, 13)),
                                         format_func=lambda x: datetime(2024, x, 1).strftime('%B'),
                                         key="state_month")
        with col3:
            selected_district = st.selectbox("District", ["All"] + DISTRICTS)
        
        # Get data
        if selected_district == "All":
            data = get_all_districts_data(selected_year, selected_month)
        else:
            data = get_district_data(selected_district, selected_month, selected_year)
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            districts_submitted = len(set([d['district'] for d in data if d.get('status') == 'submitted']))
            total_districts = len(DISTRICTS)
            submission_rate = (districts_submitted / total_districts) * 100
            st.metric("Submission Rate", f"{submission_rate:.1f}%", 
                     f"{districts_submitted}/{total_districts} districts")
        
        with col2:
            approved_count = len([d for d in data if d.get('status') == 'approved'])
            st.metric("Approved Entries", approved_count)
        
        with col3:
            pending_count = len([d for d in data if d.get('status') == 'submitted'])
            st.metric("Pending Approval", pending_count)
        
        with col4:
            total_expenditure = sum([d.get('data', {}).get('Drilling Works_drilling_expenditure', 0) + 
                                    d.get('data', {}).get('Recharge Structures_recharge_expenditure', 0) 
                                    for d in data])
            st.metric("Total Expenditure", f"₹{total_expenditure:,.0f}")
        
        # District-wise status
        st.subheader("District-wise Submission Status")
        
        status_data = []
        for district in DISTRICTS:
            district_data = [d for d in data if d.get('district') == district]
            if district_data:
                latest = district_data[0]
                status_data.append({
                    'District': district,
                    'Status': latest.get('status', 'Not Submitted'),
                    'Last Updated': latest.get('last_modified', 'N/A')
                })
            else:
                status_data.append({
                    'District': district,
                    'Status': 'Not Submitted',
                    'Last Updated': 'N/A'
                })
        
        status_df = pd.DataFrame(status_data)
        
        # Color coding
        def color_status(val):
            color = {
                'approved': 'background-color: #28a745; color: white',
                'submitted': 'background-color: #ffc107; color: black',
                'draft': 'background-color: #6c757d; color: white',
                'rejected': 'background-color: #dc3545; color: white',
                'Not Submitted': 'background-color: #f8f9fa; color: #6c757d'
            }.get(val, '')
            return color
        
        st.dataframe(status_df.style.applymap(color_status, subset=['Status']), 
                    use_container_width=True)
    
    # ===== TAB 2: USER MANAGEMENT =====
    with tab2:
        st.header("User Management")
        
        # Create new user
        with st.expander("➕ Create New User", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
            with col2:
                new_district = st.selectbox("Assign District", DISTRICTS)
                new_role = st.selectbox("Role", ["district_user", "state_admin"])
            
            if st.button("Create User", type="primary"):
                if new_email and new_password:
                    success, message = create_user(new_email, new_password, new_district, new_role)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.warning("Please fill all fields")
        
        # View existing users
        st.subheader("Existing Users")
        
        try:
            users_ref = db.collection('users')
            users = users_ref.get()
            
            user_list = []
            for user in users:
                user_data = user.to_dict()
                user_list.append({
                    'ID': user.id,
                    'Email': user_data.get('email', ''),
                    'District': user_data.get('district', ''),
                    'Role': user_data.get('role', ''),
                    'Status': 'Active' if user_data.get('is_active', False) else 'Inactive',
                    'Can Edit': 'Yes' if user_data.get('can_edit', False) else 'No'
                })
            
            if user_list:
                users_df = pd.DataFrame(user_list)
                edited_df = st.data_editor(
                    users_df,
                    column_config={
                        "Status": st.column_config.SelectboxColumn(
                            options=["Active", "Inactive"]
                        ),
                        "Can Edit": st.column_config.SelectboxColumn(
                            options=["Yes", "No"]
                        )
                    },
                    use_container_width=True
                )
                
                if st.button("Update Users"):
                    for index, row in edited_df.iterrows():
                        user_ref = users_ref.document(row['ID'])
                        user_ref.update({
                            'is_active': row['Status'] == 'Active',
                            'can_edit': row['Can Edit'] == 'Yes'
                        })
                    st.success("User permissions updated!")
            else:
                st.info("No users found")
                
        except Exception as e:
            st.error(f"Error loading users: {e}")
    
    # ===== TAB 3: APPROVALS =====
    with tab3:
        st.header("Approve/Review Submissions")
        
        # Filter for pending submissions
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            approval_year = st.selectbox("Year", 
                                        list(range(2020, datetime.now().year + 1)),
                                        key="approval_year")
        with filter_col2:
            approval_month = st.selectbox("Month", 
                                         list(range(1, 13)),
                                         format_func=lambda x: datetime(2024, x, 1).strftime('%B'),
                                         key="approval_month")
        
        # Get pending submissions
        all_data = get_all_districts_data(approval_year, approval_month)
        pending_data = [d for d in all_data if d.get('status') == 'submitted']
        
        if not pending_data:
            st.success("✅ No pending submissions for this period")
        else:
            st.info(f"📋 {len(pending_data)} submissions pending approval")
            
            for entry in pending_data:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.subheader(f"{entry['district']} - {datetime(entry['year'], entry['month'], 1).strftime('%B %Y')}")
                        st.caption(f"Submitted on: {entry.get('submitted_at', 'N/A')}")
                    
                    with col2:
                        # Quick view button
                        if st.button(f"👁️ View", key=f"view_{entry['district']}"):
                            st.session_state.view_entry = entry
                    
                    with col3:
                        # Action buttons
                        action_col1, action_col2, action_col3 = st.columns(3)
                        with action_col1:
                            if st.button("✅", key=f"approve_{entry['district']}"):
                                doc_id = f"{entry['district']}_{entry['year']}_{entry['month']:02d}"
                                success, message = update_data_status(doc_id, "approved", "Approved by State Admin")
                                if success:
                                    st.success(f"Approved {entry['district']}")
                                    st.rerun()
                        with action_col2:
                            if st.button("❌", key=f"reject_{entry['district']}"):
                                remarks = st.text_input("Rejection remarks", key=f"remarks_{entry['district']}")
                                if remarks:
                                    doc_id = f"{entry['district']}_{entry['year']}_{entry['month']:02d}"
                                    success, message = update_data_status(doc_id, "rejected", remarks)
                                    if success:
                                        st.success(f"Rejected {entry['district']}")
                                        st.rerun()
                        with action_col3:
                            if st.button("↩️", key=f"return_{entry['district']}"):
                                remarks = st.text_input("Return remarks", key=f"return_remarks_{entry['district']}")
                                if remarks:
                                    doc_id = f"{entry['district']}_{entry['year']}_{entry['month']:02d}"
                                    success, message = update_data_status(doc_id, "draft", remarks)
                                    if success:
                                        st.success(f"Returned {entry['district']} for correction")
                                        st.rerun()
                    
                    # Show entry details if viewing
                    if st.session_state.get('view_entry') == entry:
                        st.divider()
                        st.json(entry.get('data', {}))
    
    # ===== TAB 4: ANALYTICS =====
    with tab4:
        st.header("Data Analytics")
        
        # Get all approved data
        all_data = get_all_districts_data()
        approved_data = [d for d in all_data if d.get('status') == 'approved']
        
        if not approved_data:
            st.info("No approved data available for analysis")
        else:
            # Convert to DataFrame
            analysis_rows = []
            for entry in approved_data:
                row = {
                    'district': entry['district'],
                    'year': entry['year'],
                    'month': entry['month'],
                    'month_year': f"{entry['year']}-{entry['month']:02d}"
                }
                
                # Add all numeric fields
                for key, value in entry.get('data', {}).items():
                    if isinstance(value, (int, float)):
                        row[key] = value
                
                analysis_rows.append(row)
            
            df = pd.DataFrame(analysis_rows)
            
            # Analysis options
            analysis_type = st.selectbox("Select Analysis", 
                                        ["District Comparison", "Monthly Trends", "Category Performance"])
            
            if analysis_type == "District Comparison":
                st.subheader("District-wise Comparison")
                
                # Select metric for comparison
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                metric = st.selectbox("Select Metric", numeric_cols)
                
                if metric:
                    # Group by district
                    district_stats = df.groupby('district')[metric].agg(['sum', 'mean', 'max']).round(2)
                    district_stats = district_stats.sort_values('sum', ascending=False)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.dataframe(district_stats, use_container_width=True)
                    
                    with col2:
                        fig = px.bar(district_stats.reset_index(), 
                                    x='district', y='sum',
                                    title=f"Total {metric} by District")
                        st.plotly_chart(fig, use_container_width=True)
            
            elif analysis_type == "Monthly Trends":
                st.subheader("State-wide Monthly Trends")
                
                # Select metric
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                metric = st.selectbox("Select Metric", numeric_cols, key="trend_metric")
                
                if metric:
                    # Aggregate by month
                    monthly_trend = df.groupby('month_year')[metric].sum().reset_index()
                    monthly_trend = monthly_trend.sort_values('month_year')
                    
                    fig = px.line(monthly_trend, x='month_year', y=metric,
                                 title=f"State-wide Trend: {metric}")
                    st.plotly_chart(fig, use_container_width=True)
            
            elif analysis_type == "Category Performance":
                st.subheader("Category-wise Performance")
                
                # Aggregate by category
                category_data = []
                for category in MONTHLY_CATEGORIES.keys():
                    # Find main numeric field for each category
                    main_field = None
                    for field in MONTHLY_CATEGORIES[category]['fields']:
                        col_name = f"{category}_{field['id']}"
                        if col_name in df.columns:
                            main_field = col_name
                            break
                    
                    if main_field:
                        total = df[main_field].sum()
                        category_data.append({
                            'Category': category,
                            'Total': total
                        })
                
                if category_data:
                    cat_df = pd.DataFrame(category_data)
                    cat_df = cat_df.sort_values('Total', ascending=False)
                    
                    fig = px.pie(cat_df, values='Total', names='Category',
                                title="Contribution by Category")
                    st.plotly_chart(fig, use_container_width=True)
    
    # ===== TAB 5: REPORTS =====
    with tab5:
        st.header("Report Generation")
        
        col1, col2 = st.columns(2)
        with col1:
            report_year = st.selectbox("Report Year", 
                                      list(range(2020, datetime.now().year + 1)),
                                      key="report_year")
        with col2:
            report_month = st.selectbox("Report Month", 
                                       list(range(1, 13)),
                                       format_func=lambda x: datetime(2024, x, 1).strftime('%B'),
                                       key="report_month")
        
        # Report type
        report_type = st.radio("Report Type", 
                              ["State Consolidated Report", "District-wise Report"])
        
        if report_type == "District-wise Report":
            selected_district = st.selectbox("Select District", DISTRICTS)
        
        # Generate report
        if st.button("📄 Generate Report"):
            with st.spinner("Generating report..."):
                # Get data
                data = get_all_districts_data(report_year, report_month)
                approved_data = [d for d in data if d.get('status') == 'approved']
                
                if not approved_data:
                    st.warning("No approved data available for this period")
                else:
                    # Create summary DataFrame
                    summary_rows = []
                    for entry in approved_data:
                        row = {'District': entry['district']}
                        
                        # Add key metrics from each category
                        for category in MONTHLY_CATEGORIES.keys():
                            # Get first numeric field as representative
                            for field in MONTHLY_CATEGORIES[category]['fields']:
                                col_name = f"{category}_{field['id']}"
                                value = entry.get('data', {}).get(col_name, 0)
                                if isinstance(value, (int, float)):
                                    row[category] = value
                                    break
                        
                        summary_rows.append(row)
                    
                    summary_df = pd.DataFrame(summary_rows)
                    
                    # Display report
                    st.subheader(f"Monthly Progress Report - {datetime(report_year, report_month, 1).strftime('%B %Y')}")
                    
                    # Summary statistics
                    st.write("### Summary Statistics")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Districts Reported", len(approved_data))
                    with col2:
                        total_surveys = summary_df.get('Surveys & Investigations', pd.Series([0])).sum()
                        st.metric("Total Surveys", int(total_surveys))
                    with col3:
                        total_borewells = summary_df.get('Drilling Works', pd.Series([0])).sum()
                        st.metric("Borewells Drilled", int(total_borewells))
                    with col4:
                        total_expenditure = sum([d.get('data', {}).get('Drilling Works_drilling_expenditure', 0) + 
                                                d.get('data', {}).get('Recharge Structures_recharge_expenditure', 0) 
                                                for d in approved_data])
                        st.metric("Total Expenditure", f"₹{total_expenditure:,.0f}")
                    
                    # Detailed table
                    st.write("### Detailed District Data")
                    st.dataframe(summary_df, use_container_width=True)
                    
                    # Export buttons
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Export to Excel
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            summary_df.to_excel(writer, sheet_name='Summary', index=False)
                            
                            # Add raw data sheet
                            raw_data = []
                            for entry in approved_data:
                                raw_row = {
                                    'District': entry['district'],
                                    'Month': entry['month'],
                                    'Year': entry['year']
                                }
                                raw_row.update(entry.get('data', {}))
                                raw_data.append(raw_row)
                            
                            raw_df = pd.DataFrame(raw_data)
                            raw_df.to_excel(writer, sheet_name='Raw Data', index=False)
                        
                        excel_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Download Excel Report",
                            data=excel_buffer,
                            file_name=f"GWD_Report_{report_year}_{report_month:02d}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    with col2:
                        # Generate PDF (simplified)
                        if st.button("📥 Generate PDF Report"):
                            st.info("PDF generation would be implemented with ReportLab or similar library")

# ==================== MAIN APP ROUTING ====================
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        if st.session_state.user_role == "state_admin":
            state_admin_dashboard()
        else:
            district_dashboard()

if __name__ == "__main__":
    main()