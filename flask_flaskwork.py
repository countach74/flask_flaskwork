import uuid
import time
import datetime
import cProfile
import pstats
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from functools import reduce
from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from flask import jsonify, abort, request, session, url_for
from flask.ctx import has_request_context
from threading import Thread, RLock


class Flaskwork(object):
    def __init__(self, app=None, cleanup_interval=None, route=None):
        self.app = app
        self.cleanup_interval = cleanup_interval or datetime.timedelta(
            seconds=300
        )
        self.route = route or '/__flaskwork/<string:uuid>'

        self._request_info = {}
        self._request_lock = RLock()
        self._last_cleanup = datetime.datetime.now()

        if app:
            self.init_app(app)

    def _cleanup_request_info(self):
        with self._request_lock:
            cutoff = datetime.datetime.now() - self.cleanup_interval
            if self._last_cleanup < cutoff:
                deleted_items = []
                for request_uuid, info in self._request_info.items():
                    if info['timestamp'] < cutoff:
                        del(self._request_info[request_uuid])
                        deleted_items.append(request_uuid)
                self._last_cleanup = datetime.datetime.now()

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
            with self._request_lock:
                if hasattr(request, 'uuid') and (
                        request.uuid in self._request_info):
                    self._request_info[request.uuid]['profile'] = s.getvalue()
            return result

        app.dispatch_request = dispatch_request

        @app.before_request
        def before_request():
            if app.debug and request.endpoint != 'flaskwork_uuid_route':
                request.uuid = str(uuid.uuid4())
                with self._request_lock:
                    self._request_info[request.uuid] = {
                        'queries': [],
                        'start_time': time.time(),
                        'end_time': None,
                        'timestamp': datetime.datetime.now()
                    }

        @app.after_request
        def after_request(response):
            if app.debug:
                with self._request_lock:
                    if hasattr(request, 'uuid') and (
                            request.uuid in self._request_info):
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
                        response.headers['X-Flaskwork-URL'] = url_for(
                            'flaskwork_uuid_route', uuid=request.uuid,
                            _external=True
                        )
                self._cleanup_request_info()
            return response

        @app.route(self.route)
        def flaskwork_uuid_route(uuid):
            with self._request_lock:
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
            if app.debug:
                conn.info.setdefault('query_start_time', []).append(
                    time.time())

        def _request_info_queries(statement, params, total_time):
            """Given a statement and it's params return the correctly formatted SQL statement + it's time"""

            if params and isinstance(params, dict):
                for k, v in params.items():
                    # Add quotes to the values so we can just paste it in our SQL CLI.
                    params[k] = "'%s'" % v

                statement %= params

            self._request_info[request.uuid]['queries'].append({
                'statement': statement,
                'query_time': total_time
            })

        @listens_for(Engine, 'after_cursor_execute')
        def after_cursor_execute(
                conn, cursor, statement, params, context, executemany):
            if app.debug and has_request_context():
                total_time = (
                    time.time() - conn.info['query_start_time'].pop(-1)
                )
                with self._request_lock:
                    if hasattr(request, 'uuid') and (
                            request.uuid in self._request_info):

                        if executemany:
                            for param in params:
                                _request_info_queries(statement, param, total_time)
                        else:
                            _request_info_queries(statement, params, total_time)
