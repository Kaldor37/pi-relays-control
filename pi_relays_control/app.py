import os
import re
import sys
import time
from configparser import RawConfigParser
from datetime import datetime

import sqlalchemy
from flask import Flask, render_template, request, make_response
from gunicorn.app.base import BaseApplication
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import redirect

import pi_relays_control
from pi_relays_control.models import init_database, User
from pi_relays_control.relays import RelaysBoard, Relay


class PiRelaysControl(BaseApplication):

    """
    Configuration file :
    - ./pi_relays_control.conf
    - /etc/pi_relays_control.conf
    - /etc/pi_relays_control/pi_relays_control.conf
    """
    _CONF_FILE_NAME = f'{pi_relays_control.__name__}.conf'

    def __init__(self):
        self._flask_app: Flask = None
        self._conf = RawConfigParser()
        self._db_engine = None
        self._session_factory = None
        RelaysBoard.create()
        super().__init__()

    @property
    def db_engine(self) -> Engine:
        return self._db_engine

    def init(self, parser, opts, args):
        pass

    def load_config(self):
        """
        Called by Gunicorn for configuration init
        """
        read_files = self._conf.read({
            self._CONF_FILE_NAME,
            os.path.join('/etc', self._CONF_FILE_NAME),
            os.path.join('/etc', pi_relays_control.__name__, self._CONF_FILE_NAME),
        })
        if not read_files:
            print('Failed to read any configuration file!', file=sys.stderr)

        gunicorn_conf = {
            'bind': '{}:{}'.format(
                self._conf.get('app', 'listen', fallback='127.0.0.1'),
                self._conf.get('app', 'port', fallback=8080)
            ),
            'workers': self._conf.get('api', 'workers', fallback=1),
            'threads': self._conf.get('api', 'threads', fallback=16),
            'worker_class': self._conf.get('api', 'worker_class', fallback='gthread'),
            'timeout': self._conf.get('api', 'timeout', fallback=30),
            'on_exit': self._on_exit
        }
        for key, value in gunicorn_conf.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

        for section in self._conf.sections():
            search = re.search(r'^relay\.(\w+)$', section)
            if search:
                relay_id = search.group(1)
                if not relay_id:
                    continue

                relay_conf_data = dict(self._conf[section])
                if not relay_conf_data['name'] or not relay_conf_data['gpio_channel']:
                    continue

                RelaysBoard.instance().add_relay(Relay(id=relay_id, **relay_conf_data))

        RelaysBoard.instance().init()

        db_engine = self._conf.get('database', 'engine', fallback='mysql+pymysql')
        db_host = self._conf.get('database', 'host', fallback='localhost')
        db_port = self._conf.getint('database', 'port', fallback=3306)
        db_name = self._conf.get('database', 'name')
        db_user = self._conf.get('database', 'user')
        db_password = self._conf.get('database', 'password')
        self._db_engine = sqlalchemy.create_engine(
            f'{db_engine}://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}',
            echo=self._conf.getboolean('database', 'echo', fallback=False)
        )
        init_database(self._db_engine)
        self._session_factory = sessionmaker(bind=self._db_engine)

    def load(self):
        """
        Called on app loaded, initializes WSGI application
        """
        if not self._flask_app:
            self._flask_app = Flask(pi_relays_control.__name__)
            self._flask_app.wsgi_app = ProxyFix(self._flask_app.wsgi_app)

            self._flask_app.add_url_rule('/', view_func=self.index, methods=['GET'])
            self._flask_app.add_url_rule(
                '/on_relay_clicked/<relay_id>', view_func=self.on_relay_clicked, methods=['PUT']
            )
            self._flask_app.add_url_rule('/auth', view_func=self.auth, methods=['GET', 'POST'])
            self._flask_app.add_url_rule('/users', view_func=self.users, methods=['GET', 'POST'])

            self._flask_app.register_error_handler(AuthenticationException, self._handle_auth_exception)

            self._flask_app.jinja_env.globals.update({
                'title': self._conf.get('app', 'title'),
                'version': pi_relays_control.__version__
            })

        return self._flask_app

    @staticmethod
    def _on_exit(__):
        """
        Triggered when Gunicorn app is shut down, we cleanup the relays board
        """
        RelaysBoard.instance().cleanup()

    def index(self):
        """
        Home page
        """
        user = self._check_user_auth()
        return render_template(
            'index.html',
            user=user,
            waiting_users=User.get_waiting_count(self._session_factory) if user.admin else None,
            relays=RelaysBoard.instance().relays.values()
        )

    def auth(self):
        """
        Authentication page
        """
        new_auth_token = None
        auth_token = request.cookies.get('auth-token')
        user = None

        # User registration
        if request.method == 'POST':
            user = User.register(
                self._session_factory,
                request.headers.get('User-Agent'),
                request.remote_addr
            )
            new_auth_token = user.auth_token
            time.sleep(1)  # TODO enhance DDoS protection (captcha ?)

        # User loading
        elif auth_token:
            user = User.get_by_token(auth_token, self._session_factory)
            if user and user.access_granted:
                return redirect('/', code=302)

        response = make_response(render_template('auth.html', user=user))
        if new_auth_token:
            response.set_cookie(
                'auth-token',
                new_auth_token,
                secure=request.scheme.lower() == 'https',
                httponly=True
            )
        return response

    def users(self):
        user = self._check_user_auth()
        if not user.admin:
            return 'Forbidden', 403

        if request.method == 'POST':
            user_id = int(request.form.get('user_id'))
            if not user_id:
                return 'Unkown user id', 400

            action = request.form.get('action')
            if action == 'grant':
                User.grant_access(self._session_factory, user_id)
            elif action == 'revoke':
                User.revoke_access(self._session_factory, user_id)
            elif action == 'upgrade':
                User.upgrade(self._session_factory, user_id)
            elif action == 'downgrade':
                User.downgrade(self._session_factory, user_id)
            elif action == 'editName':
                User.set_name(self._session_factory, user_id, request.form.get('user_name'))
            else:
                return 'Unknown action', 400

        session = self._session_factory()
        users = session.query(User).all()
        session.close()
        return render_template('users.html', user=user, users=users)

    def on_relay_clicked(self, relay_id):
        """
        User clicked on a relay button
        """
        session = self._session_factory()
        user = self._check_user_auth(session)
        user.last_access = datetime.now()
        session.commit()
        session.close()

        # TODO display and handle errors
        RelaysBoard.instance().trigger_relay(relay_id)
        return '', 204

    def _check_user_auth(self, session=None):
        """
        Ensures user is authenticated
        """
        auth_token = request.cookies.get('auth-token')
        if auth_token:
            kwargs = {}
            if session:
                kwargs['session'] = session
            else:
                kwargs['session_factory'] = self._session_factory

            user = User.get_by_token(auth_token, **kwargs)
            if user and user.access_granted:
                return user

        raise AuthenticationException()

    @staticmethod
    def _handle_auth_exception(__):
        return redirect('/auth', code=302)


class AuthenticationException(Exception):
    pass
