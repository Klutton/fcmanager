from server import app
from database import init_database

if __name__ == "__main__":
    init_database()
    app.run(debug=True)
