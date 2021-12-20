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
"""
This submodule contains the discrete-variable quantum operations that come
from quantum chemistry applications.
"""
# pylint:disable=abstract-method,arguments-differ,protected-access
import math
import numpy as np
from scipy.sparse import coo_matrix

import pennylane as qml
from pennylane.operation import Operation

INV_SQRT2 = 1 / math.sqrt(2)

# Four term gradient recipe for controlled rotations
c1 = INV_SQRT2 * (np.sqrt(2) + 1) / 4
c2 = INV_SQRT2 * (np.sqrt(2) - 1) / 4
a = np.pi / 2
b = 3 * np.pi / 2
four_term_grad_recipe = ([[c1, 1, a], [-c1, 1, -a], [-c2, 1, b], [c2, 1, -b]],)


class SingleExcitation(Operation):
    r"""SingleExcitation(phi, wires)
    Single excitation rotation.

    .. math:: U(\phi) = \begin{bmatrix}
                1 & 0 & 0 & 0 \\
                0 & \cos(\phi/2) & -\sin(\phi/2) & 0 \\
                0 & \sin(\phi/2) & \cos(\phi/2) & 0 \\
                0 & 0 & 0 & 1
            \end{bmatrix}.

    This operation performs a rotation in the two-dimensional subspace :math:`\{|01\rangle,
    |10\rangle\}`. The name originates from the occupation-number representation of
    fermionic wavefunctions, where the transformation  from :math:`|10\rangle` to :math:`|01\rangle`
    is interpreted as "exciting" a particle from the first qubit to the second.

    **Details:**

    * Number of wires: 2
    * Number of parameters: 1
    * Gradient recipe: The ``SingleExcitation`` operator satisfies a four-term parameter-shift rule
      (see Appendix F, https://arxiv.org/abs/2104.05695)

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int]): the wires the operation acts on

    **Example**

    The following circuit performs the transformation :math:`|10\rangle\rightarrow \cos(
    \phi/2)|10\rangle -\sin(\phi/2)|01\rangle`:

    .. code-block::

        dev = qml.device('default.qubit', wires=2)

        @qml.qnode(dev)
        def circuit(phi):
            qml.PauliX(wires=0)
            qml.SingleExcitation(phi, wires=[0, 1])
            return qml.state()

        circuit(0.1)
    """

    num_wires = 2
    grad_method = "A"
    grad_recipe = four_term_grad_recipe

    def generator(self):
        w1, w2 = self.wires
        return 0.25 * qml.PauliX(w1) @ qml.PauliY(w2) - 0.25 * qml.PauliY(w1) @ qml.PauliX(w2)

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        mat = qml.math.diag([1, c, c, 1])
        off_diag = qml.math.convert_like(np.diag([0, 1, -1, 0])[::-1].copy(), theta)
        return mat + s * qml.math.cast_like(off_diag, s)

    @staticmethod
    def compute_decomposition(phi, wires):
        r"""Compute the decomposition for the specified parameter and wires. The decomposition
        defines an Operator as a product of more fundamental gates:

        .. math:: O = O_1 O_2 \dots O_n.

        ``compute_decomposition`` is a static method and can provide the decomposition of a given
        operator without creating a specific instance.
        See also :meth:`~.SingleExcitation.decomposition`.

        Args:
            phi (float): rotation angle :math:`\phi`
            wires (Iterable, Wires): Wires that the operator acts on.

        Returns:
            list[Operator]: decomposition into lower level operations

        **Example:**

        >>> qml.SingleExcitation.compute_decomposition(1.23, wires=(0,1))
        [CNOT(wires=[0, 1]), CRY(1.23, wires=[1, 0]), CNOT(wires=[0, 1])]

        """
        decomp_ops = [
            qml.CNOT(wires=[wires[0], wires[1]]),
            qml.CRY(phi, wires=[wires[1], wires[0]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
        ]
        return decomp_ops

    def adjoint(self):
        (phi,) = self.parameters
        return SingleExcitation(-phi, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G")


class SingleExcitationMinus(Operation):
    r"""SingleExcitationMinus(phi, wires)
    Single excitation rotation with negative phase-shift outside the rotation subspace.

    .. math:: U_-(\phi) = \begin{bmatrix}
                e^{-i\phi/2} & 0 & 0 & 0 \\
                0 & \cos(\phi/2) & -\sin(\phi/2) & 0 \\
                0 & \sin(\phi/2) & \cos(\phi/2) & 0 \\
                0 & 0 & 0 & e^{-i\phi/2}
            \end{bmatrix}.

    **Details:**

    * Number of wires: 2
    * Number of parameters: 1
    * Gradient recipe: :math:`\frac{d}{d\phi}f(U_-(\phi)) = \frac{1}{2}\left[f(U_-(\phi+\pi/2)) - f(U_-(\phi-\pi/2))\right]`
      where :math:`f` is an expectation value depending on :math:`U_-(\phi)`.

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int] or int): the wires the operation acts on

    """
    num_wires = 2
    grad_method = "A"

    def generator(self):
        w1, w2 = self.wires
        return (
            -0.25 * qml.Identity(w1)
            + 0.25 * qml.PauliX(w1) @ qml.PauliY(w2)
            - 0.25 * qml.PauliY(w1) @ qml.PauliX(w2)
            - 0.25 * qml.PauliZ(w1) @ qml.PauliZ(w2)
        )

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        interface = qml.math.get_interface(theta)

        if interface == "tensorflow":
            theta = qml.math.cast_like(theta, 1j)
            c = qml.math.cast_like(c, 1j)
            s = qml.math.cast_like(s, 1j)

        e = qml.math.exp(-1j * theta / 2)
        mat = qml.math.diag([e, 0, 0, e]) + qml.math.diag([0, c, c, 0])
        off_diag = qml.math.convert_like(np.diag([0, 1, -1, 0])[::-1].copy(), theta)
        return mat + s * qml.math.cast_like(off_diag, s)

    @staticmethod
    def compute_decomposition(phi, wires):
        r"""Compute the decomposition for the specified parameter and wires. The decomposition
        defines an Operator as a product of more fundamental gates:

        .. math:: O = O_1 O_2 \dots O_n.

        ``compute_decomposition`` is a static method and can provide the decomposition of a given
        operator without creating a specific instance.
        See also :meth:`~.SingleExcitationMinus.decomposition`.

        Args:
            phi (float): rotation angle :math:`\phi`
            wires (Iterable, Wires): Wires that the operator acts on.

        Returns:
            list[Operator]: decomposition into lower level operations

        **Example:**

        >>> qml.SingleExcitationMinus.compute_decomposition(1.23, wires=(0,1))
        [PauliX(wires=[0]),
        PauliX(wires=[1]),
        ControlledPhaseShift(-0.615, wires=[1, 0]),
        PauliX(wires=[0]),
        PauliX(wires=[1]),
        ControlledPhaseShift(-0.615, wires=[0, 1]),
        CNOT(wires=[0, 1]),
        CRY(1.23, wires=[1, 0]),
        CNOT(wires=[0, 1])]

        """
        decomp_ops = [
            qml.PauliX(wires=wires[0]),
            qml.PauliX(wires=wires[1]),
            qml.ControlledPhaseShift(-phi / 2, wires=[wires[1], wires[0]]),
            qml.PauliX(wires=wires[0]),
            qml.PauliX(wires=wires[1]),
            qml.ControlledPhaseShift(-phi / 2, wires=[wires[0], wires[1]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
            qml.CRY(phi, wires=[wires[1], wires[0]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
        ]
        return decomp_ops

    def adjoint(self):
        (phi,) = self.parameters
        return SingleExcitationMinus(-phi, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G₋")


class SingleExcitationPlus(Operation):
    r"""SingleExcitationPlus(phi, wires)
    Single excitation rotation with positive phase-shift outside the rotation subspace.

    .. math:: U_+(\phi) = \begin{bmatrix}
                e^{i\phi/2} & 0 & 0 & 0 \\
                0 & \cos(\phi/2) & -\sin(\phi/2) & 0 \\
                0 & \sin(\phi/2) & \cos(\phi/2) & 0 \\
                0 & 0 & 0 & e^{i\phi/2}
            \end{bmatrix}.

    **Details:**

    * Number of wires: 2
    * Number of parameters: 1
    * Gradient recipe: :math:`\frac{d}{d\phi}f(U_+(\phi)) = \frac{1}{2}\left[f(U_+(\phi+\pi/2)) - f(U_+(\phi-\pi/2))\right]`
      where :math:`f` is an expectation value depending on :math:`U_+(\phi)`.

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int] or int): the wires the operation acts on

    """
    num_wires = 2
    grad_method = "A"

    def generator(self):
        w1, w2 = self.wires
        return (
            0.25 * qml.Identity(w1)
            + 0.25 * qml.PauliX(w1) @ qml.PauliY(w2)
            - 0.25 * qml.PauliY(w1) @ qml.PauliX(w2)
            + 0.25 * qml.PauliZ(w1) @ qml.PauliZ(w2)
        )

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        interface = qml.math.get_interface(theta)

        if interface == "tensorflow":
            theta = qml.math.cast_like(theta, 1j)
            c = qml.math.cast_like(c, 1j)
            s = qml.math.cast_like(s, 1j)

        e = qml.math.exp(1j * theta / 2)
        mat = qml.math.diag([e, 0, 0, e]) + qml.math.diag([0, c, c, 0])
        off_diag = qml.math.convert_like(np.diag([0, 1, -1, 0])[::-1].copy(), theta)
        return mat + s * qml.math.cast_like(off_diag, s)

    @staticmethod
    def compute_decomposition(phi, wires):
        r"""Compute the decomposition for the specified parameter and wires. The decomposition
        defines an Operator as a product of more fundamental gates:

        .. math:: O = O_1 O_2 \dots O_n.

        ``compute_decomposition`` is a static method and can provide the decomposition of a given
        operator without creating a specific instance.
        See also :meth:`~.SingleExcitationPlus.decomposition`.

        Args:
            phi (float): rotation angle :math:`\phi`
            wires (Iterable, Wires): Wires that the operator acts on.

        Returns:
            list[Operator]: decomposition into lower level operations

        **Example:**

        >>> qml.SingleExcitationPlus.compute_decomposition(1.23, wires=(0,1))
        [PauliX(wires=[0]),
        PauliX(wires=[1]),
        ControlledPhaseShift(0.615, wires=[1, 0]),
        PauliX(wires=[0]),
        PauliX(wires=[1]),
        ControlledPhaseShift(0.615, wires=[0, 1]),
        CNOT(wires=[0, 1]),
        CRY(1.23, wires=[1, 0]),
        CNOT(wires=[0, 1])]

        """
        decomp_ops = [
            qml.PauliX(wires=wires[0]),
            qml.PauliX(wires=wires[1]),
            qml.ControlledPhaseShift(phi / 2, wires=[wires[1], wires[0]]),
            qml.PauliX(wires=wires[0]),
            qml.PauliX(wires=wires[1]),
            qml.ControlledPhaseShift(phi / 2, wires=[wires[0], wires[1]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
            qml.CRY(phi, wires=[wires[1], wires[0]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
        ]
        return decomp_ops

    def adjoint(self):
        (phi,) = self.parameters
        return SingleExcitationPlus(-phi, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G₊")


class DoubleExcitation(Operation):
    r"""DoubleExcitation(phi, wires)
    Double excitation rotation.

    This operation performs an :math:`SO(2)` rotation in the two-dimensional subspace :math:`\{
    |1100\rangle,|0011\rangle\}`. More precisely, it performs the transformation

    .. math::

        &|0011\rangle \rightarrow \cos(\phi/2) |0011\rangle - \sin(\phi/2) |1100\rangle\\
        &|1100\rangle \rightarrow \cos(\phi/2) |1100\rangle + \sin(\phi/2) |0011\rangle,

    while leaving all other basis states unchanged.

    The name originates from the occupation-number representation of fermionic wavefunctions, where
    the transformation from :math:`|1100\rangle` to :math:`|0011\rangle` is interpreted as
    "exciting" two particles from the first pair of qubits to the second pair of qubits.

    **Details:**

    * Number of wires: 4
    * Number of parameters: 1
    * Gradient recipe: The ``DoubleExcitation`` operator satisfies a four-term parameter-shift rule
      (see Appendix F, https://arxiv.org/abs/2104.05695):

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int]): the wires the operation acts on

    **Example**

    The following circuit performs the transformation :math:`|1100\rangle\rightarrow \cos(
    \phi/2)|1100\rangle +\sin(\phi/2)|0011\rangle)`:

    .. code-block::

        dev = qml.device('default.qubit', wires=4)

        @qml.qnode(dev)
        def circuit(phi):
            qml.PauliX(wires=0)
            qml.PauliX(wires=1)
            qml.DoubleExcitation(phi, wires=[0, 1, 2, 3])
            return qml.state()

        circuit(0.1)
    """
    num_wires = 4
    grad_method = "A"
    grad_recipe = four_term_grad_recipe

    def generator(self):
        w0, w1, w2, w3 = self.wires
        coeffs = [0.0625, 0.0625, -0.0625, 0.0625, -0.0625, 0.0625, -0.0625, -0.0625]
        obs = [
            qml.PauliX(w0) @ qml.PauliX(w1) @ qml.PauliX(w2) @ qml.PauliY(w3),
            qml.PauliX(w0) @ qml.PauliX(w1) @ qml.PauliY(w2) @ qml.PauliX(w3),
            qml.PauliX(w0) @ qml.PauliY(w1) @ qml.PauliX(w2) @ qml.PauliX(w3),
            qml.PauliX(w0) @ qml.PauliY(w1) @ qml.PauliY(w2) @ qml.PauliY(w3),
            qml.PauliY(w0) @ qml.PauliX(w1) @ qml.PauliX(w2) @ qml.PauliX(w3),
            qml.PauliY(w0) @ qml.PauliX(w1) @ qml.PauliY(w2) @ qml.PauliY(w3),
            qml.PauliY(w0) @ qml.PauliY(w1) @ qml.PauliX(w2) @ qml.PauliY(w3),
            qml.PauliY(w0) @ qml.PauliY(w1) @ qml.PauliY(w2) @ qml.PauliX(w3),
        ]
        return qml.Hamiltonian(coeffs, obs)

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        mat = qml.math.diag([1.0] * 3 + [c] + [1.0] * 8 + [c] + [1.0] * 3)
        mat = qml.math.scatter_element_add(mat, (3, 12), -s)
        mat = qml.math.scatter_element_add(mat, (12, 3), s)
        return mat

    @staticmethod
    def compute_decomposition(phi, wires):
        r"""Compute the decomposition for the specified parameter and wires. The decomposition
        defines an Operator as a product of more fundamental gates:

        .. math:: O = O_1 O_2 \dots O_n.

        ``compute_decomposition`` is a static method and can provide the decomposition of a given
        operator without creating a specific instance.
        See also :meth:`~.DoubleExcitation.decomposition`.

        For the source of this decomposition, see page 17 of
        `"Local, Expressive, Quantum-Number-Preserving VQE Ansatze for Fermionic Systems" <https://arxiv.org/abs/2104.05695>`_ .

        Args:
            phi (float): rotation angle :math:`\phi`
            wires (Iterable, Wires): Wires that the operator acts on.

        Returns:
            list[Operator]: decomposition into lower level operations

        **Example:**

        >>> qml.DoubleExcitation.compute_decomposition(1.23, wires=(0,1,2,3))
        [CNOT(wires=[2, 3]),
        CNOT(wires=[0, 2]),
        Hadamard(wires=[3]),
        Hadamard(wires=[0]),
        CNOT(wires=[2, 3]),
        CNOT(wires=[0, 1]),
        RY(0.15375, wires=[1]),
        RY(-0.15375, wires=[0]),
        CNOT(wires=[0, 3]),
        Hadamard(wires=[3]),
        CNOT(wires=[3, 1]),
        RY(0.15375, wires=[1]),
        RY(-0.15375, wires=[0]),
        CNOT(wires=[2, 1]),
        CNOT(wires=[2, 0]),
        RY(-0.15375, wires=[1]),
        RY(0.15375, wires=[0]),
        CNOT(wires=[3, 1]),
        Hadamard(wires=[3]),
        CNOT(wires=[0, 3]),
        RY(-0.15375, wires=[1]),
        RY(0.15375, wires=[0]),
        CNOT(wires=[0, 1]),
        CNOT(wires=[2, 0]),
        Hadamard(wires=[0]),
        Hadamard(wires=[3]),
        CNOT(wires=[0, 2]),
        CNOT(wires=[2, 3])]

        """
        # This decomposition is the "upside down" version of that on p17 of https://arxiv.org/abs/2104.05695
        decomp_ops = [
            qml.CNOT(wires=[wires[2], wires[3]]),
            qml.CNOT(wires=[wires[0], wires[2]]),
            qml.Hadamard(wires=wires[3]),
            qml.Hadamard(wires=wires[0]),
            qml.CNOT(wires=[wires[2], wires[3]]),
            qml.CNOT(wires=[wires[0], wires[1]]),
            qml.RY(phi / 8, wires=wires[1]),
            qml.RY(-phi / 8, wires=wires[0]),
            qml.CNOT(wires=[wires[0], wires[3]]),
            qml.Hadamard(wires=wires[3]),
            qml.CNOT(wires=[wires[3], wires[1]]),
            qml.RY(phi / 8, wires=wires[1]),
            qml.RY(-phi / 8, wires=wires[0]),
            qml.CNOT(wires=[wires[2], wires[1]]),
            qml.CNOT(wires=[wires[2], wires[0]]),
            qml.RY(-phi / 8, wires=wires[1]),
            qml.RY(phi / 8, wires=wires[0]),
            qml.CNOT(wires=[wires[3], wires[1]]),
            qml.Hadamard(wires=wires[3]),
            qml.CNOT(wires=[wires[0], wires[3]]),
            qml.RY(-phi / 8, wires=wires[1]),
            qml.RY(phi / 8, wires=wires[0]),
            qml.CNOT(wires=[wires[0], wires[1]]),
            qml.CNOT(wires=[wires[2], wires[0]]),
            qml.Hadamard(wires=wires[0]),
            qml.Hadamard(wires=wires[3]),
            qml.CNOT(wires=[wires[0], wires[2]]),
            qml.CNOT(wires=[wires[2], wires[3]]),
        ]

        return decomp_ops

    def adjoint(self):
        (theta,) = self.parameters
        return DoubleExcitation(-theta, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G²")


class DoubleExcitationPlus(Operation):
    r"""DoubleExcitationPlus(phi, wires)
    Double excitation rotation with positive phase-shift outside the rotation subspace.

    This operation performs an :math:`SO(2)` rotation in the two-dimensional subspace :math:`\{
    |1100\rangle,|0011\rangle\}` while applying a phase-shift on other states. More precisely,
    it performs the transformation

    .. math::

        &|0011\rangle \rightarrow \cos(\phi/2) |0011\rangle - \sin(\phi/2) |1100\rangle\\
        &|1100\rangle \rightarrow \cos(\phi/2) |1100\rangle + \sin(\phi/2) |0011\rangle\\
        &|x\rangle \rightarrow e^{i\phi/2} |x\rangle,

    for all other basis states :math:`|x\rangle`.

    **Details:**

    * Number of wires: 4
    * Number of parameters: 1
    * Gradient recipe: :math:`\frac{d}{d\phi}f(U_+(\phi)) = \frac{1}{2}\left[f(U_+(\phi+\pi/2)) - f(U_+(\phi-\pi/2))\right]`
      where :math:`f` is an expectation value depending on :math:`U_+(\phi)`

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int]): the wires the operation acts on
    """
    num_wires = 4
    grad_method = "A"

    def generator(self):
        G = -1 * np.eye(16, dtype=np.complex64)
        G[3, 3] = G[12, 12] = 0
        G[3, 12] = -1j  # 3 (dec) = 0011 (bin)
        G[12, 3] = 1j  # 12 (dec) = 1100 (bin)
        H = coo_matrix(-0.5 * G)
        return qml.SparseHamiltonian(H, wires=self.wires)

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        interface = qml.math.get_interface(theta)

        if interface == "tensorflow":
            theta = qml.math.cast_like(theta, 1j)
            c = qml.math.cast_like(c, 1j)
            s = qml.math.cast_like(s, 1j)

        e = qml.math.exp(1j * theta / 2)

        mat = qml.math.diag([e] * 3 + [0] + [e] * 8 + [0] + [e] * 3)
        mat = qml.math.scatter_element_add(mat, (3, 3), c)
        mat = qml.math.scatter_element_add(mat, (3, 12), -s)
        mat = qml.math.scatter_element_add(mat, (12, 3), s)
        mat = qml.math.scatter_element_add(mat, (12, 12), c)
        return mat

    def adjoint(self):
        (theta,) = self.parameters
        return DoubleExcitationPlus(-theta, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G²₊")


class DoubleExcitationMinus(Operation):
    r"""DoubleExcitationMinus(phi, wires)
    Double excitation rotation with negative phase-shift outside the rotation subspace.

    This operation performs an :math:`SO(2)` rotation in the two-dimensional subspace :math:`\{
    |1100\rangle,|0011\rangle\}` while applying a phase-shift on other states. More precisely,
    it performs the transformation

    .. math::

        &|0011\rangle \rightarrow \cos(\phi/2) |0011\rangle - \sin(\phi/2) |1100\rangle\\
        &|1100\rangle \rightarrow \cos(\phi/2) |1100\rangle + \sin(\phi/2) |0011\rangle\\
        &|x\rangle \rightarrow e^{-i\phi/2} |x\rangle,

    for all other basis states :math:`|x\rangle`.

    **Details:**

    * Number of wires: 4
    * Number of parameters: 1
    * Gradient recipe: :math:`\frac{d}{d\phi}f(U_-(\phi)) = \frac{1}{2}\left[f(U_-(\phi+\pi/2)) - f(U_-(\phi-\pi/2))\right]`
      where :math:`f` is an expectation value depending on :math:`U_-(\phi)`

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int]): the wires the operation acts on
    """
    num_wires = 4
    grad_method = "A"

    def generator(self):
        G = np.eye(16, dtype=np.complex64)
        G[3, 3] = 0
        G[12, 12] = 0
        G[3, 12] = -1j  # 3 (dec) = 0011 (bin)
        G[12, 3] = 1j  # 12 (dec) = 1100 (bin)
        H = coo_matrix(-0.5 * G)
        return qml.SparseHamiltonian(H, wires=self.wires)

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        theta = params[0]

        c = qml.math.cos(theta / 2)
        s = qml.math.sin(theta / 2)

        interface = qml.math.get_interface(theta)

        if interface == "tensorflow":
            theta = qml.math.cast_like(theta, 1j)
            c = qml.math.cast_like(c, 1j)
            s = qml.math.cast_like(s, 1j)

        e = qml.math.exp(-1j * theta / 2)
        mat = qml.math.diag([e] * 3 + [0] + [e] * 8 + [0] + [e] * 3)
        mat = qml.math.scatter_element_add(mat, (3, 3), c)
        mat = qml.math.scatter_element_add(mat, (3, 12), -s)
        mat = qml.math.scatter_element_add(mat, (12, 3), s)
        mat = qml.math.scatter_element_add(mat, (12, 12), c)
        return mat

    def adjoint(self):
        (theta,) = self.parameters
        return DoubleExcitationMinus(-theta, wires=self.wires)

    def label(self, decimals=None, base_label=None):
        return super().label(decimals=decimals, base_label=base_label or "G²₋")


class OrbitalRotation(Operation):
    r"""OrbitalRotation(phi, wires)
    Spin-adapted spatial orbital rotation.

    For two neighbouring spatial orbitals :math:`\{|\Phi_{0}\rangle, |\Phi_{1}\rangle\}`, this operation
    performs the following transformation

    .. math::
        &|\Phi_{0}\rangle = \cos(\phi/2)|\Phi_{0}\rangle - \sin(\phi/2)|\Phi_{1}\rangle\\
        &|\Phi_{1}\rangle = \cos(\phi/2)|\Phi_{0}\rangle + \sin(\phi/2)|\Phi_{1}\rangle,

    with the same orbital operation applied in the :math:`\alpha` and :math:`\beta` spin orbitals.

    .. figure:: ../../_static/qchem/orbital_rotation_decomposition_extended.png
        :align: center
        :width: 100%
        :target: javascript:void(0);

    Here, :math:`G(\phi)` represents a single-excitation Givens rotation, implemented in PennyLane
    as the :class:`~.SingleExcitation` operation.

    **Details:**

    * Number of wires: 4
    * Number of parameters: 1
    * Gradient recipe: The ``OrbitalRotation`` operator satisfies the four-term parameter-shift rule
      (see Appendix F, https://arxiv.org/abs/2104.05695)

    Args:
        phi (float): rotation angle :math:`\phi`
        wires (Sequence[int]): the wires the operation acts on

    **Example**

    .. code-block::

        >>> dev = qml.device('default.qubit', wires=4)
        >>> @qml.qnode(dev)
        ... def circuit(phi):
        ...     qml.BasisState(np.array([1, 1, 0, 0]), wires=[0, 1, 2, 3])
        ...     qml.OrbitalRotation(phi, wires=[0, 1, 2, 3])
        ...     return qml.state()
        >>> circuit(0.1)
        array([ 0.        +0.j,  0.        +0.j,  0.        +0.j,
                0.00249792+0.j,  0.        +0.j,  0.        +0.j,
               -0.04991671+0.j,  0.        +0.j,  0.        +0.j,
               -0.04991671+0.j,  0.        +0.j,  0.        +0.j,
                0.99750208+0.j,  0.        +0.j,  0.        +0.j,
                0.        +0.j])
    """
    num_wires = 4
    grad_method = "A"
    grad_recipe = four_term_grad_recipe

    def generator(self):
        w0, w1, w2, w3 = self.wires
        return (
            0.25 * qml.PauliX(w0) @ qml.PauliY(w2)
            - 0.25 * qml.PauliY(w0) @ qml.PauliX(w2)
            + 0.25 * qml.PauliX(w1) @ qml.PauliY(w3)
            - 0.25 * qml.PauliY(w1) @ qml.PauliX(w3)
        )

    @property
    def num_params(self):
        return 1

    @classmethod
    def _matrix(cls, *params):
        # This matrix is the "sign flipped" version of that on p18 of https://arxiv.org/abs/2104.05695,
        # where the sign flip is to adjust for the opposite convention used by authors for naming wires.
        # Additionally, there was a typo in the sign of a matrix element "s" at [2, 8], which is fixed here.

        phi = params[0]
        c = qml.math.cos(phi / 2)
        s = qml.math.sin(phi / 2)

        interface = qml.math.get_interface(phi)

        if interface == "torch":
            # Use convert_like to ensure that the tensor is put on the correct
            # Torch device
            z = qml.math.convert_like(qml.math.zeros([16]), phi)
        else:
            z = qml.math.zeros([16], like=interface)

        diag = qml.math.diag([1, c, c, c ** 2, c, 1, c ** 2, c, c, c ** 2, 1, c, c ** 2, c, c, 1])

        U = diag + qml.math.stack(
            [
                z,
                qml.math.stack([0, 0, 0, 0, -s, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                qml.math.stack([0, 0, 0, 0, 0, 0, 0, 0, -s, 0, 0, 0, 0, 0, 0, 0]),
                qml.math.stack([0, 0, 0, 0, 0, 0, -c * s, 0, 0, -c * s, 0, 0, s * s, 0, 0, 0]),
                qml.math.stack([0, s, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                z,
                qml.math.stack([0, 0, 0, c * s, 0, 0, 0, 0, 0, -s * s, 0, 0, -c * s, 0, 0, 0]),
                qml.math.stack([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -s, 0, 0]),
                qml.math.stack([0, 0, s, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
                qml.math.stack([0, 0, 0, c * s, 0, 0, -s * s, 0, 0, 0, 0, 0, -c * s, 0, 0, 0]),
                z,
                qml.math.stack([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -s, 0]),
                qml.math.stack([0, 0, 0, s * s, 0, 0, c * s, 0, 0, c * s, 0, 0, 0, 0, 0, 0]),
                qml.math.stack([0, 0, 0, 0, 0, 0, 0, s, 0, 0, 0, 0, 0, 0, 0, 0]),
                qml.math.stack([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, s, 0, 0, 0, 0]),
                z,
            ]
        )

        return U

    @staticmethod
    def compute_decomposition(phi, wires):
        r"""Compute the decomposition for the specified parameter and wires. The decomposition
        defines an Operator as a product of more fundamental gates:

        .. math:: O = O_1 O_2 \dots O_n.

        ``compute_decomposition`` is a static method and can provide the decomposition of a given
        operator without creating a specific instance.
        See also :meth:`~.OrbitalRotation.decomposition`.

        For the source of this decomposition, see page 18 of
        `"Local, Expressive, Quantum-Number-Preserving VQE Ansatze for Fermionic Systems" <https://arxiv.org/abs/2104.05695>`_ .

        Args:
            phi (float): rotation angle :math:`\phi`
            wires (Iterable, Wires): Wires that the operator acts on.

        Returns:
            list[Operator]: decomposition into lower level operations

        **Example:**

        >>> qml.OrbitalRotation.compute_decomposition(1.23, wires=(0,1,2,3))
        [Hadamard(wires=[3]),
        Hadamard(wires=[2]),
        CNOT(wires=[3, 1]),
        CNOT(wires=[2, 0]),
        RY(0.615, wires=[3]),
        RY(0.615, wires=[2]),
        RY(0.615, wires=[1]),
        RY(0.615, wires=[0]),
        CNOT(wires=[3, 1]),
        CNOT(wires=[2, 0]),
        Hadamard(wires=[3]),
        Hadamard(wires=[2])]

        """
        # This decomposition is the "upside down" version of that on p18 of https://arxiv.org/abs/2104.05695
        decomp_ops = [
            qml.Hadamard(wires=wires[3]),
            qml.Hadamard(wires=wires[2]),
            qml.CNOT(wires=[wires[3], wires[1]]),
            qml.CNOT(wires=[wires[2], wires[0]]),
            qml.RY(phi / 2, wires=wires[3]),
            qml.RY(phi / 2, wires=wires[2]),
            qml.RY(phi / 2, wires=wires[1]),
            qml.RY(phi / 2, wires=wires[0]),
            qml.CNOT(wires=[wires[3], wires[1]]),
            qml.CNOT(wires=[wires[2], wires[0]]),
            qml.Hadamard(wires=wires[3]),
            qml.Hadamard(wires=wires[2]),
        ]
        return decomp_ops

    def adjoint(self):
        (phi,) = self.parameters
        return OrbitalRotation(-phi, wires=self.wires)
