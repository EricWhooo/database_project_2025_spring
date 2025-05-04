# File: blueprints/customer.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection

customer_bp = Blueprint('customer', __name__, template_folder='../templates')

def login_required_customer(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('user_type') != 'customer':
            flash("Please log in as a customer first", "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return decorated_function

@customer_bp.route('/home')
@login_required_customer
def customer_home():
    return render_template('customer_home.html')

@customer_bp.route('/my_flights')
@login_required_customer
def my_flights():
    customer_email = session['user']['email']
    connection = get_db_connection()
    flights = []
    try:
        query = """
            SELECT f.*
            FROM ticket t
            JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
            JOIN purchases p ON p.ticket_id = t.ticket_id
            WHERE p.customer_email = %s
        """
        with connection.cursor() as cursor:
            cursor.execute(query, (customer_email,))
            flights = cursor.fetchall()
    except Exception as e:
        flash(f"Flight query failed: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('my_flights.html', flights=flights)

@customer_bp.route('/purchase_ticket', methods=['GET', 'POST'])
@login_required_customer
def purchase_ticket():
    if request.method == 'POST':
        flight_airline = request.form.get('airline_name')
        flight_num = request.form.get('flight_num')
        customer_email = session['user']['email']
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(ticket_id) as max_id FROM ticket")
                result = cursor.fetchone()
                new_ticket_id = (result['max_id'] or 0) + 1

                sql_ticket = "INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)"
                cursor.execute(sql_ticket, (new_ticket_id, flight_airline, flight_num))

                sql_purchase = "INSERT INTO purchases (ticket_id, customer_email, purchase_date) VALUES (%s, %s, CURDATE())"
                cursor.execute(sql_purchase, (new_ticket_id, customer_email))
                connection.commit()
                flash("Ticket purchase successful", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Ticket purchase failed: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('customer.my_flights'))
    return render_template('purchase_ticket.html')

@customer_bp.route('/track_spending', methods=['GET', 'POST'])
@login_required_customer
def track_spending():
    customer_email = session['user']['email']
    total_spent = 0
    monthly_spending = {}
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_total = """
                SELECT SUM(f.price) as total
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.customer_email = %s AND f.departure_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
            """
            cursor.execute(query_total, (customer_email,))
            result_total = cursor.fetchone()
            total_spent = result_total['total'] if result_total and result_total['total'] else 0

            query_monthly = """
                SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') as month, SUM(f.price) as monthly_total
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.customer_email = %s AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                GROUP BY month
            """
            cursor.execute(query_monthly, (customer_email,))
            results = cursor.fetchall()
            for row in results:
                monthly_spending[row['month']] = row['monthly_total']
    except Exception as e:
        flash(f"Failed to obtain consumption statistics: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('track_spending.html', total_spent=total_spent, monthly_spending=monthly_spending)