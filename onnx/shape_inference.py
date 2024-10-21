# Copyright (c) ONNX Project Contributors
#
# SPDX-License-Identifier: Apache-2.0

"""onnx shape inference. Shape inference is not guaranteed to be
complete.

"""

from __future__ import annotations

import os
import sys
from typing import Sequence

import onnx
import onnx.onnx_cpp2py_export.shape_inference as C  # noqa: N812
from onnx import AttributeProto, FunctionProto, ModelProto, TypeProto


def infer_shapes(  # type: ignore[return]
    model: ModelProto | bytes | str | os.PathLike,
    check_type: bool = False,
    strict_mode: bool = False,
    data_prop: bool = False,
    output_path: str | os.PathLike = "",
) -> ModelProto:
    """Apply shape inference to the provided ModelProto.

    Inferred shapes are added to the value_info field of the graph.

    If the inferred values conflict with values already provided in the
    graph, that means that the provided values are invalid (or there is a
    bug in shape inference), and the result is unspecified.

    Arguments:
        model: ModelProto. If the model bytes size is larger than 2GB, function
            should be called using model path.
        check_type: Checks the type-equality for input and output.
        strict_mode: Stricter shape inference, it will throw errors if any;
            Otherwise, simply stop if any error.
        data_prop: Enables data propagation for limited operators to perform shape computation.
        output_path: Used only if `model` is a path. The original model path is used if not specified.

    Returns:
        (ModelProto) model with inferred shape information. Return None if `model` is a path.
    """
    # If model is a path instead of ModelProto
    if isinstance(model, (str, os.PathLike)):
        model_path = os.fspath(model)
        output_path = model_path if output_path == "" else os.fspath(output_path)
        C.infer_shapes_path(model_path, output_path, check_type, strict_mode, data_prop)
    else:
        protobuf_string = (
            model if isinstance(model, bytes) else model.SerializeToString()
        )
        # If the protobuf is larger than 2GB,
        # remind users should use the model path to check
        if sys.getsizeof(protobuf_string) > onnx.checker.MAXIMUM_PROTOBUF:
            raise ValueError(
                "This protobuf of onnx model is too large (>2GB). Call infer_shapes with model path instead."
            )
        inferred_model_str = C.infer_shapes(
            protobuf_string, check_type, strict_mode, data_prop
        )
        return onnx.load_from_string(inferred_model_str)


def infer_node_outputs(
    schema: onnx.defs.OpSchema,
    node: onnx.NodeProto,
    input_types: dict[str, onnx.TypeProto],
    input_data: dict[str, onnx.TensorProto] | None = None,
    input_sparse_data: dict[str, onnx.SparseTensorProto] | None = None,
    opset_imports: list[onnx.OperatorSetIdProto] | None = None,
    ir_version: int = onnx.IR_VERSION,
) -> dict[str, onnx.TypeProto]:
    if not schema.has_type_and_shape_inference_function:  # type: ignore
        return {}
    if input_data is None:
        input_data = {}
    if input_sparse_data is None:
        input_sparse_data = {}
    if opset_imports is None:
        passed_opset_imports = {}
    else:
        passed_opset_imports = {opset.domain: opset.version for opset in opset_imports}

    # catch KeyError if node's input does not exist in input_types
    passed_input_types = {
        key: input_types[key].SerializeToString() for key in node.input if key != ""
    }
    # input_types will also be used as outer_scope_value_types so do not filter by node's input here
    for key in input_types:
        if key not in passed_input_types:
            passed_input_types[key] = input_types[key].SerializeToString()
    passed_input_data = {
        key: input_data[key].SerializeToString()
        for key in node.input
        if key in input_data
    }
    passed_sparse_input_data = {
        key: input_sparse_data[key].SerializeToString()
        for key in node.input
        if key in input_sparse_data
    }

    outputs = schema._infer_node_outputs(
        node.SerializeToString(),
        passed_input_types,
        passed_input_data,
        passed_sparse_input_data,
        passed_opset_imports,
        ir_version,
    )  # type: ignore[call-arg]
    return {key: onnx.TypeProto.FromString(out) for key, out in outputs.items()}


def infer_function_output_types(
    function: FunctionProto,
    input_types: Sequence[TypeProto],
    attributes: Sequence[AttributeProto],
) -> list[TypeProto]:
    """Apply type-and-shape-inference to given function body, with given input types
    and given input attribute values.
    """
    result = C.infer_function_output_types(
        function.SerializeToString(),
        [x.SerializeToString() for x in input_types],
        [x.SerializeToString() for x in attributes],
    )

    def to_type_proto(x) -> TypeProto:
        type_proto = onnx.TypeProto()
        type_proto.ParseFromString(x)
        return type_proto

    return [to_type_proto(x) for x in result]


InferenceError = C.InferenceError
