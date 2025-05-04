# File: blueprints/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import pymysql
from db import get_db_connection

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/register/<user_type>', methods=['GET', 'POST'])
def register(user_type):
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')  # 直接使用用户输入的纯文本密码
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if user_type == 'customer':
                    name = request.form.get('name')
                    building_number = request.form.get('building_number')
                    street = request.form.get('street')
                    city = request.form.get('city')
                    state = request.form.get('state')
                    phone_number = request.form.get('phone_number')
                    passport_number = request.form.get('passport_number')
                    passport_expiration = request.form.get('passport_expiration')
                    passport_country = request.form.get('passport_country')
                    date_of_birth = request.form.get('date_of_birth')
                    sql = """INSERT INTO customer 
                             (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth) 
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    cursor.execute(sql, (email, name, password, building_number, street, city, state, phone_number, passport_number, passport_expiration, passport_country, date_of_birth))
                elif user_type == 'agent':
                    booking_agent_id = request.form.get('booking_agent_id')
                    sql = """INSERT INTO booking_agent (email, password, booking_agent_id)
                             VALUES (%s, %s, %s)"""
                    cursor.execute(sql, (email, password, booking_agent_id))
                elif user_type == 'staff':
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    date_of_birth = request.form.get('date_of_birth')
                    airline_name = request.form.get('airline_name')
                    sql = """INSERT INTO airline_staff (username, password, first_name, last_name, date_of_birth, airline_name)
                             VALUES (%s, %s, %s, %s, %s, %s)"""
                    cursor.execute(sql, (email, password, first_name, last_name, date_of_birth, airline_name))
                connection.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('auth.login'))
        except pymysql.MySQLError as e:
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(request.url)
        finally:
            connection.close()
    return render_template('register.html', user_type=user_type)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        email = request.form.get('email')
        password = request.form.get('password')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if user_type == 'customer':
                    sql = "SELECT * FROM customer WHERE email = %s"
                elif user_type == 'agent':
                    sql = "SELECT * FROM booking_agent WHERE email = %s"
                elif user_type == 'staff':
                    sql = "SELECT * FROM airline_staff WHERE username = %s"
                else:
                    flash('Invalid user type', 'danger')
                    return redirect(request.url)
                cursor.execute(sql, (email,))
                user = cursor.fetchone()
                # 直接比较纯文本密码
                if user and user['password'] == password:
                    session['user'] = {
                        'email': email,
                        'user_type': user_type,
                        'airline_name': user.get('airline_name', None),
                        'is_admin': False,
                        'is_operator': False
                    }
                    flash('Login successful', 'success')
                    if user_type == 'customer':
                        return redirect(url_for('customer.customer_home'))
                    elif user_type == 'agent':
                        return redirect(url_for('agent.agent_home'))
                    elif user_type == 'staff':
                        return redirect(url_for('staff.staff_home'))
                else:
                    flash('Incorrect username or password', 'danger')
        except pymysql.MySQLError as e:
            flash(f'Login failed: {str(e)}', 'danger')
        finally:
            connection.close()
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have logged out', 'info')
    return redirect(url_for('public.index'))