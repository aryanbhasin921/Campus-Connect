import os
from flask import Flask, render_template
from csrf import init_csrf
from config import Config
from db import close_db
from database.sqlite_init import init_sqlite_db
from routes.auth import auth_bp
from routes.student import student_bp
from routes.driver import driver_bp
from routes.admin import admin_bp

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    init_csrf(app)

    # Initialize SQLite database if in sqlite mode and DB doesn't exist yet
    if Config.DB_TYPE == 'sqlite':
        # init is idempotent (CREATE ... IF NOT EXISTS, seed only when empty), so running it on
        # every start also adds newer tables (driver_ratings, feedback) to an existing DB file.
        if not os.path.exists(Config.SQLITE_DB_PATH):
            print("[Startup] Initializing SQLite database schema, views, triggers and seed records...")
        init_sqlite_db(force_reset=False)

    # Register Database connection teardown
    app.teardown_appcontext(close_db)

    # Register Route Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(400)
    def bad_request(e):
        # Includes CSRF failures (missing/expired form token)
        return render_template('error.html', code=400,
                               message='The request could not be verified. Please go back, refresh the page and try again.'), 400

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error("Internal server error: %s", e, exc_info=True)
        return render_template('500.html'), 500

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print("==================================================")
    print(f"CampusConnect Server starting on http://localhost:{port}")
    print(f"Admin account: {Config.ADMIN_EMAIL}")
    print("==================================================")
    # Debug mode and network exposure are opt-in (FLASK_DEBUG=1, HOST=0.0.0.0)
    app.run(
        debug=os.environ.get('FLASK_DEBUG') == '1',
        host=os.environ.get('HOST', '127.0.0.1'),
        port=port
    )
