"""Serve o Angular e a API no mesmo endereço da demonstração."""
from pathlib import Path, PurePosixPath

from whitenoise import WhiteNoise

from .wsgi import application as django_application

frontend_root = Path(__file__).resolve().parent.parent / 'frontend'
frontend = WhiteNoise(django_application, root=frontend_root, index_file=True)


def application(environ, start_response):
    """Encaminha /api/* para o Django e todo o resto para o build do Angular."""
    path = environ['PATH_INFO']
    if path == '/api' or path.startswith('/api/'):
        return django_application(environ, start_response)
    if (environ['REQUEST_METHOD'] in ('GET', 'HEAD') and path != '/assets'
            and not path.startswith('/assets/') and not PurePosixPath(path).suffix):
        # O Angular resolve as rotas da interface depois de carregar a página inicial.
        environ = {**environ, 'PATH_INFO': '/'}
    return frontend(environ, start_response)
