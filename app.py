# File: app.py
from flask import Flask
from config import Config
from blueprints.auth import auth_bp
from blueprints.customer import customer_bp
from blueprints.agent import agent_bp
from blueprints.staff import staff_bp
from blueprints.public import public_bp

app = Flask(__name__)
app.config.from_object(Config)

# 注册各个蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp, url_prefix='/customer')
app.register_blueprint(agent_bp, url_prefix='/agent')
app.register_blueprint(staff_bp, url_prefix='/staff')
app.register_blueprint(public_bp)

if __name__ == '__main__':
    app.run(debug=True)