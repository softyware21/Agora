from fractions import Fraction
import unittest

from calculator import calculate, CalculationError


class CalculatorTests(unittest.TestCase):
    def test_cost_and_budget(self):
        self.assertEqual(calculate('1000 * 10 * 30 * 0.01'), 3000)
        self.assertEqual(calculate('500 / 0.01'), 50000)
        self.assertEqual(calculate('3000 * (16.7 / 100)'), 501)

    def test_decimal_literals_are_exact(self):
        self.assertEqual(calculate('0.1 + 0.2'), Fraction('0.3'))
        self.assertEqual(calculate('1 / 3'), Fraction(1, 3))
        self.assertEqual(calculate('-(2 + .5) / +2'), Fraction('-1.25'))

    def test_rejects_code_and_unsupported_operators(self):
        for expression in ['__import__("os").getcwd()', '1 .real', '[1][0]', 'True',
                           '2 ** 10000', '1 // 2', '1 % 2', '1e1000000', '0xff', '1_000',
                           'x + 1', 'sum([1, 2])', '1 < 2']:
            with self.subTest(expression=expression), self.assertRaises(CalculationError):
                calculate(expression)

    def test_limits_and_zero_division(self):
        for expression in ['', None, '1 / 0', '1 / (2 - 2)', '1' * 51,
                           '+'.join(['1'] * 40), '(' * 300 + '1' + ')' * 300]:
            with self.subTest(expression=expression), self.assertRaises(CalculationError):
                calculate(expression)
