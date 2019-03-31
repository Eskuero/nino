import sys
import shutil
import toml
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

	def cfgfile(rconfig):
		config = {}
		# Retrieve entire configuration from local configuration file
		try:
			with open("syncall.toml", "r") as file:
				content = file.read()
				config = toml.loads(content)
		# No config file is fine
		except FileNotFoundError:
			pass
		# Update running config with avalaible values from valid definitions on config file
		defconfig = config.get("default", {})
		for option in [option for option in defconfig if option in rconfig]:
			rconfig[option] = defconfig[option]
		return config

	def cmdargs(args, rconfig, keystores):
		# Check every argument and store arguments
		for i, arg in enumerate(args):
			# Skip first iteration (script name)
			if i == 0:
				continue
			# We expect them to be splited in key/value pairs by a single equal symbol
			arg = arg.split("=")
			# Check both pair members exist.
			try:
				name = arg[0].lstrip("--")
				value = arg[1]
				# If not, report back and exit
			except IndexError:
				print("The argument " + arg[0] + " needs a value.")
				sys.exit(1)
			# Most arguments are boolean and follow the same logic
			if name in rconfig:
				if value == "y" and name not in ["deploy", "force"]:
					rconfig[name] = True
				elif value == "n" and not name == "force":
					if name == "deploy":
						rconfig["deploy"] = []
					else:
						rconfig[name] = False
				else:
					# In the case of build/force we save a keystore/list respectively
					if name == "build":
						rconfig["build"] = True
						value = value.split(",")
						try:
							keystores["overridestore"] = {
								"path": value[0],
								"aliases": {
									value[1]: {}
								}
							}
							rconfig["keystore"] = "overridestore"
							rconfig["keyalias"] = value[1]
						except IndexError:
							print("No alias was given for keystore " + value[0] + " provided through command line")
							sys.exit(1)
					elif name in ["deploy", "force"]:
						rconfig[name] = value.split(",")
					else:
						print("The argument " + arg[0] + " is expected boolean (y|n). Received: " + value)
						sys.exit(1)
