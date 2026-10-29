#!/usr/bin/env python3
"""M12: az MCP-szerver tool schemajanak exportalasa (docs/m12-tool-schema.json).

Elinditja a szervert mock backenddel stdio-n, lekerdezi az eszkozlistat, es
kiirja a szerver nevet, verziojat, az agentnek szolo instructions szoveget es
minden eszkoz nevet, leirasat, bemeneti sematjat.

Futtatas (Python 3.10+ es az mcp csomag kell hozza; a projekt 3.9-es venv-jet
nem hasznalja):

    uv run --no-project --python 3.12 --with-requirements requirements-mcp.txt \
        python scripts/export_tool_schema.py

A --ellenoriz kapcsoloval nem ir, hanem osszeveti a meglevo fajllal, es
elteres eseten nem-nulla kilepesi koddal ter vissza.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GYOKER = Path(__file__).resolve().parent.parent
KIMENET = GYOKER / "docs" / "m12-tool-schema.json"


async def sema_lekerdezese() -> dict:
    parameterek = StdioServerParameters(
        command=sys.executable,
        args=[str(GYOKER / "adapter" / "mcp_szerver.py"), "--backend", "mock"],
    )
    async with stdio_client(parameterek) as (olvaso, iro):
        async with ClientSession(olvaso, iro) as munkamenet:
            init = await munkamenet.initialize()
            eszkozok = await munkamenet.list_tools()
            return {
                "server": {"name": init.server_info.name, "version": init.server_info.version},
                "instructions": init.instructions,
                "tools": [
                    {
                        "name": eszkoz.name,
                        "description": eszkoz.description,
                        "input_schema": eszkoz.input_schema,
                    }
                    for eszkoz in eszkozok.tools
                ],
            }


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP tool schema exportalasa")
    parser.add_argument(
        "--ellenoriz",
        action="store_true",
        help="Ne irjon, csak vesse ossze a meglevo fajllal.",
    )
    args = parser.parse_args()

    sema = asyncio.run(sema_lekerdezese())
    szoveg = json.dumps(sema, ensure_ascii=False, indent=2) + "\n"

    if args.ellenoriz:
        if not KIMENET.exists():
            print(f"Hianyzik: {KIMENET}", file=sys.stderr)
            return 1
        if KIMENET.read_text(encoding="utf-8") != szoveg:
            print(
                "ELTERES: a tool schema nem egyezik a szerver jelenlegi allapotaval. "
                "Futtasd ujra a szkriptet a --ellenoriz kapcsolo nelkul.",
                file=sys.stderr,
            )
            return 1
        print("OK: a tool schema naprakesz.")
        return 0

    KIMENET.parent.mkdir(parents=True, exist_ok=True)
    KIMENET.write_text(szoveg, encoding="utf-8")
    print(f"Tool schema kiirva: {KIMENET.relative_to(GYOKER)} ({len(sema['tools'])} eszkoz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
