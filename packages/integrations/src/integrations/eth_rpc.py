"""Minimal Ethereum JSON-RPC + Multicall3 helpers (httpx)."""

from __future__ import annotations

from typing import Any

import certifi
import httpx
from eth_abi import decode, encode
from eth_hash.auto import keccak

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
DEFAULT_RPC = "https://ethereum.publicnode.com"


def function_selector(signature: str) -> bytes:
    return keccak(signature.encode())[:4]


def encode_call(signature: str, types: list[str], args: list[Any]) -> str:
    data = function_selector(signature) + encode(types, args)
    return "0x" + data.hex()


def decode_result(types: list[str], data_hex: str) -> tuple[Any, ...]:
    raw = bytes.fromhex(data_hex.removeprefix("0x"))
    if not raw:
        raise ValueError("empty eth_call result")
    return decode(types, raw)


class EthRpc:
    def __init__(self, url: str | None = None, *, timeout: float = 45.0) -> None:
        self.url = (url or DEFAULT_RPC).rstrip("/")
        self.timeout = timeout

    async def _post(self, method: str, params: list[Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout, verify=certifi.where()) as client:
            resp = await client.post(
                self.url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
            resp.raise_for_status()
            body = resp.json()
            if "error" in body:
                raise RuntimeError(f"RPC {method}: {body['error']}")
            return body["result"]

    async def block_number(self) -> int:
        return int(await self._post("eth_blockNumber", []), 16)

    async def call(self, to: str, data: str, *, block: str = "latest") -> str:
        return await self._post("eth_call", [{"to": to, "data": data}, block])

    async def multicall3(
        self,
        calls: list[tuple[str, str]],
        *,
        allow_failure: bool = True,
    ) -> list[tuple[bool, str]]:
        """calls: list of (target, calldata_hex). Returns [(ok, returnData_hex), ...]."""
        encoded_calls = [
            (to, allow_failure, bytes.fromhex(data.removeprefix("0x")))
            for to, data in calls
        ]
        data = encode_call(
            "aggregate3((address,bool,bytes)[])",
            ["(address,bool,bytes)[]"],
            [encoded_calls],
        )
        raw = await self.call(MULTICALL3, data)
        decoded = decode_result(["(bool,bytes)[]"], raw)[0]
        return [(ok, "0x" + ret.hex()) for ok, ret in decoded]
