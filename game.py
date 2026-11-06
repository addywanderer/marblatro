"""The Game class, assembled from its feature mixins.

``Game`` is one object — the board, the shop, the inventory, the run in play — but
its methods live in the modules that own their subject (game_core.py, game_runs.py,
game_payoffs.py, ...). A mixin is only a namespace for methods: they all take
``self`` and share the one set of attributes Game.__init__ (in game_core.py)
creates, so a method in one mixin calls a method in any other freely. main.py
re-exports the finished class and wires the drawing helpers onto it.
"""

from game_core import CoreMixin
from game_input import InputMixin
from game_build import BuildMixin
from game_store import StoreMixin
from game_slots import SlotsMixin
from game_actions import ActionsMixin
from game_inventory import InventoryMixin
from game_economy import EconomyMixin
from game_describe import DescribeMixin
from game_deck import DeckMixin
from game_frame import FrameMixin
from game_runs import RunsMixin
from game_contact import ContactMixin
from game_payoffs import PayoffsMixin
from game_ending import EndingMixin


class Game(CoreMixin, InputMixin, BuildMixin, StoreMixin, SlotsMixin,
           ActionsMixin, InventoryMixin, EconomyMixin, DescribeMixin,
           DeckMixin, FrameMixin, RunsMixin, ContactMixin, PayoffsMixin,
           EndingMixin):
    """One game in progress: the board, the shop, the inventory and the run.

    The state itself is created in CoreMixin.__init__; the behaviour is spread over
    the mixins listed above.
    """
