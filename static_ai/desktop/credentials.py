"""Provider keys in Windows Credential Manager; only variable names go on disk."""

import ctypes
import hashlib
import json
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

from .state import credential_names


class WindowsVault:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Saved desktop API keys require Windows Credential Manager.")

        class Credential(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        self.Credential = Credential
        self.api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self.api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        self.api.CredWriteW.restype = wintypes.BOOL
        self.api.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(Credential)),
        ]
        self.api.CredReadW.restype = wintypes.BOOL
        self.api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self.api.CredDeleteW.restype = wintypes.BOOL
        self.api.CredFree.argtypes = [ctypes.c_void_p]

    def get(self, target):
        pointer = ctypes.POINTER(self.Credential)()
        if not self.api.CredReadW(target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:
                return None
            raise RuntimeError("Windows Credential Manager could not read this key.")
        try:
            value = pointer.contents
            return ctypes.string_at(value.CredentialBlob, value.CredentialBlobSize).decode("utf-8")
        finally:
            self.api.CredFree(pointer)

    def set(self, target, secret):
        raw = secret.encode("utf-8")
        if not raw or len(raw) > 2560:
            raise ValueError("Use an API key between 1 and 2560 bytes.")
        buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        value = self.Credential()
        value.Type, value.TargetName, value.UserName, value.Persist = 1, target, "Static", 2
        value.CredentialBlobSize, value.CredentialBlob = len(raw), buffer
        if not self.api.CredWriteW(ctypes.byref(value), 0):
            raise RuntimeError("Windows Credential Manager could not save this key.")

    def delete(self, target):
        if not self.api.CredDeleteW(target, 1, 0) and ctypes.get_last_error() != 1168:
            raise RuntimeError("Windows Credential Manager could not remove this key.")


class CredentialStore:
    def __init__(self, root, vault=None):
        self.root = Path(root).resolve()
        self.vault = vault or WindowsVault()
        self.prefix = (
            "StaticAI/" + hashlib.sha256(str(self.root).lower().encode()).hexdigest()[:24] + "/"
        )

    def target(self, name):
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", name):
            raise ValueError("Use an uppercase environment variable name for this key.")
        return self.prefix + name

    def get(self, name):
        return self.vault.get(self.target(name))

    def save(self, name, secret):
        target = self.target(name)
        names = set(credential_names(self.root))
        names.add(name)
        # Record the name first so a failed write is still removable at uninstall.
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "credential-names.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(sorted(names)), encoding="utf-8")
        temporary.replace(path)
        self.vault.set(target, secret)
        os.environ[name] = secret

    def delete(self, name):
        self.vault.delete(self.target(name))
        os.environ.pop(name, None)

    def load(self):
        for name in credential_names(self.root):
            secret = self.get(name)
            if secret:
                os.environ[name] = secret

    def delete_all(self):
        for name in credential_names(self.root):
            self.delete(name)
        (self.root / "credential-names.json").unlink(missing_ok=True)
