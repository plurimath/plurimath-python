"""Thin transport for the canonical native parse/common-model/writer facade.

The native implementation owns parsing, model semantics, options and writers.
The Python object retains only the native common-model wire representation.
"""
import ctypes
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import sys
import sysconfig


class FacadeError(ValueError):
    """A structured refusal from the native format facade."""

    def __init__(self, details):
        self.details = details
        self.code = details.get("code")
        super().__init__(details.get("message", str(details)))


class FacadeUnavailableError(RuntimeError):
    """This installation does not contain a compatible native facade."""


class FacadeProtocolError(RuntimeError):
    """The native component returned an invalid ABI envelope."""


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class FacadeKernel:
    """An explicit native context; no environment or global native-path mutation."""

    def __init__(self, library_path):
        self.library_path = str(library_path)
        try:
            self._library = ctypes.CDLL(self.library_path)
            version = self._library.plurimath_facade_abi_version
            version.argtypes = []
            version.restype = ctypes.c_uint32
            if version() != 1:
                raise FacadeUnavailableError("Unsupported native format facade ABI")
            self._request = self._library.plurimath_facade_json
            self._request.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            self._request.restype = ctypes.c_void_p
            self._free = self._library.plurimath_facade_free
            self._free.argtypes = [ctypes.c_void_p]
            self._free.restype = None
        except (OSError, AttributeError) as error:
            raise FacadeUnavailableError("Native format facade could not be loaded") from error

    def request_json(self, text):
        """Return a decoded native envelope, freeing its owned reply exactly once."""
        data = text.encode("utf-8")
        source = ctypes.create_string_buffer(data)
        pointer = self._request(source, len(data))
        if not pointer:
            raise FacadeProtocolError("Native format facade returned a null reply")
        try:
            raw = ctypes.string_at(pointer)
        finally:
            self._free(pointer)
        try:
            reply = json.loads(raw)
        except (ValueError, UnicodeError) as error:
            raise FacadeProtocolError("Native format facade returned invalid JSON") from error
        if not isinstance(reply, dict) or type(reply.get("abi_version")) is not int or reply["abi_version"] != 1:
            raise FacadeProtocolError("Invalid native format facade ABI envelope")
        if reply.get("ok") is False and isinstance(reply.get("error"), dict):
            raise FacadeError(reply["error"])
        if reply.get("ok") is not True:
            raise FacadeProtocolError("Invalid native format facade outcome")
        return reply

    def request(self, value):
        return self.request_json(_encode(value))

    def parse(self, text, input_format, **options):
        reply = self.request({"op": "parse", "format": input_format, "input": text, "options": options})
        return Formula._from_reply(reply, self)

    def from_model(self, model):
        """Retain a common model after validation by the native core."""
        return Formula._from_reply(self.request({"op": "model", "model": model}), self)


class Formula:
    """A native common-model value, with native writers and isolated snapshots."""

    @classmethod
    def _from_reply(cls, reply, kernel):
        model = reply.get("model")
        if not isinstance(model, dict) or not isinstance(model.get("class"), str) or not isinstance(model.get("fields"), dict):
            raise FacadeProtocolError("Native facade returned an invalid common model")
        result = cls.__new__(cls)
        result._model_json = _encode(model)
        result._kernel = kernel
        return result

    @property
    def model(self):
        """Return a fresh copy of the canonical {class, fields} model wire."""
        return json.loads(self._model_json)

    def write(self, output_format, **options):
        reply = self._kernel.request({"op": "write", "format": output_format,
                                      "model": self.model, "options": options})
        if not isinstance(reply.get("output"), str):
            raise FacadeProtocolError("Native facade returned a non-string writer result")
        return reply["output"]

    def to_asciimath(self, **options):
        return self.write("asciimath", **options)

    def to_latex(self, **options):
        return self.write("latex", **options)

    def to_mathml(self, **options):
        return self.write("mathml", **options)

    def to_omml(self, **options):
        return self.write("omml", **options)

    def to_unicodemath(self, **options):
        return self.write("unicodemath", **options)

    def to_html(self, **options):
        return self.write("html", **options)


@lru_cache(maxsize=1)
def initialize_facade():
    """Verify and load the packaged native component before format calls."""
    directory = Path(__file__).with_name("_native")
    try:
        receipt = json.loads((directory / "facade-build-info.json").read_bytes())
    except FileNotFoundError as error:
        raise FacadeUnavailableError("This installation has no bundled native format facade; format support is incomplete") from error
    expected = "plurimath_facade.dll" if sys.platform == "win32" else "libplurimath_facade.so"
    platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    if receipt.get("abi_version") != 1 or receipt.get("library") != expected or receipt.get("platform_tag") != platform:
        raise FacadeUnavailableError("Bundled format facade targets another ABI or platform")
    library = directory / expected
    if sha256(library.read_bytes()).hexdigest() != receipt.get("sha256"):
        raise FacadeUnavailableError("Bundled native format facade failed its integrity check")
    return FacadeKernel(library)


def parse(text, input_format, **options):
    return initialize_facade().parse(text, input_format, **options)


def from_model(model):
    return initialize_facade().from_model(model)
