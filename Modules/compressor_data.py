import streamlit as st
import pandas as pd
from datetime import datetime
import os

COMPRESSOR_DATA_PATH = "Data/Compressor_Data.xlsx"

def load_compressor_data():
    """Load compressor data from Excel file"""
    try:
        if not os.path.exists(COMPRESSOR_DATA_PATH):
            # Create initial data if file doesn't exist
            initial_data = {
                'Compressor ID': ['A', 'B', 'C'],
                'Compressor Name': ['Compressor A', 'Compressor B', 'Compressor C'],
                'Current Hours': [500, 79300, 76900],
                'Date Updated': [datetime.now().date()] * 3,
                'Status': ['Active', 'Active', 'Active'],
                'Notes': ['Initial setup', 'High usage unit', 'Standard operation']
            }
            df = pd.DataFrame(initial_data)
            df.to_excel(COMPRESSOR_DATA_PATH, index=False, engine='openpyxl')
        
        df = pd.read_excel(COMPRESSOR_DATA_PATH)
        df.columns = df.columns.str.strip()
        
        # Ensure Date Updated is datetime
        if 'Date Updated' in df.columns:
            df['Date Updated'] = pd.to_datetime(df['Date Updated'], errors='coerce').dt.date
        
        return df
    except Exception as e:
        st.error(f"Error loading compressor data: {e}")
        return pd.DataFrame()

def save_compressor_data(df):
    """Save compressor data to Excel file"""
    try:
        df.to_excel(COMPRESSOR_DATA_PATH, index=False, engine='openpyxl')
        return True
    except Exception as e:
        st.error(f"Error saving compressor data: {e}")
        return False

def append_compressor_entry(new_data: dict):
    """Append new compressor entry or update existing one"""
    try:
        df = load_compressor_data()
        
        # Check if compressor ID already exists
        if new_data['Compressor ID'] in df['Compressor ID'].values:
            # Update existing record
            mask = df['Compressor ID'] == new_data['Compressor ID']
            for key, value in new_data.items():
                df.loc[mask, key] = value
            st.success(f"Updated data for {new_data['Compressor ID']}")
        else:
            # Add new record
            new_row = pd.DataFrame([new_data])
            df = pd.concat([df, new_row], ignore_index=True)
            st.success(f"Added new compressor {new_data['Compressor ID']}")
        
        return save_compressor_data(df)
    except Exception as e:
        st.error(f"Error updating compressor data: {e}")
        return False

def calculate_next_maintenance(current_hours, last_maintenance_type):
    """Calculate next maintenance due based on current hours and last maintenance"""
    maintenance_intervals = {3000: 3000, 6000: 3000, 21000: 3000}
    
    if last_maintenance_type in maintenance_intervals:
        return current_hours + maintenance_intervals[last_maintenance_type]
    else:
        return current_hours + 3000  # Default to 3000 hours

def get_maintenance_type_options():
    """Get available maintenance type options"""
    return [3000, 6000, 21000]

def get_status_options():
    """Get available status options"""
    return ['Active', 'Maintenance', 'Inactive', 'Repair']

def show_compressor_data_entry():
    """Display simplified compressor data entry form"""
    st.subheader("🔧 Update Compressor Data")
    
    # Load existing data
    df = load_compressor_data()
    
    with st.form("compressor_data_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Compressor selection/creation
            existing_compressors = df['Compressor ID'].tolist() if not df.empty else []
            compressor_option = st.selectbox(
                "Select Existing or Create New",
                options=["Create New"] + existing_compressors,
                help="Choose an existing compressor to update or create a new one"
            )
            
            if compressor_option == "Create New":
                compressor_id = st.text_input("Compressor ID", placeholder="e.g., D, E, F")
                compressor_name = st.text_input("Compressor Name", placeholder="e.g., Compressor D")
            else:
                compressor_id = compressor_option
                existing_data = df[df['Compressor ID'] == compressor_id].iloc[0]
                compressor_name = st.text_input("Compressor Name", value=existing_data['Compressor Name'])
            
            # Current hours
            if compressor_option != "Create New":
                current_hours = st.number_input(
                    "Current Hours", 
                    min_value=0, 
                    value=int(existing_data['Current Hours']),
                    step=1,
                    help="Total operating hours of the compressor"
                )
            else:
                current_hours = st.number_input(
                    "Current Hours", 
                    min_value=0, 
                    value=0,
                    step=1,
                    help="Total operating hours of the compressor"
                )
        
        with col2:
            # Status
            status = st.selectbox(
                "Status",
                options=get_status_options(),
                index=0 if compressor_option == "Create New" else get_status_options().index(existing_data['Status']) if existing_data['Status'] in get_status_options() else 0
            )
            
            notes = st.text_area(
                "Notes",
                value="" if compressor_option == "Create New" else existing_data['Notes'],
                placeholder="Additional notes about the compressor",
                height=100
            )
        
        # Submit button
        submitted = st.form_submit_button("💾 Save Compressor Data", type="primary")
        
        if submitted:
            if not compressor_id or not compressor_name:
                st.error("Please fill in Compressor ID and Name")
            else:
                # Prepare data for saving
                new_data = {
                    'Compressor ID': compressor_id,
                    'Compressor Name': compressor_name,
                    'Current Hours': current_hours,
                    'Date Updated': datetime.now().date(),
                    'Status': status,
                    'Notes': notes
                }
                
                # Save data
                if append_compressor_entry(new_data):
                    st.balloons()
                    st.rerun()

def show_compressor_data_view():
    """Display current compressor data"""
    st.subheader("📊 Current Compressor Data")
    
    df = load_compressor_data()
    
    if df.empty:
        st.warning("No compressor data available. Please add some data first.")
        return
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Compressors", len(df))
    
    with col2:
        active_count = len(df[df['Status'] == 'Active'])
        st.metric("Active Compressors", active_count)
    
    with col3:
        total_hours = df['Current Hours'].sum()
        st.metric("Total Hours", f"{total_hours:,}")
    
    with col4:
        avg_hours = df['Current Hours'].mean()
        st.metric("Average Hours", f"{avg_hours:,.0f}")
    
    # Display data table
    st.dataframe(df, use_container_width=True)
    
    # Download option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"compressor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

def show_compressor_dashboard():
    """Main compressor dashboard function"""
    st.title("🔧 Air Compressor Management")
    
    tab1, tab2 = st.tabs(["📝 Data Entry", "📊 View Data"])
    
    with tab1:
        show_compressor_data_entry()
    
    with tab2:
        show_compressor_data_view()
