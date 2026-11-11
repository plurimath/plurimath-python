from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sysconfig

from setuptools import Distribution, setup
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel


class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True


class NativeWheel(bdist_wheel):
    def get_tag(self):
        return "py3", "none", sysconfig.get_platform().replace("-", "_").replace(".", "_")


class BuildNative(build_py):
    def run(self):
        super().run()
        try:
            binary = Path(os.environ["PLURIMATH_NATIVE"])
            receipt = Path(os.environ["PLURIMATH_NATIVE_RECEIPT"])
        except KeyError as error:
            raise RuntimeError("Supply the pinned plurimath-rs library and its native receipt") from error
        info = json.loads(receipt.read_bytes())
        if binary.name != info["library"] or sha256(binary.read_bytes()).hexdigest() != info["sha256"]:
            raise RuntimeError("Native library disagrees with its receipt")
        platform = sysconfig.get_platform().replace("-", "_").replace(".", "_")
        if info["platform_tag"] != platform:
            raise RuntimeError("Native library receipt targets another platform")
        native = Path(self.build_lib) / "plurimath" / "_native"
        native.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(binary, native / binary.name)
        shutil.copyfile(receipt, native / "build-info.json")
        notices = receipt.parent / "licenses"
        if not notices.is_dir():
            raise RuntimeError("Native dependency licenses are required")
        shutil.copytree(notices, native / "licenses", dirs_exist_ok=True)
        facade_binary = os.environ.get("PLURIMATH_FACADE_NATIVE")
        facade_receipt = os.environ.get("PLURIMATH_FACADE_RECEIPT")
        if bool(facade_binary) != bool(facade_receipt):
            raise RuntimeError("Supply both native facade library and its receipt")
        if facade_binary:
            component = Path(facade_binary)
            component_receipt = Path(facade_receipt)
            facade = json.loads(component_receipt.read_bytes())
            expected = "plurimath_facade.dll" if platform == "win_amd64" else "libplurimath_facade.so"
            if (facade.get("platform_tag") != platform or facade.get("abi_version") != 1
                    or component.name != expected or facade.get("library") != expected
                    or sha256(component.read_bytes()).hexdigest() != facade.get("sha256")):
                raise RuntimeError("Native facade library disagrees with its platform receipt")
            facade_notices = component_receipt.parent / "licenses"
            if not facade_notices.is_dir():
                raise RuntimeError("Native facade dependency notices are required")
            shutil.copyfile(component, native / expected)
            shutil.copyfile(component_receipt, native / "facade-build-info.json")
            shutil.copytree(facade_notices, native / "facade-licenses", dirs_exist_ok=True)



setup(distclass=NativeDistribution, cmdclass={"build_py": BuildNative, "bdist_wheel": NativeWheel})
