import sys
import shutil
from .statics import fetchmethods, dependencies

def dpnds():
	ready = True
	for dep in dependencies:
		if not shutil.which(dep):
			# Do not consider missing fetchmethods and critical failure and just disable it
			if dep in ["git", "hg"]:
				fetchmethods.pop("." + dep)
			else:
				ready = False
			print("The required dependency '" + dep + "' is not in your PATH. Please refer to " + dependencies[dep])
	if not ready:
		sys.exit(1)
