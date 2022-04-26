# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Code for the adjoint transform."""
from collections.abc import Sequence
from functools import wraps


from pennylane.operation import Operator, AdjointUndefinedError
from pennylane.queuing import QueuingContext, QueuingError
from pennylane.tape import QuantumTape, stop_recording
from pennylane.ops.arithmetic import Adjoint


def adjoint(fn):
    """Create a function that applies the adjoint (inverse) of the provided operation or template.

    This transform can be used to apply the adjoint of an arbitrary sequence of operations.

    Args:
        fn (function): A single operator or a quantum function that
            applies quantum operations.

    Returns:
        function: A new function that will apply the same operations but adjointed and in reverse order.

    **Example**

    The adjoint transforms can be used within a QNode to apply the adjoint of
    any quantum function. Consider the following quantum function, that applies two
    operations:

    .. code-block:: python3

        def my_ops(a, wire):
            qml.RX(a, wires=wire)
            qml.SX(wire)

    We can create a QNode that applies this quantum function,
    followed by the adjoint of this function:

    .. code-block:: python3

        dev = qml.device('default.qubit', wires=1)

        @qml.qnode(dev)
        def circuit(a):
            my_ops(a, wire=0)
            qml.adjoint(my_ops)(a, wire=0)
            return qml.expval(qml.PauliZ(0))

    Printing this out, we can see that the inverse quantum
    function has indeed been applied:

    >>> print(qml.draw(circuit)(0.2))
    0: ──RX(0.20)──SX──SX†──RX(-0.20)─┤  <Z>

    If a "shortcut" exists to easily compute the adjoint, see :meth:`~.operation.Operator.adjoint`, then this
    shortcut is eagerly used.  Otherwise, the operator is wrapped in an :class:`~.ops.arithmetic.Adjoint` class
    for later handling. The adjoint function can also be applied directly to templates and operations:

    >>> qml.adjoint(qml.RX)(0.123, wires=0)
    RX(-0.123, wires=[0])
    >>> qml.adjoint(qml.QFT)(wires=(0,1,2,3))
    Adjoint(QFT)(wires=[0, 1, 2, 3])

    .. UsageDetails::

        **Adjoint of a function**

        Here, we apply the ``subroutine`` function, and then apply its adjoint.
        Notice that in addition to adjointing all of the operations, they are also
        applied in reverse construction order.

        .. code-block:: python3

            def subroutine(wire):
                qml.RX(0.123, wires=wire)
                qml.RY(0.456, wires=wire)

            dev = qml.device('default.qubit', wires=1)
            @qml.qnode(dev)
            def circuit():
                subroutine(0)
                qml.adjoint(subroutine)(0)
                return qml.expval(qml.PauliZ(0))

        This creates the following circuit:

        >>> print(qml.draw(circuit)())
        0: ──RX(0.12)──T──T†──RX(-0.12)─┤  <Z>

        **Single operation**

        You can also easily adjoint a single operation just by wrapping it with ``adjoint``:

        .. code-block:: python3

            dev = qml.device('default.qubit', wires=1)
            @qml.qnode(dev)
            def circuit():
                qml.RX(0.123, wires=0)
                qml.adjoint(qml.RX)(0.123, wires=0)
                return qml.expval(qml.PauliZ(0))

        This creates the following circuit:

        >>> print(qml.draw(circuit)())
        0: ──RX(0.12)──RX(-0.12)─┤  <Z>
    """
    if not callable(fn):
        raise ValueError(
            f"The object {fn} of type {type(fn)} is not callable. "
            "This error might occur if you apply adjoint to a list "
            "of operations instead of a function or template."
        )

    @wraps(fn)
    def wrapper(*args, **kwargs):
        with stop_recording(), QuantumTape() as tape:
            res = fn(*args, **kwargs)

        if not tape.operations:
            # we called op.expand(): get the outputted tape
            tape = res

        adjoint_ops = [Adjoint(op) for op in reversed(tape.operations)]

        return adjoint_ops[0] if len(adjoint_ops) == 1 else adjoint_ops

    return wrapper
