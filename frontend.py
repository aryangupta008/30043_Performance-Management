# frontend.py

import streamlit as st
import backend as db
from datetime import date, time
import pandas as pd

# --- Page Setup ---
st.set_page_config(page_title="Event Management App", layout="wide")
st.title("🎫 Event Management Application")
db.create_tables()

# --- Session State Management (for a single user) ---
if 'logged_in_user' not in st.session_state:
    st.session_state['logged_in_user'] = None

# --- User Authentication and Initial Screen ---
if st.session_state['logged_in_user'] is None:
    st.markdown("### Welcome! 👋")
    st.info("This application is for a single user to manage events. Please log in or register.")
    
    st.header("Login")
    login_email = st.text_input("Enter your email to log in:")
    if st.button("Log In"):
        user_profile = db.get_user_by_email(login_email)
        if user_profile:
            st.session_state['logged_in_user'] = user_profile
            st.success(f"Welcome back, {user_profile['name']}!")
            st.rerun()
        else:
            st.error("User not found. Please register below.")

    st.markdown("---")
    st.header("New User Registration")
    new_name = st.text_input("Name")
    new_email = st.text_input("Email")
    new_org = st.text_input("Organization")
    if st.button("Register"):
        user_id = db.create_app_user(new_name, new_email, new_org)
        if user_id:
            st.success("Registration successful! You can now log in.")
        else:
            st.error("Registration failed. Email may already be in use.")

else:
    # --- Main Application (Visible after login) ---
    user = st.session_state['logged_in_user']
    st.sidebar.header(f"Hello, {user['name']}!")
    
    app_mode = st.sidebar.radio("Navigation", ["My Events", "Create New Event", "Register Attendee"])
    st.sidebar.markdown("---")

    if app_mode == "My Events":
        st.header("Your Events & Dashboards")
        events_df = db.get_all_events(user['user_id'])
        
        if events_df.empty:
            st.info("You haven't created any events yet. Go to 'Create New Event' to get started.")
        else:
            selected_event_name = st.selectbox("Select an Event", events_df['event_name'])
            # The fix: convert numpy.int64 to a standard Python int
            selected_event_id = int(events_df[events_df['event_name'] == selected_event_name]['event_id'].iloc[0])

            st.markdown("---")
            st.subheader(f"Dashboard for {selected_event_name}")
            
            event_details = db.get_event_details(selected_event_id)
            st.info(f"**Location:** {event_details.get('location')} | **Date:** {event_details.get('event_date')} | **Time:** {event_details.get('event_time')}")

            dashboard_data = db.get_event_dashboard_data(selected_event_id)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Attendees", dashboard_data.get('total_attendees', 0))
            with col2:
                st.metric("Total Revenue", f"${dashboard_data.get('total_revenue', 0):.2f}")

            st.subheader("Tickets Sold by Type")
            tickets_sold_df = pd.DataFrame(dashboard_data.get('tickets_sold_per_type', {}).items(), columns=['Ticket Type', 'Tickets Sold'])
            st.dataframe(tickets_sold_df, use_container_width=True)

            st.subheader("Registered Attendees")
            event_tickets = db.get_event_tickets(selected_event_id)
            if not event_tickets.empty:
                ticket_types = event_tickets['ticket_type_name'].tolist()
                selected_ticket_type = st.selectbox("Filter attendees by ticket type:", ["All"] + ticket_types)

                if selected_ticket_type == "All":
                    attendees_df = pd.read_sql_query("SELECT name, email FROM attendees WHERE event_id = %s;", db.get_db_connection(), params=(selected_event_id,))
                else:
                    attendees_df = db.get_attendees_by_ticket_type(selected_event_id, selected_ticket_type)
                
                if not attendees_df.empty:
                    st.dataframe(attendees_df, use_container_width=True)
                else:
                    st.info("No attendees found for this ticket type.")
            else:
                st.warning("No ticket types defined for this event.")
    
    elif app_mode == "Create New Event":
        st.header("Create a New Event")
        with st.form("new_event_form"):
            event_name = st.text_input("Event Name")
            event_date = st.date_input("Event Date", date.today())
            event_time = st.time_input("Event Time", time(19, 0))
            location = st.text_input("Location")
            description = st.text_area("Description")
            submitted = st.form_submit_button("Create Event")

            if submitted:
                event_id = db.create_event(user['user_id'], event_name, event_date, event_time, location, description)
                if event_id:
                    st.success(f"Event '{event_name}' created successfully! Add ticket types below.")
                    st.session_state['current_event_id'] = event_id
                else:
                    st.error("Failed to create event.")

        if 'current_event_id' in st.session_state:
            st.markdown("---")
            st.subheader("Add Ticket Types for this Event")
            with st.form("new_ticket_form"):
                ticket_type_name = st.text_input("Ticket Type Name (e.g., 'VIP')")
                price = st.number_input("Price", min_value=0.01)
                quantity_available = st.number_input("Quantity Available", min_value=1)
                add_ticket_submitted = st.form_submit_button("Add Ticket Type")
                if add_ticket_submitted:
                    if db.add_ticket_type(st.session_state['current_event_id'], ticket_type_name, price, quantity_available):
                        st.success(f"Ticket type '{ticket_type_name}' added.")
                    else:
                        st.error("Failed to add ticket type.")
    
    elif app_mode == "Register Attendee":
        st.header("Register a New Attendee")
        events_df = db.get_all_events(user['user_id'])
        if events_df.empty:
            st.info("No events available to register attendees for.")
        else:
            selected_event_name = st.selectbox("Select Event", events_df['event_name'])
            selected_event_id = int(events_df[events_df['event_name'] == selected_event_name]['event_id'].iloc[0])
            
            with st.form("register_attendee_form"):
                attendee_name = st.text_input("Attendee Name")
                attendee_email = st.text_input("Attendee Email")

                st.subheader("Select Tickets")
                tickets_df = db.get_event_tickets(selected_event_id)
                purchases = {}
                if not tickets_df.empty:
                    for _, row in tickets_df.iterrows():
                        key = f"quantity_{row['ticket_id']}"
                        quantity = st.number_input(f"{row['ticket_type_name']} (${row['price']:.2f}) - Available: {row['quantity_available']}", min_value=0, max_value=int(row['quantity_available']), key=key)
                        if quantity > 0:
                            purchases[int(row['ticket_id'])] = quantity
                else:
                    st.warning("No ticket types have been created for this event.")
                
                submitted = st.form_submit_button("Complete Registration")
                if submitted:
                    if not attendee_name or not attendee_email or not purchases:
                        st.warning("Please fill in all details and select at least one ticket.")
                    else:
                        success = db.register_attendee(selected_event_id, attendee_name, attendee_email, purchases)
                        if success:
                            st.success("Attendee registered and tickets purchased successfully!")
                            tickets_str = ", ".join([f"{q}x {tickets_df[tickets_df['ticket_id'] == t_id]['ticket_type_name'].iloc[0]}" for t_id, q in purchases.items()])
                            db.send_confirmation_email(attendee_email, selected_event_name, tickets_str)
                        else:
                            st.error("Failed to complete registration.")