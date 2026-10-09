#!/usr/bin/env python3
# Faithful bounded equivalent of pinned GameCI Input.getSerialFromLicenseFile.
# stdout is consumed by shell command substitution, NEVER by a workflow log.
import base64,os,re,sys
try:
    value=os.environ['UNITY_LICENSE'];marker='<DeveloperData Value="';start=value.index(marker)+len(marker);end=value.index('"/>',start)
    serial=base64.b64decode(value[start:end],validate=True).decode('latin1')[4:]
    if not re.fullmatch(r'[A-Za-z0-9-]{27}',serial):raise ValueError()
    sys.stdout.write(serial)
except Exception:sys.exit(1)
