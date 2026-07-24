"""
manage.py — Flask CLI management commands.

Usage:
    python manage.py create-db
    python manage.py seed
    python manage.py model-status
"""
import click
from flask.cli import with_appcontext
from app import create_app, db, bcrypt
from app.models import User, Patient, Doctor
from app.services.model_loader import ModelRegistry

app = create_app()


@app.cli.command("create-db")
@with_appcontext
def create_db():
    db.create_all()
    click.echo("Database tables created.")


@app.cli.command("seed")
@with_appcontext
def seed():
    """Seed demo users. Safe to run multiple times."""
    if not User.query.filter_by(email="doctor@neurotrace.ai").first():
        doc = User(email="doctor@neurotrace.ai",
                   password_hash=bcrypt.generate_password_hash("Doctor123!").decode(),
                   role="doctor", first_name="Sarah", last_name="Chen", is_active=True)
        db.session.add(doc)
        db.session.flush()
        db.session.add(Doctor(user_id=doc.id, specialisation="Neurology", license_number="NRL-2024-001"))
        click.echo("  + Doctor: doctor@neurotrace.ai / Doctor123!")

    patients = [
        ("james.h@neurotrace.ai",  "James",  "Harrington", "PT-001", 67, "Male",   2019),
        ("maria.c@neurotrace.ai",  "Maria",  "Chen",       "PT-002", 58, "Female", 2021),
        ("robert.o@neurotrace.ai", "Robert", "Okafor",     "PT-003", 72, "Male",   2016),
        ("susan.p@neurotrace.ai",  "Susan",  "Patel",      "PT-004", 63, "Female", 2020),
    ]
    for email, first, last, uid, age, gender, onset in patients:
        if not User.query.filter_by(email=email).first():
            u = User(email=email,
                     password_hash=bcrypt.generate_password_hash("Patient123!").decode(),
                     role="patient", first_name=first, last_name=last, is_active=True)
            db.session.add(u)
            db.session.flush()
            db.session.add(Patient(user_id=u.id, patient_uid=uid, age=age,
                                   gender=gender, diagnosis="Parkinson's Disease", onset_year=onset))
            click.echo(f"  + Patient: {email} / Patient123!")

    db.session.commit()
    click.echo("Seed complete.")


@app.cli.command("model-status")
@with_appcontext
def model_status():
    ModelRegistry.load_all(app)
    for name, loaded in ModelRegistry.status().items():
        click.echo(f"  {'OK' if loaded else 'MISSING':7} {name}")


if __name__ == "__main__":
    app.run()