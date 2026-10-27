import os

from sanic.response import text

from app import create_app
from app.misc.log import log
from config import Config, LocalDBConfig

app = create_app(Config, LocalDBConfig)


@app.route("/", methods={'GET'})
async def hello_world(request):
    return text("Hello World")

if __name__ == '__main__':
    import argparse
    import ssl
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('--https', action='store_true', help='Run local TLS on port 8443')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    settings = dict(app.config['RUN_SETTING'])
    if args.https:
        certificates = Path(__file__).resolve().parent / 'certs'
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificates / 'localhost.crt', certificates / 'localhost.key')
        settings.update(ssl=context, host='127.0.0.1', port=8443, workers=1, auto_reload=False, single_process=True)
    if args.port:
        settings['port'] = args.port
    if 'SECRET_KEY' not in os.environ:
        log(message='SECRET KEY is not set in the environment variable.', keyword='WARN')
    app.run(**settings)
