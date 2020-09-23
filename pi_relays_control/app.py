import os
import re
import sys
from configparser import RawConfigParser

from flask import Flask, render_template
from gunicorn.app.base import BaseApplication

import pi_relays_control
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
        RelaysBoard.create()
        super().__init__()

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

    def load(self):
        """
        Called on app loaded, initializes WSGI application
        """
        if not self._flask_app:
            self._flask_app = Flask(pi_relays_control.__name__)

            self._flask_app.add_url_rule('/', view_func=self.index, methods=['GET'])
            self._flask_app.add_url_rule(
                '/on_relay_clicked/<relay_id>', view_func=self.on_relay_clicked, methods=['PUT']
            )

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
        return render_template(
            'index.html',
            title=self._conf.get('app', 'title'),
            version=pi_relays_control.__version__,
            relays=RelaysBoard.instance().relays.values()
        )

    def on_relay_clicked(self, relay_id):
        """
        User clicked on a relay button
        """
        # TODO rights management
        # TODO display and handle errors
        RelaysBoard.instance().trigger_relay(relay_id)
        return '', 204
