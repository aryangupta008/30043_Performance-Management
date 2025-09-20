import psycopg2
import pandas as pd
from typing import List, Dict, Any
from datetime import date, time

# Database credentials
DB_HOST = "localhost"
DB_NAME = "event_management"
DB_USER = "postgres"
DB_PASSWORD = "KaliNew"

def get_db_connection():
    """Establishes and returns a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to database: {e}")
        return None

def create_tables():
    """Creates all necessary tables for the application."""
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_user (user_id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, email VARCHAR(255) UNIQUE NOT NULL, organization VARCHAR(255));
            CREATE TABLE IF NOT EXISTS events (event_id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES app_user(user_id) ON DELETE CASCADE, event_name VARCHAR(255) NOT NULL, event_date DATE NOT NULL, event_time TIME NOT NULL, location VARCHAR(255) NOT NULL, description TEXT);
            CREATE TABLE IF NOT EXISTS tickets (ticket_id SERIAL PRIMARY KEY, event_id INTEGER REFERENCES events(event_id) ON DELETE CASCADE, ticket_type_name VARCHAR(255) NOT NULL, price DECIMAL(10, 2) NOT NULL, quantity_available INTEGER NOT NULL, UNIQUE (event_id, ticket_type_name));
            CREATE TABLE IF NOT EXISTS attendees (attendee_id SERIAL PRIMARY KEY, event_id INTEGER REFERENCES events(event_id) ON DELETE CASCADE, name VARCHAR(255) NOT NULL, email VARCHAR(255) NOT NULL);
            CREATE TABLE IF NOT EXISTS attendee_tickets (attendee_id INTEGER REFERENCES attendees(attendee_id) ON DELETE CASCADE, ticket_id INTEGER REFERENCES tickets(ticket_id) ON DELETE CASCADE, quantity INTEGER NOT NULL, PRIMARY KEY (attendee_id, ticket_id));
        """)
        conn.commit()
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        print(f"Error creating tables: {error}")
    finally:
        if conn: cur.close(); conn.close()

# --- CRUD Operations ---

# CREATE
def create_app_user(name: str, email: str, organization: str):
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO app_user (name, email, organization) VALUES (%s, %s, %s) RETURNING user_id;", (name, email, organization))
        user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        print(f"Error creating user: {error}")
        return None
    finally:
        if conn: cur.close(); conn.close()

def create_event(user_id: int, event_name: str, event_date: date, event_time: time, location: str, description: str):
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO events (user_id, event_name, event_date, event_time, location, description) VALUES (%s, %s, %s, %s, %s, %s) RETURNING event_id;", (user_id, event_name, event_date, event_time, location, description))
        event_id = cur.fetchone()[0]
        conn.commit()
        return event_id
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        print(f"Error creating event: {error}")
        return None
    finally:
        if conn: cur.close(); conn.close()

def add_ticket_type(event_id: int, ticket_type_name: str, price: float, quantity_available: int):
    conn = get_db_connection()
    if not conn: return False
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO tickets (event_id, ticket_type_name, price, quantity_available) VALUES (%s, %s, %s, %s);", (event_id, ticket_type_name, price, quantity_available))
        conn.commit()
        return True
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        print(f"Error adding ticket type: {error}")
        return False
    finally:
        if conn: cur.close(); conn.close()

def register_attendee(event_id: int, name: str, email: str, ticket_purchases: Dict[int, int]):
    conn = get_db_connection()
    if not conn: return False
    cur = conn.cursor()
    try:
        # Check if enough tickets are available and update quantities
        for ticket_id, quantity in ticket_purchases.items():
            cur.execute("SELECT quantity_available FROM tickets WHERE ticket_id = %s;", (ticket_id,))
            available = cur.fetchone()[0]
            if quantity > available:
                raise ValueError(f"Not enough tickets available for ticket ID {ticket_id}.")
            cur.execute("UPDATE tickets SET quantity_available = quantity_available - %s WHERE ticket_id = %s;", (quantity, ticket_id))

        # Insert attendee
        cur.execute("INSERT INTO attendees (event_id, name, email) VALUES (%s, %s, %s) RETURNING attendee_id;", (event_id, name, email))
        attendee_id = cur.fetchone()[0]

        # Insert attendee_tickets records
        for ticket_id, quantity in ticket_purchases.items():
            cur.execute("INSERT INTO attendee_tickets (attendee_id, ticket_id, quantity) VALUES (%s, %s, %s);", (attendee_id, ticket_id, quantity))

        conn.commit()
        return True
    except (Exception, psycopg2.Error) as error:
        conn.rollback()
        print(f"Error registering attendee: {error}")
        return False
    finally:
        if conn: cur.close(); conn.close()

# READ
def get_user_by_email(email: str):
    conn = get_db_connection()
    if not conn: return None
    df = pd.read_sql_query("SELECT * FROM app_user WHERE email = %s;", conn, params=(email,))
    conn.close()
    return df.to_dict('records')[0] if not df.empty else None

def get_all_events(user_id: int):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    df = pd.read_sql_query("SELECT event_id, event_name FROM events WHERE user_id = %s ORDER BY event_date DESC;", conn, params=(user_id,))
    conn.close()
    return df

def get_event_details(event_id: int):
    conn = get_db_connection()
    if not conn: return {}
    df = pd.read_sql_query("SELECT * FROM events WHERE event_id = %s;", conn, params=(event_id,))
    conn.close()
    return df.to_dict('records')[0] if not df.empty else {}

def get_event_tickets(event_id: int):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    df = pd.read_sql_query("SELECT ticket_id, ticket_type_name, price, quantity_available FROM tickets WHERE event_id = %s;", conn, params=(event_id,))
    conn.close()
    return df

def get_event_dashboard_data(event_id: int):
    conn = get_db_connection()
    if not conn: return {}
    cur = conn.cursor()
    try:
        # COUNT total attendees
        cur.execute("SELECT COUNT(attendee_id) FROM attendees WHERE event_id = %s;", (event_id,))
        total_attendees = cur.fetchone()[0]

        # SUM total revenue
        cur.execute("SELECT SUM(at.quantity * t.price) FROM attendee_tickets at JOIN tickets t ON at.ticket_id = t.ticket_id WHERE t.event_id = %s;", (event_id,))
        total_revenue = cur.fetchone()[0]

        # COUNT tickets sold per type
        cur.execute("SELECT t.ticket_type_name, SUM(at.quantity) FROM attendee_tickets at JOIN tickets t ON at.ticket_id = t.ticket_id WHERE t.event_id = %s GROUP BY t.ticket_type_name;", (event_id,))
        tickets_sold_per_type = {row[0]: int(row[1]) for row in cur.fetchall()}

        return {
            'total_attendees': total_attendees,
            'total_revenue': total_revenue if total_revenue else 0,
            'tickets_sold_per_type': tickets_sold_per_type
        }
    except (Exception, psycopg2.Error) as error:
        print(f"Error fetching dashboard data: {error}")
        return {}
    finally:
        if conn: cur.close(); conn.close()

def get_attendees_by_ticket_type(event_id: int, ticket_type_name: str):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = """
    SELECT a.name, a.email
    FROM attendees a
    JOIN attendee_tickets at ON a.attendee_id = at.attendee_id
    JOIN tickets t ON at.ticket_id = t.ticket_id
    WHERE a.event_id = %s AND t.ticket_type_name = %s;
    """
    df = pd.read_sql_query(query, conn, params=(event_id, ticket_type_name))
    conn.close()
    return df

# Helper for communication (dummy function)
def send_confirmation_email(attendee_email: str, event_name: str, tickets_purchased: str):
    """Simulates sending a confirmation email."""
    print(f"Email sent to {attendee_email} for event '{event_name}'.")
    print(f"Tickets purchased: {tickets_purchased}")
    # In a real app, you would use a library like smtplib here.
    return True