from waitress import serve
from revenue.api import create_app

if __name__ == "__main__":
    serve(create_app(), host="0.0.0.0", port=8000, threads=4)
