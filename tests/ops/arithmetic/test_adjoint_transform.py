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
import pytest
import numpy as np

import pennylane as qml
from pennylane import adjoint
from pennylane.ops.arithmetic import Adjoint

noncallable_objects = [
    qml.RX(0.2, wires=0),
    qml.AngleEmbedding(list(range(2)), wires=range(2)),
    [qml.Hadamard(1), qml.RX(-0.2, wires=1)],
    qml.tape.QuantumTape(),
]


@pytest.mark.parametrize("obj", noncallable_objects)
def test_error_adjoint_on_noncallable(obj):
    """Test that an error is raised if qml.adjoint is applied to an object that
    is not callable, as it silently does not have any effect on those."""
    with pytest.raises(ValueError, match=f"{type(obj)} is not callable."):
        adjoint(obj)


class TestDifferentCallableTypes:
    def test_adjoint_single_op(self):

        with qml.tape.QuantumTape() as tape:
            out = adjoint(qml.RX)(1.234, wires="a")

        assert out == tape[0]
        assert out.__class__ is Adjoint
        assert out.base.__class__ is qml.RX
        assert out.data == [1.234]
        assert out.wires == qml.wires.Wires("a")

    def test_adjoint_template(self):

        with qml.tape.QuantumTape() as tape:
            out = adjoint(qml.QFT)(wires=(0, 1, 2))

        assert len(tape) == 1
        assert out == tape[0]
        assert out.__class__ is Adjoint
        assert out.base.__class__ is qml.QFT
        assert out.wires == qml.wires.Wires((0, 1, 2))

    def test_adjoint_on_function(self):
        """Test adjoint transform on a function"""

        def func(x, y, z):
            qml.RX(x, wires=0)
            qml.RY(y, wires=0)
            qml.RZ(z, wires=0)

        x = 1.23
        y = 2.34
        z = 3.45
        with qml.tape.QuantumTape() as tape:
            out = adjoint(func)(x, y, z)

        assert out == tape.circuit

        for op in tape:
            assert op.__class__ is Adjoint

        # check order reversed
        assert tape[0].base.__class__ is qml.RZ
        assert tape[1].base.__class__ is qml.RY
        assert tape[2].base.__class__ is qml.RX

        # check parameters assigned correctly
        assert tape[0].data == [z]
        assert tape[1].data == [y]
        assert tape[2].data == [x]

    def test_nested_adjoint(self):

        x = 4.321
        with qml.tape.QuantumTape() as tape:
            out = adjoint(adjoint(qml.RX))(x, wires="b")

        assert out is tape[0]
        assert out.__class__ is Adjoint
        assert out.base.__class__ is Adjoint
        assert out.base.base.__class__ is qml.RX
        assert out.data == [x]
        assert out.wires == qml.wires.Wires("b")


class TestOutsideofQueuing:
    def test_single_op_outside_of_queuing(self):

        x = 1.234
        out = adjoint(qml.IsingXX)(x, wires=(0, 1))

        assert out.__class__ is Adjoint
        assert out.base.__class__ is qml.IsingXX
        assert out.data == [1.234]
        assert out.wires == qml.wires.Wires((0, 1))

    def test_function_outside_of_queuing(self):
        def func(wire):
            qml.S(wire)
            qml.SX(wire)

        wire = 1.234
        out = adjoint(func)(wire)

        assert len(out) == 2
        assert all(op.__class__ is Adjoint for op in out)
        assert all(op.wires == qml.wires.Wires(wire) for op in out)


class TestIntegration:
    """Test circuit execution and gradients with the adjoint transform."""

    def test_single_op(self):
        """Test the adjoint of a single op against analytically expected results."""

        @qml.qnode(qml.device("default.qubit", wires=1))
        def circ():
            qml.PauliX(0)
            adjoint(qml.S)(0)
            return qml.state()

        res = circ()
        expected = np.array([0, -1j])

        assert np.allclose(res, expected)

    @pytest.mark.autograd
    @pytest.mark.parametrize("diff_method", ("backprop", "adjoint", "parameter-shift"))
    def test_gradient_autograd(self, diff_method):
        """Test gradients through the adjoint transform with autograd."""
        import autograd

        @qml.qnode(
            qml.device("default.qubit", wires=1), diff_method=diff_method, interface="autograd"
        )
        def circ(x):
            adjoint(qml.RX)(x, wires=0)
            return qml.expval(qml.PauliY(0))

        x = autograd.numpy.array(0.234)
        expected_res = np.sin(x)
        expected_grad = np.cos(x)
        assert qml.math.allclose(circ(x), expected_res)
        assert qml.math.allclose(autograd.grad(circ)(x), expected_grad)

    @pytest.mark.jax
    @pytest.mark.parametrize("diff_method", ("backprop", "adjoint", "parameter-shift"))
    def test_gradient_jax(self, diff_method):
        """Test gradients through the adjoint transform with jax."""
        import jax

        @qml.qnode(qml.device("default.qubit", wires=1), diff_method=diff_method, interface="jax")
        def circ(x):
            adjoint(qml.RX)(x, wires=0)
            return qml.expval(qml.PauliY(0))

        x = jax.numpy.array(0.234)
        expected_res = jax.numpy.sin(x)
        expected_grad = jax.numpy.cos(x)
        assert qml.math.allclose(circ(x), expected_res)
        assert qml.math.allclose(jax.grad(circ)(x), expected_grad)

    @pytest.mark.torch
    @pytest.mark.parametrize("diff_method", ("backprop", "adjoint", "parameter-shift"))
    def test_gradient_torch(self, diff_method):
        """Test gradients through the adjoint transform with torch."""
        import torch

        @qml.qnode(qml.device("default.qubit", wires=1), diff_method=diff_method, interface="torch")
        def circ(x):
            adjoint(qml.RX)(x, wires=0)
            return qml.expval(qml.PauliY(0))

        x = torch.tensor(0.234, requires_grad=True)
        y = circ(x)
        y.backward()

        assert qml.math.allclose(y, torch.sin(x))
        assert qml.math.allclose(x.grad, torch.cos(x))

    @pytest.mark.tf
    @pytest.mark.parametrize("diff_method", ("backprop", "adjoint", "parameter-shift"))
    def test_gradient_torch(self, diff_method):
        """Test gradients through the adjoint transform with tensorflow."""

        import tensorflow as tf

        @qml.qnode(qml.device("default.qubit", wires=1), diff_method=diff_method, interface="tf")
        def circ(x):
            adjoint(qml.RX)(x, wires=0)
            return qml.expval(qml.PauliY(0))

        x = tf.Variable(0.234)
        with tf.GradientTape() as tape:
            y = circ(x)

        grad = tape.gradient(y, x)

        assert qml.math.allclose(y, tf.sin(x))
        assert qml.math.allclose(grad, tf.cos(x))