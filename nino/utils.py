import sys
import shutil
from .statics import fetchmethods, dependencies, ansiescape

def dpnds():
	ready = True
	for dep in dependencies:
		if not shutil.which(dep):
			# Do not consider missing fetchmethods a critical failure and just disable them
			if dep in ["git"]:
				fetchmethods.pop("." + dep)
			else:
				ready = False
			print("The required dependency '" + dep + "' is not in your PATH. Please refer to " + dependencies[dep])
	if not ready:
		sys.exit(1)

def cprint(msg, color, end = "\n"):
    print(ansiescape[color] + msg + ansiescape["close"], end = end)
