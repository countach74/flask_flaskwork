import uuid
import time
import cProfile
import pstats
try:
    from io import StringIO
except ImportError:
    from StringIO import StringIO
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from flask import jsonify, abort, request, session


class Flaskwork(object):
    def __init__(self, app=None):
        self.app = app
        self._request_info = {}

        if app:
            self.init_app(app)

    def init_app(self, app):
        original_dispatch_request = app.dispatch_request

        def dispatch_request():
            pr = cProfile.Profile()
            pr.enable()
            result = original_dispatch_request()
            pr.disable()
            s = StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
            ps.print_stats()
            if hasattr(request, 'uuid') and request.uuid in self._request_info:
                self._request_info[request.uuid]['profile'] = s.getvalue()
            return result

        app.dispatch_request = dispatch_request

        @app.before_request
        def before_request():
            if app.debug and request.endpoint != 'flaskwork_uuid_route':
                request.uuid = str(uuid.uuid4())
                self._request_info[request.uuid] = {
                    'queries': [],
                    'start_time': time.time(),
                    'end_time': None
                }

        @app.after_request
        def after_request(response):
            if hasattr(request, 'uuid') and request.uuid in self._request_info:
                info = self._request_info[request.uuid]
                info.update({
                    'end_time': time.time(),
                    'request': {
                        'url': request.url,
                        'method': request.method,
                        'headers': dict(request.headers),
                        'url_rule': str(request.url_rule),
                        'endpoint': request.endpoint,
                        'view_args': request.view_args
                    },
                    'response': {
                        'status': response.status_code,
                        'headers': dict(response.headers)
                    },
                    'session': dict(session)
                })
                response.headers['X-Flaskwork-UUID'] = request.uuid
            return response

        @app.route('/__flaskwork/<string:uuid>')
        def flaskwork_uuid_route(uuid):
            if uuid in self._request_info:
                info = self._request_info[uuid]
                db_time = reduce(
                    lambda a, b: a + b,
                    map(lambda x: x['query_time'], info['queries']),
                    0
                )
                return jsonify({
                    'queries': info['queries'],
                    'total_time': info['end_time'] - info['start_time'],
                    'database_time': db_time,
                    'request': info['request'],
                    'response': info['response'],
                    'profile': info.get('profile'),
                    'session': info['session']
                }), 200, {
                    'Access-Control-Allow-Origin': '*'
                }
            return ('Not Found', 404, {
                'Content-Type': 'text/plain',
                'Access-Control-Allow-Origin': '*'
            })

        @listens_for(Engine, 'before_cursor_execute')
        def before_cursor_execute(
                conn, cursor, statement, params, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())

        @listens_for(Engine, 'after_cursor_execute')
        def after_cursor_execute(
                conn, cursor, statement, params, context, executemany):
            total_time = time.time() - conn.info['query_start_time'].pop(-1)

            try:
                request.url
            except RuntimeError:
                pass
            else:
                if hasattr(request, 'uuid') and request.uuid in self._request_info:
                    self._request_info[request.uuid]['queries'].append({
                        'statement': statement % params,
                        'query_time': total_time
                    })

