import warnings
warnings.filterwarnings("ignore", message="Failed to load image Python extension")

from app import create_app

# Create app using factory
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )