import os
from app import app
from waitress import serve

if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    serve(app, host=host, port=port, threads=8)
