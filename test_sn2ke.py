__author__ = 'iped'
from sn2ke import *
import unittest


class MyTestCase(unittest.TestCase):
    def test_add_tail_piece(self):
        snake = Model.Snake([10,10], [0,1], 5)
        self.assertEqual(len(snake.tail), 4)
        self.assertEqual(len(snake), 5)
        snake.add_tail_piece()
        self.assertEqual(len(snake.tail), 5)
        self.assertEqual(len(snake), 6)

if __name__ == '__main__':
    unittest.main()
