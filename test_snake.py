__author__ = 'iped'

import unittest
import snake


class MyTestCase(unittest.TestCase):

    def test_snake_piece(self):
        snake_piece0 = snake.Model.SnakePiece(None, xy=[1, 1], dxdy=[0, 1])
        self.assertEqual(snake_piece0.xy, [1, 1],
                         'xy improperly set')
        self.assertEqual(snake_piece0.dxdy, [0, 1],
                         'dxdy improperly set')
        snake_piece0.move()
        self.assertEqual(snake_piece0.xy, [1, 2],
                         'snake_piece did not move properly')

        snake_piece1 = snake.Model.SnakePiece(None, snake_piece0)
        self.assertEqual(snake_piece1.xy, [1, 1],
                         'xy improperly set from leader')
        self.assertEqual(snake_piece1.dxdy, [0, 1],
                         'dxdy improperly set from leader')

    def test_snake(self):
        xy = [1, 1]
        dxdy = snake.Model.Snake.DOWN
        length = 5
        test_snake = snake.Model.Snake(xy[:], dxdy, length)
        self.assertEqual(test_snake.xy, xy,
                         'xy improperly set for snake')
        self.assertEqual(test_snake.dxdy, dxdy,
                         'dxdy improperly set for snake')
        self.assertEqual(len(test_snake), length,
                         'length improperly set for snake')
        self.assertEqual(test_snake.tail[0].xy, [xy[0]+dxdy[0], xy[1]+dxdy[1]],
                         'Tail starts in wrong place')
        self.assertEqual(test_snake.tail[-1].xy,
                         [xy[0]+dxdy[0]*(length-1), xy[1]+dxdy[1]*(length-1)],
                         'Tail ends in wrong place')
        test_snake.move()
        self.assertEqual(test_snake.tail[0].xy, [xy[0]+(dxdy[0]*2), xy[1]+(dxdy[1]*2)],
                         'Tail starts in wrong place after move')
        self.assertEqual(test_snake.tail[-1].xy,
                         [xy[0]+dxdy[0]*length, xy[1]+dxdy[1]*length],
                         'Tail ends in wrong place after move')
        test_snake.add_tail_piece()
        self.assertEqual(len(test_snake), length+1)

        self.assertEqual(test_snake[0].get_icon(),
                         snake.Model.HeadPiece.DOWN_CHAR,
                         'Unexpected character in snake head')
        self.assertEqual(test_snake[1].get_icon(),
                         snake.Model.TailPiece.VERTICAL_CHAR,
                         'Unexpected character in snake tail')

        expected_chars = (
            (snake.Model.TailPiece.VERTICAL_CHAR,
             snake.Model.HeadPiece.UP_CHAR,
             snake.Model.Snake.UP),
            (snake.Model.TailPiece.HORIZONTAL_CHAR,
             snake.Model.HeadPiece.RIGHT_CHAR,
             snake.Model.Snake.RIGHT),
            (snake.Model.TailPiece.VERTICAL_CHAR,
             snake.Model.HeadPiece.DOWN_CHAR,
             snake.Model.Snake.DOWN),
            (snake.Model.TailPiece.HORIZONTAL_CHAR,
             snake.Model.HeadPiece.LEFT_CHAR,
             snake.Model.Snake.LEFT)
        )

        for (tail_char, head_char, direction) in expected_chars:
            test_snake.turn(direction)
            test_snake.move()
            test_snake.move()
            self.assertEqual(test_snake[0].get_icon(),
                             head_char,
                             'Unexpected character in snake head')
            self.assertEqual(test_snake[1].get_icon(),
                             tail_char,
                             'Unexpected character in snake tail')

    def test_init_viewable(self):
        viewable = snake.View.Viewable((1, 2), 'X')
        self.assertEqual(viewable.xy, (1, 2),
                         'Coord initialization failed')
        self.assertEqual(viewable.piece_char, 'X',
                         'Setting icon failed')
        self.assertEqual(viewable.viewables_by_location(),
                         {(1, 2): viewable},
                         'Location map incorrect')

    def assert_entries_in_dict(self, entries, dictionary, message=''):
        for key in entries:
            self.assertIn(key, dictionary,
                          '%s: Key not in dictionary' % message)
            self.assertEqual(dictionary[key], entries[key],
                             '%s: Entry in dictionary incorrect' % message)

    def test_viewable_container(self):
        viewable_params = (
            ((1, 2), 'X'),
            ((3, 4), 'Y'),
            ((5, 6), 'Z'),
            ((7, 8), 'A'),
            ((1, 2), 'C')
        )

        viewables = [snake.View.Viewable(*params)
                     for params in viewable_params]

        container0 = snake.View.ViewableContainer(viewables[0])
        self.assert_entries_in_dict({viewable_params[0][0]: viewables[0]},
                                    container0.viewables_by_location())

        container12 = snake.View.ViewableContainer(*viewables[1:3])
        for params, viewable in zip(viewable_params[1:3], viewables[1:3]):
            self.assert_entries_in_dict({params[0]: viewable},
                                        container12.viewables_by_location(),
                                        'Viewable container did not concatenate viewables')

        container012 = snake.View.ViewableContainer(container0, container12)

        for params, viewable in zip(viewable_params[0:2], viewables[0:2]):
            self.assert_entries_in_dict({params[0]: viewable},
                                        container012.viewables_by_location(),
                                        'Viewable container did not concatenate viewable_container')

        container0123 = container012 + snake.View.ViewableContainer(viewables[3])

        for params, viewable in zip(viewable_params[0:4], viewables[0:4]):
            self.assert_entries_in_dict({params[0]: viewable},
                                        container0123.viewables_by_location(),
                                        'Viewable container did not add viewable_container')

        self.assertEqual(container0123.get_collision(viewables[-1]),
                         viewables[0])

    def test_model(self):
        params = {
            'xy': (2, 2),
            'dxdy': (1, 0),
            'length': 3,
            'n_apples': 4,
            'n_blocks': 3,
            'width': 40,
            'height': 30
        }
        model = snake.Model(**params)

        self.assertEqual(len(model.apples), params['n_apples'],
                         'Wrong number of apples created')
        self.assertEqual(len(model.blocks), params['n_blocks'],
                         'Wrong number of blocks created')
        self.assertEqual(len(model.snake), params['length'],
                         'Wrong length snake')

        model.add_apple()
        self.assertEqual(len(model.apples), params['n_apples']+1,
                         'Apple not added')


        self.assertFalse(model.is_colliding() and model.is_colliding_with_environment(),
                         'Bad collision with environment')

        model.add_block(model.snake.xy)
        self.assertEqual(len(model.blocks), params['n_blocks']+1,
                         'New block not created')

        self.assertTrue(model.is_colliding() and model.is_colliding_with_environment(),
                        'Collision with environment undetected')

if __name__ == '__main__':
    unittest.main()
