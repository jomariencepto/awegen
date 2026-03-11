import warnings
warnings.filterwarnings("ignore", message="Failed to load image Python extension")

import os

from app import create_app

# Create app using factory
app = create_app()

if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=debug_enabled,
        use_reloader=debug_enabled
    )
