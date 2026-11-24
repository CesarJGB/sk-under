#!/usr/bin/env python3
"""Escáner Frida de cadenas en memoria para diagnóstico autorizado.

Uso:
    python3 scan_memory.py --process 'Soul Knight' --pattern loginType \
      --pattern /UserAuth/Login --out /tmp/scan.json

Requiere frida y un frida-server accesible. No modifica el proceso, no
desactiva TLS y no elude la validación de certificados. Los resultados pueden
contener datos personales: guárdalos en una ruta privada y no los publiques.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import frida  # type: ignore
except ImportError:
    raise SystemExit("Falta el paquete frida en el entorno de diagnóstico.") from None


def _patterns(values: list[str], encoding: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for value in values:
        if encoding in ("utf8", "both"):
            result.append(
                {"name": "utf8:" + value, "hex": " ".join(f"{b:02x}" for b in value.encode())}
            )
        if encoding in ("utf16", "both"):
            result.append(
                {
                    "name": "utf16:" + value,
                    "hex": " ".join(f"{b:02x}" for b in value.encode("utf-16le")),
                }
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="10.0.0.2:27044", help="host:puerto de frida-server")
    parser.add_argument("--process", default="Soul Knight")
    parser.add_argument("--pattern", action="append", required=True)
    parser.add_argument("--encoding", choices=("utf8", "utf16", "both"), default="both")
    parser.add_argument("--max-mb", type=int, default=2500)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    patterns = _patterns(args.pattern, args.encoding)
    script = r"""
const pats=%s, limit=%d;
const out=[], seen=new Set();
let scanned=0;
for (const r of Process.enumerateRanges('rw-').filter(r=>r.size>4096 && r.size<300*1024*1024).sort((a,b)=>b.size-a.size)) {
  if (scanned>limit) break;
  scanned+=r.size;
  for (const p of pats) {
    let hits=[];
    try { hits=Memory.scanSync(r.base,r.size,p.hex); } catch(e) { continue; }
    for (const h of hits.slice(0,8)) {
      const key=p.name+'@'+h.address;
      if (seen.has(key)) continue;
      seen.add(key);
      let text='', text16='';
      try { text=h.address.sub(256).readUtf8String(1024)||''; } catch(e) {}
      try { text16=h.address.sub(256).readUtf16String(512)||''; } catch(e) {}
      out.push({name:p.name,address:h.address.toString(),text,text16});
    }
  }
}
send({scanned,items:out.slice(0,300)});
""" % (json.dumps(patterns), args.max_mb * 1024 * 1024)
    device = frida.get_device_manager().add_remote_device(args.device)
    session = device.attach(args.process)
    payload: dict[str, object] = {}
    complete = False

    def on_message(message, _data):
        nonlocal complete
        if message.get("type") == "send":
            payload.update(message["payload"])
            complete = True
        else:
            print(json.dumps({"error": "instrumentation"}), file=sys.stderr)

    script_obj = session.create_script(script)
    script_obj.on("message", on_message)
    try:
        script_obj.load()
        for _ in range(60):
            if complete:
                break
            time.sleep(0.5)
    finally:
        session.detach()
    if not complete:
        print(json.dumps({"error": "timeout"}), file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    print(json.dumps({"scanned": payload.get("scanned"), "items": len(payload.get("items", []))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
