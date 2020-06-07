# @generated by generate_proto_mypy_stubs.py.  Do not edit!
import sys
from google.protobuf.descriptor import (
    Descriptor as google___protobuf___descriptor___Descriptor,
    EnumDescriptor as google___protobuf___descriptor___EnumDescriptor,
    FileDescriptor as google___protobuf___descriptor___FileDescriptor,
)

from google.protobuf.message import (
    Message as google___protobuf___message___Message,
)

from typing import (
    List as typing___List,
    NewType as typing___NewType,
    Optional as typing___Optional,
    Text as typing___Text,
    Tuple as typing___Tuple,
    Union as typing___Union,
    cast as typing___cast,
)

from typing_extensions import (
    Literal as typing_extensions___Literal,
)


builtin___bool = bool
builtin___bytes = bytes
builtin___float = float
builtin___int = int
builtin___str = str
if sys.version_info < (3,):
    builtin___buffer = buffer
    builtin___unicode = unicode


DESCRIPTOR: google___protobuf___descriptor___FileDescriptor = ...

RGPStateValue = typing___NewType('RGPStateValue', builtin___int)
type___RGPStateValue = RGPStateValue
class RGPState(object):
    DESCRIPTOR: google___protobuf___descriptor___EnumDescriptor = ...
    @classmethod
    def Name(cls, number: builtin___int) -> builtin___str: ...
    @classmethod
    def Value(cls, name: builtin___str) -> RGPStateValue: ...
    @classmethod
    def keys(cls) -> typing___List[builtin___str]: ...
    @classmethod
    def values(cls) -> typing___List[RGPStateValue]: ...
    @classmethod
    def items(cls) -> typing___List[typing___Tuple[builtin___str, RGPStateValue]]: ...
    Unknown = typing___cast(RGPStateValue, 0)
    AddPeriod = typing___cast(RGPStateValue, 1)
    AutoRenewPeriod = typing___cast(RGPStateValue, 2)
    RenewPeriod = typing___cast(RGPStateValue, 3)
    TransferPeriod = typing___cast(RGPStateValue, 4)
    RedemptionPeriod = typing___cast(RGPStateValue, 5)
    PendingRestore = typing___cast(RGPStateValue, 6)
    PendingDelete = typing___cast(RGPStateValue, 7)
Unknown = typing___cast(RGPStateValue, 0)
AddPeriod = typing___cast(RGPStateValue, 1)
AutoRenewPeriod = typing___cast(RGPStateValue, 2)
RenewPeriod = typing___cast(RGPStateValue, 3)
TransferPeriod = typing___cast(RGPStateValue, 4)
RedemptionPeriod = typing___cast(RGPStateValue, 5)
PendingRestore = typing___cast(RGPStateValue, 6)
PendingDelete = typing___cast(RGPStateValue, 7)
type___RGPState = RGPState

class RequestRequest(google___protobuf___message___Message):
    DESCRIPTOR: google___protobuf___descriptor___Descriptor = ...
    name: typing___Text = ...

    def __init__(self,
        *,
        name : typing___Optional[typing___Text] = None,
        ) -> None: ...
    if sys.version_info >= (3,):
        @classmethod
        def FromString(cls, s: builtin___bytes) -> RequestRequest: ...
    else:
        @classmethod
        def FromString(cls, s: typing___Union[builtin___bytes, builtin___buffer, builtin___unicode]) -> RequestRequest: ...
    def ClearField(self, field_name: typing_extensions___Literal[u"name",b"name"]) -> None: ...
type___RequestRequest = RequestRequest

class RestoreReply(google___protobuf___message___Message):
    DESCRIPTOR: google___protobuf___descriptor___Descriptor = ...
    pending: builtin___bool = ...
    state: type___RGPStateValue = ...
    registry_name: typing___Text = ...

    def __init__(self,
        *,
        pending : typing___Optional[builtin___bool] = None,
        state : typing___Optional[type___RGPStateValue] = None,
        registry_name : typing___Optional[typing___Text] = None,
        ) -> None: ...
    if sys.version_info >= (3,):
        @classmethod
        def FromString(cls, s: builtin___bytes) -> RestoreReply: ...
    else:
        @classmethod
        def FromString(cls, s: typing___Union[builtin___bytes, builtin___buffer, builtin___unicode]) -> RestoreReply: ...
    def ClearField(self, field_name: typing_extensions___Literal[u"pending",b"pending",u"registry_name",b"registry_name",u"state",b"state"]) -> None: ...
type___RestoreReply = RestoreReply