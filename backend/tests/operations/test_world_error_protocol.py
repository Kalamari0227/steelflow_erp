"""World errors preserve their payload while supporting Python propagation state."""
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, asdict
from json import JSONDecodeError

import pytest

from app.operations.bundle_registry import ServiceError, verify_test_bytes
from app.operations.world_contract import read_json
from app.operations.world_types import WorldContractError, require


@contextmanager
def passthrough() -> Iterator[None]:
    yield


def test_require_preserves_world_error_across_contextmanager() -> None:
    with pytest.raises(WorldContractError) as caught:
        with passthrough():
            require(False, 'optional_exit_branch', 'src:ti-shl-sheet')
    error = caught.value
    assert type(error) is WorldContractError
    assert isinstance(error, ValueError)
    assert (error.code, error.reference) == ('optional_exit_branch', 'src:ti-shl-sheet')
    assert str(error) == 'optional_exit_branch: src:ti-shl-sheet'


def test_existing_error_retains_identity_across_contextmanager() -> None:
    original = WorldContractError('reference', 'segment:missing')
    with pytest.raises(WorldContractError) as caught:
        with passthrough():
            raise original
    assert caught.value is original
    assert original.__traceback__ is not None


def test_malformed_json_retains_decoder_cause_across_contextmanager() -> None:
    with pytest.raises(WorldContractError) as caught:
        with passthrough():
            read_json('{')
    error = caught.value
    assert error.code == 'json'
    assert isinstance(error.__cause__, JSONDecodeError)
    assert error.reference == str(error.__cause__)
    assert error.__context__ is error.__cause__
    assert error.__suppress_context__ is True


def test_duplicate_json_retains_validator_payload_across_contextmanager() -> None:
    with pytest.raises(WorldContractError) as caught:
        with passthrough():
            read_json('{"a":1,"a":2}')
    assert (caught.value.code, caught.value.reference) == ('duplicate', 'JSON member')
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_exception_metadata_supports_tracebacks_chaining_and_notes() -> None:
    error = WorldContractError('reference', 'segment:missing')
    with pytest.raises(WorldContractError):
        raise error
    traceback = error.__traceback__
    assert traceback is not None
    error.__traceback__ = traceback
    assert error.with_traceback(traceback) is error
    assert error.__traceback__ is traceback
    assert error.with_traceback(None) is error
    assert error.__traceback__ is None
    cause = ValueError('cause')
    context = TypeError('context')
    error.__cause__ = cause
    error.__context__ = context
    error.__suppress_context__ = False
    assert error.__cause__ is cause
    assert error.__context__ is context
    assert error.__suppress_context__ is False
    error.__suppress_context__ = True
    assert error.__suppress_context__ is True
    error.add_note('first note')
    error.add_note('second note')
    assert error.__notes__ == ['first note', 'second note']
    del error.__notes__
    with pytest.raises(AttributeError):
        getattr(error, '__notes__')
    error.__cause__ = None
    error.__context__ = None
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize('attribute', ['__traceback__', '__cause__', '__context__', '__suppress_context__'])
def test_invalid_exception_metadata_uses_native_type_error(attribute: str) -> None:
    error = WorldContractError('reference', 'segment:missing')
    with pytest.raises(TypeError) as caught:
        setattr(error, attribute, 'invalid metadata')
    assert type(caught.value) is TypeError
    assert 'super(type, obj)' not in str(caught.value)


@pytest.mark.parametrize('attribute', ['code', 'reference'])
def test_error_payload_rejects_assignment_and_deletion(attribute: str) -> None:
    error = WorldContractError('reference', 'segment:missing')
    original_hash = hash(error)
    with pytest.raises(FrozenInstanceError):
        setattr(error, attribute, 'changed')
    with pytest.raises(FrozenInstanceError):
        delattr(error, attribute)
    assert (error.code, error.reference) == ('reference', 'segment:missing')
    assert hash(error) == original_hash


def test_error_keeps_constructor_dataclass_and_value_contracts() -> None:
    positional = WorldContractError('reference', 'segment:missing')
    keyword = WorldContractError(code='reference', reference='segment:missing')
    assert positional.args == ('reference', 'segment:missing')
    assert keyword.args == ()
    assert positional == keyword
    assert hash(positional) == hash(keyword)
    assert positional != WorldContractError('json', 'segment:missing')
    assert positional != WorldContractError('reference', 'segment:other')
    assert repr(positional) == "WorldContractError(code='reference', reference='segment:missing')"
    assert asdict(positional) == {'code': 'reference', 'reference': 'segment:missing'}
    assert str(keyword) == 'reference: segment:missing'


def test_admission_adapter_retains_world_error_cause_across_contextmanager() -> None:
    with pytest.raises(ServiceError) as caught:
        with passthrough():
            verify_test_bytes(b'{"a":1,"a":2}', {})
    error = caught.value
    assert (error.code, error.detail, error.status_code) == (
        'unsupported_bundle', 'duplicate: JSON member', 422,
    )
    assert type(error.__cause__) is WorldContractError
    assert (error.__cause__.code, error.__cause__.reference) == ('duplicate', 'JSON member')
    assert error.__context__ is error.__cause__
    assert error.__suppress_context__ is True
