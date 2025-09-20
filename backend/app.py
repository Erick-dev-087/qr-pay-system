from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config  import DatabaseConfigs

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URL'] = DatabaseConfigs.SQLALCHEMY_DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = DatabaseConfigs.SQLALCHEMY_TRACK_MODIFICATIONS

db = SQLAlchemy(app)
 