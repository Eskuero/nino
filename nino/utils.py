import sys
import shutil
from .statics import dependencies

def dpnds():
	ready = True
	for dep in dependencies:
		if not shutil.which(dep):
			ready = False
			print("The required dependency '" + dep + "' is not in your PATH. Please refer to " + dependencies[dep])
	if not ready:
		sys.exit(1)
