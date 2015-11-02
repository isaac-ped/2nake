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

    DEAD_MESSAGE = r"""
    |---\  ---  /-\  |---\
    |   | |    |   | |   |
    |   | |--- |   | |   |
    |   | |    |---| |   |
    |---/ |--- |   | |---/
"""

    def render(self):
        self.stdscr.clear()
        viewable_locations = self.model.get_all_drawable_locations()
        for location in viewable_locations:
            self.stdscr.addch(int(location[0]), int(location[1]),
                              viewable_locations[location].get_icon(),
                              curses.color_pair(viewable_locations[location].color))
        self.stdscr.refresh()

    def show_dead_message(self):
        self.stdscr.addstr(0, 0, self.DEAD_MESSAGE, curses.color_pair(View.COLORS['red']))
        self.stdscr.refresh()

    def __init__(self, model):
        self.model = model
        self.stdscr = curses.initscr()
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
            (self._xy, self.icon, self.color) =\
                (xy, icon, color)
            self.viewable_by_location = {tuple(xy), self}

        @property
        def xy(self):
            return self._xy

        @xy.setter
        def xy(self, xy):
            self.viewable_by_location = {tuple(xy), self}
            self._xy = xy

    class Collidable(Viewable):

        def collision_callback(self, *args):
            raise NotImplementedError

    class ViewableContainer(Viewable):

        def __init__(self, *viewables):
            """
            :param *viewables: Each Viewable or ViewableContainer input as a separate argument
            """
            self.viewables = list(viewables)
            self.expanded_viewables = self._expand_viewables()

        def __add__(self, viewable):
            return Model.ViewableContainer((viewable, self.viewables))

        def append(self, viewable):
            if isinstance(viewable, Model.Viewable):
                self.viewables.append(viewable)
            else:
                raise Exception('Attempted to append non-viewable %s to viewable container'
                                % viewable.__repr__())
            self.expanded_viewables += viewable

        def remove(self, item):
            del self.viewables[self.viewables.index(item)]
            self.expanded_viewables = self._expand_viewables()

        def _expand_viewables(self):
            expanded = []
            for viewable in self.viewables:
                if isinstance(viewable, Model.ViewableContainer):
                    expanded.extend(viewable.expanded_viewables)
                else:
                    expanded.append(viewable)
            return expanded

        def __iter__(self):
            for viewable in self.expanded_viewables:
                yield viewable

        def __getitem__(self, x):
            """
            Addressing ViewableContainer by index descends into contained ViewableContainers
            :param x:
            :return:
            """
            viewables = self.expanded_viewables[x]
            if isinstance(viewables, list):
                viewables = Model.ViewableContainer(*viewables)
            return viewables

        def viewables_by_location(self):
            locations = {}
            for viewable in self.expanded_viewables:
                locations.update(viewable.viewables_by_location())
            return locations

        def get_collision(self, viewable):
            xy = tuple(viewable.xy)
            if xy in self.viewables_by_location():
                return self.viewables_by_location()[xy]
            else:
                return None

        def __len__(self):
            return len(self.expanded_viewables)

        def __repr__(self):
            return "ViewableContainer containing %s" % self.viewables.__repr__()

    class SnakePiece(Viewable):
        DEFAULT_COLOR = View.COLORS['green']

        def __init__(self,
                     parent,
                     leader=None,
                     xy=None,
                     dxdy=None,
                     icon=None,
                     color=None):

            # Inherit position and speed from leader if provided
            if leader and not xy:
                xy = [leader.xy[0]-leader.dxdy[0],
                      leader.xy[1]-leader.dxdy[1]]

            if leader and not dxdy:
                dxdy = leader.dxdy[:]

            if color:
                self.color = self.DEFAULT_COLOR

            super(Model.SnakePiece, self).__init__(xy, icon)
            (self.leader, self._dxdy, self.parent) = (leader, dxdy, parent)

        def move(self):
            """
            Advances the SnakePiece by a single position
            """
            if self.leader:  # If leader is available, inherit position from leading piece
                (self.dxdy, self.icon, self.xy) = \
                    (self.leader.dxdy[:], self.leader.piece_char, self.leader.xy[:])
            else:
                self.xy[0] += self.dxdy[0]
                self.xy[1] += self.dxdy[1]

        def is_opposite_direction(self, dxdy):
            """
            Returns whether the provided location is in the opposite direction as the snake piece
            :param dxdy:
            :return:
            """
            return dxdy[0] != -self.dxdy[0] or dxdy[1] != -self.dxdy[1]

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

        def __init__(self, xy, dxdy, length):

            (self.xy, self.dxdy, self.length, ) = \
                (xy, dxdy[:], length, )
            self.head = Model.HeadPiece(self, xy=xy, dxdy=dxdy)
            self.tail = self.create_tail(self.head, length)
            self.full_body = Model.ViewableContainer(*[self.head, self.tail])
            self.dead = False
            self.tail_color = None
            super(Model.Snake, self).__init__(self.full_body)

        def create_tail(self, head, length):
            tail = [Model.TailPiece(self, head)]
            for _ in range(length-2):
                tail.append(self.new_tail_piece(tail))
            return Model.ViewableContainer(*tail)

        def new_tail_piece(self, tail=None):
            if not tail:
                tail = self.tail
            return Model.TailPiece(self, tail[-1])

        def add_tail_piece(self):
            self.tail.append(self.new_tail_piece())
            if self.tail_color:
                self.tail[-1].set_color(self.tail_color)

        def is_colliding_with_self(self):
            return self.xy in self.viewables_by_location()

        def move(self):
            self.head.dxdy = self.dxdy
            for piece in self.tail[::-1]:
                piece.move()
            self.head.move()

        @property
        def head_color(self):
            return self.head.color

        @head_color.setter
        def head_color(self, color):
            self.head.color = color

        @property
        def tail_color(self):
            return [tail.color for tail in self.tail.color]

        @tail_color.setter
        def tail_color(self, color):
            for tail in self.tail:
                tail.color = color

    class Apple(Collidable):
        DEFAULT_COLOR = View.COLORS['red']

        def __init__(self, xy, model):
            super(Model.Apple, self).__init__(xy, View.APPLE_CHAR)
            self.color = self.DEFAULT_COLOR
            self.model = model

        def collision_callback(self, snake):
            snake.add_tail_piece()
            self.model.add_apple()
            self.model.remove_apple(self)
            self.model.add_block()
            self.model.increment_score(snake)
            del self

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

    INIT_LENGTH = 5

    DEFAULT_WIDTH = 70
    DEFAULT_HEIGHT = 25

    DEFAULT_N_APPLES = 2
    DEFAULT_N_BLOCKS = 1

    def __init__(self, length=INIT_LENGTH,
                 n_apples=DEFAULT_N_APPLES, n_blocks=DEFAULT_N_BLOCKS,
                 width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 paired=False):
        (self.width, self.height,) = (width, height,)

        # Create and color the snakes
        (xy1, dxdy1, xy2, dxdy2,) = self.get_starting_location(paired)
        self.snake1 = Model.Snake(xy1, dxdy1, length)
        self.snake1.head_color = View.COLORS['green']
        self.snake1.tail_color = View.COLORS['cyan']
        self.snake2 = Model.Snake(xy2, dxdy2, length)
        self.snake2.head_color = View.COLORS['blue']
        self.snake2.tail_color = View.COLORS['cyan']
        self.snakes = [self.snake1, self.snake2]

        # Create the four walls
        self.walls = Model.ViewableContainer(*[
            Model.Wall([0, 0], self.width, False),
            Model.Wall([0, 0], self.height, True),
            Model.Wall([0, self.width], self.height, True),
            Model.Wall([self.height, 0], self.width, False)
        ])

        # Obstacles and goals
        self.apples = self.random_apples(n_apples)
        self.blocks = self.random_blocks(n_blocks)

        # Scoreboard show up as non-collidable viewables
        # (They are rendered after the wall, so they still show up
        #  even though that spot is already occupied)
        self.scores = [0, 0]
        self.score1 = Model.Viewable([self.height, 5], '0')
        self.score1.color = View.COLORS['green']
        self.score2 = Model.Viewable([self.height, width - 5], '0')
        self.score2.color = View.COLORS['cyan']

        self.all_objects = Model.ViewableContainer(self.blocks,
                                                   self.apples,
                                                   self.walls,
                                                   self.score1,
                                                   self.score2,
                                                   *self.snakes)

        self.collidable_objects = Model.ViewableContainer(self.blocks,
                                                          self.snake1.tail[1:],
                                                          self.snake2.tail[1:],
                                                          self.apples,
                                                          self.walls)

    def get_starting_location(self, paired):
        if not paired:
            xy1 = [5, int(self.width/3)]
            dxdy1 = [1, 0]
            xy2 = [5, int(2*self.width/3)]
            dxdy2 = [1, 0]
        else:
            xy1 = [5, int(self.width/3)]
            dxdy1 = [1, 0]
            xy2 = [self.height-5, int((2*self.width)/3)]
            dxdy2 = [-1,  0]
        return xy1, dxdy1, xy2, dxdy2

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

    def advance_snake(self, snake_num):
        self.snakes[snake_num].move()

    def is_colliding(self, snake_num):
        return self.snakes[snake_num].is_colliding_with_self() or \
            self.is_colliding_with_environment(snake_num)

    def is_colliding_with_environment(self, snake_num):
        return self.snakes[snake_num].xy in self.blocks.viewables_by_location()

    def get_all_drawable_locations(self):
        return self.all_objects.viewables_by_location()

    def get_all_collidable_locations(self):
        return self.collidable_objects.viewables_by_location()

    def is_game_over(self):
        return any([snake.dead for snake in self.snakes])

    def increment_score(self, snake):
        if self.snake1 == snake:
            self.scores[0] += 1
            self.score1.icon = str(self.scores[0])
        else:
            self.scores[1] += 1
            self.score2.icon = str(self.scores[1])


class Controller:
    SPEED = 15.

    KEY_MAPS = [{
        curses.KEY_DOWN: Model.Snake.UP,
        curses.KEY_UP: Model.Snake.DOWN,
        curses.KEY_RIGHT: Model.Snake.LEFT,
        curses.KEY_LEFT: Model.Snake.RIGHT
    }, {
        curses.KEY_UP: Model.Snake.UP,
        curses.KEY_DOWN: Model.Snake.DOWN,
        curses.KEY_LEFT: Model.Snake.LEFT,
        curses.KEY_RIGHT: Model.Snake.RIGHT
    }, {
        ord('w'): Model.Snake.UP,
        ord('s'): Model.Snake.DOWN,
        ord('a'): Model.Snake.LEFT,
        ord('d'): Model.Snake.RIGHT
    }]

    STOP_KEY = curses.KEY_ENTER

    def __init__(self, paired):
        self.interrupted = False
        if paired:
            self.key_map = Controller.KEY_MAPS[0:2]
        else:
            self.key_map = Controller.KEY_MAPS[2:0:-1]

        self.model = Model(paired=paired)
        self.view = View(self.model)
        self.stdscr = curses.initscr()

    def _init_monitor_keypress(self):
        curses.wrapper(self._monitor_keypress)

    def _monitor_keypress(self, stdscr):
        curses.curs_set(0)
        while not self.interrupted:
            char_pressed = stdscr.getch()
            for i in range(2):
                if char_pressed in self.key_map[i]:
                    self.model.snakes[i].dxdy = self.key_map[i][char_pressed]
                if char_pressed == self.STOP_KEY:
                    self.interrupted = True

    def start_game(self):
        self.interrupted = False
        thread = threading.Thread(target=self._init_monitor_keypress)
        thread.start()
        self._render_loop()

    def _render_loop(self):
        while not self.model.is_game_over() and not self.interrupted:
            self.view.render()
            for i in range(2):
                self.model.advance_snake(i)
                hit_item = self.model.collidable_objects.get_collision(self.model.snakes[i].head)
                if hit_item:
                    hit_item.collided(self.model.snakes[i])
            time.sleep(1/self.SPEED)
        self.interrupted = True
        self.view.show_dead_message()


def run():
    controller = Controller('wasd' not in sys.argv)
    controller.start_game()

if __name__ == '__main__':
    run()
