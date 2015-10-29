import tty
import sys
import termios
import curses
import random
import threading
import time

#curses.initscr()


class View:

    BLOCK_CHAR = "x"
    APPLE_CHAR = "o"

    RED_COLOR = 1
    GREEN_COLOR = 2
    YELLOW_COLOR = 3
    CYAN_COLOR = 4
    BLUE_COLOR = 5

    DEAD_MESSAGE = r"""
    |---\  ---  /--\  |---\
    |   | |    |    | |   |
    |   | |--- |    | |   |
    |   | |    |----| |   |
    |---/ |--- |    | |---/
"""
    class Viewable(object):

        def __init__(self, xy, piece_char, attr=None):
            (self.xy, self.piece_char, self.attr) =\
                (xy, piece_char, attr)
            self.color = 0

        def get_piece_char(self):
            return self.piece_char

        def get_location_map(self):
            return {tuple([int(coord) for coord in self.xy]): self}

        def collision_callback(self, *args):
            raise NotImplementedError

        def collided(self, collided_with):
            self.collision_callback(collided_with)

        def set_color(self, color):
            self.color = color

    class ViewableContainer(Viewable):

        def __init__(self, *args):
            """
            :param args: list of Viewables or ViewableContainers to watch
            """
            self.viewables = []
            for arg in args:
                self._add_internal(arg)

        def __add__(self, viewable):
            return View.ViewableContainer(viewable, *self.viewables)

        def _add_internal(self, arg):
            if isinstance(arg, View.ViewableContainer) or\
                    isinstance(arg,View.Viewable):
                self.viewables.append(arg)
            else:
                raise Exception('Attempted to append non-viewable %s to viewable container'
                                % arg.__repr__())

        def append(self, viewable):
            self._add_internal(viewable)

        def remove(self, item):
            del self.viewables[self.viewables.index(item)]

        def expand_viewables(self):
            expanded = []
            for viewable in self.viewables:
                if issubclass(type(viewable), View.ViewableContainer):
                    expanded.extend(viewable.expand_viewables())
                else:
                    expanded.append(viewable)
            return expanded

        def __iter__(self):
            for viewable in self.expand_viewables():
                yield viewable

        def __getitem__(self, x):
            viewables = self.expand_viewables()[x]
            if isinstance(viewables, list):
                viewables = View.ViewableContainer(*viewables)
            return viewables

        def get_location_map(self):
            locations = {}
            for viewable in self.expand_viewables():
                locations.update(viewable.get_location_map())
            return locations

        def get_collision(self, viewable):
            xy = tuple([int(coord) for coord in viewable.xy])
            if xy in self.get_location_map():
                return self.get_location_map()[xy]
            else:
                return None

        def __len__(self):
            return len(self.expand_viewables())

        def __repr__(self):
            return "ViewableContainer containing %s" % self.viewables.__repr__()

    def __init__(self, model):
        self.model = model
        self.stdscr = curses.initscr()
        curses.start_color()
        curses.init_pair(self.RED_COLOR, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(self.GREEN_COLOR, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(self.YELLOW_COLOR, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(self.BLUE_COLOR, curses.COLOR_BLUE, curses.COLOR_BLACK)
        curses.init_pair(self.CYAN_COLOR, curses.COLOR_CYAN, curses.COLOR_BLACK)

    @staticmethod
    def clear():
        sys.stdout.write("\x1b[2J\x1b[H")

    def render(self):
        self.stdscr.clear()
        pieces = self.model.get_all_drawable_locations()
        for location in pieces:
            attr = pieces[location].attr
            self.stdscr.addch(int(location[0]), int(location[1]),
                              pieces[location].get_piece_char(),
                              curses.color_pair(pieces[location].color))
        self.stdscr.refresh()

    def show_dead_message(self):
        self.stdscr.addstr(0, 0, self.DEAD_MESSAGE, curses.color_pair(View.RED_COLOR))
        self.stdscr.refresh()


class Model:

    class SnakePiece(View.Viewable):
        DEFAULT_COLOR = View.GREEN_COLOR

        def __init__(self,
                     parent,
                     leader=None,
                     xy=None, dxdy=None,
                     piece_char=None,):
            if leader:
                xy = [leader.xy[0]-leader.dxdy[0],
                      leader.xy[1]-leader.dxdy[1]]
                dxdy = leader.dxdy[:]

            super(Model.SnakePiece, self).__init__(xy, piece_char)
            (self.leader, self.dxdy, self.parent) = (leader, dxdy, parent)
            self.color = self.DEFAULT_COLOR

        def move(self):
            if self.leader:
                (self.dxdy, self.piece_char, self.xy) = \
                    (self.leader.dxdy[:], self.leader.piece_char, self.leader.xy[:])
            else:
                self.xy[0] += self.dxdy[0]
                self.xy[1] += self.dxdy[1]


        def set_char(self, piece_char):
            self.piece_char = piece_char

        def set_dxdy(self, dxdy):
            if dxdy[0]!=-self.dxdy[0] or dxdy[1] != -self.dxdy[1]:
                self.dxdy = dxdy


    class TailPiece(SnakePiece):
        VERTICAL_CHAR = '|'
        HORIZONTAL_CHAR = '-'

        def collision_callback(self, snake):
            snake.dead = True

        def get_piece_char(self):
            if self.dxdy[0] != 0:
                return self.VERTICAL_CHAR
            elif self.dxdy[1] != 0:
                return self.HORIZONTAL_CHAR

    class HeadPiece(SnakePiece):
        UP_CHAR = '^'
        DOWN_CHAR = 'V'
        LEFT_CHAR = '<'
        RIGHT_CHAR = '>'
        DEFAULT_COLOR = View.YELLOW_COLOR

        def __init__(self, *args, **kwargs):
            super(Model.HeadPiece, self).__init__(*args, **kwargs)
            self.color = self.DEFAULT_COLOR


        def get_piece_char(self):
            if self.dxdy == Model.Snake.DOWN:
                return self.DOWN_CHAR
            elif self.dxdy == Model.Snake.UP:
                return self.UP_CHAR
            elif self.dxdy == Model.Snake.RIGHT:
                return self.RIGHT_CHAR
            elif self.dxdy == Model.Snake.LEFT:
                return self.LEFT_CHAR
            else:
                return '0'

        def collision_callback(self, *args, **kwarg):
            pass

    class Snake(View.ViewableContainer):

        LEFT = (0, -1)
        RIGHT = (0, 1)
        UP = (-1, 0)
        DOWN = (1, 0)

        DIRECTIONS = [LEFT, RIGHT, UP, DOWN]

        def __init__(self, xy, dxdy, length):

            (self.xy, self.dxdy, self.length, ) = \
                (xy, dxdy[:], length, )
            self.head = Model.HeadPiece(self, xy=xy, dxdy=dxdy)
            self.tail = self.create_tail(self.head, length)
            self.full_body = View.ViewableContainer(*[self.head, self.tail])
            self.dead = False
            self.tail_color = None
            super(Model.Snake, self).__init__(self.full_body)

        def create_tail(self, head, length):
            tail = [Model.TailPiece(self, head)]
            for _ in range(length-2):
                tail.append(self.new_tail_piece(tail))
            return View.ViewableContainer(*tail)

        def new_tail_piece(self, tail=None):
            if not tail:
                tail = self.tail
            return Model.TailPiece(self, tail[-1])

        def add_tail_piece(self):
            self.tail.append(self.new_tail_piece())
            if self.tail_color:
                self.tail[-1].set_color(self.tail_color)

        def is_colliding_with_self(self):
            return self.xy in self.get_location_map()

        def move(self):
            self.head.set_dxdy(self.dxdy)
            for piece in self.tail[::-1]:
                piece.move()
            self.head.move()

        def turn(self, direction):
            if direction not in self.DIRECTIONS:
                raise Exception('Direction invalid')
            self.dxdy = direction

        def set_color(self, head_color, tail_color):
            self.tail_color = tail_color
            for tail in self.tail:
                tail.color = tail_color
            self.head.color = head_color

    class Apple(View.Viewable):
        def __init__(self, xy, model):
            super(Model.Apple, self).__init__(xy, View.APPLE_CHAR)
            self.color = View.RED_COLOR
            self.model = model

        def collision_callback(self, snake):
            snake.add_tail_piece()
            self.model.add_apple()
            self.model.remove_apple(self)
            self.model.add_block()
            self.model.increment_score(snake)

    class Block(View.Viewable):
        def __init__(self, xy):
            super(Model.Block, self).__init__(xy, View.BLOCK_CHAR)

        def collision_callback(self, snake):
            snake.dead = True

    class WallBlock(View.Viewable):
        VERTICAL_CHAR = '|'
        HORIZONTAL_CHAR = '-'

        def __init__(self, xy, is_vertical):
            super(Model.WallBlock, self).__init__(xy,
                             self.VERTICAL_CHAR if is_vertical else self.HORIZONTAL_CHAR)

        def collision_callback(self, snake):
            snake.dead = True

    class Wall(View.ViewableContainer):

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

    def __init__(self, xy=None, dxdy=None,
                 length=INIT_LENGTH,
                 n_apples=DEFAULT_N_APPLES, n_blocks=DEFAULT_N_BLOCKS,
                 width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 paired=False):
        (self.width, self.height,) = (width, height,)

        if not paired:
            xy1 = [5, int(self.width/3)]
            dxdy1 = [1, 0]
            xy2 = [5, int(2*self.width/3)]
            dxdy2 = [1, 0]
        else:
            xy1 = [5, int(self.width/3)]
            dxdy1 = [1, 0]
            xy2 = [height-5, int((2*self.width)/3)]
            dxdy2 = [-1,  0]
        self.apples = self.random_apples(n_apples)
        self.blocks = self.random_blocks(n_blocks)
        self.snake1 = Model.Snake(xy1, dxdy1, length)
        self.snake2 = Model.Snake(xy2, dxdy2, length)
        self.snake2.set_color(View.BLUE_COLOR, View.CYAN_COLOR)
        self.snakes = [self.snake1, self.snake2]
        self.walls = View.ViewableContainer(*[
            Model.Wall([0, 0], self.width, False),
            Model.Wall([0, 0], self.height, True),
            Model.Wall([0, self.width], self.height, True),
            Model.Wall([self.height, 0], self.width, False)
        ])
        self.score1 = View.Viewable([self.height, 5], '0')
        self.score1.set_color(View.GREEN_COLOR)
        self.score2 = View.Viewable([self.height, width - 5], '0')
        self.score2.set_color(View.CYAN_COLOR)
        self.scores = [0, 0]

        self.all_objects = View.ViewableContainer(self.blocks,
                                                  self.apples,
                                                  self.walls,
                                                  self.score1,
                                                  self.score2,
                                                  *self.snakes)
        self.collidable_objects = View.ViewableContainer(self.blocks,
                                                         self.snake1.tail[1:],
                                                         self.snake2.tail[1:],
                                                         self.apples,
                                                         self.walls)

    def random_location(self):
        return random.randint(1, self.height-1), random.randint(1, self.width-1)

    def random_apples(self, n_apples):
        apples = [Model.Apple(self.random_location(), self)
                  for _ in range(n_apples)]
        return View.ViewableContainer(*apples)

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
        return View.ViewableContainer(*blocks)

    def advance_snake(self, snake_num):
        self.snakes[snake_num].move()

    def is_colliding(self, snake_num):
        return self.snakes[snake_num].is_colliding_with_self() or \
            self.is_colliding_with_environment(snake_num)

    def is_colliding_with_environment(self, snake_num):
        return self.snakes[snake_num].xy in self.blocks.get_location_map()

    def get_all_drawable_locations(self):
        return self.all_objects.get_location_map()

    def get_all_collidable_locations(self):
        return self.collidable_objects.get_location_map()

    def is_game_over(self):
        return any([snake.dead for snake in self.snakes])

    def increment_score(self, snake):
        if self.snake1 == snake:
            self.scores[0] += 1
            self.score1.piece_char = str(self.scores[0])
        else:
            self.scores[1] += 1
            self.score2.piece_char = str(self.scores[1])


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