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
              JOIN flight f
                ON t.airline_name = f.airline_name
               AND t.flight_num    = f.flight_num
              JOIN purchases p
                ON p.ticket_id = t.ticket_id
             WHERE p.customer_email = %s
          ORDER BY f.departure_time
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
        airline = request.form.get('airline_name')
        flight_num = request.form.get('flight_num')
        customer_email = session['user']['email']
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # 1. 检查航班并获取 airplane_id
                cursor.execute("""
                    SELECT airplane_id
                      FROM flight
                     WHERE airline_name=%s AND flight_num=%s
                """, (airline, flight_num))
                row = cursor.fetchone()
                if not row:
                    flash("The specified flight does not exist.", "warning")
                    return redirect(url_for('customer.purchase_ticket'))
                airplane_id = row['airplane_id']

                # 2. 查询飞机座位数
                cursor.execute("""
                    SELECT seats
                      FROM airplane
                     WHERE airline_name=%s AND airplane_id=%s
                """, (airline, airplane_id))
                seats = cursor.fetchone()['seats'] or 0

                # 3. 查询已售出票数
                cursor.execute("""
                    SELECT COUNT(*) AS sold
                      FROM ticket t
                      JOIN purchases p ON t.ticket_id = p.ticket_id
                     WHERE t.airline_name=%s AND t.flight_num=%s
                """, (airline, flight_num))
                sold = cursor.fetchone()['sold'] or 0

                if sold >= seats:
                    flash("Sorry, there are no seats available on this flight.", "warning")
                    return redirect(url_for('customer.purchase_ticket'))

                # 4. 插入 ticket & purchases
                cursor.execute("SELECT MAX(ticket_id) AS max_id FROM ticket")
                new_ticket_id = (cursor.fetchone()['max_id'] or 0) + 1

                cursor.execute(
                    "INSERT INTO ticket (ticket_id, airline_name, flight_num) VALUES (%s, %s, %s)",
                    (new_ticket_id, airline, flight_num)
                )
                cursor.execute(
                    "INSERT INTO purchases (ticket_id, customer_email, purchase_date) VALUES (%s, %s, CURDATE())",
                    (new_ticket_id, customer_email)
                )
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
    # 默认统计过去 6 个月
    months_interval = 6
    # 默认总计过去一年
    year_interval = 12

    # 可扩展：从 request.form 获取自定义日期区间（此处简化只用固定区间）
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. 过去一年总支出
            query_total = """
                SELECT SUM(f.price) AS total
                  FROM purchases p
                  JOIN ticket t ON p.ticket_id = t.ticket_id
                  JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                 WHERE p.customer_email=%s
                   AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
            """
            cursor.execute(query_total, (customer_email, year_interval))
            result_total = cursor.fetchone()
            total_spent = result_total['total'] or 0

            # 2. 最近 6 个月按月统计
            query_monthly = """
                SELECT DATE_FORMAT(p.purchase_date,'%%Y-%%m') AS month,
                       SUM(f.price) AS monthly_total
                  FROM purchases p
                  JOIN ticket t ON p.ticket_id = t.ticket_id
                  JOIN flight f ON t.airline_name=f.airline_name AND t.flight_num=f.flight_num
                 WHERE p.customer_email=%s
                   AND p.purchase_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
                 GROUP BY month
                 ORDER BY month
            """
            cursor.execute(query_monthly, (customer_email, months_interval))
            for row in cursor.fetchall():
                monthly_spending[row['month']] = row['monthly_total'] or 0
    except Exception as e:
        flash(f"Failed to obtain spending statistics: {str(e)}", "danger")
    finally:
        connection.close()

    return render_template('track_spending.html',
                           total_spent=total_spent,
                           monthly_spending=monthly_spending)