import sys
sys.path[:0]=['/usr/lib/guideos/installer','/usr/lib/guideos/application-host','/usr/lib/guideos/ipc']
from guide_installer import Installer
installer=Installer()
try:installer.recover()
finally:installer.close()
