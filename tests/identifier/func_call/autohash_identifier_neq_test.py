from checkpointing.identifier.func_call.hash import AutoHashIdentifier
from checkpointing.identifier.func_call.context import FuncCallContext


def assert_context_neq(c1: FuncCallContext, c2: FuncCallContext):
    ahi = AutoHashIdentifier(unify_code=True)
    assert ahi.identify(c1) != ahi.identify(c2)

def test_change_argument_default_value():
    def foo(a=1):
        return a

    def bar(a=2):
        return a

    c1 = FuncCallContext(foo, (), {})
    c2 = FuncCallContext(bar, (), {})

    assert_context_neq(c1, c2)

def test_apply_argument_different_value():
    def foo(a):
        return a

    def bar(a):
        return a

    c1 = FuncCallContext(foo, (1,), {})
    c2 = FuncCallContext(bar, (2,), {})

    assert_context_neq(c1, c2)

def test_code_different_logic():
    def foo(a):
        return a + 1

    def bar(a):
        return a - 1

    c1 = FuncCallContext(foo, (1,), {})
    c2 = FuncCallContext(bar, (2,), {})

    assert_context_neq(c1, c2)

def test_swap_argument_order_but_apply_different_logic():
    def foo(a, b):
        return a - b

    def bar(b, a):
        return b - a

    c1 = FuncCallContext(foo, (1, 2), {})
    c2 = FuncCallContext(bar, (2, 1), {})

    assert_context_neq(c1, c2)

def test_add_varargs():
    def foo(a):
        return a

    def bar(a, *b):
        return a

    c1 = FuncCallContext(foo, (1,), {})
    c2 = FuncCallContext(bar, (2,), {})

    assert_context_neq(c1, c2)


def test_add_kwargs():
    def foo(a):
        return a

    def bar(a, **b):
        return a

    c1 = FuncCallContext(foo, (1,), {})
    c2 = FuncCallContext(bar, (2,), {})

    assert_context_neq(c1, c2)