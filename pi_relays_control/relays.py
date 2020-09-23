import sys
import time
from collections import OrderedDict
from typing import Dict


class RPiGPIOInterface:
    """
    Communication interface with RPi GPIO
    """

    _active: bool = None

    @classmethod
    def active(cls):
        """
        Indicates whether GPIO interface is useable (if we are on a Rapsberry Pi)
        """
        return cls._active

    @classmethod
    def init(cls, **kwargs):
        # noinspection PyBroadException
        try:
            from RPi import GPIO  # noqa: F401
            cls._active = True
            GPIO.setwarnings(bool(kwargs.get('warnings', False)))
            GPIO.setmode(getattr(GPIO, kwargs.get('mode', 'BCM')))

        except Exception as ex:
            print(f'GPIO operations are not supported on this device: {str(ex)}', file=sys.stderr)
            cls._active = False

    @classmethod
    def init_channel(cls, channel: int, mode: str, initial_state: str = None):
        assert mode
        if cls._active:
            from RPi import GPIO
            kwargs = {'initial': getattr(GPIO, initial_state)} if initial_state else {}
            GPIO.setup(channel, getattr(GPIO, mode), **kwargs)

    @classmethod
    def cleanup(cls):
        if cls.active():
            from RPi import GPIO
            GPIO.cleanup()

    @classmethod
    def output(cls, channel: int, state: str):
        if cls.active():
            from RPi import GPIO
            GPIO.output(channel, getattr(GPIO, state))


class Relay:
    """
    Representation of a relay on the board
    """

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.gpio_channel = int(kwargs.get('gpio_channel'))

        self.gpio_initial_state = kwargs.get('gpio_default_state', 'HIGH')
        self.behavior = kwargs.get('behavior', 'impulse')
        self.impulse_time = float(kwargs.get('impulse_time', 1))


class RelaysBoard:
    """
    Relays board management singleton
    """

    _instance = None

    def __init__(self):
        self._relays: Dict[str, Relay] = OrderedDict()

    @property
    def relays(self):
        """
        List of relays
        """
        return self._relays

    def add_relay(self, relay: Relay):
        """
        Declares a relay to the board
        """
        self._relays[relay.id] = relay

    def init(self):
        """
        Initialization of GPIO channels
        """
        RPiGPIOInterface.init()

        for relay in self._relays.values():
            RPiGPIOInterface.init_channel(relay.gpio_channel, 'OUT', relay.gpio_initial_state)

    def cleanup(self):
        """
        Cleans GPIO
        """
        RPiGPIOInterface.cleanup()

    def trigger_relay(self, relay_id: int):
        """
        Triggers a relay by his id
        """
        relay = self._relays[relay_id]
        assert relay
        assert relay.gpio_channel

        print(f'Triggering channel {relay.gpio_channel} (relay "{relay.id}")')
        if relay.behavior == 'impulse':
            assert relay.impulse_time
            RPiGPIOInterface.output(relay.gpio_channel, 'LOW' if relay.gpio_initial_state == 'HIGH' else 'HIGH')
            time.sleep(relay.impulse_time)
            RPiGPIOInterface.output(relay.gpio_channel, 'HIGH' if relay.gpio_initial_state == 'HIGH' else 'LOW')

        else:
            assert False, f'Unmanaged relay behavior {relay.behavior}'

    @classmethod
    def create(cls):
        """
        Creates the singleton instance
        """
        if not cls._instance:
            cls._instance = cls()

    @classmethod
    def instance(cls) -> 'RelaysBoard':
        """
        Retrieves the singleton instance
        """
        return cls._instance
