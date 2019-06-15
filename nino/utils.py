import sys
import shutil
from .statics import statics

class utils():
	def dpnds():
		ready = True
		for dep in statics.dependencies:
			if not shutil.which(dep):
				ready = False
				print("The required dependency '" + dep + "' is not in your PATH. Please refer to " + statics.dependencies[dep])
		if not ready:
			sys.exit(1)
