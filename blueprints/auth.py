# File: blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db_connection
import pymysql

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/register/<user_type>', methods=['GET', 'POST'])
def register(user_type):
    if user_type not in ('customer', 'agent', 'staff'):
        flash("Invalid registration type", "danger")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash("Email and password are required", "warning")
            return redirect(request.url)

        # 收集其它字段，视 user_type 而定
        data = {}
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                if user_type == 'customer':
                    required = ('name','building_number','street','city','state',
                                'phone_number','passport_number','passport_expiration',
                                'passport_country','date_of_birth')
                    for f in required:
                        v = request.form.get(f, '').strip()
                        if not v:
                            raise ValueError(f"{f.replace('_', ' ').capitalize()} is required")
                        data[f] = v
                    sql = """
                    INSERT INTO customer
                     (email, password, name,
                      building_number, street, city, state,
                      phone_number, passport_number, passport_expiration,
                      passport_country, date_of_birth)
                    VALUES (%s, MD5(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    params = (
                        email, password, data['name'],
                        data['building_number'], data['street'],
                        data['city'], data['state'], data['phone_number'],
                        data['passport_number'], data['passport_expiration'],
                        data['passport_country'], data['date_of_birth']
                    )
                    cur.execute(sql, params)
                elif user_type == 'agent':
                    ba_id = request.form.get('booking_agent_id', '').strip()
                    if not ba_id:
                        raise ValueError("Booking Agent ID is required")
                    sql = """
                    INSERT INTO booking_agent
                     (email, password, booking_agent_id)
                    VALUES (%s, MD5(%s), %s)
                    """
                    params = (email, password, ba_id)
                    cur.execute(sql, params)
                else:  # staff
                    required = ('first_name','last_name','date_of_birth','airline_name')
                    for f in required:
                        v = request.form.get(f, '').strip()
                        if not v:
                            raise ValueError(f"{f.replace('_', ' ').capitalize()} is required")
                        data[f] = v
                    sql = """
                    INSERT INTO airline_staff
                     (username, password, first_name, last_name,
                      date_of_birth, airline_name)
                    VALUES (%s, MD5(%s), %s, %s, %s, %s)
                    """
                    params = (
                        email, password,
                        data['first_name'], data['last_name'],
                        data['date_of_birth'], data['airline_name']
                    )
                    cur.execute(sql, params)
                    if request.form.get('is_admin'):
                        cur.execute(
                        "INSERT INTO permission (username, permission_type) VALUES (%s, %s)",
                        (email, 'Admin')
                        )
                    if request.form.get('is_operator'):
                        cur.execute(
                        "INSERT INTO permission (username, permission_type) VALUES (%s, %s)",
                        (email, 'Operator')
                        )

            conn.commit()
            flash("Registration successful, please login", "success")
            return redirect(url_for('auth.login'))

        except ValueError as ve:
            flash(str(ve), "warning")
            return redirect(request.url)
        except pymysql.err.IntegrityError:
            flash("This email is already registered", "danger")
            return redirect(request.url)
        except Exception as e:
            flash(f"Registration failed: {e}", "danger")
            return redirect(request.url)
        finally:
            conn.close()

    # GET
    return render_template('register.html', user_type=user_type)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        email     = request.form.get('email', '').strip()
        password  = request.form.get('password', '')

        if user_type not in ('customer', 'agent', 'staff') or not email or not password:
            flash("Please fill in all fields correctly", "warning")
            return redirect(request.url)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                if user_type == 'customer':
                    cur.execute(
                        "SELECT email,name,city FROM customer "
                        "WHERE email=%s AND password=MD5(%s)",
                        (email, password)
                    )
                elif user_type == 'agent':
                    cur.execute(
                        "SELECT email,booking_agent_id FROM booking_agent "
                        "WHERE email=%s AND password=MD5(%s)",
                        (email, password)
                    )
                else:  # staff
                    cur.execute(
                        "SELECT username,airline_name FROM airline_staff "
                        "WHERE username=%s AND password=MD5(%s)",
                        (email, password)
                    )
                user = cur.fetchone()

            if not user:
                flash("Incorrect username or password", "danger")
                return redirect(request.url)

            # 登录成功
            session.clear()
            if user_type == 'customer':
                session['user'] = {
                    'email': user['email'],
                    'user_type': 'customer',
                    'name': user.get('name')
                }
                redirect_to = 'customer.customer_home'
            elif user_type == 'agent':
                session['user'] = {
                    'email': user['email'],
                    'user_type': 'agent',
                    'agent_id': user.get('booking_agent_id')
                }
                redirect_to = 'agent.agent_home'
            else:
                session['user'] = {
                    'email': user['username'],
                    'user_type': 'staff',
                    'airline_name': user.get('airline_name')
                }
                redirect_to = 'staff.staff_home'

            flash("Login successful", "success")
            return redirect(url_for(redirect_to))

        finally:
            conn.close()

    # GET
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have logged out", "info")
    return redirect(url_for('public.index'))