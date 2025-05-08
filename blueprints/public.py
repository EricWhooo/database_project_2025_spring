# blueprints/public.py
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify)
from db import get_db_connection

public_bp = Blueprint('public', __name__, template_folder='../templates')

@public_bp.route('/')
def index():
    return render_template('index.html')

@public_bp.route('/search', methods=['POST'])
def search_flights():
    src_input  = request.form.get('source', '').strip()
    dest_input = request.form.get('destination', '').strip()

    conn = get_db_connection()
    flights = []
    try:
        with conn.cursor() as cur:
            # 根据输入（机场三字码或城市/机场名）解析可匹配的三字码列表
            def resolve_airports(val):
                val_uc = val.upper()
                if len(val_uc) == 3 and val_uc.isalpha():
                    return [val_uc]
                pattern = f"%{val_uc}%"
                cur.execute("""
                  SELECT airport_name
                    FROM airport
                   WHERE UPPER(airport_city) LIKE %s
                      OR UPPER(airport_name) LIKE %s
                   ORDER BY airport_name
                """, (pattern, pattern))
                return [r['airport_name'] for r in cur.fetchall()]

            src_codes  = resolve_airports(src_input)
            dest_codes = resolve_airports(dest_input)
            if not src_codes or not dest_codes:
                flash("找不到对应的机场或城市，请检查后重试。", "warning")
                return redirect(request.referrer or url_for('public.index'))

            ps_src  = ",".join(["%s"] * len(src_codes))
            ps_dest = ",".join(["%s"] * len(dest_codes))
            sql = f"""
                SELECT f.airline_name, f.flight_num,
                       f.departure_time, f.arrival_time,
                       f.price, f.status,
                       f.departure_airport, f.arrival_airport
                  FROM flight f
                 WHERE f.departure_airport IN ({ps_src})
                   AND f.arrival_airport   IN ({ps_dest})
                 ORDER BY f.departure_time
            """
            cur.execute(sql, src_codes + dest_codes)
            flights = cur.fetchall()
    except Exception as e:
        flash(f"Flight query failed: {e}", "danger")
    finally:
        conn.close()

    return render_template('search_results.html',
                           flights=flights,
                           source=src_input,
                           dest=dest_input)

@public_bp.route('/api/airports')
def api_airports():
    q = request.args.get('q', '').strip().upper()
    conn = get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cur:
            if q:
                pattern = f"%{q}%"
                cur.execute(
                    """SELECT airport_name
                         FROM airport
                        WHERE airport_name LIKE %s
                           OR airport_city   LIKE %s
                        ORDER BY airport_name
                        LIMIT 200""",
                    (pattern, pattern)
                )
            else:
                cur.execute(
                    "SELECT airport_name FROM airport ORDER BY airport_name LIMIT 200"
                )
            result = [row['airport_name'] for row in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(result)