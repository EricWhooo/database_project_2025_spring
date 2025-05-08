# blueprints/agent.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from functools import wraps

agent_bp = Blueprint('agent', __name__, template_folder='../templates')

def login_required_agent(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('user_type') != 'agent':
            flash("Please log in as a booking agent first.", "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return decorated_function

def _get_agent_id_by_email(email):
    """Helper: fetch booking_agent_id from booking_agent by email."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT booking_agent_id FROM booking_agent WHERE email = %s",
                (email,)
            )
            row = cursor.fetchone()
            return row['booking_agent_id'] if row else None
    finally:
        conn.close()

@agent_bp.route('/home')
@login_required_agent
def agent_home():
    return render_template('agent_home.html')

@agent_bp.route('/my_flights')
@login_required_agent
def my_flights():
    agent_email = session['user']['email']
    conn = get_db_connection()
    flights = []
    try:
        sql = """
            SELECT f.*
              FROM ticket t
              JOIN flight f
                ON t.airline_name = f.airline_name
               AND t.flight_num    = f.flight_num
              JOIN purchases p
                ON p.ticket_id = t.ticket_id
             WHERE p.booking_agent_id = (
                       SELECT booking_agent_id
                         FROM booking_agent
                        WHERE email = %s
                   )
          ORDER BY f.departure_time
        """
        with conn.cursor() as cur:
            cur.execute(sql, (agent_email,))
            flights = cur.fetchall()
    except Exception as e:
        flash(f"Failed to load your flights: {e}", "danger")
    finally:
        conn.close()
    return render_template('agent_my_flights.html', flights=flights)

@agent_bp.route('/purchase_ticket', methods=['GET', 'POST'])
@login_required_agent
def purchase_ticket():
    if request.method == 'POST':
        airline = request.form.get('airline_name')
        flight_num = request.form.get('flight_num')
        customer_email = request.form.get('customer_email')
        agent_email = session['user']['email']
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Verify agent is authorized for this airline
                cur.execute("""
                    SELECT 1
                      FROM booking_agent_work_for
                     WHERE email=%s AND airline_name=%s
                """, (agent_email, airline))
                if not cur.fetchone():
                    flash("You are not authorized to book for this airline.", "danger")
                    return redirect(url_for('agent.purchase_ticket'))

                # Get the airplane_id for this flight
                cur.execute("""
                    SELECT airplane_id
                      FROM flight
                     WHERE airline_name=%s AND flight_num=%s
                """, (airline, flight_num))
                row = cur.fetchone()
                if not row:
                    flash("The specified flight does not exist.", "warning")
                    return redirect(url_for('agent.purchase_ticket'))
                airplane_id = row['airplane_id']

                # Check capacity vs. already sold
                cur.execute("""
                    SELECT seats
                      FROM airplane
                     WHERE airline_name=%s AND airplane_id=%s
                """, (airline, airplane_id))
                seats = cur.fetchone()['seats'] or 0

                cur.execute("""
                    SELECT COUNT(*) AS sold
                      FROM ticket t
                      JOIN purchases p ON t.ticket_id = p.ticket_id
                     WHERE t.airline_name=%s AND t.flight_num=%s
                """, (airline, flight_num))
                sold = cur.fetchone()['sold'] or 0

                if sold >= seats:
                    flash("Sorry, there are no available seats on this flight.", "warning")
                    return redirect(url_for('agent.purchase_ticket'))

                # Insert new ticket
                cur.execute("SELECT MAX(ticket_id) AS max_id FROM ticket")
                new_ticket_id = (cur.fetchone()['max_id'] or 0) + 1
                cur.execute(
                    "INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)",
                    (new_ticket_id, airline, flight_num)
                )

                # Insert purchase record
                agent_id = _get_agent_id_by_email(agent_email)
                if agent_id is None:
                    flash("Internal error: cannot determine your agent ID.", "danger")
                    return redirect(url_for('agent.purchase_ticket'))

                cur.execute(
                    "INSERT INTO purchases (ticket_id, customer_email, booking_agent_id, purchase_date) "
                    "VALUES (%s, %s, %s, CURDATE())",
                    (new_ticket_id, customer_email, agent_id)
                )

            conn.commit()
            flash("Ticket purchase successful.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Failed to purchase ticket: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('agent.my_flights'))

    return render_template('agent_purchase_ticket.html')

@agent_bp.route('/view_commission')
@login_required_agent
def view_commission():
    """
    Total commission, ticket count and average commission
    in the past 30 days for this agent.
    """
    agent_email = session['user']['email']
    agent_id = _get_agent_id_by_email(agent_email)
    if agent_id is None:
        flash("Internal error: cannot determine your agent ID.", "danger")
        return redirect(url_for('agent.agent_home'))

    ticket_count = 0
    total_commission = 0.0
    average_commission = 0.0

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  COUNT(*) AS tickets,
                  SUM(f.price * 0.01) AS commission
                FROM purchases p
                  JOIN ticket t
                    ON p.ticket_id = t.ticket_id
                  JOIN flight f
                    ON t.airline_name = f.airline_name
                   AND t.flight_num    = f.flight_num
                WHERE p.booking_agent_id = %s
                  AND p.purchase_date >= CURDATE() - INTERVAL 30 DAY
            """, (agent_id,))
            row = cur.fetchone()
            ticket_count = row['tickets'] or 0
            total_commission = float(row['commission'] or 0.0)
            if ticket_count > 0:
                average_commission = total_commission / ticket_count
    except Exception as e:
        flash(f"Failed to load commission data: {e}", "danger")
    finally:
        conn.close()

    return render_template(
        'agent_view_commission.html',
        total_commission=round(total_commission, 2),
        ticket_count=ticket_count,
        average_commission=round(average_commission, 2)
    )

@agent_bp.route('/view_top_customers')
@login_required_agent
def view_top_customers():
    """
    Show top 10 customers for this agent by:
      1) ticket count
      2) commission amount (1% of ticket price)
    """
    agent_email = session['user']['email']
    agent_id = _get_agent_id_by_email(agent_email)
    if agent_id is None:
        flash("Internal error: cannot determine your agent ID.", "danger")
        return redirect(url_for('agent.agent_home'))

    sql_by_count = """
        SELECT
          p.customer_email    AS customer_email,
          COUNT(*)            AS ticket_count
        FROM purchases p
        WHERE p.booking_agent_id = %s
        GROUP BY p.customer_email
        ORDER BY ticket_count DESC
        LIMIT 10
    """
    sql_by_comm = """
        SELECT
          p.customer_email               AS customer_email,
          ROUND(SUM(f.price * 0.01), 2)  AS total_commission
        FROM purchases p
          JOIN ticket t
            ON p.ticket_id = t.ticket_id
          JOIN flight f
            ON t.airline_name = f.airline_name
           AND t.flight_num    = f.flight_num
        WHERE p.booking_agent_id = %s
        GROUP BY p.customer_email
        ORDER BY total_commission DESC
        LIMIT 10
    """

    top_customers_by_tickets = []
    top_customers_by_commission = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_by_count, (agent_id,))
            top_customers_by_tickets = cur.fetchall()

            cur.execute(sql_by_comm, (agent_id,))
            top_customers_by_commission = cur.fetchall()
    except Exception as e:
        flash(f"Failed to load top customers: {e}", "danger")
    finally:
        conn.close()

    return render_template(
        'agent_view_top_customers.html',
        top_customers_by_tickets=top_customers_by_tickets,
        top_customers_by_commission=top_customers_by_commission
    )