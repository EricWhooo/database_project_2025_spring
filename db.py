# File: db.py
import pymysql
from config import Config

def get_db_connection():
    connection = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='latin1',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    return connection