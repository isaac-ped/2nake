import sys
import curses
import random
import threading
import time


class View:

    BLOCK_CHAR = "x"
    APPLE_CHAR = "o"

    COLORS = {'white': 0,
              'red': 1,
              'green': 2,
              'yellow': 3,
              'cyan': 4,
              'blue': 5}

    HEAD_COLORS = (COLORS['green'], COLORS['cyan'])
    TAIL_COLORS = (COLORS['yellow'], COLORS['blue'])

    DEAD_MESSAGE = r"""
    |---\  ---  /-\  |---\
    |   | |    |   | |   |
    |   | |--- |   | |   |
    |   | |    |---| |   |
    |---/ |--- |   | |---/
"""

    WELCOME_MESSAGE = r"""
                   ____   _       ____         _____
                  /      / \   / /    / /   / /
                 /____  /  |  /  ____/ /___/ /____
                     / /   | /  /     / \   /
                ____/ /    |/  /____ /   \ /____

                * Press UP to play mirror-mode
                * Press DN to play switch-mirror-mode
                * Press W to play two-handed mode
                * Press Q to quit
"""

    def render(self, viewables_by_location, stdscr):
        stdscr.clear()
        for (location, viewable) in viewables_by_location.items():
            stdscr.addch(int(location[0]), int(location[1]),
                         viewable.icon,
                         curses.color_pair(viewable.color))
        stdscr.refresh()

    def show_dead_message(self, stdscr):
        stdscr.addstr(0, 0, self.DEAD_MESSAGE, curses.color_pair(View.COLORS['red']))
        stdscr.refresh()

    def show_home_screen(self, stdscr):
        stdscr.clear()
        stdscr.addstr(5, 0, self.WELCOME_MESSAGE, curses.color_pair(View.COLORS['green']))
        stdscr.refresh()

    def __init__(self):
        # TODO: I'd like stdscr to be a local variable here, but it's also needed for
        #       gathering keypress, which should be in controller?
        self._define_colors()

    def _define_colors(self):
        curses.start_color()
        curses.init_pair(self.COLORS['red'], curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(self.COLORS['green'], curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(self.COLORS['yellow'], curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(self.COLORS['blue'], curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(self.COLORS['cyan'], curses.COLOR_CYAN, curses.COLOR_BLACK)


class Model:

    LEFT = (0, -1)
    RIGHT = (0, 1)
    UP = (-1, 0)
    DOWN = (1, 0)

    DIRECTIONS = [LEFT, RIGHT, UP, DOWN]

    class Viewable(object):

        def __init__(self, xy, icon, color=0):
            (self._xy, self.color) = (xy, color)
            if icon:
                self.icon = icon

            self._viewable_by_location = {tuple(xy): self}

        @property
        def xy(self):
            return self._xy

        @xy.setter
        def xy(self, xy):
            self._viewable_by_location = {tuple(xy): self}
            self._xy = xy

        @property
        def viewables_by_location(self):
            return self._viewable_by_location

    class Collidable(Viewable):

        def collision_callback(self, *args):
            raise NotImplementedError

    class ViewableContainer(Viewable):

        def __init__(self, *viewables):
            """
            :param *viewables: Each Viewable or ViewableContainer input as a separate argument
            """
            if not all([isinstance(viewable, Model.Viewable) for viewable in viewables]):
                raise Exception('Viewable list %s contains non-viewables'%viewables.__repr__())
            if len(viewables) > 0:
                self.viewables = list(viewables)
                self.expanded_viewables = self._expand_viewables()
            else:
                self.viewables = []
                self.expanded_viewables = []

        def __add__(self, viewable):
            if isinstance(viewable, Model.Viewable):
                if self.viewables:
                    return Model.ViewableContainer(viewable, *self.viewables)
                else:
                    return Model.ViewableContainer(viewable)
            else:
                raise Exception('Attempted to append non-viewable %s to viewable container'
                                % viewable.__repr__())

        def append(self, viewable):
            if isinstance(viewable, Model.Viewable):
                if self.viewables:
                    self.viewables.append(viewable)
                else:
                    self.viewables = [viewable]
            else:
                raise Exception('Attempted to append non-viewable %s to viewable container'
                                % viewable.__repr__())
            if isinstance(viewable, Model.ViewableContainer):
                self.expanded_viewables.extend(viewable._expand_viewables())
            else:
                self.expanded_viewables.append(viewable)

        def remove(self, item):
            del self.viewables[self.viewables.index(item)]
            self.expanded_viewables = self._expand_viewables()

        def _expand_viewables(self):
            expanded = []
            for viewable in self.viewables:
                if isinstance(viewable, Model.ViewableContainer):
                    expanded.extend(viewable._expand_viewables())
                elif isinstance(viewable, Model.Viewable):
                    expanded.append(viewable)
                else:
                    raise Exception('Non-Viewable in viewableContainer. How???')
            return expanded

        def __iter__(self):
            for viewable in self.viewables:
                yield viewable

        def __getitem__(self, x):
            viewables = self.viewables[x]
            if isinstance(viewables, list):
                viewables = Model.ViewableContainer(*viewables)
            return viewables

        @property
        def viewables_by_location(self):
            """
            Returns a {location:viewable} dict for all objects in all viewables
            :return:
            """
            #  FIXME: Should not have to recalculate every time?
            locations = {}
            for viewable in self._expand_viewables():
                locations.update(viewable.viewables_by_location)
            return locations

        def get_collision(self, viewable):
            xy = tuple(viewable.xy)
            try:
                return self.viewables_by_location[xy]
            except KeyError:
                return None

        def __len__(self):
            return len(self._expand_viewables())

        def __repr__(self):
            return "%s:<%s>" % (type(self).__name__, self.viewables.__repr__())

    class SnakePiece(Viewable):
        DEFAULT_COLOR = View.COLORS['green']

        def __init__(self,
                     parent,
                     xy=None,
                     dxdy=None,
                     icon=None,
                     color=None):

            if color:
                self.color = self.DEFAULT_COLOR

            super(Model.SnakePiece, self).__init__(xy, icon)
            (self._dxdy, self.parent) = (dxdy, parent)

        def move(self):
            """
            Advances the SnakePiece by a single position
            """
            self.xy = (self.xy[0]+self.dxdy[0], self.xy[1]+self.dxdy[1])

        def is_opposite_direction(self, dxdy):
            """
            Returns whether the provided location is in the opposite direction as the snake piece
            :param dxdy:
            :return:
            """
            return dxdy[0] == -self.dxdy[0] or dxdy[1] == -self.dxdy[1]

        @property
        def dxdy(self):
            return self._dxdy

        @dxdy.setter
        def dxdy(self, dxdy):
            """
            Only allow setting of direction if it is not in the opposite direction
            :param dxdy:
            :return:
            """
            if not self.is_opposite_direction(dxdy):
                self._dxdy = dxdy

    class TailPiece(SnakePiece, Collidable):
        VERTICAL_CHAR = '|'
        HORIZONTAL_CHAR = '-'

        def __init__(self,
                     parent,
                     leader=None,
                     color=None,
                     icon=None):

            xy = [leader.xy[0]-leader.dxdy[0],
                  leader.xy[1]-leader.dxdy[1]]

            dxdy = leader.dxdy[:]

            self.leader = leader

            super(Model.TailPiece, self).__init__(parent, xy, dxdy, icon, color)

        def collision_callback(self, snake):
            snake.dead = True

        @property
        def icon(self):
            if self.dxdy[0] != 0:
                return self.VERTICAL_CHAR
            elif self.dxdy[1] != 0:
                return self.HORIZONTAL_CHAR
            else:
                raise Exception('No icon defined for stationary TailPiece')

        def move(self):
            (self.dxdy, self.xy) = \
                    (self.leader.dxdy[:], self.leader.xy[:])

    class HeadPiece(SnakePiece):
        UP_CHAR = '^'
        DOWN_CHAR = 'V'
        LEFT_CHAR = '<'
        RIGHT_CHAR = '>'
        DEFAULT_COLOR = View.COLORS['yellow']

        def __init__(self, *args, **kwargs):
            super(Model.HeadPiece, self).__init__(*args, **kwargs)
            self.color = self.DEFAULT_COLOR

        @property
        def icon(self):
            if self.dxdy == Model.DOWN:
                return self.DOWN_CHAR
            elif self.dxdy == Model.UP:
                return self.UP_CHAR
            elif self.dxdy == Model.RIGHT:
                return self.RIGHT_CHAR
            elif self.dxdy == Model.LEFT:
                return self.LEFT_CHAR
            else:
                raise Exception('No icon defined for stationary HeadPiece')

    class Snake(ViewableContainer):

        VERTICAL_SPEED = 9
        HORIZONTAL_SPEED = 15

        def __init__(self, xy, dxdy, length, keymap):

            (self.xy, self._dxdy, self.length, ) = \
                (xy, dxdy[:], length, )
            self.head = Model.HeadPiece(self, xy=xy, dxdy=dxdy)
            self.tail = self.create_tail(self.head, length)
            self.full_body = Model.ViewableContainer(self.head, self.tail)
            self.dead = False
            self.tail_color = None
            self.keymap = keymap
            super(Model.Snake, self).__init__(self.full_body)

        def create_tail(self, head, length):
            tail = Model.ViewableContainer(Model.TailPiece(self, head))
            for _ in range(length-2):
                tail.append(self.new_tail_piece(tail))
            return tail

        def new_tail_piece(self, tail=None):
            """
            Creates a new TailPiece that falls directly behind the last piece
            in the current tail
            :param tail: (optional) if not provided, uses self.tail
            :return: new TailPiece with self as parent
            """
            if not tail:
                tail = self.tail
            return Model.TailPiece(self, tail[-1])

        def add_tail_piece(self):
            self.tail.append(self.new_tail_piece())
            if self.tail_color:
                self.tail[-1].color = self.tail_color

        def is_colliding_with_self(self):
            return self.xy in self.tail.viewables_by_location

        def move(self):
            for piece in self.tail[::-1]:
                piece.move()
            self.head.move()

        @property
        def dxdy(self):
            return self._dxdy

        @dxdy.setter
        def dxdy(self, dxdy):
            self._dxdy = dxdy
            self.head.dxdy = dxdy

        @property
        def head_color(self):
            return self.head.color

        @head_color.setter
        def head_color(self, color):
            self.head.color = color

        @property
        def tail_color(self):
            return self.tail[0].color

        @tail_color.setter
        def tail_color(self, color):
            for tail in self.tail:
                tail.color = color

        @property
        def speed(self):
            if self.dxdy[0] != 0:
                return self.VERTICAL_SPEED
            else:
                return self.HORIZONTAL_SPEED

    class Apple(Collidable):
        DEFAULT_COLOR = View.COLORS['red']

        def __init__(self, xy, model):
            super(Model.Apple, self).__init__(xy, View.APPLE_CHAR)
            self.color = self.DEFAULT_COLOR
            self.model = model

        def collision_callback(self, snake):
            self.model.increment_score(snake)
            snake.add_tail_piece()
            self.model.add_apple()
            self.model.remove_apple(self)
            self.model.add_block()
            if self.model.switching:
                self.model.switch_snakes()

    class Block(Collidable):
        def __init__(self, xy):
            super(Model.Block, self).__init__(xy, View.BLOCK_CHAR)

        def collision_callback(self, snake):
            snake.dead = True

    class WallBlock(Collidable):
        VERTICAL_CHAR = '|'
        HORIZONTAL_CHAR = '-'

        def __init__(self, xy, is_vertical):
            super(Model.WallBlock, self).__init__(xy,
                                                  self.VERTICAL_CHAR if is_vertical
                                                  else self.HORIZONTAL_CHAR)

        def collision_callback(self, snake):
            snake.dead = True

    class Wall(ViewableContainer):

        def __init__(self, xy, wall_length, is_vertical):
            xys = [[xy[0]+(i if is_vertical else 0),
                    xy[1]+(i if not is_vertical else 0)]
                   for i in range(wall_length)]
            self.walls = [Model.WallBlock(xy, is_vertical) for xy in xys]
            super(Model.Wall, self).__init__(*self.walls)

    class ScoreNumber(Viewable):

        def __init__(self, xy, value=0, color=None):
            self._value = value
            super(Model.ScoreNumber, self).__init__(xy, str(value), color)

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, value):
            self._value = value
            self.icon = str(value)

    INIT_LENGTH = 5

    DEFAULT_WIDTH = 70
    DEFAULT_HEIGHT = 30

    DEFAULT_N_APPLES = 2
    DEFAULT_N_BLOCKS = 1

    def __init__(self, length=INIT_LENGTH,
                 n_apples=DEFAULT_N_APPLES, n_blocks=DEFAULT_N_BLOCKS,
                 width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 paired=False, switching=False, keymaps=None):
        (self.width, self.height, self.switching) = (width, height, switching)

        # Create and color the snakes
        (xys, dxdys) = self.get_starting_locations(paired)

        # Initialize as empty. Will fill one for each starting location
        self.snakes = Model.ViewableContainer()

        # Scores also start as empty
        self.scores = Model.ViewableContainer()

        # Make a snake and value for each starting location
        for (i, (xy, dxdy, keymap)) in enumerate(zip(xys, dxdys, keymaps)):
            new_snake = Model.Snake(xy, dxdy, length, keymap)
            new_snake.head_color = View.HEAD_COLORS[i]
            new_snake.tail_color = View.TAIL_COLORS[i]
            self.snakes += new_snake
            self.scores += Model.ScoreNumber([self.height, xy[1]],
                                             color=View.HEAD_COLORS[i])

        # Create the four walls
        self.walls = self.make_walls()

        # Obstacles and goals
        self.apples = self.random_apples(n_apples)
        self.blocks = self.random_blocks(n_blocks)

        self.all_objects = Model.ViewableContainer(self.blocks,
                                                   self.apples,
                                                   self.walls,
                                                   self.scores,
                                                   self.snakes)

        self.collidable_objects = Model.ViewableContainer(self.blocks,
                                                          self.apples,
                                                          self.walls,
                                                          *[snake.tail[1:] for snake in
                                                            self.snakes])

    def switch_snakes(self):
        self.snakes[0].keymap, self.snakes[1].keymap = \
            self.snakes[1].keymap, self.snakes[0].keymap

        self.snakes[0].head_color, self.snakes[1].head_color = \
            self.snakes[1].head_color, self.snakes[0].head_color

        self.snakes[0].tail_color, self.snakes[1].tail_color = \
            self.snakes[1].tail_color, self.snakes[0].tail_color

    def make_walls(self):
        return Model.ViewableContainer(*[
            Model.Wall([0, 0], self.width, False),
            Model.Wall([0, 0], self.height, True),
            Model.Wall([0, self.width], self.height, True),
            Model.Wall([self.height, 0], self.width, False)
        ])

    def get_starting_locations(self, paired):
        if not paired:
            xys = [[5, int(self.width/3)]]
            dxdys = [Model.DOWN]
            xys.append([5, int(2*self.width/3)])
            dxdys.append(Model.DOWN)
        else:
            xys = [[5, int(self.width/3)]]
            dxdys = [Model.DOWN]
            xys.append([self.height-5, int((2*self.width)/3)])
            dxdys.append(Model.UP)
        return xys, dxdys

    def random_location(self):
        return random.randint(1, self.height-1), random.randint(1, self.width-1)

    def random_apples(self, n_apples):
        apples = [Model.Apple(self.random_location(), self)
                  for _ in range(n_apples)]
        return Model.ViewableContainer(*apples)

    def add_apple(self, xy=None):
        if not xy:
            xy = self.random_location()
        self.apples.append(Model.Apple(xy, self))

    def remove_apple(self, apple):
        self.apples.remove(apple)

    def add_block(self, xy=None):
        if not xy:
            xy = self.random_location()
        self.blocks.append(Model.Block(xy))

    def random_blocks(self, n_blocks):
        blocks = [Model.Block(self.random_location())
                  for _ in range(n_blocks)]
        return Model.ViewableContainer(*blocks)

    def is_colliding(self, snake_num):
        return self.snakes[snake_num].is_colliding_with_self() or \
            self.is_colliding_with_environment(snake_num)

    def is_colliding_with_environment(self, snake_num):
        return self.snakes[snake_num].xy in self.blocks.viewables_by_location

    def is_game_over(self):
        return any([snake.dead for snake in self.snakes])

    def increment_score(self, scored_snake):
        for (score, snake) in zip(self.scores, self.snakes):
            if scored_snake == snake:
                score.value += 1


class Controller:
    RENDER_SPEED = 100

    CHOOSE_PAIRED_KEY = curses.KEY_UP
    CHOOSE_SWITCH_KEY = curses.KEY_DOWN

    PAIRED_KEY_MAPS = [{
        curses.KEY_DOWN: Model.DOWN,
        curses.KEY_UP: Model.UP,
        curses.KEY_RIGHT: Model.RIGHT,
        curses.KEY_LEFT: Model.LEFT
    }, {
        curses.KEY_DOWN: Model.UP,
        curses.KEY_UP: Model.DOWN,
        curses.KEY_RIGHT: Model.LEFT,
        curses.KEY_LEFT: Model.RIGHT
    }]

    CHOOSE_INDEPENDENT_KEY = ord('w')

    INDEPENDENT_KEY_MAPS = [{
        ord('w'): Model.UP,
        ord('s'): Model.DOWN,
        ord('a'): Model.LEFT,
        ord('d'): Model.RIGHT
    }, {
        curses.KEY_UP: Model.UP,
        curses.KEY_DOWN: Model.DOWN,
        curses.KEY_LEFT: Model.LEFT,
        curses.KEY_RIGHT: Model.RIGHT
    }]

    STOP_KEY = ord('q')

    def __init__(self):
        self.stdscr = curses.initscr()
        self.view = View()
        self.interrupted = False
        self.model = None

    def _monitor_keypress(self, stdscr):

        while not self.interrupted:
            char_pressed = stdscr.getch()
            if char_pressed == self.STOP_KEY:
                self.interrupted = True
            for snake in self.model.snakes:
                if char_pressed in snake.keymap:
                    snake.dxdy = snake.keymap[char_pressed]

    def _advance_single_snake_loop(self, snake):
        while not self.model.is_game_over() and not self.interrupted:
            snake.move()
            hit_item = self.model.collidable_objects.get_collision(snake.head)
            if hit_item:
                hit_item.collision_callback(snake)
            time.sleep(1/snake.speed)

    def start_game(self):
        ch = None
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(1)
        curses.curs_set(0)
        while ch != self.STOP_KEY:
            self.view.show_home_screen(self.stdscr)
            ch = self.stdscr.getch()
            if ch == self.CHOOSE_INDEPENDENT_KEY:
                self.model = Model(paired=False, keymaps=self.INDEPENDENT_KEY_MAPS)
                self.play_round(self.stdscr)
            elif ch == self.CHOOSE_PAIRED_KEY:
                self.model = Model(paired=True, keymaps=self.PAIRED_KEY_MAPS)
                self.play_round(self.stdscr)
            elif ch == self.CHOOSE_SWITCH_KEY:
                self.model = Model(paired=True, switching=True, keymaps=self.PAIRED_KEY_MAPS)
                self.play_round(self.stdscr)
        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()

    def play_round(self, stdscr):
        self.interrupted = False
        keypress_thread = threading.Thread(target=self._monitor_keypress,
                                           args=[stdscr])
        keypress_thread.start()
        for snake in self.model.snakes:
            snake_thread = threading.Thread(target=self._advance_single_snake_loop,
                                            args=[snake])
            snake_thread.start()

        self._render_loop(stdscr)
        stdscr.getch()

    def _render_loop(self, stdscr):
        while not self.model.is_game_over() and not self.interrupted:
            self.view.render(self.model.all_objects.viewables_by_location, stdscr)
            time.sleep(1/self.RENDER_SPEED)
        self.interrupted = True
        self.view.show_dead_message(stdscr)


def run():
    controller = Controller()
    controller.start_game()

if __name__ == '__main__':
    run()
