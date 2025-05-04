# File: blueprints/agent.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection

agent_bp = Blueprint('agent', __name__, template_folder='../templates')

def login_required_agent(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('user_type') != 'agent':
            flash("Please log in as a booking agent first", "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return decorated_function

@agent_bp.route('/home')
@login_required_agent
def agent_home():
    return render_template('agent_home.html')

@agent_bp.route('/my_flights')
@login_required_agent
def my_flights():
    agent_email = session['user']['email']
    connection = get_db_connection()
    flights = []
    try:
        query = """
            SELECT f.*
            FROM ticket t
            JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
            JOIN purchases p ON p.ticket_id = t.ticket_id
            WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
        """
        with connection.cursor() as cursor:
            cursor.execute(query, (agent_email,))
            flights = cursor.fetchall()
    except Exception as e:
        flash(f"Flight query failed: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('agent_my_flights.html', flights=flights)

@agent_bp.route('/purchase_ticket', methods=['GET', 'POST'])
@login_required_agent
def purchase_ticket():
    if request.method == 'POST':
        flight_airline = request.form.get('airline_name')
        flight_num = request.form.get('flight_num')
        customer_email = request.form.get('customer_email')
        agent_email = session['user']['email']
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(ticket_id) as max_id FROM ticket")
                result = cursor.fetchone()
                new_ticket_id = (result['max_id'] or 0) + 1

                sql_ticket = "INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)"
                cursor.execute(sql_ticket, (new_ticket_id, flight_airline, flight_num))

                agent_id_query = "SELECT booking_agent_id FROM booking_agent WHERE email = %s"
                cursor.execute(agent_id_query, (agent_email,))
                agent = cursor.fetchone()
                booking_agent_id = agent['booking_agent_id'] if agent else None

                sql_purchase = "INSERT INTO purchases (ticket_id, customer_email, booking_agent_id, purchase_date) VALUES (%s, %s, %s, CURDATE())"
                cursor.execute(sql_purchase, (new_ticket_id, customer_email, booking_agent_id))
                connection.commit()
                flash("Ticket purchase by agent is successful", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Failed to purchase tickets on behalf of others: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('agent.my_flights'))
    return render_template('agent_purchase_ticket.html')

@agent_bp.route('/view_commission', methods=['GET', 'POST'])
@login_required_agent
def view_commission():
    agent_email = session['user']['email']
    total_commission = 0
    average_commission = 0
    ticket_count = 0
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT SUM(f.price*0.1) as total_commission, COUNT(*) as ticket_count
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
                  AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            """
            cursor.execute(query, (agent_email,))
            result = cursor.fetchone()
            if result:
                total_commission = result['total_commission'] or 0
                ticket_count = result['ticket_count'] or 0
                average_commission = total_commission / ticket_count if ticket_count > 0 else 0
    except Exception as e:
        flash(f"Commission query failed: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('agent_view_commission.html', total_commission=total_commission, average_commission=average_commission, ticket_count=ticket_count)

@agent_bp.route('/view_top_customers')
@login_required_agent
def view_top_customers():
    agent_email = session['user']['email']
    top_customers_by_tickets = []
    top_customers_by_commission = []
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_tickets = """
                SELECT p.customer_email, COUNT(*) as ticket_count
                FROM purchases p
                WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
                  AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY p.customer_email
                ORDER BY ticket_count DESC
                LIMIT 5
            """
            cursor.execute(query_tickets, (agent_email,))
            top_customers_by_tickets = cursor.fetchall()

            query_commission = """
                SELECT p.customer_email, SUM(f.price*0.1) as total_commission
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.booking_agent_id = (SELECT booking_agent_id FROM booking_agent WHERE email = %s)
                  AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY p.customer_email
                ORDER BY total_commission DESC
                LIMIT 5
            """
            cursor.execute(query_commission, (agent_email,))
            top_customers_by_commission = cursor.fetchall()
    except Exception as e:
        flash(f"Customer query failed: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('agent_view_top_customers.html', top_customers_by_tickets=top_customers_by_tickets, top_customers_by_commission=top_customers_by_commission)