# File: config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'verysecretkey'
    DB_HOST = 'localhost'
    DB_USER = 'admin'
    DB_PASSWORD = 'password'
    DB_NAME = 'ticket_sys'