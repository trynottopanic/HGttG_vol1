#!/usr/bin/python3 -I
import sys
sys.path[:0] = ['/usr/lib/guideos/application-host','/usr/lib/guideos/ipc']
from guide_application_runtime import main
raise SystemExit(main(int(sys.argv[1].split(':')[0]),sys.argv[1].endswith(':health')))
