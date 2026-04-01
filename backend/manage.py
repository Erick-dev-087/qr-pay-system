from flask import Flask
from flask.cli import FlaskGroup
from app import create_app, db
from models import User, Vendor, Transaction, QRCode, ScanLog, PaymentSession

app = create_app()
cli = FlaskGroup(app)

@cli.command("db_init")
def db_init():
    """Initialize the database migration."""
    from flask_migrate import init
    init()
    print("✅ Migrations directory initialized successfully!")

@cli.command("db_migrate")
def db_migrate():
    """Create a new database migration."""
    from flask_migrate import migrate
    migrate(message='Update database schema')
    print("✅ New migration created successfully!")

@cli.command("db_upgrade")
def db_upgrade():
    """Apply all database migrations."""
    from flask_migrate import upgrade
    upgrade()
    print("✅ Database upgraded successfully!")

if __name__ == '__main__':
    cli()