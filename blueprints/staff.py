# File: blueprints/staff.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection

staff_bp = Blueprint('staff', __name__, template_folder='../templates')

def login_required_staff(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('user_type') != 'staff':
            flash("Please log in as an airline staff", "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return decorated_function

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user.get('is_admin'):
            flash("This action requires admin privileges", "danger")
            return redirect(url_for('staff.staff_home'))
        return func(*args, **kwargs)
    return decorated_function

def operator_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user.get('is_operator'):
            flash("This action requires operator privileges", "danger")
            return redirect(url_for('staff.staff_home'))
        return func(*args, **kwargs)
    return decorated_function

@staff_bp.route('/home')
@login_required_staff
def staff_home():
    return render_template('staff_home.html')

@staff_bp.route('/my_flights')
@login_required_staff
def my_flights():
    airline_name = session['user'].get('airline_name')
    connection = get_db_connection()
    flights = []
    try:
        query = """
            SELECT * FROM flight 
            WHERE airline_name = %s AND departure_time >= NOW() AND departure_time <= DATE_ADD(NOW(), INTERVAL 30 DAY)
        """
        with connection.cursor() as cursor:
            cursor.execute(query, (airline_name,))
            flights = cursor.fetchall()
    except Exception as e:
        flash(f"Failed to retrieve flights: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('staff_my_flights.html', flights=flights)

@staff_bp.route('/create_flight', methods=['GET', 'POST'])
@login_required_staff
@admin_required
def create_flight():
    if request.method == 'POST':
        airline_name = session['user'].get('airline_name')
        flight_num = request.form.get('flight_num')
        departure_airport = request.form.get('departure_airport')
        departure_time = request.form.get('departure_time')
        arrival_airport = request.form.get('arrival_airport')
        arrival_time = request.form.get('arrival_time')
        price = request.form.get('price')
        status = request.form.get('status')
        airplane_id = request.form.get('airplane_id')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = """
                    INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (airline_name, flight_num, departure_airport, departure_time, arrival_airport, arrival_time, price, status, airplane_id))
                connection.commit()
                flash("Flight created successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Flight creation failed: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.my_flights'))
    return render_template('create_flight.html')

@staff_bp.route('/change_status', methods=['GET', 'POST'])
@login_required_staff
@operator_required
def change_status():
    if request.method == 'POST':
        airline_name = session['user'].get('airline_name')
        flight_num = request.form.get('flight_num')
        new_status = request.form.get('new_status')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "UPDATE flight SET status = %s WHERE airline_name = %s AND flight_num = %s"
                cursor.execute(sql, (new_status, airline_name, flight_num))
                connection.commit()
                flash("Flight status updated successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Status update failed: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.my_flights'))
    return render_template('change_status.html')

@staff_bp.route('/add_airplane', methods=['GET', 'POST'])
@login_required_staff
@admin_required
def add_airplane():
    if request.method == 'POST':
        airline_name = session['user'].get('airline_name')
        airplane_id = request.form.get('airplane_id')
        seats = request.form.get('seats')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO airplane (airline_name, airplane_id, seats) VALUES (%s, %s, %s)"
                cursor.execute(sql, (airline_name, airplane_id, seats))
                connection.commit()
                flash("Airplane added successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Failed to add airplane: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_airplane.html')

@staff_bp.route('/add_airport', methods=['GET', 'POST'])
@login_required_staff
@admin_required
def add_airport():
    if request.method == 'POST':
        airport_name = request.form.get('airport_name')
        airport_city = request.form.get('airport_city')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO airport (airport_name, airport_city) VALUES (%s, %s)"
                cursor.execute(sql, (airport_name, airport_city))
                connection.commit()
                flash("Airport added successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Failed to add airport: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_airport.html')

@staff_bp.route('/view_agents')
@login_required_staff
def view_agents():
    top_month = []
    top_year = []
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_month = """
                SELECT ba.email, COUNT(*) as ticket_count
                FROM purchases p
                JOIN booking_agent ba ON p.booking_agent_id = ba.booking_agent_id
                WHERE p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
                GROUP BY ba.email
                ORDER BY ticket_count DESC
                LIMIT 5
            """
            cursor.execute(query_month)
            top_month = cursor.fetchall()

            query_year = """
                SELECT ba.email, SUM(f.price*0.1) as total_commission
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                JOIN booking_agent ba ON p.booking_agent_id = ba.booking_agent_id
                WHERE p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY ba.email
                ORDER BY total_commission DESC
                LIMIT 5
            """
            cursor.execute(query_year)
            top_year = cursor.fetchall()
    except Exception as e:
        flash(f"Failed to retrieve agent data: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('view_agents.html', top_month=top_month, top_year=top_year)

@staff_bp.route('/view_frequent_customers')
@login_required_staff
def view_frequent_customers():
    frequent_customers = []
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT p.customer_email, COUNT(*) as ticket_count
                FROM purchases p
                WHERE p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY p.customer_email
                ORDER BY ticket_count DESC
                LIMIT 1
            """
            cursor.execute(query)
            frequent_customers = cursor.fetchall()
    except Exception as e:
        flash(f"Failed to retrieve frequent customers: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('view_frequent_customers.html', frequent_customers=frequent_customers)

@staff_bp.route('/view_reports')
@login_required_staff
def view_reports():
    reports = {}
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_total = "SELECT COUNT(*) as total_tickets FROM purchases WHERE purchase_date BETWEEN %s AND %s"
            cursor.execute(query_total, ('2025-01-01', '2025-12-31'))
            reports['total_tickets'] = cursor.fetchone()['total_tickets']
            query_monthly = """
                SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') as month, COUNT(*) as tickets_sold
                FROM purchases p
                GROUP BY month
            """
            cursor.execute(query_monthly)
            reports['monthly'] = cursor.fetchall()
    except Exception as e:
        flash(f"Failed to get reports: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('view_reports.html', reports=reports)

@staff_bp.route('/compare_revenue')
@login_required_staff
def compare_revenue():
    direct_revenue = 0
    indirect_revenue = 0
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_direct = """
                SELECT SUM(f.price) as revenue
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.booking_agent_id IS NULL AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            """
            cursor.execute(query_direct)
            result = cursor.fetchone()
            direct_revenue = result['revenue'] if result and result['revenue'] else 0

            query_indirect = """
                SELECT SUM(f.price) as revenue
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.airline_name = f.airline_name AND t.flight_num = f.flight_num
                WHERE p.booking_agent_id IS NOT NULL AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            """
            cursor.execute(query_indirect)
            result = cursor.fetchone()
            indirect_revenue = result['revenue'] if result and result['revenue'] else 0
    except Exception as e:
        flash(f"Failed to retrieve revenue comparison: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('compare_revenue.html', direct_revenue=direct_revenue, indirect_revenue=indirect_revenue)

@staff_bp.route('/view_top_destinations')
@login_required_staff
def view_top_destinations():
    top_destinations_3m = []
    top_destinations_year = []
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            query_3m = """
                SELECT arrival_airport, COUNT(*) as count
                FROM flight
                WHERE departure_time >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
                GROUP BY arrival_airport
                ORDER BY count DESC
                LIMIT 3
            """
            cursor.execute(query_3m)
            top_destinations_3m = cursor.fetchall()

            query_year = """
                SELECT arrival_airport, COUNT(*) as count
                FROM flight
                WHERE departure_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY arrival_airport
                ORDER BY count DESC
                LIMIT 3
            """
            cursor.execute(query_year)
            top_destinations_year = cursor.fetchall()
    except Exception as e:
        flash(f"Failed to retrieve top destinations: {str(e)}", "danger")
    finally:
        connection.close()
    return render_template('view_top_destinations.html', top_destinations_3m=top_destinations_3m, top_destinations_year=top_destinations_year)

@staff_bp.route('/grant_permission', methods=['GET', 'POST'])
@login_required_staff
@admin_required
def grant_permission():
    if request.method == 'POST':
        staff_username = request.form.get('staff_username')
        permission_type = request.form.get('permission_type')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO permission (username, permission_type) VALUES (%s, %s)"
                cursor.execute(sql, (staff_username, permission_type))
                connection.commit()
                flash("Permission granted successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Failed to grant permission: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('grant_permission.html')

@staff_bp.route('/add_booking_agent', methods=['GET', 'POST'])
@login_required_staff
@admin_required
def add_booking_agent():
    if request.method == 'POST':
        agent_email = request.form.get('agent_email')
        airline_name = session['user'].get('airline_name')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO booking_agent_work_for (email, airline_name) VALUES (%s, %s)"
                cursor.execute(sql, (agent_email, airline_name))
                connection.commit()
                flash("Booking agent added successfully", "success")
        except Exception as e:
            connection.rollback()
            flash(f"Failed to add booking agent: {str(e)}", "danger")
        finally:
            connection.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_booking_agent.html')