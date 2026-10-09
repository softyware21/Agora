"""Evaluate bounded arithmetic without executing model-generated code."""
import ast
from fractions import Fraction
import re

VERSION = 1
NUMBER = re.compile(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z')


class CalculationError(ValueError):
    pass


def calculate(expression):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 256:
        raise CalculationError('Use an expression of 1-256 characters.')
    expression = expression.strip()
    try:
        tree = ast.parse(expression, mode='eval')
    except (SyntaxError, ValueError, RecursionError):
        raise CalculationError('Invalid arithmetic syntax.') from None
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise CalculationError('Expression is too complex.')

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(expression, node)
            if not literal or len(literal) > 50 or not NUMBER.fullmatch(literal):
                raise CalculationError('Use plain decimal numbers of at most 50 characters.')
            value = Fraction(literal)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = visit(node.operand)
            value = operand if isinstance(node.op, ast.UAdd) else -operand
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            elif isinstance(node.op, ast.Mult):
                value = left * right
            else:
                if right == 0:
                    raise CalculationError('Division by zero.')
                value = left / right
        else:
            raise CalculationError('Only decimal numbers, parentheses, and + - * / are supported.')
        if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
            raise CalculationError('Result exceeds the arithmetic size limit.')
        return value

    return visit(tree.body)
