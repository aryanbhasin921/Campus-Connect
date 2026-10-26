import os
from flask import Flask, render_template
from config import Config
from db import close_db
from database.sqlite_init import init_sqlite_db
from routes.auth import auth_bp
from routes.student import student_bp
from routes.driver import driver_bp
from routes.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize SQLite database if in sqlite mode and DB doesn't exist yet
    if Config.DB_TYPE == 'sqlite':
        if not os.path.exists(Config.SQLITE_DB_PATH):
            print("[Startup] Initializing SQLite database schema, views, triggers and seed records...")
            init_sqlite_db(force_reset=False)
        else:
            print("[Startup] SQLite database verified at", Config.SQLITE_DB_PATH)

    # Register Database connection teardown
    app.teardown_appcontext(close_db)

    # Register Route Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', content="<div class='alert alert-warning text-center my-5'><h4>404 - Page Not Found</h4><p>The page you requested does not exist.</p><a href='/' class='btn btn-primary'>Return Home</a></div>"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('base.html', content=f"<div class='alert alert-danger text-center my-5'><h4>500 - Internal Server Error</h4><p>{str(e)}</p><a href='/' class='btn btn-primary'>Return Home</a></div>"), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f"==================================================")
    print(f"CampusConnect Server starting on http://localhost:{port}")
    print(f"Pre-decided Admin: {Config.ADMIN_EMAIL} | Password: {Config.ADMIN_PASSWORD}")
    print(f"==================================================")
    app.run(debug=True, host='0.0.0.0', port=port)
