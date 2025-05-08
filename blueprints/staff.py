from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
from functools import wraps

staff_bp = Blueprint('staff', __name__, template_folder='../templates')

def login_required_staff(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        if not user or user.get('user_type') != 'staff':
            flash("Please log in as airline staff", "warning")
            return redirect(url_for('auth.login'))
        return func(*args, **kwargs)
    return wrapper

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM permission WHERE username=%s AND LOWER(permission_type)='admin'",
                    (user['email'],)
                )
                if not cur.fetchone():
                    flash("Admin privilege required", "danger")
                    return redirect(url_for('staff.staff_home'))
        finally:
            conn.close()
        return func(*args, **kwargs)
    return wrapper

def operator_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = session.get('user')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM permission WHERE username=%s AND LOWER(permission_type)='operator'",
                    (user['email'],)
                )
                if not cur.fetchone():
                    flash("Operator privilege required", "danger")
                    return redirect(url_for('staff.staff_home'))
        finally:
            conn.close()
        return func(*args, **kwargs)
    return wrapper

@staff_bp.route('/home')
@login_required_staff
def staff_home():
    return render_template('staff_home.html')

@staff_bp.route('/my_flights')
@login_required_staff
def my_flights():
    airline = session['user']['airline_name']
    conn = get_db_connection()
    flights = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM flight
                WHERE airline_name=%s
                  AND departure_time>=NOW()
                  AND departure_time<=DATE_ADD(NOW(),INTERVAL 30 DAY)
            """, (airline,))
            flights = cur.fetchall()
    finally:
        conn.close()
    return render_template('staff_my_flights.html', flights=flights)

@staff_bp.route('/create_flight', methods=['GET','POST'])
@login_required_staff
@admin_required
def create_flight():
    if request.method=='POST':
        airline = session['user']['airline_name']
        data = {k: request.form[k] for k in (
            'flight_num','departure_airport','departure_time',
            'arrival_airport','arrival_time','price','status','airplane_id'
        )}
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                  INSERT INTO flight
                  (airline_name, flight_num, departure_airport, departure_time,
                   arrival_airport, arrival_time, price, status, airplane_id)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                  airline, data['flight_num'], data['departure_airport'], data['departure_time'],
                  data['arrival_airport'], data['arrival_time'], data['price'],
                  data['status'], data['airplane_id']
                ))
                conn.commit()
                flash("Flight created", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Create flight failed: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('staff.my_flights'))
    return render_template('create_flight.html')

@staff_bp.route('/change_status', methods=['GET','POST'])
@login_required_staff
@operator_required
def change_status():
    airline = session['user']['airline_name']

    if request.method == 'POST':
        flight_num = request.form.get('flight_num')
        new_status = request.form.get('new_status')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                  UPDATE flight
                     SET status=%s
                   WHERE airline_name=%s AND flight_num=%s
                """, (new_status, airline, flight_num))
            conn.commit()
            flash("Status updated", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Update failed: {e}", "danger")
        finally:
            conn.close()
        # 留在本页以查看更新结果
        return redirect(url_for('staff.change_status'))

    # GET: 先拉取该 airline 的所有航班
    conn = get_db_connection()
    flights = []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT flight_num, departure_airport, arrival_airport,
                       departure_time, arrival_time, status
                  FROM flight
                 WHERE airline_name=%s
                 ORDER BY departure_time
            """, (airline,))
            flights = cur.fetchall()
    finally:
        conn.close()

    return render_template('change_status.html', flights=flights)

@staff_bp.route('/add_airplane', methods=['GET','POST'])
@login_required_staff
@admin_required
def add_airplane():
    if request.method=='POST':
        airline = session['user']['airline_name']
        aid = request.form['airplane_id']
        seats = request.form['seats']
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                  "INSERT INTO airplane (airline_name, airplane_id, seats) VALUES (%s,%s,%s)",
                  (airline, aid, seats)
                )
                conn.commit()
                flash("Airplane added", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Add airplane failed: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_airplane.html')

@staff_bp.route('/add_airport', methods=['GET','POST'])
@login_required_staff
@admin_required
def add_airport():
    if request.method=='POST':
        name = request.form['airport_name']
        city = request.form['airport_city']
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                  "INSERT INTO airport (airport_name, airport_city) VALUES (%s,%s)",
                  (name, city)
                )
                conn.commit()
                flash("Airport added", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Add airport failed: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_airport.html')

@staff_bp.route('/view_agents')
@login_required_staff
def view_agents():
    top_month, top_year = [], []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT ba.email, COUNT(*) AS ticket_count
                FROM purchases p
                JOIN booking_agent ba ON p.booking_agent_id=ba.booking_agent_id
                WHERE p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
                GROUP BY ba.email
                ORDER BY ticket_count DESC
                LIMIT 5
            """)
            top_month = cur.fetchall()
            cur.execute("""
              SELECT ba.email, SUM(f.price*0.1) AS total_commission
                FROM purchases p
                JOIN ticket t ON p.ticket_id=t.ticket_id
                JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                JOIN booking_agent ba ON p.booking_agent_id=ba.booking_agent_id
                WHERE p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY ba.email
                ORDER BY total_commission DESC
                LIMIT 5
            """)
            top_year = cur.fetchall()
    finally:
        conn.close()
    return render_template('view_agents.html', top_month=top_month, top_year=top_year)

@staff_bp.route('/view_frequent_customers')
@login_required_staff
def view_frequent_customers():
    data = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT p.customer_email, COUNT(*) AS ticket_count
                FROM purchases p
                WHERE p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY p.customer_email
                ORDER BY ticket_count DESC
                LIMIT 5
            """)
            data = cur.fetchall()
    finally:
        conn.close()
    return render_template('view_frequent_customers.html', frequent_customers=data)

@staff_bp.route('/view_reports')
@login_required_staff
def view_reports():
    rpt = {'total_tickets':0, 'monthly':[]}
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total_tickets FROM purchases")
            rpt['total_tickets'] = cur.fetchone()['total_tickets']
            cur.execute("""
              SELECT DATE_FORMAT(p.purchase_date,'%Y-%m') AS month,
                     COUNT(*) AS tickets_sold
                FROM purchases p
                GROUP BY month
            """)
            rpt['monthly'] = cur.fetchall()
    finally:
        conn.close()
    return render_template('view_reports.html', reports=rpt)

@staff_bp.route('/compare_revenue')
@login_required_staff
def compare_revenue():
    direct = indirect = 0
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT SUM(f.price) AS revenue
                FROM purchases p
                JOIN ticket t ON p.ticket_id=t.ticket_id
                JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                WHERE p.booking_agent_id IS NULL
                  AND p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            """)
            direct = cur.fetchone().get('revenue') or 0
            cur.execute("""
              SELECT SUM(f.price) AS revenue
                FROM purchases p
                JOIN ticket t ON p.ticket_id=t.ticket_id
                JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                WHERE p.booking_agent_id IS NOT NULL
                  AND p.purchase_date>=DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
            """)
            indirect = cur.fetchone().get('revenue') or 0
    finally:
        conn.close()
    return render_template('compare_revenue.html',
                           direct_revenue=direct,
                           indirect_revenue=indirect)

@staff_bp.route('/view_top_destinations')
@login_required_staff
def view_top_destinations():
    top3m = top1y = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT arrival_airport, COUNT(*) AS count
                FROM flight
                WHERE departure_time>=DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
                GROUP BY arrival_airport
                ORDER BY count DESC
                LIMIT 3
            """)
            top3m = cur.fetchall()
            cur.execute("""
              SELECT arrival_airport, COUNT(*) AS count
                FROM flight
                WHERE departure_time>=DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
                GROUP BY arrival_airport
                ORDER BY count DESC
                LIMIT 3
            """)
            top1y = cur.fetchall()
    finally:
        conn.close()
    return render_template('view_top_destinations.html',
                           top_destinations_3m=top3m,
                           top_destinations_year=top1y)

@staff_bp.route('/grant_permission', methods=['GET','POST'])
@login_required_staff
@admin_required
def grant_permission():
    if request.method=='POST':
        usern = request.form['staff_username']
        perm  = request.form['permission_type']
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                  "INSERT INTO permission (username, permission_type) VALUES (%s,%s)",
                  (usern, perm)
                )
                conn.commit()
                flash("Permission granted", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Grant failed: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('grant_permission.html')

@staff_bp.route('/add_booking_agent', methods=['GET','POST'])
@login_required_staff
@admin_required
def add_booking_agent():
    if request.method=='POST':
        email = request.form['agent_email']
        airline = session['user']['airline_name']
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                  "INSERT INTO booking_agent_work_for (email, airline_name) VALUES (%s,%s)",
                  (email, airline)
                )
                conn.commit()
                flash("Agent added", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Add agent failed: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('staff.staff_home'))
    return render_template('add_booking_agent.html')

@staff_bp.route('/view_passengers', methods=['GET','POST'])
@login_required_staff
def view_passengers():
    airline = session['user']['airline_name']
    passengers = []
    flight_num = None
    if request.method == 'POST':
        flight_num = request.form.get('flight_num')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT p.customer_email, p.booking_agent_id, p.purchase_date
                    FROM purchases p
                    JOIN ticket t ON p.ticket_id = t.ticket_id
                   WHERE t.airline_name=%s AND t.flight_num=%s
                """, (airline, flight_num))
                passengers = cur.fetchall()
        finally:
            conn.close()
    return render_template('view_passengers.html',
                           passengers=passengers,
                           flight_num=flight_num)

@staff_bp.route('/customer_flights', methods=['GET','POST'])
@login_required_staff
def customer_flights():
    airline = session['user']['airline_name']
    flights = []
    customer_email = None
    if request.method == 'POST':
        customer_email = request.form.get('customer_email')
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                  SELECT f.*
                    FROM purchases p
                    JOIN ticket t ON p.ticket_id = t.ticket_id
                    JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                   WHERE p.customer_email=%s AND f.airline_name=%s
                   ORDER BY f.departure_time
                """, (customer_email, airline))
                flights = cur.fetchall()
        finally:
            conn.close()
    return render_template('staff_customer_flights.html',
                           flights=flights,
                           customer_email=customer_email)

@staff_bp.route('/status_summary')
@login_required_staff
def status_summary():
    airline = session['user']['airline_name']
    summary = []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT status, COUNT(*) AS count
                FROM flight
               WHERE airline_name=%s
               GROUP BY status
            """, (airline,))
            summary = cur.fetchall()
    finally:
        conn.close()
    return render_template('status_summary.html', summary=summary)