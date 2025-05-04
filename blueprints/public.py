# File: blueprints/public.py
from flask import Blueprint, render_template, request, flash
from db import get_db_connection

public_bp = Blueprint('public', __name__, template_folder='../templates')

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/search', methods=['GET', 'POST'])
def search_flights():
    flights = []
    if request.method == 'POST':
        source = request.form.get('source')
        destination = request.form.get('destination')
        date = request.form.get('date')
        connection = get_db_connection()
        try:
            query = """
                SELECT f.*, a1.airport_city as departure_city, a2.airport_city as arrival_city
                FROM flight f
                JOIN airport a1 ON f.departure_airport = a1.airport_name
                JOIN airport a2 ON f.arrival_airport = a2.airport_name
                WHERE (a1.airport_name = %s OR a1.airport_city = %s)
                  AND (a2.airport_name = %s OR a2.airport_city = %s)
                  AND DATE(f.departure_time) = %s
            """
            with connection.cursor() as cursor:
                cursor.execute(query, (source, source, destination, destination, date))
                flights = cursor.fetchall()
        except Exception as e:
            flash(f"Flight query failed: {str(e)}", "danger")
        finally:
            connection.close()
    return render_template('search_results.html', flights=flights)